"""Keep Telegram copy human: no unsolicited links, no farm-to-farm sales loops."""
from __future__ import annotations

import re
from typing import Any, Iterable

_URL_RE = re.compile(
    r"(https?://[^\s<>\]]+|www\.[^\s<>\]]+|(?:[a-z0-9-]+\.)+(?:ru|com|io|net|org|app|dev)(?:/[^\s]*)?)",
    re.IGNORECASE,
)
_ASK_LINK_RE = re.compile(
    r"(скин[ьи]\w*\s+(?:ссылк|линк)|дай\s+(?:ссылк|линк|промо)|кинь\s+(?:ссылк|линк)|"
    r"есть\s+ссылк|ссылку\s+(?:плиз|пожалуйста)?|промо[\s-]?код|промокод|"
    r"куда\s+заход|куда\s+зайти|закинь\s+ссылк)",
    re.IGNORECASE,
)
_PRODUCT_RE = re.compile(r"seo[-\s]?jarvis|seojarvis|джарвис|jarvis10", re.IGNORECASE)
_NAME_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def normalize_person_name(value: str | None) -> str:
    text = _NAME_RE.sub(" ", (value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def peer_identity_keys(
    *,
    username: str | None = None,
    display_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> set[str]:
    keys: set[str] = set()
    handle = (username or "").strip().lstrip("@").lower()
    if handle:
        keys.add(handle)
    for raw in (display_name, " ".join(part for part in (first_name, last_name) if part)):
        name = normalize_person_name(raw)
        if name:
            keys.add(name)
    return keys


def entity_matches_peer_keys(entity: Any, keys: set[str]) -> bool:
    if not keys or entity is None:
        return False
    return bool(
        peer_identity_keys(
            username=getattr(entity, "username", None),
            first_name=getattr(entity, "first_name", None),
            last_name=getattr(entity, "last_name", None),
        )
        & keys
    )


def text_contains_url(text: str | None) -> bool:
    return bool(_URL_RE.search(text or ""))


def incoming_asks_for_link(text: str | None) -> bool:
    return bool(_ASK_LINK_RE.search(text or ""))


def text_contains_product_pitch(text: str | None) -> bool:
    blob = text or ""
    return bool(_PRODUCT_RE.search(blob) or text_contains_url(blob))


def strip_urls(text: str | None) -> str:
    cleaned = _URL_RE.sub(" ", text or "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(" \t,;:-")


def conversation_has_link(texts: Iterable[str | None]) -> bool:
    return any(text_contains_url(item) for item in texts)


def sanitize_dm_text(text: str | None, *, allow_link: bool) -> str:
    raw = (text or "").strip()
    if allow_link:
        return raw
    return strip_urls(raw)


def sanitize_public_text(text: str | None) -> str:
    return strip_urls(text)


def offer_fields(*, url: str | None, promo: str | None, allow_link: bool) -> tuple[str, str]:
    if not allow_link:
        return "", ""
    return (url or "").strip(), (promo or "").strip()


def peer_dialog_text_ok(text: str | None) -> bool:
    blob = (text or "").strip()
    if len(blob) < 2:
        return False
    return not text_contains_product_pitch(blob)
