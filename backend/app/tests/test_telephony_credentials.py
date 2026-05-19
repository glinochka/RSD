from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.telephony.credentials import (
    TELEPHONY_CHANNEL_PROVIDER,
    TELEPHONY_CREDENTIALS_PROVIDER,
    TelephonyCredentialsV1,
    parse_telephony_credentials,
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / "schemas" / "telephony" / "credentials.v1.schema.json"
)


def _valid_payload() -> dict:
    return {
        "provider": "voximplant",
        "account_id": "12345",
        "api_key": "test-api-key-xxxxxxxx",
        "application_id": "app-1",
        "rule_id": "rule-1",
        "phone_number_e164": "+79001234567",
        "webhook_secret": "a" * 32,
        "operator_transfer_e164": "+79007654321",
        "voice_id": "default",
        "language": "ru-RU",
        "record_calls": True,
        "disclaimer_played": True,
    }


def test_channel_provider_constant():
    assert TELEPHONY_CHANNEL_PROVIDER == "telephony_voximplant"
    assert TELEPHONY_CREDENTIALS_PROVIDER == "voximplant"


def test_valid_credentials_roundtrip():
    creds = TelephonyCredentialsV1.model_validate(_valid_payload())
    restored = TelephonyCredentialsV1.from_decrypted_json(creds.to_encrypted_payload())
    assert restored.phone_number_e164 == "+79001234567"
    assert restored.record_calls is True


def test_parse_telephony_credentials_from_dict():
    creds = parse_telephony_credentials(_valid_payload())
    assert creds.application_id == "app-1"


def test_rejects_invalid_e164():
    payload = _valid_payload()
    payload["phone_number_e164"] = "89001234567"
    with pytest.raises(ValidationError):
        TelephonyCredentialsV1.model_validate(payload)


def test_rejects_short_webhook_secret():
    payload = _valid_payload()
    payload["webhook_secret"] = "short"
    with pytest.raises(ValidationError):
        TelephonyCredentialsV1.model_validate(payload)


def test_rejects_unknown_provider():
    payload = _valid_payload()
    payload["provider"] = "twilio"
    with pytest.raises(ValidationError):
        TelephonyCredentialsV1.model_validate(payload)


def test_rejects_extra_fields():
    payload = _valid_payload()
    payload["extra"] = "nope"
    with pytest.raises(ValidationError):
        TelephonyCredentialsV1.model_validate(payload)


def test_json_schema_file_exists_and_matches_required_keys():
    assert _SCHEMA_PATH.is_file()
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    required = set(schema["required"])
    model_fields = set(TelephonyCredentialsV1.model_fields.keys())
    assert required == model_fields
