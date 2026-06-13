"""Парсинг списков email из «грязного» текста (вставки из Excel, через запятую и т.д.)."""

from __future__ import annotations

import re

_EMAIL_FIND_RE = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*",
    re.IGNORECASE,
)


def parse_emails_from_raw_text(raw: str) -> list[str]:
    """Извлекает валидно выглядящие email, приводит к lower, убирает дубли (порядок — по первому вхождению)."""
    if not raw or not str(raw).strip():
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _EMAIL_FIND_RE.finditer(raw):
        token = match.group(0).strip().rstrip(".,;)>]}\"'`")
        lowered = token.lower()
        if lowered not in seen:
            seen.add(lowered)
            ordered.append(lowered)
    return ordered
