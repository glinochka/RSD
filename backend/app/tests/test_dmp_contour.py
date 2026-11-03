"""DMP contour: webhook idempotency, order status, delivery history, secrets."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import (
    CustomAdmin,
    CustomAutomation,
    CustomAutomationCredential,
    CustomLead,
    DmpOneImport,
)
from app.utils.security import get_password_hash


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="dmp_contour_admin",
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

    automation = CustomAutomation(
        name="DMP Contour",
        client_name="DMP Client",
        status="active",
        solution_kind="dmp_bot",
        is_dmp_one_enabled=True,
        is_lead_qualification_enabled=False,
        created_by_admin_id=custom_admin.id,
    )
    test_session.add(automation)
    await test_session.flush()
    await get_or_create_default_pool(test_session, automation.id)
    await test_session.commit()
    await test_session.refresh(automation)
    return automation


@pytest.fixture
async def client_token(client: AsyncClient, test_session: AsyncSession, custom_automation: CustomAutomation) -> str:
    credential = CustomAutomationCredential(
        custom_automation_id=custom_automation.id,
        username="dmp_contour_client",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(credential)
    await test_session.commit()
    response = await client.post(
        "/api/custom/login",
        json={"username": "dmp_contour_client", "password": "password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _enable_webhook(client: AsyncClient, automation_id: int, token: str) -> str:
    from app.config import settings

    with patch.object(settings, "BASE_URL", "https://app.example.com"):
        updated = await client.patch(
            f"/api/custom/automations/{automation_id}/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_dmp_one_enabled": True},
        )
    assert updated.status_code == 200, updated.text
    return updated.json()["dmp_webhook_secret"]


class TestDmpWebhookContour:
    async def test_repeated_visit_reuses_import_and_fills_name(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        automation_id = custom_automation.id
        secret = await _enable_webhook(client, automation_id, client_token)
        first = await client.post(
            f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
            json=[{"phone": "79001110001", "website": "shop.example"}],
        )
        assert first.status_code == 200, first.text
        assert first.json()["created_leads"] == 1

        second = await client.post(
            f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
            json=[{"phone": "79001110001", "website": "shop.example", "name": "Анна"}],
        )
        assert second.status_code == 200, second.text
        assert second.json()["created_leads"] == 0

        test_session.expire_all()
        imports = (
            await test_session.scalars(
                select(DmpOneImport).where(DmpOneImport.custom_automation_id == automation_id)
            )
        ).all()
        assert len(imports) == 1
        assert imports[0].status == "completed"
        lead = await test_session.scalar(
            select(CustomLead).where(CustomLead.custom_automation_id == automation_id)
        )
        assert lead is not None
        assert lead.full_name == "Анна"
        assert lead.company == "shop.example"

    async def test_site_alias_and_empty_push_do_not_stick_in_processing(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        automation_id = custom_automation.id
        secret = await _enable_webhook(client, automation_id, client_token)
        visit = await client.post(
            f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
            json=[{"phone": "79001110002", "site": "alias.example", "page": "/price"}],
        )
        assert visit.status_code == 200, visit.text
        empty = await client.post(
            f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
            json=[],
        )
        assert empty.status_code == 200, empty.text
        assert empty.json()["created_leads"] == 0

        test_session.expire_all()
        lead = await test_session.scalar(
            select(CustomLead).where(CustomLead.contact_value.in_(("79001110002", "+79001110002")))
        )
        assert lead is not None
        assert lead.company == "alias.example"
        assert lead.position == "/price"
        statuses = (
            await test_session.scalars(
                select(DmpOneImport.status).where(DmpOneImport.custom_automation_id == automation_id)
            )
        ).all()
        assert "processing" not in statuses

    async def test_same_order_id_is_one_import(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        automation_id = custom_automation.id
        secret = await _enable_webhook(client, automation_id, client_token)
        body = {"order_id": "ord-77", "contacts": [{"phone": "79001110003", "website": "ord.example"}]}
        first = await client.post(f"/api/custom/webhooks/dmp/{automation_id}/{secret}", json=body)
        second = await client.post(f"/api/custom/webhooks/dmp/{automation_id}/{secret}", json=body)
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert second.json()["created_leads"] == 0
        test_session.expire_all()
        count = await test_session.scalar(
            select(func.count(DmpOneImport.id)).where(DmpOneImport.custom_automation_id == automation_id)
        )
        assert count == 1

    async def test_global_secret_does_not_override_automation_secret(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        from app.services.custom import dmp_one_service

        automation_id = custom_automation.id
        secret = await _enable_webhook(client, automation_id, client_token)
        with patch.object(dmp_one_service.settings, "DMP_ONE_WEBHOOK_SECRET", "global-secret"):
            denied = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}",
                headers={"X-DMP-Webhook-Secret": "global-secret"},
                json=[{"phone": "79001110004"}],
            )
            allowed = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}/{secret}",
                json=[{"phone": "79001110004"}],
            )
        assert denied.status_code == 401
        assert allowed.status_code == 200, allowed.text

        await test_session.execute(
            update(CustomAutomation)
            .where(CustomAutomation.id == automation_id)
            .values(dmp_webhook_secret=None)
        )
        await test_session.commit()
        with patch.object(dmp_one_service.settings, "DMP_ONE_WEBHOOK_SECRET", "global-secret"):
            fallback = await client.post(
                f"/api/custom/webhooks/dmp/{automation_id}",
                headers={"X-DMP-Webhook-Secret": "global-secret"},
                json=[{"phone": "79001110005"}],
            )
        assert fallback.status_code == 200, fallback.text


class TestDmpOrdersAndDelivery:
    async def test_order_without_module_is_rejected(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        automation_id = custom_automation.id
        custom_automation.is_dmp_one_enabled = False
        await test_session.commit()
        response = await client.post(
            f"/api/custom/automations/{automation_id}/dmp/orders",
            headers={"Authorization": f"Bearer {client_token}"},
            json={"import_type": "website", "source_url": "https://example.com", "requested_count": 10},
        )
        assert response.status_code == 400, response.text

    async def test_order_without_id_is_not_stored(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
        test_session: AsyncSession,
    ):
        from app.config import settings

        automation_id = custom_automation.id

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "pending"}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, json=None):
                return FakeResponse()

        with patch.object(settings, "DMP_ONE_API_BASE_URL", "https://dmp.example"), patch.object(
            settings, "DMP_ONE_API_KEY", "key"
        ), patch.object(settings, "BASE_URL", "https://app.example.com"), patch(
            "app.services.custom.dmp_one_service.httpx.AsyncClient",
            return_value=FakeClient(),
        ):
            response = await client.post(
                f"/api/custom/automations/{automation_id}/dmp/orders",
                headers={"Authorization": f"Bearer {client_token}"},
                json={"import_type": "website", "source_url": "https://example.com", "requested_count": 10},
            )
        assert response.status_code == 502, response.text
        test_session.expire_all()
        count = await test_session.scalar(
            select(func.count(DmpOneImport.id)).where(DmpOneImport.custom_automation_id == automation_id)
        )
        assert count == 0

    async def test_vendor_status_completes_empty_order_and_keeps_open_order(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.services.custom.dmp_one_service import process_order_results

        done = DmpOneImport(
            custom_automation_id=custom_automation.id,
            import_type="website",
            status="processing",
            raw_payload={"external_order_id": "done-1"},
        )
        waiting = DmpOneImport(
            custom_automation_id=custom_automation.id,
            import_type="website",
            status="processing",
            raw_payload={"external_order_id": "wait-1"},
        )
        test_session.add_all([done, waiting])
        await test_session.commit()
        automation_id = custom_automation.id
        await process_order_results(test_session, automation_id, done, {"status": "completed", "contacts": []})
        await process_order_results(
            test_session,
            automation_id,
            waiting,
            {"status": "processing", "contacts": [{"phone": "79001110006"}]},
        )
        await test_session.refresh(done)
        await test_session.refresh(waiting)
        assert done.status == "completed"
        assert waiting.status == "processing"

    async def test_manual_poll_returns_result(
        self,
        client: AsyncClient,
        custom_automation: CustomAutomation,
        client_token: str,
    ):
        response = await client.post(
            f"/api/custom/automations/{custom_automation.id}/dmp/poll",
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "done"
        assert body["imports_processed"] == 0
        assert "leads_retried" in body

    async def test_notify_retry_does_not_append_history(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.services.custom.telegram_notify_bot_service import dispatch_dmp_notifications

        lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="dmp_one",
            contact_type="phone",
            contact_value="79001110007",
            status="new",
            dmp_raw_data={"phone": "79001110007"},
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)
        await dispatch_dmp_notifications(test_session, custom_automation, lead)
        await dispatch_dmp_notifications(test_session, custom_automation, lead)
        await test_session.refresh(lead)
        assert lead.status == "transferred"
        assert lead.bot_notified_at is None
        transferred = [item for item in (lead.status_history or []) if item.get("status") == "transferred"]
        assert len(transferred) == 1

    async def test_amo_toggle_is_used_on_dmp_handoff(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from unittest.mock import AsyncMock, patch

        from app.services.custom.telegram_notify_bot_service import dispatch_dmp_notifications

        automation_id = custom_automation.id
        lead = CustomLead(
            custom_automation_id=automation_id,
            source="dmp_one",
            contact_type="phone",
            contact_value="79001110008",
            status="new",
            dmp_raw_data={"phone": "79001110008"},
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)
        lead_id = lead.id
        with patch(
            "app.services.custom.amocrm_service.transfer_lead_to_amocrm",
            new=AsyncMock(return_value={"transferred": False, "reason": "no_connection"}),
        ) as amo:
            skipped = await dispatch_dmp_notifications(test_session, custom_automation, lead)
            assert skipped["amocrm"] is None
            amo.assert_not_awaited()
            await test_session.execute(
                update(CustomAutomation)
                .where(CustomAutomation.id == automation_id)
                .values(is_amocrm_enabled=True)
            )
            await test_session.commit()
            automation = await test_session.get(CustomAutomation, automation_id)
            lead = await test_session.get(CustomLead, lead_id)
            sent = await dispatch_dmp_notifications(test_session, automation, lead)
        assert sent["amocrm"]["reason"] == "no_connection"
        amo.assert_awaited()

    async def test_outreach_prompt_receives_partner_fields(
        self,
        test_session: AsyncSession,
        custom_automation: CustomAutomation,
    ):
        from app.services.custom.dmp_one_service import _generate_outreach_message

        custom_automation.partner_utm_url = "https://saas.example/?utm_source=tg"
        custom_automation.partner_promo_code = "PROMO77"
        await test_session.commit()
        captured: dict = {}

        class _Message:
            content = '{"message":"привет"}'

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        async def _create(**kwargs):
            captured["content"] = kwargs["messages"][0]["content"]
            return _Response()

        with patch(
            "app.services.custom.dmp_one_service.ai_client.chat.completions.create",
            new=AsyncMock(side_effect=_create),
        ):
            text = await _generate_outreach_message(
                test_session,
                custom_automation,
                name="Иван",
                company="Shop",
            )
        assert text
        assert "utm_source=tg" in captured["content"]
        assert "PROMO77" in captured["content"]
