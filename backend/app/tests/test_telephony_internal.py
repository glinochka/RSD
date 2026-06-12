from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.router_telephony.service import _event_to_status, upsert_call_event
from app.telephony.credentials import TelephonyCredentialsV1


def test_event_to_status_mapping():
    assert _event_to_status("call.inbound", None) == "ringing"
    assert _event_to_status("call.answered", None) == "active"
    assert _event_to_status("call.hangup", "transferred") == "transferred"


def test_webhook_signature_v1_matches_rfc():
    secret = "test-secret"
    timestamp = "1710000000"
    connection_id = 42
    body = b'{"schema_version":1,"event":"call.inbound"}'
    prefix = f"v1\n{timestamp}\n{connection_id}\n".encode()
    expected = hmac.new(secret.encode(), prefix + body, hashlib.sha256).hexdigest()
    assert len(expected) == 64


@pytest.mark.asyncio
async def test_upsert_call_event_creates_then_updates():
    connection = AsyncMock()
    connection.id = 7
    connection.agent_id = 3
    connection.provider = "telephony_voximplant"
    connection.is_active = True
    connection.encrypted_credentials = "enc"

    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = lambda obj: None
    session.flush = AsyncMock()

    with (
        patch("app.router_telephony.service.resolve_inbound_connection", AsyncMock(return_value=(7, "webhook"))),
        patch("app.router_telephony.service.cache_call_mapping", AsyncMock()),
        patch("app.router_telephony.service.load_active_telephony_connection", AsyncMock(return_value=connection)),
    ):
        call, created = await upsert_call_event(
            session,
            connection_id=7,
            external_call_id="call-1",
            caller_e164="+79001234567",
            event="call.inbound",
            status_override=None,
            recording_url=None,
            duration_sec=None,
            metadata={"event_id": "e1"},
        )
    assert created is True
    assert call.status == "ringing"
    assert call.agent_id == 3


def test_telephony_credentials_roundtrip_for_connect():
    creds = TelephonyCredentialsV1(
        account_id="1",
        api_key="x" * 8,
        application_id="app",
        rule_id="rule",
        phone_number_e164="+79001111111",
        webhook_secret="b" * 32,
        operator_transfer_e164="+79002222222",
        voice_id="default",
    )
    loaded = TelephonyCredentialsV1.from_decrypted_json(json.loads(creds.to_encrypted_payload()))
    assert loaded.phone_number_e164 == "+79001111111"
