"""Safe logging for telephony (PII + secrets)."""

from __future__ import annotations

import re

from ..utils.pii import redact_pii_text

_API_KEY_RE = re.compile(r"(?i)(api[_-]?key|webhook[_-]?secret|bearer)\s*[:=]\s*\S+")
_RECORDING_URL_TOKEN_RE = re.compile(r"(https?://\S+\?)(\S+)")


def redact_telephony_log_message(value: str | None) -> str:
    text = redact_pii_text(value or "")
    text = _API_KEY_RE.sub(r"\1 [REDACTED]", text)
    text = _RECORDING_URL_TOKEN_RE.sub(r"\1[REDACTED]", text)
    return text
