"""PII masking for telephony UI."""

from __future__ import annotations

import re


def mask_caller_e164(value: str | None) -> str:
    """Mask E.164 for UI, e.g. +79001234567 → +7900***4567."""
    raw = (value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 8:
        return "***"
    return f"+{digits[:4]}***{digits[-4:]}"
