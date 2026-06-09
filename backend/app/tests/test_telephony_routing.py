from __future__ import annotations

import pytest

from app.telephony.credentials import TelephonyCredentialsV1
from app.telephony.routing import (
    dedicated_did_numbers,
    normalize_extension,
    normalize_inbound_numbers,
    pool_line_e164,
    resolve_agent_by_extension,
    telephony_routing_public_fields,
)


def _creds(**patch) -> TelephonyCredentialsV1:
    base = {
        "account_id": "1",
        "api_key": "test-api-key-xxxxxxxx",
        "application_id": "app",
        "rule_id": "rule",
        "phone_number_e164": "+79001234567",
        "webhook_secret": "a" * 32,
        "operator_transfer_e164": "+79007654321",
        "voice_id": "default",
        "language": "ru-RU",
        "record_calls": True,
        "disclaimer_played": True,
    }
    base.update(patch)
    return TelephonyCredentialsV1.model_validate(base)


def test_normalize_extension():
    assert normalize_extension("1234") == "1234"
    assert normalize_extension("12a4") is None
    assert normalize_extension("") is None


def test_dedicated_did_legacy_single_number():
    creds = _creds()
    assert dedicated_did_numbers(creds) == ["+79001234567"]


def test_dedicated_did_skips_pool_primary_when_extension_set():
    creds = _creds(routing_extension="1234", inbound_numbers=["+74951111111"])
    assert "+79001234567" not in dedicated_did_numbers(creds)
    assert "+74951111111" in dedicated_did_numbers(creds)
    assert pool_line_e164(creds) == "+79001234567"


def test_inbound_numbers_deduped():
    nums = normalize_inbound_numbers(["+74951111111", "+74951111111", ""])
    assert nums == ["+74951111111"]


def test_routing_public_fields():
    creds = _creds(routing_extension="5678", inbound_numbers=["+74952222222"])
    public = telephony_routing_public_fields(creds)
    assert public["routing_extension"] == "5678"
    assert public["inbound_numbers"] == []
    assert public["pool_line_e164"] == "+79001234567"
    assert public["dial_hint"] == "+79001234567,5678"
    assert public["routing_mode"] == "dtmf_extension"


def test_rejects_invalid_extension_in_credentials():
    with pytest.raises(Exception):
        _creds(routing_extension="12")


@pytest.mark.asyncio
async def test_resolve_agent_by_extension_falls_back_to_db_when_redis_miss(test_session):
    from app.alembic.models import AgentChannelConnection
    from app.utils.crypto import encrypt_token

    agent_id = 77
    connection_id = 501
    creds = _creds(routing_extension="1234")
    encrypted = encrypt_token(creds.to_encrypted_payload())

    async with test_session.begin():
        test_session.add(
            AgentChannelConnection(
                id=connection_id,
                agent_id=agent_id,
                provider="telephony_voximplant",
                connection_type="api",
                external_id="pool:1234",
                encrypted_credentials=encrypted,
                is_primary=False,
                is_active=True,
            )
        )

    resolved = await resolve_agent_by_extension("1234")
    assert resolved == agent_id
