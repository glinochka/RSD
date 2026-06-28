"""WhatsApp JID normalization and shared wa_bridge HTTP client."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import settings

MIN_WHATSAPP_PHONE_DIGITS = 5


class WhatsAppJidError(ValueError):
    """Invalid WhatsApp external id or JID."""


def normalize_whatsapp_external_id(value: str) -> str:
    """Normalize user_external_id for WhatsApp channel lookups."""
    uid = (value or "").strip()
    if not uid:
        return uid
    if "@" in uid:
        return uid.lower()
    digits = "".join(ch for ch in uid if ch.isdigit())
    if digits:
        return f"{digits}@s.whatsapp.net"
    return uid.lower()


def external_id_to_jid(value: str) -> str:
    """Build full JID from analytics id (preferred) or phone digits only."""
    raw = (value or "").strip()
    if not raw:
        raise WhatsAppJidError("Пустой идентификатор получателя WhatsApp")
    if "@" in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < MIN_WHATSAPP_PHONE_DIGITS:
        raise WhatsAppJidError(
            "Некорректный номер или JID WhatsApp (нужны цифры номера или полный JID)"
        )
    return f"{digits}@s.whatsapp.net"


def jid_for_whatsapp_analytics(remote_jid: str) -> str:
    """Store full Baileys JID in analytics (…@s.whatsapp.net, …@lid, etc.)."""
    jid = str(remote_jid or "").strip()
    if len(jid) > 128:
        return jid[:128]
    return jid


def is_private_whatsapp_jid(jid: str) -> bool:
    """True for direct (non-group/broadcast) WhatsApp chats."""
    value = str(jid or "").strip().lower()
    if not value:
        return False
    if value.endswith("@g.us") or value.endswith("@broadcast") or value == "status@broadcast":
        return False
    return ("@" in value) and (value.endswith("@s.whatsapp.net") or value.endswith("@lid"))


async def bridge_post(
    path: str,
    payload: dict[str, Any],
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """POST JSON to WhatsApp userbot bridge (wa_bridge)."""
    base = (settings.WHATSAPP_USERBOT_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("WHATSAPP_USERBOT_BRIDGE_URL is not configured")
    api_key = (settings.WHATSAPP_USERBOT_BRIDGE_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("WHATSAPP_USERBOT_BRIDGE_API_KEY is not configured")

    timeout_seconds = timeout if timeout is not None else float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS)
    url = f"{base}/{path.lstrip('/')}"
    httpx_timeout = httpx.Timeout(timeout_seconds, connect=min(20.0, timeout_seconds))
    async with httpx.AsyncClient(timeout=httpx_timeout) as client:
        response = await client.post(url, json=payload, headers={"X-API-Key": api_key})
    if not response.is_success:
        raise RuntimeError(
            f"wa_bridge {path} failed: HTTP {response.status_code} {response.text[:300]}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"wa_bridge {path} returned unexpected payload")
    return data
