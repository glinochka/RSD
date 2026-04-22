import re

_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]{1,64})@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\-\s()]{6,}\d)(?!\d)")
_TOKEN_RE = re.compile(r"(?i)\b(bearer\s+)?([a-z0-9_\-]{20,})\b")


def _mask_email(match: re.Match) -> str:
    local = match.group(1) or ""
    domain = match.group(2) or ""
    if len(local) <= 2:
        local_masked = "*" * len(local)
    else:
        local_masked = local[:1] + ("*" * (len(local) - 2)) + local[-1:]
    return f"{local_masked}@{domain}"


def _mask_phone(match: re.Match) -> str:
    raw = match.group(1) or ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return raw
    masked = digits[:2] + ("*" * max(0, len(digits) - 4)) + digits[-2:]
    return masked


def redact_pii_text(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = _EMAIL_RE.sub(_mask_email, text)
    text = _PHONE_RE.sub(_mask_phone, text)
    # Generic long token masking as a last-resort safety net.
    text = _TOKEN_RE.sub("[REDACTED]", text)
    return text


def mask_external_id(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) <= 4:
        return "*" * len(raw)
    return f"{raw[:2]}{'*' * (len(raw) - 4)}{raw[-2:]}"
