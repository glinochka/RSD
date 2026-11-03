"""Shared Telegram webhook secret.

The same value is sent to setWebhook and checked on the bot process.
It is derived from ENCRYPTION_KEY so a restart does not rotate it.
"""
from __future__ import annotations

import hashlib
import hmac


def telegram_webhook_secret(*, encryption_key: str, scope: str) -> str:
    key = (encryption_key or "").encode("utf-8")
    digest = hmac.new(key, f"tg-webhook:{scope}".encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:64]


def telegram_webhook_secret_matches(presented: str, expected: str) -> bool:
    presented = (presented or "").strip()
    expected = (expected or "").strip()
    if not presented or not expected or len(presented) != len(expected):
        return False
    return hmac.compare_digest(presented, expected)
