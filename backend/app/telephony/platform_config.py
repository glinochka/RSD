"""Platform-wide Voximplant pool (one DID for all agents, DTMF extension per agent)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status

from ..config import settings

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _normalize_e164(value: str) -> str | None:
    raw = (value or "").strip().replace(" ", "")
    if not raw:
        return None
    if not raw.startswith("+"):
        if raw.startswith("8") and len(raw) == 11:
            raw = "+7" + raw[1:]
        else:
            raw = f"+{raw}"
    if not _E164_RE.match(raw):
        return None
    return raw


@dataclass(frozen=True)
class PlatformTelephonyConfig:
    shared_pool_e164: str
    account_id: str
    api_key: str
    application_id: str
    rule_id: str
    operator_transfer_e164: str


def _missing_platform_fields() -> list[str]:
    missing: list[str] = []
    if not (settings.TELEPHONY_SHARED_POOL_E164 or "").strip():
        missing.append("TELEPHONY_SHARED_POOL_E164")
    if not (settings.TELEPHONY_VOXIMPLANT_ACCOUNT_ID or "").strip():
        missing.append("TELEPHONY_VOXIMPLANT_ACCOUNT_ID")
    if not (settings.TELEPHONY_VOXIMPLANT_API_KEY or "").strip():
        missing.append("TELEPHONY_VOXIMPLANT_API_KEY")
    if not (settings.TELEPHONY_VOXIMPLANT_APPLICATION_ID or "").strip():
        missing.append("TELEPHONY_VOXIMPLANT_APPLICATION_ID")
    if not (settings.TELEPHONY_VOXIMPLANT_RULE_ID or "").strip():
        missing.append("TELEPHONY_VOXIMPLANT_RULE_ID")
    if not (settings.TELEPHONY_OPERATOR_TRANSFER_E164 or "").strip():
        missing.append("TELEPHONY_OPERATOR_TRANSFER_E164")
    return missing


def platform_telephony_configured() -> bool:
    return not _missing_platform_fields()


def require_platform_telephony_config() -> PlatformTelephonyConfig:
    missing = _missing_platform_fields()
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Телефония платформы не настроена. Задайте в .env: "
                + ", ".join(missing)
            ),
        )
    pool = _normalize_e164(settings.TELEPHONY_SHARED_POOL_E164)
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEPHONY_SHARED_POOL_E164: некорректный E.164",
        )
    operator = _normalize_e164(settings.TELEPHONY_OPERATOR_TRANSFER_E164)
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEPHONY_OPERATOR_TRANSFER_E164: некорректный E.164",
        )
    return PlatformTelephonyConfig(
        shared_pool_e164=pool,
        account_id=settings.TELEPHONY_VOXIMPLANT_ACCOUNT_ID.strip(),
        api_key=settings.TELEPHONY_VOXIMPLANT_API_KEY.strip(),
        application_id=settings.TELEPHONY_VOXIMPLANT_APPLICATION_ID.strip(),
        rule_id=settings.TELEPHONY_VOXIMPLANT_RULE_ID.strip(),
        operator_transfer_e164=operator,
    )


def format_dial_with_extension(e164: str, extension: str | None) -> str:
    """Display hint: номер,добавочный (например +74951234567,1234)."""
    base = (e164 or "").strip()
    ext = (extension or "").strip()
    if base and ext:
        return f"{base},{ext}"
    return base


def platform_telephony_public_fields() -> dict[str, Any]:
    """Safe fields for UI (no API keys)."""
    missing = _missing_platform_fields()
    pool = _normalize_e164(settings.TELEPHONY_SHARED_POOL_E164 or "")
    operator = _normalize_e164(settings.TELEPHONY_OPERATOR_TRANSFER_E164 or "")
    return {
        "platform_ready": not missing,
        "missing_env": missing,
        "shared_pool_e164": pool,
        "operator_transfer_e164": operator,
        "routing_mode": "dtmf_extension",
        "extension_digits": 4,
        "dial_hint": (
            format_dial_with_extension(pool, "1234")
            if pool
            else "Настройте TELEPHONY_SHARED_POOL_E164 в .env"
        ),
        "instructions": (
            "Позвоните на общий номер и после гудка введите 4-значный добавочный агента "
            "(или наберите номер,добавочный с клавиатуры телефона)."
        ),
    }
