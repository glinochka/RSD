"""Backend tests for /custom mass-automation subsystem."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import (
    AccountClass,
    AccountPool,
    ChatDiscoveryTask,
    ChatMessage,
    ChatTarget,
    CustomAdmin,
    CustomAutomation,
    CustomAutomationCredential,
    CustomLead,
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
    ) -> ChatTarget:
        from app.alembic.models import ChatJoinStatus, ChatMode

        chat = ChatTarget(
            custom_automation_id=automation.id,
            provider="telegram",
            external_chat_id="222",
            title="Shill chat",
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
            roll=lambda: 0.5,
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
            roll=lambda: 0.01,
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
            roll=lambda: 0.01,
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
            roll=lambda: 0.01,
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
