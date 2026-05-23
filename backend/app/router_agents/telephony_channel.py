"""Telephony channel connect / validate helpers."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, status

from ..services.voximplant_client import (
    VoximplantApiError,
    validate_voximplant_channel_setup,
)
from ..telephony.credentials import TELEPHONY_CHANNEL_PROVIDER, TelephonyCredentialsV1
from ..telephony.webhook_urls import build_telephony_webhook_url
from .schemas import TelephonyChannelCredentialsInput


async def validate_telephony_credentials_input(payload: TelephonyChannelCredentialsInput) -> TelephonyCredentialsV1:
    try:
        await validate_voximplant_channel_setup(
            account_id=payload.account_id,
            api_key=payload.api_key,
            phone_number_e164=payload.phone_number_e164,
            application_id=payload.application_id,
            rule_id=payload.rule_id,
        )
    except VoximplantApiError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    webhook_secret = secrets.token_hex(32)
    return TelephonyCredentialsV1(
        account_id=payload.account_id.strip(),
        api_key=payload.api_key.strip(),
        application_id=payload.application_id.strip(),
        rule_id=payload.rule_id.strip(),
        phone_number_e164=payload.phone_number_e164.strip(),
        webhook_secret=webhook_secret,
        operator_transfer_e164=payload.operator_transfer_e164.strip(),
        voice_id=(payload.voice_id or "default").strip(),
        language=(payload.language or "ru-RU").strip(),
        record_calls=bool(payload.record_calls),
        disclaimer_played=bool(payload.disclaimer_played),
        routing_extension=(payload.routing_extension or "").strip() or None,
        inbound_numbers=list(payload.inbound_numbers or []),
    )


def telephony_external_id(phone_number_e164: str, routing_extension: str | None = None) -> str:
    """Pool agents share one E.164; extension makes external_id unique."""
    ext = (routing_extension or "").strip()
    if ext:
        return f"pool:{ext}"
    return phone_number_e164.strip()


def build_encrypted_telephony_bundle(creds: TelephonyCredentialsV1, encrypt_token) -> str:
    return encrypt_token(creds.to_encrypted_payload())


def telephony_connect_response_extra(connection_id: int) -> dict[str, Any]:
    return {
        "provider": TELEPHONY_CHANNEL_PROVIDER,
        "webhook_url": build_telephony_webhook_url(connection_id),
        "webhook_path": f"/webhook/voximplant/{connection_id}",
    }
