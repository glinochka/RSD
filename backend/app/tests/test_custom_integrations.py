"""Custom integration webhook constructor."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import CustomAutomation, CustomAutomationCredential, CustomAdmin, CustomLead
from app.utils.security import get_password_hash
from app.services.custom.integration_webhook_service import dispatch_event, upsert_route


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="integ_admin",
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
        name="Integrations Automation",
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
        username="integ_client",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(credential)
    await test_session.commit()
    await test_session.refresh(credential)
    return credential


@pytest.fixture
async def client_token(client: AsyncClient, custom_credential: CustomAutomationCredential) -> str:
    response = await client.post("/api/custom/login", json={
        "username": "integ_client",
        "password": "password",
    })
    assert response.status_code == 200
    return response.json()["access_token"]


class TestIntegrationWebhooks:
    async def test_save_outbound_and_ingest_inbound(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation,
        test_session: AsyncSession,
    ):
        headers = {"Authorization": f"Bearer {client_token}"}
        create = await client.put(
            f"/api/custom/automations/{custom_automation.id}/integrations/routes",
            headers=headers,
            json={
                "name": "CRM hook",
                "direction": "outbound",
                "event": "lead.transferred",
                "url": "https://example.com/hooks/leads",
                "secret_header": "X-Webhook-Secret",
                "secret": "s3cret",
                "mappings": [{"source": "contact_value", "target": "phone"}],
            },
        )
        assert create.status_code == 200, create.text
        data = create.json()
        assert data["direction"] == "outbound"
        assert data["url"] == "https://example.com/hooks/leads"
        assert data["secret"] == "s3cret"

        inbound = await client.put(
            f"/api/custom/automations/{custom_automation.id}/integrations/routes",
            headers=headers,
            json={
                "name": "Incoming form",
                "direction": "inbound",
                "event": "lead.created",
                "secret": "in-secret",
                "mappings": [{"source": "phone", "target": "contact_value"}],
            },
        )
        assert inbound.status_code == 200, inbound.text
        route = inbound.json()
        assert route["id"]

        posted = await client.post(
            f"/api/custom/webhooks/integrations/{custom_automation.id}/{route['id']}/in-secret",
            json={"phone": "+79990001122", "name": "Ivan"},
        )
        assert posted.status_code == 200, posted.text
        lead_id = posted.json()["lead_id"]
        lead = await test_session.get(CustomLead, lead_id)
        assert lead is not None
        assert lead.contact_value == "+79990001122"

        listed = await client.get(
            f"/api/custom/automations/{custom_automation.id}/integrations/routes",
            headers=headers,
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 2

    async def test_dispatch_outbound_uses_mapping(
        self,
        test_session: AsyncSession,
        custom_automation,
    ):
        upsert_route(
            custom_automation,
            {
                "name": "Out",
                "direction": "outbound",
                "event": "lead.created",
                "url": "https://hooks.example/lead",
                "secret": "abc",
                "mappings": [{"source": "contact_value", "target": "user.phone"}],
            },
        )
        await test_session.commit()
        lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="test",
            contact_type="phone",
            contact_value="+7000",
            status="new",
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)

        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.custom.integration_webhook_service.httpx.AsyncClient", return_value=mock_client):
            await dispatch_event(test_session, custom_automation, "lead.created", lead)

        mock_client.post.assert_awaited()
        kwargs = mock_client.post.await_args.kwargs
        assert kwargs["json"]["user"]["phone"] == "+7000"
        assert kwargs["headers"]["X-Webhook-Secret"] == "abc"
