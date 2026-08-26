"""Backend tests for /custom mass-automation subsystem."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import (
    AccountClass,
    AccountPool,
    AutomationActionLog,
    ChatDiscoveryTask,
    ChatMessage,
    ChatTarget,
    CustomAdmin,
    CustomAutomation,
    CustomAutomationCredential,
    CustomLead,
    CustomLeadMessage,
    PoolAccount,
    SocialAccount,
)
from app.utils.security import get_password_hash


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="test_custom_admin",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)
    return admin


@pytest.fixture
async def custom_automation(test_session: AsyncSession, custom_admin: CustomAdmin) -> CustomAutomation:
    from app.services.account_pool_service import get_or_create_default_pool
    from app.services.custom.prompt_service import create_default_prompts

    automation = CustomAutomation(
        name="Test Automation",
        client_name="Test Client",
        status="active",
        created_by_admin_id=custom_admin.id,
    )
    test_session.add(automation)
    await test_session.flush()
    await get_or_create_default_pool(test_session, automation.id)
    await create_default_prompts(test_session, automation.id)
    await test_session.commit()
    await test_session.refresh(automation)
    return automation


@pytest.fixture
async def custom_credential(test_session: AsyncSession, custom_automation: CustomAutomation) -> CustomAutomationCredential:
    credential = CustomAutomationCredential(
        custom_automation_id=custom_automation.id,
        username="test_client",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(credential)
    await test_session.commit()
    await test_session.refresh(credential)
    return credential


@pytest.fixture
async def admin_token(client: AsyncClient, custom_admin: CustomAdmin) -> str:
    response = await client.post("/api/custom/admin/login", json={
        "username": "test_custom_admin",
        "password": "password",
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
async def client_token(client: AsyncClient, custom_credential: CustomAutomationCredential) -> str:
    response = await client.post("/api/custom/login", json={
        "username": "test_client",
        "password": "password",
    })
    assert response.status_code == 200
    return response.json()["access_token"]


class TestCustomAdmin:
    async def test_admin_login_and_create_automation(self, client: AsyncClient, admin_token: str, custom_automation: CustomAutomation):
        response = await client.get(
            "/api/custom/admin/automations",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(item["id"] == custom_automation.id for item in data["items"])

    async def test_admin_can_open_automation_dashboard(self, client: AsyncClient, admin_token: str, custom_automation: CustomAutomation):
        response = await client.get(
            f"/api/custom/automations/{custom_automation.id}/dashboard",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["automation_id"] == custom_automation.id


class TestCustomClient:
    async def test_client_login(self, client: AsyncClient, client_token: str, custom_automation: CustomAutomation):
        response = await client.get(
            f"/api/custom/automations/{custom_automation.id}/dashboard",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["automation_id"] == custom_automation.id


class TestDashboardActivity:
    async def test_last_24h_keeps_product_actions_only(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from datetime import datetime, timedelta, timezone

        from app.services.account_pool_service import get_or_create_default_pool
        from app.services.custom.analytics_service import get_automation_dashboard

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000999",
            username="activity_acc",
            display_name="Activity",
            account_class=AccountClass.TRUSTED.value,
            encrypted_session="mock_encrypted_session",
            session_file_path="sessions/activity_acc.session",
            is_active=True,
            is_banned=False,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.TRUSTED.value,
                custom_automation_id=custom_automation.id,
            )
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for action_type, count in (
            ("profile_update", 4),
            ("discussion", 3),
            ("dmp_outreach", 2),
            ("lead_warmup", 2),
            ("dm", 5),
            ("neurocommenting", 2),
            ("shilling_chat", 1),
            ("shilling_post", 2),
            ("unsubscribe", 1),
        ):
            for _ in range(count):
                test_session.add(
                    AutomationActionLog(
                        custom_automation_id=custom_automation.id,
                        social_account_id=account.id,
                        action_type=action_type,
                        target_id="t",
                        target_type="chat",
                        result="success",
                        payload={},
                        created_at=now - timedelta(hours=1),
                    )
                )
        test_session.add(
            CustomLead(
                custom_automation_id=custom_automation.id,
                source="chat_monitoring",
                contact_type="telegram",
                contact_value="amo_lead",
                status="transferred",
                amocrm_lead_id="777",
                transferred_at=now - timedelta(hours=2),
            )
        )
        await test_session.commit()

        data = await get_automation_dashboard(test_session, custom_automation.id)
        last_24h = data["actions"]["last_24h"]
        assert last_24h == {
            "chat_monitoring": 5,
            "neurocommenting": 2,
            "shilling": 3,
            "unsubscribe": 1,
            "amocrm_transfer": 1,
        }
        assert "profile_update" not in last_24h
        assert "discussion" not in last_24h


class TestActivityFeed:
    async def test_feed_filters_and_sorts_telegram_blocks(
        self,
        client: AsyncClient,
        client_token: str,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from datetime import datetime, timedelta, timezone

        from app.alembic.models import ChatJoinStatus
        from app.services.account_pool_service import get_or_create_default_pool

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000888",
            username="feed_acc",
            display_name="Feed Acc",
            account_class=AccountClass.TRUSTED.value,
            encrypted_session="mock_encrypted_session",
            session_file_path="sessions/feed_acc.session",
            is_active=True,
            is_banned=False,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.TRUSTED.value,
                custom_automation_id=custom_automation.id,
            )
        )
        chat = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            external_chat_id="-1001",
            title="Канал оффера",
            chat_type="channel",
            mode="monitoring",
            source="manual",
            join_status=ChatJoinStatus.JOINED.value,
            is_active=True,
        )
        test_session.add(chat)
        await test_session.flush()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="neurocommenting",
                target_id=f"{chat.id}:11",
                target_type="chat_post",
                result="success",
                payload={"chat_target_id": chat.id, "post_id": 11, "post_text": "Новый пост", "text": "Круто"},
                created_at=now - timedelta(hours=3),
            )
        )
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="shilling_chat",
                target_id=str(chat.id),
                target_type="chat",
                result="success",
                payload={
                    "chat_target_id": chat.id,
                    "setup": "А чем вы пользуетесь?",
                    "reply": "Мы на этом сервисе",
                    "setup_account_id": account.id,
                    "reply_account_id": account.id,
                },
                created_at=now - timedelta(hours=2),
            )
        )
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="shilling_chat",
                target_id=f"{chat.id}:skip",
                target_type="chat",
                result="success",
                payload={"reason": "daily_probability"},
                created_at=now - timedelta(hours=2),
            )
        )
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="discussion",
                target_id=f"{chat.id}:5",
                target_type="chat_thread",
                result="success",
                payload={"chat_target_id": chat.id, "source_text": "Кто пробовал?", "text": "Мы пробовали"},
                created_at=now - timedelta(hours=1),
            )
        )
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="profile_update",
                target_id=f"account:{account.id}",
                target_type="account",
                result="success",
                payload={"bio": "x"},
                created_at=now,
            )
        )
        chat_message = ChatMessage(
            custom_automation_id=custom_automation.id,
            chat_target_id=chat.id,
            external_message_id="77",
            external_chat_id="-1001",
            sender_name="Иван",
            sender_username="ivan",
            text="Нужен расчёт поставки",
            sent_at=now - timedelta(minutes=40),
            is_processed=True,
            matched_intent="lead",
        )
        test_session.add(chat_message)
        await test_session.flush()
        intercept = CustomLead(
            custom_automation_id=custom_automation.id,
            source="chat_monitoring",
            contact_type="telegram",
            contact_value="ivan",
            full_name="Иван",
            chat_message_id=chat_message.id,
            assigned_account_id=account.id,
            status="warming",
            created_at=now - timedelta(minutes=39),
            last_message_at=now - timedelta(minutes=38),
        )
        dmp_lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="dmp_one",
            contact_type="telegram",
            contact_value="dmp_user",
            full_name="DMP Лид",
            company="ООО Ромашка",
            status="warming",
            created_at=now - timedelta(minutes=10),
            last_message_at=now - timedelta(minutes=9),
        )
        test_session.add_all([intercept, dmp_lead])
        await test_session.flush()
        test_session.add_all([
            CustomLeadMessage(
                custom_lead_id=intercept.id,
                direction="incoming",
                text="Нужен расчёт поставки",
                sent_at=now - timedelta(minutes=40),
            ),
            CustomLeadMessage(
                custom_lead_id=intercept.id,
                social_account_id=account.id,
                direction="outgoing",
                text="Напишите объём, посчитаем",
                sent_at=now - timedelta(minutes=38),
            ),
            CustomLeadMessage(
                custom_lead_id=dmp_lead.id,
                social_account_id=account.id,
                direction="outgoing",
                text="Привет, это по вашей заявке",
                sent_at=now - timedelta(minutes=9),
            ),
        ])
        await test_session.commit()

        headers = {"Authorization": f"Bearer {client_token}"}
        all_resp = await client.get(
            f"/api/custom/automations/{custom_automation.id}/activity",
            headers=headers,
        )
        assert all_resp.status_code == 200, all_resp.text
        payload = all_resp.json()
        types = [item["activity_type"] for item in payload["items"]]
        assert payload["total"] == 5
        assert "profile_update" not in types
        assert set(types) == {"neurocommenting", "shilling", "discussion", "chat_monitoring", "dmp"}
        assert types[0] == "dmp"

        neuro = await client.get(
            f"/api/custom/automations/{custom_automation.id}/activity",
            params={"activity_type": "neurocommenting"},
            headers=headers,
        )
        assert neuro.status_code == 200
        neuro_items = neuro.json()["items"]
        assert len(neuro_items) == 1
        assert neuro_items[0]["comment"] == "Круто"
        assert neuro_items[0]["post_text"] == "Новый пост"
        assert neuro_items[0]["chat"]["title"] == "Канал оффера"

        oldest = await client.get(
            f"/api/custom/automations/{custom_automation.id}/activity",
            params={"sort": "oldest"},
            headers=headers,
        )
        assert oldest.json()["items"][0]["activity_type"] == "neurocommenting"

        intercept_resp = await client.get(
            f"/api/custom/automations/{custom_automation.id}/activity",
            params={"activity_type": "chat_monitoring"},
            headers=headers,
        )
        intercept_item = intercept_resp.json()["items"][0]
        assert intercept_item["user_message"] == "Нужен расчёт поставки"
        assert intercept_item["dm_reply"] == "Напишите объём, посчитаем"
        assert len(intercept_item["messages"]) == 2


class TestAccountPoolAndRotation:
    async def test_pool_created_with_automation(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        pool = await test_session.scalar(
            select(AccountPool).where(
                AccountPool.custom_automation_id == custom_automation.id,
                AccountPool.is_default.is_(True),
            )
        )
        assert pool is not None

    async def test_add_account_and_select_for_action(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        from app.services.account_pool_service import get_or_create_default_pool
        from app.services.custom.rotation_service import select_account_for_action

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000000",
            username="test_account",
            display_name="Test Account",
            account_class=AccountClass.TRUSTED.value,
            risk_score=0.1,
            trust_score=0.9,
            activity_score=50.0,
            encrypted_session="mock_encrypted_session",
            session_file_path="sessions/test_account.session",
            is_active=True,
            is_banned=False,
        )
        test_session.add(account)
        await test_session.flush()
        pool_account = PoolAccount(
            account_pool_id=pool.id,
            social_account_id=account.id,
            assigned_class=AccountClass.TRUSTED.value,
            custom_automation_id=custom_automation.id,
        )
        test_session.add(pool_account)
        await test_session.commit()

        selected = await select_account_for_action(test_session, custom_automation.id, "dm")
        assert selected is not None
        assert selected.id == account.id


class TestLeadLifecycle:
    async def test_create_lead_and_transfer_to_manager(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        custom_automation.lead_manager_contact = "manager@example.com"
        custom_automation.is_amocrm_enabled = False
        await test_session.commit()

        lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="chat_monitoring",
            contact_type="telegram",
            contact_value="testlead",
            full_name="Test Lead",
            status="qualified",
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)

        with patch("app.services.custom.lead_delivery_service._send_email", new=AsyncMock(return_value=True)) as mock_email:
            response = await client.post(
                f"/api/custom/automations/{custom_automation.id}/leads/{lead.id}/transfer",
                headers={"Authorization": f"Bearer {client_token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "transferred"
            assert data["reason"] == "email"
            assert mock_email.called

        refreshed = await test_session.get(CustomLead, lead.id)
        await test_session.refresh(refreshed)
        assert refreshed.status == "transferred"


class TestChatDiscovery:
    async def test_create_and_approve_discovery_task(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        task = ChatDiscoveryTask(
            custom_automation_id=custom_automation.id,
            query="SEO optimization",
            status="awaiting_approval",
            mode="monitoring",
            max_chats=10,
            require_approval=True,
            relevance_threshold=0.6,
            found_chats=[
                {
                    "id": "123456",
                    "title": "SEO Chat",
                    "description": "Chat about SEO",
                    "username": "seochat",
                    "chat_type": "chat",
                    "participants_count": 100,
                    "score": 0.85,
                    "relevant": True,
                },
            ],
        )
        test_session.add(task)
        await test_session.commit()
        await test_session.refresh(task)

        response = await client.post(
            f"/api/custom/automations/{custom_automation.id}/chats/discovery/{task.id}/approve",
            json={"indices": [0]},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 1

        chat_target = await test_session.scalar(
            select(ChatTarget).where(ChatTarget.discovery_task_id == task.id)
        )
        assert chat_target is not None
        assert chat_target.title == "SEO Chat"

    async def test_discovery_prompt_created(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        with patch("app.services.custom.chat_discovery_service._search_telegram", new=AsyncMock(return_value=[])):
            response = await client.post(
                f"/api/custom/automations/{custom_automation.id}/chats/discovery",
                json={"query": "marketing", "mode": "monitoring", "max_chats": 5, "require_approval": True},
                headers={"Authorization": f"Bearer {client_token}"},
            )
            assert response.status_code == 201
            data = response.json()
            assert data["query"] == "marketing"


class TestSettings:
    async def test_update_settings_and_get_warnings(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        response = await client.patch(
            f"/api/custom/automations/{custom_automation.id}/settings",
            json={"is_chat_monitoring_enabled": True, "lead_manager_contact": "@manager"},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_chat_monitoring_enabled"] is True
        assert "warnings" in data
        # No trusted accounts exist, so enabling monitoring should warn.
        assert any("trusted" in warning for warning in data["warnings"])


class TestChatImportAndDedup:
    async def test_import_chats_from_csv(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        from app.services.custom.chat_import_service import import_chats_from_file

        csv_content = (
            "invite_link,title\n"
            "https://t.me/seo_chat,SEO Chat\n"
            "https://t.me/fulfillment,Fulfillment\n"
        ).encode("utf-8")
        job = await import_chats_from_file(
            test_session,
            automation_id=custom_automation.id,
            filename="chats.csv",
            content=csv_content,
        )
        assert job.processed_rows == 2
        chats = (
            await test_session.execute(
                select(ChatTarget).where(ChatTarget.custom_automation_id == custom_automation.id)
            )
        ).scalars().all()
        assert len(chats) == 2

    async def test_message_dedup(self, test_session: AsyncSession, custom_automation: CustomAutomation):
        from app.services.custom.chat_monitoring_service import save_chat_message

        chat = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            external_chat_id="111",
            title="Test",
            mode="monitoring",
            source="manual",
            join_status="joined",
            is_active=True,
        )
        test_session.add(chat)
        await test_session.commit()
        await test_session.refresh(chat)

        payload = {
            "external_message_id": "42",
            "external_chat_id": "111",
            "sender_id": "99",
            "sender_username": "lead",
            "sender_name": "Lead",
            "text": "Кто делает SEO?",
            "sent_at": None,
        }
        from datetime import datetime, timezone
        payload["sent_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        first = await save_chat_message(test_session, chat, payload)
        second = await save_chat_message(test_session, chat, payload)
        assert first is not None
        assert first.is_duplicate is False
        assert second is not None
        assert second.id == first.id
        assert second.is_duplicate is False
        count = await test_session.scalar(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.chat_target_id == chat.id)
        )
        assert count == 1


class TestChatCreateAndJoin:
    async def _add_pool_account(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        tmp_path,
        monkeypatch,
    ) -> SocialAccount:
        from app.config import settings
        from app.services.account_pool_service import get_or_create_default_pool

        monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
        session_rel = "sessions/join_acc.session"
        session_file = tmp_path / session_rel
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_bytes(b"session")

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000111",
            username="joinbot",
            display_name="Join Bot",
            account_class=AccountClass.TRUSTED.value,
            encrypted_session="mock",
            session_file_path=session_rel,
            is_active=True,
            is_banned=False,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.TRUSTED.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()
        await test_session.refresh(account)
        return account

    async def test_create_rejects_bad_link(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        response = await client.post(
            f"/api/custom/automations/{custom_automation.id}/chats",
            json={"invite_link": "https://google.com/x"},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 400

    async def test_create_resolves_title_and_type_from_telegram(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
        test_session: AsyncSession,
        tmp_path,
        monkeypatch,
    ):
        from app.services.custom.chat_join_service import create_chat_from_link

        await self._add_pool_account(test_session, custom_automation, tmp_path, monkeypatch)

        class FakeChannel:
            id = 555
            title = "SEO Chat"
            broadcast = False
            megagroup = True
            username = "seo_chat"

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get_entity(self, identifier):
                assert identifier in {"seo_chat", "https://t.me/seo_chat"}
                return FakeChannel()

            async def __call__(self, request):
                return FakeChannel()

        with patch(
            "app.services.custom.chat_join_service.TelegramAccountClient",
            return_value=FakeClient(),
        ), patch(
            "app.router_custom.automation_router.join_pending_chats",
            new=AsyncMock(),
        ):
            chat = await create_chat_from_link(test_session, custom_automation.id, "@SEO_chat")
            response = await client.post(
                f"/api/custom/automations/{custom_automation.id}/chats",
                json={"invite_link": "t.me/seo_chat"},
                headers={"Authorization": f"Bearer {client_token}"},
            )

        assert chat.title == "SEO Chat"
        assert chat.chat_type == "chat"
        assert chat.invite_link == "https://t.me/seo_chat"
        assert chat.external_chat_id == "555"
        assert response.status_code == 400
        assert "уже добавлен" in response.json()["detail"]

    async def test_join_public_channel_and_private_invite(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        tmp_path,
        monkeypatch,
    ):
        from telethon.errors import UserAlreadyParticipantError

        from app.services.custom.chat_join_service import _try_join_chat

        account = await self._add_pool_account(test_session, custom_automation, tmp_path, monkeypatch)

        class FakeChannel:
            def __init__(self, *, chat_id, title, broadcast):
                self.id = chat_id
                self.title = title
                self.broadcast = broadcast
                self.megagroup = not broadcast
                self.username = "news" if broadcast else None

        class FakeClient:
            def __init__(self, entity, already=False):
                self.entity = entity
                self.already = already
                self.calls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get_entity(self, identifier):
                self.calls.append(("get_entity", identifier))
                return self.entity

            async def __call__(self, request):
                name = type(request).__name__
                self.calls.append(name)
                if self.already and name in {"JoinChannelRequest", "ImportChatInviteRequest"}:
                    raise UserAlreadyParticipantError(request=None)
                return self.entity

        channel = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            invite_link="t.me/news_channel",
            mode="monitoring",
            source="manual",
            join_status="pending",
            is_active=True,
        )
        group = ChatTarget(
            custom_automation_id=custom_automation.id,
            provider="telegram",
            invite_link="+AbCdEfGhIjKl",
            mode="monitoring",
            source="manual",
            join_status="pending",
            is_active=True,
        )
        test_session.add_all([channel, group])
        await test_session.commit()
        await test_session.refresh(channel)
        await test_session.refresh(group)

        public_client = FakeClient(FakeChannel(chat_id=10, title="News", broadcast=True))
        with patch(
            "app.services.custom.chat_join_service.TelegramAccountClient",
            return_value=public_client,
        ):
            result = await _try_join_chat(test_session, channel, account)
        assert result["status"] == "joined"
        assert channel.title == "News"
        assert channel.chat_type == "channel"
        assert channel.invite_link == "https://t.me/news_channel"
        assert "JoinChannelRequest" in public_client.calls

        private_client = FakeClient(FakeChannel(chat_id=20, title="Leads", broadcast=False), already=True)
        with patch(
            "app.services.custom.chat_join_service.TelegramAccountClient",
            return_value=private_client,
        ):
            result = await _try_join_chat(test_session, group, account)
        assert result["status"] == "joined"
        assert group.title == "Leads"
        assert group.chat_type == "chat"
        assert group.invite_link == "https://t.me/+AbCdEfGhIjKl"
        assert "ImportChatInviteRequest" in private_client.calls
        assert "CheckChatInviteRequest" in private_client.calls


class TestLeadKeywords:
    async def test_normalize_and_match(self):
        from app.services.custom.lead_keywords import matched_lead_keyword, normalize_lead_keywords

        assert normalize_lead_keywords(["SEO", "seo", "  сайт  ", "x", "нужен сайт"]) == [
            "seo",
            "сайт",
            "нужен сайт",
        ]
        assert normalize_lead_keywords("купить, заявка\nсайт") == ["купить", "заявка", "сайт"]
        assert normalize_lead_keywords([]) == []
        assert matched_lead_keyword("Кто делает SEO под ключ?", ["seo"]) == "seo"
        assert matched_lead_keyword("Ребята, нужен сайт завтра", ["нужен сайт"]) == "нужен сайт"
        assert matched_lead_keyword("привет как дела", ["seo"]) is None
        assert matched_lead_keyword("сколько стоит индонезия", ["ии"]) is None
        assert matched_lead_keyword("нужно ии для чата", ["ии"]) == "ии"

    async def _add_message(
        self,
        session: AsyncSession,
        automation: CustomAutomation,
        text: str,
        *,
        external_id: str = "42",
    ) -> ChatMessage:
        from datetime import datetime, timezone

        chat = ChatTarget(
            custom_automation_id=automation.id,
            provider="telegram",
            external_chat_id="111",
            title="Test",
            mode="monitoring",
            source="manual",
            join_status="joined",
            is_active=True,
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        message = ChatMessage(
            custom_automation_id=automation.id,
            chat_target_id=chat.id,
            external_message_id=external_id,
            external_chat_id="111",
            sender_id="99",
            sender_username="lead",
            sender_name="Lead",
            text=text,
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
            dedup_key=f"telegram:111:{external_id}",
            is_processed=False,
            is_duplicate=False,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    async def test_keyword_miss_skips_llm(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_monitoring_service import process_unprocessed_messages

        custom_automation.lead_keywords = ["seo"]
        await test_session.commit()
        message = await self._add_message(test_session, custom_automation, "привет как дела")
        with patch(
            "app.services.custom.chat_monitoring_service._classify_message",
            new=AsyncMock(),
        ) as classify:
            result = await process_unprocessed_messages(test_session, custom_automation.id)
        classify.assert_not_called()
        await test_session.refresh(message)
        assert message.is_processed is True
        assert message.matched_intent == "no_keyword"
        assert result["leads_created"] == 0

    async def test_empty_keywords_skip_llm(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_monitoring_service import process_unprocessed_messages

        message = await self._add_message(test_session, custom_automation, "Кто делает SEO?")
        with patch(
            "app.services.custom.chat_monitoring_service._classify_message",
            new=AsyncMock(),
        ) as classify:
            await process_unprocessed_messages(test_session, custom_automation.id)
        classify.assert_not_called()
        await test_session.refresh(message)
        assert message.matched_intent == "no_keyword"

    async def test_keyword_hit_calls_classify(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.chat_monitoring_service import process_unprocessed_messages

        custom_automation.lead_keywords = ["seo"]
        await test_session.commit()
        message = await self._add_message(test_session, custom_automation, "Кто делает SEO?")
        with patch(
            "app.services.custom.chat_monitoring_service._classify_message",
            new=AsyncMock(
                return_value={
                    "is_lead": False,
                    "confidence": 0.1,
                    "reason": "no",
                    "contact_type": "telegram",
                    "contact_value": "",
                }
            ),
        ) as classify:
            await process_unprocessed_messages(test_session, custom_automation.id)
        classify.assert_called_once()
        await test_session.refresh(message)
        assert message.is_processed is True
        assert message.matched_intent == "not_lead"

    async def test_settings_roundtrip_and_warning(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        response = await client.patch(
            f"/api/custom/automations/{custom_automation.id}/settings",
            json={"lead_keywords": ["SEO", "seo", "  сайт  ", "x"]},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200
        assert response.json()["lead_keywords"] == ["seo", "сайт"]

        empty = await client.patch(
            f"/api/custom/automations/{custom_automation.id}/settings",
            json={"is_chat_monitoring_enabled": True, "lead_keywords": []},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert empty.status_code == 200
        warnings = empty.json()["warnings"]
        assert any("ключев" in warning.lower() for warning in warnings)


class TestSchedulerContracts:
    async def test_job_factories_accept_automation_id_only(self):
        import inspect
        from app.services.custom.scheduler_manager import CustomAutomationScheduler

        factories = CustomAutomationScheduler._job_factories()
        assert "discovery" in factories
        assert "join" in factories
        assert "lead_warmup" in factories
        for name, fn in factories.items():
            params = [
                p for p in inspect.signature(fn).parameters.values()
                if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                and p.default is inspect.Parameter.empty
            ]
            assert len(params) == 1, f"{name} must take only automation_id, got {params}"

    async def test_draft_with_modules_is_runnable(self):
        from types import SimpleNamespace
        from app.services.custom.scheduler_manager import CustomAutomationScheduler

        draft_on = SimpleNamespace(
            is_chat_monitoring_enabled=True,
            is_neurocommenting_enabled=False,
            is_digital_footprint_enabled=False,
            is_dmp_one_enabled=False,
            is_amocrm_enabled=False,
            is_shilling_enabled=False,
        )
        draft_off = SimpleNamespace(
            is_chat_monitoring_enabled=False,
            is_neurocommenting_enabled=False,
            is_digital_footprint_enabled=False,
            is_dmp_one_enabled=False,
            is_amocrm_enabled=False,
            is_shilling_enabled=False,
        )
        assert CustomAutomationScheduler._has_modules_on(draft_on) is True
        assert CustomAutomationScheduler._has_modules_on(draft_off) is False
        jobs = CustomAutomationScheduler._enabled_jobs(draft_on)
        assert "join" in jobs
        assert "monitor" in jobs
        assert "lead_warmup" in jobs


class TestLeadDeliveryParsing:
    async def test_parse_contact_channels(self):
        from app.services.custom.lead_delivery_service import _parse_contact

        assert _parse_contact("manager@example.com")[0] == "email"
        assert _parse_contact("@manager")[0] == "telegram"
        assert _parse_contact("https://hooks.example.com/lead")[0] == "url"


class TestShilling:
    async def _add_account(
        self,
        session: AsyncSession,
        automation: CustomAutomation,
        *,
        account_class: str,
        username: str,
        phone: str,
    ) -> SocialAccount:
        from app.services.account_pool_service import get_or_create_default_pool

        pool = await get_or_create_default_pool(session, automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number=phone,
            username=username,
            display_name=username,
            account_class=account_class,
            encrypted_session="mock_encrypted_session",
            session_file_path=f"sessions/{username}.session",
            is_active=True,
            is_banned=False,
        )
        session.add(account)
        await session.flush()
        session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=account_class,
                custom_automation_id=automation.id,
            )
        )
        await session.commit()
        await session.refresh(account)
        return account

    async def _add_chat(
        self,
        session: AsyncSession,
        automation: CustomAutomation,
        *,
        mode: str = "shilling",
        chat_type: str = "chat",
    ) -> ChatTarget:
        from app.alembic.models import ChatJoinStatus, ChatMode

        chat = ChatTarget(
            custom_automation_id=automation.id,
            provider="telegram",
            external_chat_id="222",
            title="Shill chat",
            chat_type=chat_type,
            mode=mode or ChatMode.SHILLING.value,
            source="manual",
            join_status=ChatJoinStatus.JOINED.value,
            is_active=True,
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        return chat

    async def test_commenting_does_not_pick_shilling_class(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.rotation_service import select_account_for_action

        await self._add_account(
            test_session,
            custom_automation,
            account_class=AccountClass.SHILLING.value,
            username="shill_only",
            phone="+79990000001",
        )
        selected = await select_account_for_action(test_session, custom_automation.id, "commenting")
        assert selected is None

    async def test_select_two_distinct_shilling_accounts(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.rotation_service import select_distinct_accounts_for_action

        first = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="shill_a", phone="+79990000002"
        )
        second = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="shill_b", phone="+79990000003"
        )
        pair = await select_distinct_accounts_for_action(test_session, custom_automation.id, "shilling", count=2)
        assert len(pair) == 2
        assert {pair[0].id, pair[1].id} == {first.id, second.id}
        assert pair[0].id != pair[1].id

    async def test_one_shilling_account_is_not_enough(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.rotation_service import accounts_are_distinct, select_distinct_accounts_for_action
        from app.services.custom.shilling_service import process_shilling_chat

        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="lonely", phone="+79990000004"
        )
        assert accounts_are_distinct(account, account) is False
        pair = await select_distinct_accounts_for_action(test_session, custom_automation.id, "shilling", count=2)
        assert pair == []
        chat = await self._add_chat(test_session, custom_automation)
        custom_automation.is_shilling_enabled = True
        await test_session.commit()
        result = await process_shilling_chat(test_session, custom_automation, chat)
        assert result["reason"] == "need_two_accounts"

    async def test_post_engagement_skip_and_mutual_exclusion(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.post_engagement import SKIP, claim_post_engagement, get_post_engagement_claim

        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.ONE_DAY.value, username="scanner", phone="+79990000005"
        )
        skipped = await claim_post_engagement(
            test_session,
            automation_id=custom_automation.id,
            chat_target_id=1,
            post_id=10,
            account_id=account.id,
            neuro_enabled=True,
            shilling_enabled=True,
            pick_gap=lambda: 1,
        )
        assert skipped == SKIP
        again = await claim_post_engagement(
            test_session,
            automation_id=custom_automation.id,
            chat_target_id=1,
            post_id=10,
            account_id=account.id,
            neuro_enabled=True,
            shilling_enabled=True,
            pick_gap=lambda: 1,
            pick=lambda options: "shilling",
        )
        assert again == SKIP

        first = await claim_post_engagement(
            test_session,
            automation_id=custom_automation.id,
            chat_target_id=1,
            post_id=11,
            account_id=account.id,
            neuro_enabled=True,
            shilling_enabled=True,
            pick_gap=lambda: 1,
            pick=lambda options: "neurocommenting",
        )
        second = await claim_post_engagement(
            test_session,
            automation_id=custom_automation.id,
            chat_target_id=1,
            post_id=11,
            account_id=account.id,
            neuro_enabled=True,
            shilling_enabled=True,
            pick_gap=lambda: 1,
            pick=lambda options: "shilling",
        )
        assert first == "neurocommenting"
        assert second == "neurocommenting"
        claim = await get_post_engagement_claim(test_session, custom_automation.id, 1, 11)
        assert claim is not None
        assert claim.result == "neurocommenting"

    async def test_chat_daily_probability_not_rerolled(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo

        from app.alembic.models import AutomationActionLog
        from app.services.custom.shilling_service import decide_chat_shilling_today

        try:
            moscow = ZoneInfo("Europe/Moscow")
        except Exception:
            moscow = timezone(timedelta(hours=3))
        noon = datetime(2026, 8, 25, 12, 0, tzinfo=moscow)
        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="dice", phone="+79990000006"
        )
        chat = await self._add_chat(test_session, custom_automation)
        first = await decide_chat_shilling_today(
            test_session,
            custom_automation,
            chat,
            account.id,
            roll=lambda: 0.9,
            now=noon,
        )
        second = await decide_chat_shilling_today(
            test_session,
            custom_automation,
            chat,
            account.id,
            roll=lambda: 0.01,
            now=noon,
        )
        assert first == "skip"
        assert second == "skip"
        logs = (
            await test_session.execute(
                select(func.count()).select_from(AutomationActionLog).where(
                    AutomationActionLog.action_type == "shilling_chat",
                    AutomationActionLog.target_id == str(chat.id),
                )
            )
        ).scalar_one()
        assert logs == 1

    async def test_dialogue_never_uses_one_account(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from unittest.mock import AsyncMock, patch

        from app.services.custom.shilling_service import perform_shilling_dialogue

        a = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="pair_a", phone="+79990000007"
        )
        b = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="pair_b", phone="+79990000008"
        )
        chat = await self._add_chat(test_session, custom_automation)

        async def fake_sleep(_seconds):
            return None

        with patch(
            "app.services.custom.shilling_service.generate_shilling_dialogue",
            new=AsyncMock(return_value=("Позиции просели, кто в сео шарит?", "Пользуюсь СЕОДжарвис уже полгода")),
        ), patch(
            "app.services.custom.shilling_service._telegram_ids_distinct",
            new=AsyncMock(return_value=True),
        ), patch(
            "app.services.custom.shilling_service._send_message",
            new=AsyncMock(side_effect=[101, 102]),
        ) as send:
            result = await perform_shilling_dialogue(
                test_session,
                custom_automation,
                chat,
                action_type="shilling_chat",
                target_id=str(chat.id),
                target_type="chat",
                delay_seconds=0,
                sleep=fake_sleep,
            )
        assert result["status"] == "ok"
        assert result["setup_account_id"] != result["reply_account_id"]
        assert {result["setup_account_id"], result["reply_account_id"]} == {a.id, b.id}
        used = {call.args[3].id for call in send.await_args_list}
        assert used == {a.id, b.id}

    async def test_shilling_runs_without_per_chat_mode(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.rotation_service import select_distinct_accounts_for_action
        from app.services.custom.shilling_service import process_shilling_chat

        await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="mode_a", phone="+79990000021"
        )
        await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="mode_b", phone="+79990000022"
        )
        chat = await self._add_chat(test_session, custom_automation, mode="monitoring")
        custom_automation.is_shilling_enabled = True
        await test_session.commit()
        pair = await select_distinct_accounts_for_action(test_session, custom_automation.id, "shilling", count=2)
        assert len(pair) == 2
        result = await process_shilling_chat(
            test_session,
            custom_automation,
            chat,
            now=None,
            roll=lambda: 0.9,
        )
        assert result["reason"] in {"skip", "wait"}

    async def test_chat_shilling_skips_channels(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.shilling_service import process_shilling_chat

        await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="ch_a", phone="+79990000023"
        )
        await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="ch_b", phone="+79990000024"
        )
        chat = await self._add_chat(test_session, custom_automation, mode="monitoring", chat_type="channel")
        custom_automation.is_shilling_enabled = True
        await test_session.commit()
        result = await process_shilling_chat(test_session, custom_automation, chat)
        assert result["reason"] == "channel"

    async def test_shilling_cooldown_two_days(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo

        from app.alembic.models import AutomationActionLog
        from app.services.custom.shilling_service import decide_chat_shilling_today

        try:
            moscow = ZoneInfo("Europe/Moscow")
        except Exception:
            moscow = timezone(timedelta(hours=3))
        now = datetime(2026, 8, 26, 12, 0, tzinfo=moscow)
        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="cool", phone="+79990000025"
        )
        chat = await self._add_chat(test_session, custom_automation, mode="monitoring")
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="shilling_chat",
                target_id=str(chat.id),
                target_type="chat",
                result="success",
                payload={},
                created_at=(now - timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None),
            )
        )
        await test_session.commit()
        decision = await decide_chat_shilling_today(
            test_session,
            custom_automation,
            chat,
            account.id,
            roll=lambda: 0.01,
            now=now,
        )
        assert decision == "done"

    async def test_post_cadence_skips_between_actions(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.post_engagement import SKIP, claim_post_engagement

        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.ONE_DAY.value, username="cadence", phone="+79990000026"
        )
        results = []
        for post_id in range(20, 26):
            results.append(
                await claim_post_engagement(
                    test_session,
                    automation_id=custom_automation.id,
                    chat_target_id=7,
                    post_id=post_id,
                    account_id=account.id,
                    neuro_enabled=True,
                    shilling_enabled=False,
                    pick_gap=lambda: 2,
                    pick=lambda options: "neurocommenting",
                )
            )
        assert results[0] == SKIP
        assert results[1] == SKIP
        assert results[2] == "neurocommenting"
        assert results[3] == SKIP
        assert results[4] == SKIP
        assert results[5] == "neurocommenting"

    async def test_monitoring_ignores_shilling_messages(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from datetime import datetime, timezone

        from app.alembic.models import AutomationActionLog
        from app.services.custom.chat_monitoring_service import save_chat_message
        from app.services.custom.chat_scope import load_own_sender_keys, load_shilling_message_ids, message_is_own_activity

        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="shill_bot", phone="+79990000027"
        )
        chat = await self._add_chat(test_session, custom_automation, mode="monitoring")
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="shilling_chat",
                target_id=str(chat.id),
                target_type="chat",
                result="success",
                payload={"setup_message_id": 501, "reply_message_id": 502, "chat_target_id": chat.id},
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        await test_session.commit()
        own_keys = await load_own_sender_keys(test_session, custom_automation.id)
        shill_ids = await load_shilling_message_ids(test_session, custom_automation.id, chat.id)
        payload = {
            "external_message_id": "501",
            "external_chat_id": "222",
            "sender_id": "1",
            "sender_username": "shill_bot",
            "sender_name": "shill_bot",
            "text": "Кто шарит в SEO?",
            "sent_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }
        assert message_is_own_activity(payload, own_keys, shill_ids) is True
        saved = await save_chat_message(test_session, chat, payload, ignore_as="own_activity")
        assert saved is not None
        assert saved.is_processed is True
        assert saved.matched_intent == "own_activity"

    async def test_discussion_once_per_chat_per_day(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from datetime import datetime, timezone

        from app.alembic.models import AutomationActionLog
        from app.services.custom.discussion_service import _already_replied_today, process_chat_target

        chat = await self._add_chat(test_session, custom_automation, mode="monitoring")
        account = await self._add_account(
            test_session, custom_automation, account_class=AccountClass.ONE_DAY.value, username="disc", phone="+79990000028"
        )
        test_session.add(
            AutomationActionLog(
                custom_automation_id=custom_automation.id,
                social_account_id=account.id,
                action_type="discussion",
                target_id=f"{chat.id}:99",
                target_type="chat_thread",
                result="success",
                payload={"chat_target_id": chat.id},
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        await test_session.commit()
        assert await _already_replied_today(test_session, custom_automation.id, chat.id) is True
        result = await process_chat_target(test_session, custom_automation.id, chat, max_daily=50)
        assert result["reason"] == "daily_limit"

    async def test_neurocommenting_skips_groups(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.neurocommenting_service import process_chat_target

        chat = await self._add_chat(test_session, custom_automation, mode="monitoring", chat_type="chat")
        custom_automation.is_neurocommenting_enabled = True
        await test_session.commit()
        result = await process_chat_target(test_session, custom_automation.id, chat)
        assert result["reason"] == "not_channel"

    async def test_settings_require_two_shilling_accounts(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.custom.settings_service import validate_settings

        await self._add_account(
            test_session, custom_automation, account_class=AccountClass.SHILLING.value, username="only_one", phone="+79990000009"
        )
        custom_automation.is_shilling_enabled = True
        await test_session.commit()
        validation = await validate_settings(test_session, custom_automation)
        assert validation["can_enable"]["shilling"] is False
        assert any("шиллинг" in warning.lower() for warning in validation["warnings"])

    async def test_scheduler_starts_shilling_job(self):
        from types import SimpleNamespace
        from app.services.custom.scheduler_manager import CustomAutomationScheduler

        factories = CustomAutomationScheduler._job_factories()
        assert "shilling" in factories
        on = SimpleNamespace(
            is_chat_monitoring_enabled=False,
            is_neurocommenting_enabled=False,
            is_digital_footprint_enabled=False,
            is_dmp_one_enabled=False,
            is_amocrm_enabled=False,
            is_shilling_enabled=True,
        )
        jobs = CustomAutomationScheduler._enabled_jobs(on)
        assert "shilling" in jobs
        assert "neurocommenting" in jobs

    async def test_default_prompts_include_shilling(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.alembic.models import CustomPrompt, PromptType
        from app.services.custom.prompt_service import list_prompts

        prompts = await list_prompts(test_session, custom_automation.id)
        types = {prompt.prompt_type for prompt in prompts}
        assert PromptType.SHILLING.value in types
        row = await test_session.scalar(
            select(CustomPrompt).where(
                CustomPrompt.custom_automation_id == custom_automation.id,
                CustomPrompt.prompt_type == PromptType.SHILLING.value,
            )
        )
        assert row is not None


class TestAmocrmOAuthAndDmpWebhook:
    async def test_oauth_start_callback_stores_tokens(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        from urllib.parse import parse_qs, urlparse

        from app.alembic.models import AmocrmConnection
        from app.config import settings

        automation_id = custom_automation.id
        headers = {"Authorization": f"Bearer {client_token}"}
        custom_automation.is_amocrm_enabled = True
        await test_session.commit()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "access_token": "access-from-code",
                    "refresh_token": "refresh-from-code",
                    "expires_in": 86400,
                }

        class FakeHttpClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None):
                assert "oauth2/access_token" in url
                assert json["grant_type"] == "authorization_code"
                assert json["code"] == "auth-code"
                return FakeResponse()

        with patch.object(
            settings,
            "AMOCRM_REDIRECT_URI",
            "https://app.example.com/api/custom/amocrm/oauth/callback",
        ), patch(
            "app.services.custom.amocrm_service.httpx.AsyncClient",
            return_value=FakeHttpClient(),
        ):
            creds = await client.post(
                f"/api/custom/automations/{automation_id}/amocrm/credentials",
                headers=headers,
                json={
                    "subdomain": "company",
                    "client_id": "cid-1",
                    "client_secret": "csecret-1",
                },
            )
            assert creds.status_code == 200, creds.text
            started = await client.post(
                f"/api/custom/automations/{automation_id}/amocrm/oauth/start",
                headers=headers,
                json={
                    "return_url": f"https://app.example.com/custom/automations/{automation_id}/settings",
                },
            )
            assert started.status_code == 200, started.text
            auth_url = started.json()["auth_url"]
            state = parse_qs(urlparse(auth_url).query)["state"][0]
            callback = await client.get(
                "/api/custom/amocrm/oauth/callback",
                params={
                    "code": "auth-code",
                    "state": state,
                    "referer": "https://company.amocrm.ru",
                },
                follow_redirects=False,
            )
            assert callback.status_code == 302
            assert "amocrm=connected" in (callback.headers.get("location") or "")

        test_session.expire_all()
        connection = await test_session.scalar(
            select(AmocrmConnection).where(AmocrmConnection.custom_automation_id == automation_id)
        )
        assert connection is not None
        assert connection.is_active is True
        assert "access-from-code" in (connection.access_token_hash or "")
        assert "refresh-from-code" in (connection.refresh_token_hash or "")

    async def test_refresh_persists_new_token_pair(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from datetime import datetime

        from app.alembic.models import AmocrmConnection
        from app.services.custom.amocrm_service import _refresh_and_persist

        connection = AmocrmConnection(
            custom_automation_id=custom_automation.id,
            subdomain="company",
            client_id="cid-1",
            client_secret_enc="csecret",
            access_token_hash="old-access",
            refresh_token_hash="old-refresh",
            expires_at=datetime(2020, 1, 1),
            is_active=True,
        )
        test_session.add(connection)
        await test_session.commit()
        await test_session.refresh(connection)

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "access_token": "rotated-access",
                    "refresh_token": "rotated-refresh",
                    "expires_in": 3600,
                }

        class FakeHttpClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None):
                assert json["grant_type"] == "refresh_token"
                assert json["refresh_token"] == "old-refresh"
                return FakeResponse()

        with patch(
            "app.services.custom.amocrm_service.httpx.AsyncClient",
            return_value=FakeHttpClient(),
        ):
            ok = await _refresh_and_persist(test_session, connection)
        assert ok is True
        await test_session.refresh(connection)
        from app.utils.crypto import decrypt_token
        assert decrypt_token(connection.access_token_hash) == "rotated-access"
        assert decrypt_token(connection.refresh_token_hash) == "rotated-refresh"

    async def test_dmp_webhook_array_creates_lead_and_dedups(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        from app.config import settings

        automation_id = custom_automation.id
        headers = {"Authorization": f"Bearer {client_token}"}
        with patch.object(settings, "BASE_URL", "https://app.example.com"):
            updated = await client.patch(
                f"/api/custom/automations/{automation_id}/settings",
                headers=headers,
                json={"is_dmp_one_enabled": True},
            )
            assert updated.status_code == 200, updated.text
            data = updated.json()
            secret = data["dmp_webhook_secret"]
            assert secret
            assert secret in (data["dmp_webhook_url"] or "")

            payload = [
                {
                    "phone": "79001234567",
                    "website": "example.com",
                    "ip": "192.168.1.1",
                    "page": "https://example.com/landing",
                }
            ]
            first = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=payload,
            )
            assert first.status_code == 200, first.text
            assert first.json()["created_leads"] == 1

            second = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=payload,
            )
            assert second.status_code == 200, second.text
            assert second.json()["created_leads"] == 0

        test_session.expire_all()
        total = await test_session.scalar(
            select(func.count(CustomLead.id)).where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.source == "dmp_one",
                CustomLead.contact_value == "79001234567",
            )
        )
        assert total == 1
        lead = await test_session.scalar(
            select(CustomLead).where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.contact_value == "79001234567",
            )
        )
        assert lead.company == "example.com"
        assert (lead.dmp_raw_data or {}).get("website") == "example.com"


class TestBuiltinSolutions:
    async def test_ensure_builtin_solutions_seeds_two_pipelines(self, test_session: AsyncSession):
        from app.services.custom.solution_templates import (
            KIND_DMP_BOT,
            KIND_FULFILLMENT,
            KIND_SEO_SAAS,
            SLUG_DMP_BOT,
            SLUG_FULFILLMENT,
            SLUG_SEO_SAAS,
            ensure_builtin_solutions,
        )

        ids = await ensure_builtin_solutions(test_session)
        assert len(ids) == 3
        again = await ensure_builtin_solutions(test_session)
        assert set(again) == set(ids)

        seo = await test_session.scalar(
            select(CustomAutomation).where(CustomAutomation.solution_slug == SLUG_SEO_SAAS)
        )
        fulfillment = await test_session.scalar(
            select(CustomAutomation).where(CustomAutomation.solution_slug == SLUG_FULFILLMENT)
        )
        dmp_bot = await test_session.scalar(
            select(CustomAutomation).where(CustomAutomation.solution_slug == SLUG_DMP_BOT)
        )
        assert seo is not None
        assert fulfillment is not None
        assert dmp_bot is not None
        assert seo.solution_kind == KIND_SEO_SAAS
        assert seo.is_dmp_one_enabled is True
        assert seo.is_amocrm_enabled is False
        assert seo.is_chat_monitoring_enabled is True
        assert seo.is_shilling_enabled is True
        assert seo.is_digital_footprint_enabled is True
        assert fulfillment.solution_kind == KIND_FULFILLMENT
        assert fulfillment.is_amocrm_enabled is True
        assert fulfillment.is_dmp_one_enabled is True
        assert dmp_bot.solution_kind == KIND_DMP_BOT
        assert dmp_bot.is_dmp_one_enabled is True
        assert dmp_bot.is_amocrm_enabled is False
        assert dmp_bot.is_chat_monitoring_enabled is False
        assert dmp_bot.is_shilling_enabled is False
        assert dmp_bot.is_lead_qualification_enabled is False
        assert dmp_bot.lead_warmup_enabled is False

    async def test_seo_saas_does_not_hand_off_to_sales(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.services.custom.lead_warmup_service import auto_transfer_lead

        custom_automation.solution_kind = "seo_saas"
        custom_automation.lead_manager_contact = "@mop"
        custom_automation.is_amocrm_enabled = False
        await test_session.commit()

        lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="dmp_one",
            contact_type="telegram",
            contact_value="leaduser",
            status="qualified",
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)

        result = await auto_transfer_lead(test_session, custom_automation.id, lead)
        assert result.get("converted") is True
        assert result.get("transferred") is False
        await test_session.refresh(lead)
        assert lead.status == "converted"

    async def test_partner_settings_roundtrip(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        response = await client.patch(
            f"/api/custom/automations/{custom_automation.id}/settings",
            json={
                "is_dmp_one_enabled": True,
                "partner_utm_url": "https://saas.example.com/?utm_source=tg",
                "partner_promo_code": "SEO20",
                "conversion_check_url": "https://saas.example.com/api/lead-status",
            },
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["partner_utm_url"] == "https://saas.example.com/?utm_source=tg"
        assert data["partner_promo_code"] == "SEO20"
        assert data["conversion_check_url"] == "https://saas.example.com/api/lead-status"

    async def test_conversion_check_skips_subscribed_dmp_lead(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        from app.config import settings

        custom_automation.conversion_check_url = "https://saas.example.com/api/lead-status"
        custom_automation.solution_kind = "seo_saas"
        await test_session.commit()

        class FakeResponse:
            content = b'{"subscribed": true, "registered": true}'
            def raise_for_status(self):
                return None
            def json(self):
                return {"subscribed": True, "registered": True}

        class FakeHttpClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, url, json=None):
                assert url == "https://saas.example.com/api/lead-status"
                return FakeResponse()

        headers = {"Authorization": f"Bearer {client_token}"}
        automation_id = custom_automation.id
        with patch.object(settings, "BASE_URL", "https://app.example.com"), patch(
            "app.services.custom.dmp_one_service.httpx.AsyncClient",
            return_value=FakeHttpClient(),
        ):
            updated = await client.patch(
                f"/api/custom/automations/{automation_id}/settings",
                headers=headers,
                json={"is_dmp_one_enabled": True},
            )
            assert updated.status_code == 200, updated.text
            secret = updated.json()["dmp_webhook_secret"]
            first = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=[{"phone": "79007654321", "website": "saas.example.com"}],
            )
            assert first.status_code == 200, first.text
            assert first.json()["created_leads"] == 1

        test_session.expire_all()
        lead = await test_session.scalar(
            select(CustomLead).where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.contact_value == "79007654321",
            )
        )
        assert lead is not None
        assert lead.status == "converted"


class FakeTelegramClient:
    sent: list[dict] = []
    webhooks: list[dict] = []
    fail_send = False

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        payload = dict(json or {})
        if "setWebhook" in url:
            FakeTelegramClient.webhooks.append(payload)
        if "sendMessage" in url:
            if FakeTelegramClient.fail_send:
                class FailResp:
                    content = b'{"ok":false}'

                    def json(self):
                        return {"ok": False, "description": "Bad Gateway"}

                return FailResp()
            FakeTelegramClient.sent.append(payload)

        class Resp:
            content = b"{}"

            def json(self):
                if "getMe" in url:
                    return {"ok": True, "result": {"username": "notify_bot"}}
                if "getWebhookInfo" in url:
                    return {"ok": True, "result": {"url": ""}}
                return {"ok": True}

        return Resp()


def _bot_message(chat_id: int, text: str) -> dict:
    return {"message": {"chat": {"id": chat_id}, "from": {"username": "ops"}, "text": text}}


class TestDmpBotPipeline:
    async def test_qualification_defaults_off_and_roundtrips(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        custom_automation.solution_kind = "dmp_bot"
        custom_automation.is_dmp_one_enabled = True
        await test_session.commit()
        automation_id = custom_automation.id
        headers = {"Authorization": f"Bearer {client_token}"}

        settings = await client.get(f"/api/custom/automations/{automation_id}/settings", headers=headers)
        assert settings.status_code == 200, settings.text
        data = settings.json()
        assert data["is_lead_qualification_enabled"] is False
        assert "telegram_bot_token_enc" not in data
        assert data["telegram_bot_token_set"] is False

        updated = await client.patch(
            f"/api/custom/automations/{automation_id}/settings",
            headers=headers,
            json={"is_lead_qualification_enabled": True},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["is_lead_qualification_enabled"] is True
        test_session.expire_all()
        row = await test_session.get(CustomAutomation, automation_id)
        assert row.is_lead_qualification_enabled is True
        assert row.lead_warmup_enabled is True
        assert row.is_chat_monitoring_enabled is False
        assert row.is_amocrm_enabled is False

    async def test_dmp_webhook_creates_lead_without_telegram_resolve(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        from app.config import settings
        from app.services.custom.scheduler_manager import CustomAutomationScheduler

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.is_dmp_one_enabled = True
        custom_automation.is_lead_qualification_enabled = False
        await test_session.commit()
        automation_id = custom_automation.id
        jobs = CustomAutomationScheduler._enabled_jobs(custom_automation)
        assert jobs == {"dmp_poll", "dmp_notify"}
        assert "join" not in jobs
        assert "lead_warmup" not in jobs

        headers = {"Authorization": f"Bearer {client_token}"}
        with patch.object(settings, "BASE_URL", "https://app.example.com"):
            updated = await client.patch(
                f"/api/custom/automations/{automation_id}/settings",
                headers=headers,
                json={"is_dmp_one_enabled": True},
            )
            assert updated.status_code == 200, updated.text
            secret = updated.json()["dmp_webhook_secret"]
            first = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=[{"phone": "79001112233", "website": "dmp.example.com", "ip": "10.0.0.1", "page": "/x"}],
            )
        assert first.status_code == 200, first.text
        assert first.json()["created_leads"] == 1

        test_session.expire_all()
        lead = await test_session.scalar(
            select(CustomLead).where(
                CustomLead.custom_automation_id == automation_id,
                CustomLead.contact_value == "79001112233",
            )
        )
        assert lead is not None
        assert lead.status == "transferred"

    async def test_bot_login_password_then_notifies_on_dmp_lead(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        custom_credential: CustomAutomationCredential,
        client_token: str,
    ):
        from app.config import settings
        from app.utils.crypto import encrypt_token

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.is_dmp_one_enabled = True
        custom_automation.telegram_bot_token_enc = encrypt_token("123456:test-token")
        custom_automation.telegram_bot_webhook_secret = "botsecret"
        custom_automation.telegram_bot_username = "notify_bot"
        await test_session.commit()
        automation_id = custom_automation.id
        FakeTelegramClient.sent = []

        with patch("app.services.custom.telegram_notify_bot_service.httpx.AsyncClient", FakeTelegramClient), patch.object(
            settings, "BASE_URL", "https://app.example.com"
        ):
            start = await client.post(
                f"/api/custom/webhooks/telegram/{automation_id}/botsecret",
                json=_bot_message(777, "/start"),
            )
            assert start.status_code == 200
            login = await client.post(
                f"/api/custom/webhooks/telegram/{automation_id}/botsecret",
                json=_bot_message(777, custom_credential.username),
            )
            assert login.status_code == 200
            password = await client.post(
                f"/api/custom/webhooks/telegram/{automation_id}/botsecret",
                json=_bot_message(777, "password"),
            )
            assert password.status_code == 200

            test_session.expire_all()
            from app.alembic.models import CustomBotSubscriber

            subscriber = await test_session.scalar(
                select(CustomBotSubscriber).where(
                    CustomBotSubscriber.custom_automation_id == automation_id,
                    CustomBotSubscriber.telegram_chat_id == 777,
                )
            )
            assert subscriber is not None
            assert subscriber.status == "subscribed"

            headers = {"Authorization": f"Bearer {client_token}"}
            updated = await client.patch(
                f"/api/custom/automations/{automation_id}/settings",
                headers=headers,
                json={"is_dmp_one_enabled": True},
            )
            secret = updated.json()["dmp_webhook_secret"]
            FakeTelegramClient.sent = []
            dmp = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=[{"phone": "79009998877", "website": "lead.example.com", "name": "Иван"}],
            )
            assert dmp.status_code == 200, dmp.text
            assert dmp.json()["created_leads"] == 1

        texts = [item.get("text") or "" for item in FakeTelegramClient.sent]
        assert any(text.startswith("Новый лид:") for text in texts)
        assert any("79009998877" in text for text in texts)

    async def test_bot_rate_limit_locks_after_failed_passwords(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        custom_credential: CustomAutomationCredential,
    ):
        from app.alembic.models import CustomBotSubscriber
        from app.utils.crypto import encrypt_token

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.telegram_bot_token_enc = encrypt_token("123456:test-token")
        custom_automation.telegram_bot_webhook_secret = "botsecret"
        await test_session.commit()
        automation_id = custom_automation.id
        FakeTelegramClient.sent = []

        with patch("app.services.custom.telegram_notify_bot_service.httpx.AsyncClient", FakeTelegramClient):
            for _ in range(5):
                await client.post(
                    f"/api/custom/webhooks/telegram/{automation_id}/botsecret",
                    json=_bot_message(888, custom_credential.username),
                )
                await client.post(
                    f"/api/custom/webhooks/telegram/{automation_id}/botsecret",
                    json=_bot_message(888, "wrong-password"),
                )

        test_session.expire_all()
        subscriber = await test_session.scalar(
            select(CustomBotSubscriber).where(
                CustomBotSubscriber.custom_automation_id == automation_id,
                CustomBotSubscriber.telegram_chat_id == 888,
            )
        )
        assert subscriber is not None
        assert subscriber.failed_attempts >= 5
        assert subscriber.locked_until is not None
        assert any("Слишком много попыток" in (item.get("text") or "") for item in FakeTelegramClient.sent)

    async def test_google_sheets_save_and_mocked_append(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        from app.config import settings

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.is_dmp_one_enabled = True
        await test_session.commit()
        automation_id = custom_automation.id
        headers = {"Authorization": f"Bearer {client_token}"}

        saved = await client.post(
            f"/api/custom/automations/{automation_id}/google-sheets",
            headers=headers,
            json={
                "spreadsheet": "https://docs.google.com/spreadsheets/d/abc123def456ghi789jk/edit",
                "worksheet": "Лиды",
                "service_account_json": (
                    '{"client_email":"sheets@proj.iam.gserviceaccount.com",'
                    '"private_key":"-----BEGIN RSA PRIVATE KEY-----\\nABC\\n-----END RSA PRIVATE KEY-----\\n"}'
                ),
            },
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["google_sheets_spreadsheet_id"] == "abc123def456ghi789jk"
        assert body["google_sheets_worksheet"] == "Лиды"
        assert body["google_sheets_credentials_set"] is True
        assert body["google_sheets_service_account_email"] == "sheets@proj.iam.gserviceaccount.com"
        assert "google_sheets_credentials_enc" not in body

        with patch.object(settings, "BASE_URL", "https://app.example.com"), patch(
            "app.services.custom.telegram_notify_bot_service.ensure_header_and_append",
            new=AsyncMock(return_value={"ok": True}),
        ) as append:
            updated = await client.patch(
                f"/api/custom/automations/{automation_id}/settings",
                headers=headers,
                json={"is_dmp_one_enabled": True},
            )
            secret = updated.json()["dmp_webhook_secret"]
            dmp = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=[{"phone": "79005554433", "website": "sheet.example.com"}],
            )
            assert dmp.status_code == 200, dmp.text
            assert append.await_count == 1

    async def test_persisted_subscriber_gets_lead_without_start(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.alembic.models import CustomBotSubscriber
        from app.services.custom.telegram_notify_bot_service import dispatch_dmp_notifications
        from app.utils.crypto import encrypt_token

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.telegram_bot_token_enc = encrypt_token("123456:test-token")
        await test_session.commit()
        test_session.add(
            CustomBotSubscriber(
                custom_automation_id=custom_automation.id,
                telegram_chat_id=999001,
                status="subscribed",
            )
        )
        lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="dmp_one",
            contact_type="phone",
            contact_value="79001230000",
            status="new",
            dmp_raw_data={"phone": "79001230000", "website": "persist.example.com"},
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)
        FakeTelegramClient.sent = []
        FakeTelegramClient.fail_send = False
        with patch("app.services.custom.telegram_notify_bot_service.httpx.AsyncClient", FakeTelegramClient):
            result = await dispatch_dmp_notifications(test_session, custom_automation, lead)
        assert result["bot_sent"] == 1
        assert result["bot_pending"] is False
        await test_session.refresh(lead)
        assert lead.bot_notified_at is not None
        assert 999001 in (lead.bot_notified_chat_ids or [])
        assert any("79001230000" in (item.get("text") or "") for item in FakeTelegramClient.sent)

    async def test_retry_sends_after_telegram_outage_without_start(
        self,
        test_session: AsyncSession,
        test_engine,
        custom_automation: CustomAutomation,
    ):
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as SAAsyncSession
        from app.alembic.models import CustomBotSubscriber
        from app.services.custom import telegram_notify_bot_service as bot_service
        from app.utils.crypto import encrypt_token
        from app.config import settings

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.telegram_bot_token_enc = encrypt_token("123456:test-token")
        custom_automation.telegram_bot_webhook_secret = "botsecret"
        await test_session.commit()
        automation_id = custom_automation.id
        test_session.add(
            CustomBotSubscriber(
                custom_automation_id=automation_id,
                telegram_chat_id=999002,
                status="subscribed",
            )
        )
        lead = CustomLead(
            custom_automation_id=automation_id,
            source="dmp_one",
            contact_type="phone",
            contact_value="79001230001",
            status="new",
            dmp_raw_data={"phone": "79001230001"},
        )
        test_session.add(lead)
        await test_session.commit()
        lead_id = lead.id
        FakeTelegramClient.sent = []
        FakeTelegramClient.fail_send = True
        FakeTelegramClient.webhooks = []
        with patch.object(bot_service, "SEND_ATTEMPTS", 1), patch(
            "app.services.custom.telegram_notify_bot_service.httpx.AsyncClient",
            FakeTelegramClient,
        ):
            first = await bot_service.dispatch_dmp_notifications(test_session, custom_automation, lead)
        assert first["bot_pending"] is True
        await test_session.refresh(lead)
        assert lead.bot_notified_at is None
        FakeTelegramClient.fail_send = False
        FakeTelegramClient.sent = []
        factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=SAAsyncSession)
        with patch.object(bot_service, "async_session_maker", factory), patch(
            "app.services.custom.telegram_notify_bot_service.httpx.AsyncClient",
            FakeTelegramClient,
        ), patch.object(settings, "BASE_URL", "https://app.example.com"):
            retried = await bot_service.retry_pending_dmp_notifications(automation_id)
        assert retried["retried"] >= 1
        test_session.expire(lead)
        await test_session.refresh(lead)
        assert lead.bot_notified_at is not None
        assert any("79001230001" in (item.get("text") or "") for item in FakeTelegramClient.sent)
        assert FakeTelegramClient.webhooks
        assert FakeTelegramClient.webhooks[-1].get("drop_pending_updates") is False

    async def test_restore_webhook_keeps_subscribers(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.alembic.models import CustomBotSubscriber
        from app.services.custom.telegram_notify_bot_service import restore_telegram_webhook
        from app.utils.crypto import encrypt_token
        from app.config import settings

        custom_automation.solution_kind = "dmp_bot"
        custom_automation.telegram_bot_token_enc = encrypt_token("123456:test-token")
        custom_automation.telegram_bot_webhook_secret = "keepsecret"
        await test_session.commit()
        test_session.add(
            CustomBotSubscriber(
                custom_automation_id=custom_automation.id,
                telegram_chat_id=999003,
                status="subscribed",
            )
        )
        await test_session.commit()
        FakeTelegramClient.webhooks = []
        with patch("app.services.custom.telegram_notify_bot_service.httpx.AsyncClient", FakeTelegramClient), patch.object(
            settings, "BASE_URL", "https://app.example.com"
        ):
            info = await restore_telegram_webhook(custom_automation)
        assert info.get("ok") is True
        assert FakeTelegramClient.webhooks[-1].get("drop_pending_updates") is False
        subscriber = await test_session.scalar(
            select(CustomBotSubscriber).where(CustomBotSubscriber.telegram_chat_id == 999003)
        )
        assert subscriber.status == "subscribed"


_FAKE_SESSION_BYTES = b"SQLite format 3\x00" + b"\x00" * 48


def _qr_login_payload(*, auth_id: str, already_authorized: bool = False, session_string: str = "1Asession"):
    return {
        "auth_id": auth_id,
        "qr_url": "" if already_authorized else "tg://login?token=abc",
        "qr_data_url": "" if already_authorized else "data:image/png;base64,aaa",
        "pending_session_string": session_string,
        "already_authorized": already_authorized,
        "api_id": 2040,
        "api_hash": "testhash",
    }


class TestAccountQrConnect:
    async def test_qr_start_requires_auth(self, client: AsyncClient, custom_automation: CustomAutomation):
        response = await client.post(f"/api/custom/automations/{custom_automation.id}/accounts/qr/start")
        assert response.status_code in (401, 403)

    async def test_qr_already_authorized_creates_account(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
        tmp_path,
        monkeypatch,
    ):
        from app.config import settings
        from app.services.custom import account_connect_service

        account_connect_service._persisted_by_auth_id.clear()
        monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
        mock_worker = MagicMock()
        mock_worker.check_all_accounts_for_automation = AsyncMock(return_value=[])
        with (
            patch(
                "app.services.custom.account_connect_service.start_qr_login",
                AsyncMock(return_value=_qr_login_payload(auth_id="auth-already", already_authorized=True)),
            ),
            patch(
                "app.services.custom.account_connect_service.get_qr_status",
                AsyncMock(
                    return_value={
                        "status": "success",
                        "session_string": "1Asession",
                        "me": {
                            "telegram_id": 555001,
                            "username": "qruser",
                            "first_name": "Qr",
                            "last_name": "User",
                            "phone_number": "+79991112233",
                        },
                    }
                ),
            ),
            patch(
                "app.services.account_pool_service.string_session_to_sqlite_bytes",
                return_value=_FAKE_SESSION_BYTES,
            ),
            patch("app.router_custom.automation_router.AccountHealthWorker", return_value=mock_worker),
        ):
            response = await client.post(
                f"/api/custom/automations/{custom_automation.id}/accounts/qr/start",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"assign_class": "one_day"},
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["already_authorized"] is True
        assert data["account"]["username"] == "qruser"
        assert data["account"]["phone_number"] == "+79991112233"
        assert data["account"]["status"] == "active"
        test_session.expire_all()
        saved = await test_session.scalar(select(SocialAccount).where(SocialAccount.username == "qruser"))
        assert saved is not None
        assert saved.session_file_path

    async def test_qr_status_success_persists_once(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
        tmp_path,
        monkeypatch,
    ):
        from app.config import settings
        from app.services.custom import account_connect_service

        account_connect_service._persisted_by_auth_id.clear()
        monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
        mock_worker = MagicMock()
        mock_worker.check_all_accounts_for_automation = AsyncMock(return_value=[])
        with (
            patch(
                "app.services.custom.account_connect_service.start_qr_login",
                AsyncMock(return_value=_qr_login_payload(auth_id="auth-poll")),
            ),
            patch(
                "app.services.account_pool_service.string_session_to_sqlite_bytes",
                return_value=_FAKE_SESSION_BYTES,
            ),
            patch("app.router_custom.automation_router.AccountHealthWorker", return_value=mock_worker),
        ):
            start = await client.post(
                f"/api/custom/automations/{custom_automation.id}/accounts/qr/start",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"assign_class": "mid"},
            )
            assert start.status_code == 200, start.text
            auth_token = start.json()["auth_token"]
            assert start.json()["account"] is None
            with patch(
                "app.services.custom.account_connect_service.get_qr_status",
                AsyncMock(
                    return_value={
                        "status": "success",
                        "session_string": "1Asession",
                        "me": {
                            "telegram_id": 555002,
                            "username": "polluser",
                            "phone_number": "+79990001122",
                        },
                    }
                ),
            ):
                first = await client.post(
                    f"/api/custom/automations/{custom_automation.id}/accounts/qr/status",
                    headers={"Authorization": f"Bearer {client_token}"},
                    json={"auth_token": auth_token},
                )
                second = await client.post(
                    f"/api/custom/automations/{custom_automation.id}/accounts/qr/status",
                    headers={"Authorization": f"Bearer {client_token}"},
                    json={"auth_token": auth_token},
                )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["status"] == "success"
        assert first.json()["account"]["username"] == "polluser"
        assert second.json()["account"]["id"] == first.json()["account"]["id"]
        test_session.expire_all()
        count = await test_session.scalar(
            select(func.count(SocialAccount.id)).where(SocialAccount.username == "polluser")
        )
        assert count == 1

    async def test_qr_verify_2fa_creates_account(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
        tmp_path,
        monkeypatch,
    ):
        from app.config import settings
        from app.services.custom import account_connect_service

        account_connect_service._persisted_by_auth_id.clear()
        monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
        mock_worker = MagicMock()
        mock_worker.check_all_accounts_for_automation = AsyncMock(return_value=[])
        with (
            patch(
                "app.services.custom.account_connect_service.start_qr_login",
                AsyncMock(return_value=_qr_login_payload(auth_id="auth-2fa")),
            ),
            patch(
                "app.services.custom.account_connect_service.get_qr_status",
                AsyncMock(return_value={"status": "need_2fa", "session_string": "1Apending"}),
            ),
            patch(
                "app.services.custom.account_connect_service.complete_qr_2fa",
                AsyncMock(
                    return_value={
                        "session_string": "1Adone",
                        "telegram_id": 555003,
                        "username": "twofauser",
                        "first_name": "Two",
                        "last_name": "Fa",
                        "phone_number": "+79993334455",
                    }
                ),
            ),
            patch(
                "app.services.account_pool_service.string_session_to_sqlite_bytes",
                return_value=_FAKE_SESSION_BYTES,
            ),
            patch("app.router_custom.automation_router.AccountHealthWorker", return_value=mock_worker),
        ):
            start = await client.post(
                f"/api/custom/automations/{custom_automation.id}/accounts/qr/start",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"assign_class": "one_day"},
            )
            assert start.status_code == 200, start.text
            response = await client.post(
                f"/api/custom/automations/{custom_automation.id}/accounts/qr/verify_2fa",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"auth_token": start.json()["auth_token"], "password": "secret-2fa"},
            )
        assert response.status_code == 200, response.text
        assert response.json()["account"]["username"] == "twofauser"
        test_session.expire_all()
        saved = await test_session.scalar(select(SocialAccount).where(SocialAccount.username == "twofauser"))
        assert saved is not None
        assert saved.session_file_path


class TestAccountHealthSpamblockAndDelete:
    async def test_spambot_parser(self):
        from app.services.custom.telegram_error_handler import parse_spambot_reply

        assert parse_spambot_reply("Good news, no limits are currently applied to your account.") is False
        assert parse_spambot_reply("Ваш аккаунт свободен от каких-либо ограничений.") is False
        assert parse_spambot_reply(
            "I'm afraid some Telegram users found your messages annoying and have reported them as spam. Your account is now limited."
        ) is True
        assert parse_spambot_reply("На ваш аккаунт наложены некоторые ограничения.") is True
        assert parse_spambot_reply("") is None
        assert parse_spambot_reply("hello") is None

    async def test_channel_ban_does_not_mark_account_banned(
        self, test_session: AsyncSession, custom_automation: CustomAutomation
    ):
        from app.services.account_pool_service import get_or_create_default_pool
        from app.services.custom.telegram_error_handler import update_account_after_telegram_error

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000011",
            username="chatban",
            encrypted_session="x",
            session_file_path="sessions/chatban.session",
            is_active=True,
            is_banned=False,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.ONE_DAY.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()
        kind = await update_account_after_telegram_error(
            test_session, account, Exception("USER_BANNED_IN_CHANNEL")
        )
        assert kind == "chat_restricted"
        await test_session.refresh(account)
        assert account.is_banned is False
        assert account.is_active is True

    async def test_revoked_session_marked_inactive(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        tmp_path,
        monkeypatch,
    ):
        from app.config import settings
        from app.services.account_pool_service import get_or_create_default_pool
        from app.services.custom.account_health_worker import AccountHealthWorker
        from app.services.custom.telegram_error_handler import SessionInvalidError

        monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))
        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        session_rel = Path("sessions") / str(custom_automation.id) / "revoked.session"
        session_file = tmp_path / session_rel
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_bytes(b"SQLite format 3\x00" + b"\x00" * 32)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000012",
            username="revokeduser",
            encrypted_session="x",
            session_file_path=str(session_rel).replace("\\", "/"),
            is_active=True,
            is_banned=False,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.ONE_DAY.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()
        account_id = account.id

        class _FakeClient:
            async def __aenter__(self):
                raise SessionInvalidError("Session is not authorized")

            async def __aexit__(self, *args):
                return False

        fake = _FakeClient()
        mock_cls = MagicMock()
        mock_cls.return_value = fake
        mock_cls.for_account.return_value = fake
        with patch(
            "app.services.custom.account_health_worker.TelegramAccountClient",
            mock_cls,
        ), patch(
            "app.services.custom.account_health_worker.asyncio.sleep",
            new=AsyncMock(),
        ):
            result = await AccountHealthWorker().process_account(
                test_session, custom_automation.id, account_id
            )
        assert result["status"] == "session_invalid"
        test_session.expire_all()
        saved = await test_session.get(SocialAccount, account_id)
        assert saved.is_active is False
        assert saved.is_banned is False

    async def test_delete_account(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        from app.services.account_pool_service import get_or_create_default_pool

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000013",
            username="todelete",
            encrypted_session="x",
            session_file_path="sessions/todelete.session",
            is_active=True,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.ONE_DAY.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()
        account_id = account.id
        response = await client.delete(
            f"/api/custom/automations/{custom_automation.id}/accounts/{account_id}",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 204, response.text
        test_session.expire_all()
        assert await test_session.get(SocialAccount, account_id) is None


class TestAccountProfile:
    async def test_account_list_includes_avatar_and_bio(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        from app.services.account_pool_service import get_or_create_default_pool

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000040",
            username="face",
            display_name="Иван Тестов",
            bio="Короткое био",
            current_bio="Короткое био",
            avatar_file_path="avatars/1/40.jpg",
            avatar_url="/media/avatars/1/40.jpg",
            encrypted_session="x",
            session_file_path="sessions/face.session",
            is_active=True,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.ONE_DAY.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()
        response = await client.get(
            f"/api/custom/automations/{custom_automation.id}/accounts",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200, response.text
        item = next(row for row in response.json()["items"] if row["id"] == account.id)
        assert item["display_name"] == "Иван Тестов"
        assert item["bio"] == "Короткое био"
        assert item["avatar_url"] == "/media/avatars/1/40.jpg"

    async def test_patch_display_name(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        from app.services.account_pool_service import get_or_create_default_pool

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000041",
            username="rename",
            display_name="Старое",
            encrypted_session="x",
            session_file_path="sessions/rename.session",
            is_active=True,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.ONE_DAY.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()

        async def fake_update(session, automation_id, social_account, display_name):
            social_account.display_name = display_name
            return display_name

        with patch(
            "app.router_custom.automation_router.update_account_display_name",
            fake_update,
        ):
            response = await client.patch(
                f"/api/custom/automations/{custom_automation.id}/accounts/{account.id}",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"display_name": "Новое Имя"},
            )
        assert response.status_code == 200, response.text
        assert response.json()["display_name"] == "Новое Имя"

    async def test_patch_bio(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        from app.services.account_pool_service import get_or_create_default_pool

        pool = await get_or_create_default_pool(test_session, custom_automation.id)
        account = SocialAccount(
            provider="telegram",
            phone_number="+79990000042",
            username="bioedit",
            display_name="Имя",
            bio="Старое",
            current_bio="Старое",
            encrypted_session="x",
            session_file_path="sessions/bioedit.session",
            is_active=True,
        )
        test_session.add(account)
        await test_session.flush()
        test_session.add(
            PoolAccount(
                account_pool_id=pool.id,
                social_account_id=account.id,
                assigned_class=AccountClass.ONE_DAY.value,
                custom_automation_id=custom_automation.id,
            )
        )
        await test_session.commit()

        async def fake_bio(session, automation_id, social_account, bio):
            social_account.bio = bio
            social_account.current_bio = bio
            return bio

        with patch(
            "app.router_custom.automation_router.update_account_bio",
            fake_bio,
        ):
            response = await client.patch(
                f"/api/custom/automations/{custom_automation.id}/accounts/{account.id}",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"bio": "Новое описание"},
            )
        assert response.status_code == 200, response.text
        assert response.json()["bio"] == "Новое описание"

    async def test_bulk_worker_exposes_process_accounts(self):
        from app.services.custom.bulk_profile_service import BulkProfileUpdateWorker

        assert callable(BulkProfileUpdateWorker().process_accounts)

    async def test_restore_encrypted_session_and_copy(self, tmp_path):
        from app.services.account_pool_service import encrypt_session_bytes
        from app.services.custom.telegram_account_client import (
            copy_session_bundle,
            restore_encrypted_session_file,
            session_file_has_auth_key,
        )

        payload = encrypt_session_bytes(b"SQLite format 3\x00" + b"\x00" * 64)
        dest = tmp_path / "account.session"
        assert restore_encrypted_session_file(payload, dest) is True
        assert dest.read_bytes().startswith(b"SQLite format 3\x00")
        other = tmp_path / "copy.session"
        copy_session_bundle(dest, other)
        assert other.read_bytes() == dest.read_bytes()
        assert session_file_has_auth_key(dest) is False





