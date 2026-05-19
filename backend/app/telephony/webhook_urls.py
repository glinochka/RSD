"""Webhook URL helpers for telephony channel."""

from __future__ import annotations

from ..config import settings


def build_telephony_webhook_url(connection_id: int) -> str:
    base = (settings.TELEPHONY_WEBHOOK_BASE_URL or "").strip().rstrip("/")
    if not base:
        return f"/webhook/voximplant/{connection_id}"
    return f"{base}/webhook/voximplant/{connection_id}"
