"""Async HTTP client for wa_bridge (единый контракт с WhatsAppUserbotManager)."""
from __future__ import annotations

from typing import Any

import httpx

from ..config import settings


def _headers() -> dict[str, str]:
    api_key = (settings.WHATSAPP_USERBOT_BRIDGE_API_KEY or "").strip()
    if not api_key:
        raise ValueError("WHATSAPP_USERBOT_BRIDGE_API_KEY не настроен на сервере")
    return {"X-API-Key": api_key}


def _base_url() -> str:
    base = (settings.WHATSAPP_USERBOT_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        raise ValueError("WHATSAPP_USERBOT_BRIDGE_URL не настроен на сервере")
    return base


async def wa_bridge_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}/{path.lstrip('/')}"
    timeout = httpx.Timeout(
        float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS),
        connect=min(20.0, float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS)),
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=_headers())
    if not response.is_success:
        raise RuntimeError(f"wa_bridge {path} failed: HTTP {response.status_code} {response.text[:300]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"wa_bridge {path} returned unexpected payload")
    return data
