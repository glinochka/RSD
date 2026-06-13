"""Telephony channel (ИИ-оператор по телефону). Stage 0: credentials contract."""

from .constants import ANALYTICS_CHANNEL_PHONE
from .credentials import (
    TELEPHONY_CHANNEL_PROVIDER,
    TelephonyCredentialsV1,
    parse_telephony_credentials,
)
from .compliance import recording_disclaimer_text
from .webhook_urls import build_telephony_webhook_url

__all__ = [
    "ANALYTICS_CHANNEL_PHONE",
    "TELEPHONY_CHANNEL_PROVIDER",
    "TelephonyCredentialsV1",
    "build_telephony_webhook_url",
    "parse_telephony_credentials",
]
