"""Sasha AI + DMP.one integration."""
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import CustomAdmin, CustomAutomation, CustomAutomationCredential, CustomLead, SashaAiCall
from app.utils.security import get_password_hash


pytestmark = pytest.mark.asyncio

SASHA_UPLOAD_URL = "https://platform.trysasha.ru/api/upload-contacts-integrations/webhook/test-token"


class _FakeUploadResponse:
    status_code = 200
    text = '{"success":true,"uploadedCount":1,"skippedCount":0,"skippedPhones":[]}'
    content = text.encode()

    def json(self):
        return {"success": True, "uploadedCount": 1, "skippedCount": 0, "skippedPhones": [], "message": "ok"}


class _FakeUploadClient:
    last_json = None
    last_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).last_url = url
        type(self).last_json = json
        return _FakeUploadResponse()


@pytest.fixture
async def custom_admin(test_session: AsyncSession) -> CustomAdmin:
    admin = CustomAdmin(
        username="sasha_admin",
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
        name="Sasha Automation",
        client_name="Sasha Client",
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
async def client_token(client: AsyncClient, test_session: AsyncSession, custom_automation: CustomAutomation) -> str:
    credential = CustomAutomationCredential(
        custom_automation_id=custom_automation.id,
        username="sasha_client",
        password_hash=get_password_hash("password"),
        is_active=True,
    )
    test_session.add(credential)
    await test_session.commit()
    response = await client.post("/api/custom/login", json={"username": "sasha_client", "password": "password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _connect_sasha(client: AsyncClient, automation_id: int, token: str, **extra) -> dict:
    from app.config import settings

    payload = {
        "sasha_upload_url": SASHA_UPLOAD_URL,
        "sasha_upload_format": "api",
        "sasha_hmac_secret": "sasha-hmac-secret",
        "is_sasha_ai_enabled": True,
        **extra,
    }
    with patch.object(settings, "BASE_URL", "https://app.example.com"):
        response = await client.put(
            f"/api/custom/automations/{automation_id}/sasha/connection",
            headers=_headers(token),
            json=payload,
        )
    assert response.status_code == 200, response.text
    return response.json()


class TestSashaConnection:
    async def test_save_connection_builds_inbound_url(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
    ):
        data = await _connect_sasha(client, custom_automation.id, client_token)
        assert data["is_sasha_ai_enabled"] is True
        assert data["sasha_connected"] is True
        assert data["sasha_upload_url"] == SASHA_UPLOAD_URL
        assert data["sasha_hmac_secret_set"] is True
        assert data["sasha_webhook_secret"]
        assert str(custom_automation.id) in (data["sasha_webhook_url"] or "")
        assert data["sasha_webhook_secret"] in (data["sasha_webhook_url"] or "")

    async def test_rejects_bad_upload_url(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
    ):
        response = await client.put(
            f"/api/custom/automations/{custom_automation.id}/sasha/connection",
            headers=_headers(client_token),
            json={"sasha_upload_url": "not-a-url", "is_sasha_ai_enabled": True},
        )
        assert response.status_code == 422


class TestSashaDmpBridge:
    async def test_dmp_contact_is_pushed_and_call_result_qualifies_lead(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        from app.config import settings

        automation_id = custom_automation.id
        with patch.object(settings, "BASE_URL", "https://app.example.com"):
            dmp = await client.patch(
                f"/api/custom/automations/{automation_id}/settings",
                headers=_headers(client_token),
                json={"is_dmp_one_enabled": True},
            )
            assert dmp.status_code == 200, dmp.text
            dmp_secret = dmp.json()["dmp_webhook_secret"]
            sasha = await _connect_sasha(client, automation_id, client_token)
            inbound_secret = sasha["sasha_webhook_secret"]

            _FakeUploadClient.last_json = None
            with patch("app.services.custom.sasha_ai_service.httpx.AsyncClient", return_value=_FakeUploadClient()):
                created = await client.post(
                    f"/api/custom/webhooks/dmp/{automation_id}/{dmp_secret}",
                    json=[{"phone": "79001234567", "website": "example.com", "page": "https://example.com/x", "name": "Иван"}],
                )
            assert created.status_code == 200, created.text
            assert created.json()["created_leads"] == 1
            assert _FakeUploadClient.last_url == SASHA_UPLOAD_URL
            uploaded = _FakeUploadClient.last_json[0]
            assert uploaded["phone"] == "79001234567"
            assert "dmp.one" in uploaded["tags"]
            assert uploaded["additionalFields"]["website"] == "example.com"

        test_session.expire_all()
        lead = (
            await test_session.execute(
                select(CustomLead).where(CustomLead.custom_automation_id == automation_id)
            )
        ).scalar_one()
        assert lead.sasha_status == "uploaded"

        event = {
            "id": "call-event-1",
            "type": "call_result",
            "call": {
                "id": "call-event-1",
                "status": "completed",
                "duration": 120000,
                "hangupReason": "hangup",
                "recordUrl": "https://example.com/record.mp3",
                "callDetails": {
                    "chatHistory": [
                        {"role": "assistant", "content": "Алло, меня зовут Саша"},
                        {"role": "user", "content": "Да, слушаю, Иван Петров"},
                    ]
                },
                "agreements": {
                    "isCommit": True,
                    "client_name": "Иван Петров",
                    "client_facts": "Интересуется интеграцией DMP",
                    "agreements": "Договорились созвониться с менеджером",
                    "lead_quality": 8,
                    "status": "transfer",
                    "lead_destination": "sales",
                },
            },
            "contact": {
                "phone": "79001234567",
                "additionalFields": {"lead_id": str(lead.id), "website": "example.com"},
            },
        }
        raw = json.dumps(event, ensure_ascii=False).encode("utf-8")
        signature = _sign(raw, "sasha-hmac-secret")
        posted = await client.post(
            f"/api/custom/webhooks/sasha/{automation_id}/{inbound_secret}",
            content=raw,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": signature},
        )
        assert posted.status_code == 200, posted.text
        assert posted.json()["is_commit"] is True

        duplicate = await client.post(
            f"/api/custom/webhooks/sasha/{automation_id}/{inbound_secret}",
            content=raw,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": signature},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["status"] == "duplicate"

        test_session.expire_all()
        await test_session.refresh(lead)
        assert lead.full_name == "Иван Петров"
        assert lead.sasha_is_commit is True
        assert lead.sasha_lead_quality == 8
        assert lead.status == "qualified"
        assert "Интересуется интеграцией DMP" in (lead.sasha_summary or "")
        from app.services.custom.telegram_notify_bot_service import format_lead_bot_message

        card = format_lead_bot_message(lead)
        assert "Источник: DMP.one" in card
        assert "79001234567" in card
        assert "Имя: Иван Петров" in card
        assert "Что нужно: Интересуется интеграцией DMP" in card
        assert "Квалификация: звонок Sasha AI" in card
        assert "Прогрев: 8/10 (горячий)" in card
        assert "Договорённость: Договорились созвониться с менеджером" in card
        assert "Звонок:" in card
        assert "Клиент: Да, слушаю, Иван Петров" in card
        assert "Запись: https://example.com/record.mp3" in card

        listed = await client.get(
            f"/api/custom/automations/{automation_id}/sasha",
            headers=_headers(client_token),
        )
        assert listed.status_code == 200, listed.text
        data = listed.json()
        assert data["total"] == 1
        assert data["items"][0]["client_name"] == "Иван Петров"
        assert data["items"][0]["warmth"] == "горячий"
        assert "Клиент: Да, слушаю, Иван Петров" in data["items"][0]["transcript_text"]
        assert data["stats"]["committed_leads"] == 1

    async def test_invalid_hmac_is_rejected(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
    ):
        sasha = await _connect_sasha(client, custom_automation.id, client_token)
        body = json.dumps({"id": "x", "type": "call_result", "call": {}, "contact": {"phone": "79001112233"}}).encode()
        response = await client.post(
            f"/api/custom/webhooks/sasha/{custom_automation.id}/{sasha['sasha_webhook_secret']}",
            content=body,
            headers={"Content-Type": "application/json", "X-Webhook-Signature": "00" * 32},
        )
        assert response.status_code == 401

    async def test_manual_push_sends_existing_dmp_lead(
        self,
        client: AsyncClient,
        client_token: str,
        custom_automation: CustomAutomation,
        test_session: AsyncSession,
    ):
        lead = CustomLead(
            custom_automation_id=custom_automation.id,
            source="dmp_one",
            contact_type="phone",
            contact_value="79007654321",
            full_name="Мария",
            company="site.ru",
            status="new",
            dmp_raw_data={"phone": "79007654321", "website": "site.ru"},
        )
        test_session.add(lead)
        await test_session.commit()
        await test_session.refresh(lead)
        lead_id = lead.id
        await _connect_sasha(client, custom_automation.id, client_token, sasha_auto_push=False)
        _FakeUploadClient.last_json = None
        with patch("app.services.custom.sasha_ai_service.httpx.AsyncClient", return_value=_FakeUploadClient()):
            pushed = await client.post(
                f"/api/custom/automations/{custom_automation.id}/leads/{lead_id}/sasha/push",
                headers=_headers(client_token),
            )
        assert pushed.status_code == 200, pushed.text
        assert pushed.json()["status"] == "uploaded"
        assert _FakeUploadClient.last_json[0]["phone"] == "79007654321"

        test_session.expire_all()
        stored = await test_session.get(CustomLead, lead_id)
        assert stored.sasha_status == "uploaded"
        calls = await test_session.scalar(select(SashaAiCall.id).limit(1))
        assert calls is None
