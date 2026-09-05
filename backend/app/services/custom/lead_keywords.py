"""Keyword gate for chat lead intercept (before LLM)."""
from __future__ import annotations

import re
from typing import Any

MAX_LEAD_KEYWORDS = 50
MAX_LEAD_KEYWORD_LEN = 64
MIN_LEAD_KEYWORD_LEN = 2
_SHORT_KEYWORD_LEN = 3
_SPLIT_RE = re.compile(r"[\n,;]+")
_WORD_CHARS = r"0-9a-zа-яё"
# Common RU/EN marketing spellings so «сео» matches keyword «seo».
_KEYWORD_ALIASES = {
    "seo": ("сео",),
    "сео": ("seo",),
    "smm": ("смм",),
    "смм": ("smm",),
}


def _coerce_keyword_items(raw_value: Any) -> list[Any]:
    if raw_value is None:
        return []
    if isinstance(raw_value, dict):
        return []
    if isinstance(raw_value, str):
        return [part.strip() for part in _SPLIT_RE.split(raw_value) if part.strip()]
    if isinstance(raw_value, (list, tuple, set)):
        items: list[Any] = []
        for item in raw_value:
            if isinstance(item, str) and _SPLIT_RE.search(item):
                items.extend(_coerce_keyword_items(item))
            else:
                items.append(item)
        return items
    return []


def normalize_lead_keywords(raw_value: Any) -> list[str]:
    """Lowercase unique phrases; empty list means skip LLM entirely."""
    normalized: list[str] = []
    seen: set[str] = set()
    for item in _coerce_keyword_items(raw_value):
        word = " ".join(str(item or "").strip().casefold().split())
        if len(word) < MIN_LEAD_KEYWORD_LEN:
            continue
        if len(word) > MAX_LEAD_KEYWORD_LEN:
            word = word[:MAX_LEAD_KEYWORD_LEN]
        if word in seen:
            continue
        seen.add(word)
        normalized.append(word)
        if len(normalized) >= MAX_LEAD_KEYWORDS:
            break
    return normalized


def _keyword_needles(keyword: str) -> list[str]:
    needle = (keyword or "").casefold()
    if not needle:
        return []
    variants = [needle]
    for alias in _KEYWORD_ALIASES.get(needle, ()):
        if alias not in variants:
            variants.append(alias)
    return variants


def _haystack_contains(haystack: str, needle: str) -> bool:
    if len(needle) < _SHORT_KEYWORD_LEN:
        pattern = rf"(?<![{_WORD_CHARS}]){re.escape(needle)}(?![{_WORD_CHARS}])"
        return bool(re.search(pattern, haystack, re.IGNORECASE))
    return needle in haystack


def matched_lead_keyword(text: str, keywords: list[str]) -> str | None:
    """Return the first matching keyword (longer phrases first) or None."""
    haystack = (text or "").casefold()
    if not haystack or not keywords:
        return None
    ordered = sorted(keywords, key=lambda item: (-len(item), item))
    for keyword in ordered:
        for needle in _keyword_needles(keyword):
            if len(needle) < MIN_LEAD_KEYWORD_LEN:
                continue
            if _haystack_contains(haystack, needle):
                return keyword
    return None
