"""Telephony encrypted_credentials schema (v1). See schemas/telephony/credentials.v1.schema.json."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

TELEPHONY_CHANNEL_PROVIDER = "telephony_voximplant"
TELEPHONY_CREDENTIALS_PROVIDER = "voximplant"

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_BCP47_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class TelephonyCredentialsV1(BaseModel):
    """Plaintext credentials before encrypt_token (Voximplant MVP)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(default=TELEPHONY_CREDENTIALS_PROVIDER)
    account_id: str = Field(min_length=1)
    api_key: str = Field(min_length=8)
    application_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    phone_number_e164: str
    webhook_secret: str = Field(min_length=32)
    operator_transfer_e164: str
    voice_id: str = Field(min_length=1)
    language: str = "ru-RU"
    record_calls: bool = True
    disclaimer_played: bool = True

    @field_validator("provider")
    @classmethod
    def provider_must_be_voximplant(cls, v: str) -> str:
        if v != TELEPHONY_CREDENTIALS_PROVIDER:
            raise ValueError(f"provider must be {TELEPHONY_CREDENTIALS_PROVIDER!r}")
        return v

    @field_validator("phone_number_e164", "operator_transfer_e164")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        if not _E164_RE.match(v):
            raise ValueError("invalid E.164 phone number")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if not _BCP47_RE.match(v):
            raise ValueError("language must be a BCP 47 tag, e.g. ru-RU")
        return v

    def to_encrypted_payload(self) -> str:
        """JSON string for encrypt_token."""
        return self.model_dump_json()

    @classmethod
    def from_decrypted_json(cls, raw: str | dict[str, Any]) -> TelephonyCredentialsV1:
        if isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = raw
        return cls.model_validate(data)


def parse_telephony_credentials(decrypted: str | dict[str, Any]) -> TelephonyCredentialsV1:
    """Validate decrypted credentials blob from agent_channel_connections."""
    return TelephonyCredentialsV1.from_decrypted_json(decrypted)
