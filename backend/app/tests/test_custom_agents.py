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
        )
        draft_off = SimpleNamespace(
            is_chat_monitoring_enabled=False,
            is_neurocommenting_enabled=False,
            is_digital_footprint_enabled=False,
            is_dmp_one_enabled=False,
            is_amocrm_enabled=False,
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
