"""Detect user consent before executing high-risk tool actions."""

from __future__ import annotations

import re
from typing import Any

_EXPLICIT_CONFIRM_MARKERS = (
    "подтверждаю",
    "подтвердить",
    "подтверждено",
    "confirm",
    "confirmed",
    "ок, выполняй",
    "выполняй",
)

_AFFIRMATIVE_WORDS = frozenset(
    {
        "да",
        "ага",
        "угу",
        "верно",
        "правильно",
        "точно",
        "согласен",
        "согласна",
        "подходит",
        "ок",
        "окей",
        "okay",
        "yes",
        "yep",
        "давайте",
        "давай",
        "записывайте",
        "запишите",
        "бронируй",
        "бронируйте",
        "оформляйте",
        "подтверждаю",
    }
)

_AFFIRMATIVE_PHRASES = (
    "все верно",
    "всё верно",
    "да все",
    "да, все",
    "именно так",
    "все правильно",
    "всё правильно",
    "без проблем",
    "так и есть",
)

_CONFIRMATION_QUESTION_MARKERS = (
    "верно?",
    "правильно?",
    "подтверд",
    "подходит?",
    "согласн",
    "записать",
    "забронир",
    "оформить",
    "всё так",
    "все так",
    "подтвержда",
    "уточн",
    "как вам",
    "устраивает",
)

TOOL_CONFIRMATION_REQUIRED_HINT = (
    "Сначала согласуйте с клиентом детали и получите его согласие в свободной форме "
    "(например: «Записать вас на завтра в 15:00 — верно?»). "
    "Когда клиент подтвердит — повторите вызов инструмента с теми же параметрами."
)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _last_assistant_message(recent_history: list[dict[str, Any]] | None) -> str:
    if not recent_history:
        return ""
    for item in reversed(recent_history):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role in {"assistant", "agent"}:
            return str(item.get("content") or "").strip()
    return ""


def _assistant_asked_confirmation(assistant_text: str) -> bool:
    text = _normalize(assistant_text)
    if not text:
        return False
    return any(marker in text for marker in _CONFIRMATION_QUESTION_MARKERS)


def _is_explicit_confirmation(user_message: str) -> bool:
    text = _normalize(user_message)
    if not text:
        return False
    return any(marker in text for marker in _EXPLICIT_CONFIRM_MARKERS)


def _is_natural_affirmative(user_message: str) -> bool:
    text = _normalize(user_message)
    if not text:
        return False
    cleaned = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    words = [w for w in cleaned.split() if w]
    if not words or len(words) > 8:
        return False
    if any(word in _AFFIRMATIVE_WORDS for word in words):
        return True
    joined = " ".join(words)
    return any(phrase in joined for phrase in _AFFIRMATIVE_PHRASES)


def user_has_confirmed_action(
    user_message: str,
    *,
    recent_history: list[dict[str, Any]] | None = None,
) -> bool:
    if _is_explicit_confirmation(user_message):
        return True
    if not _is_natural_affirmative(user_message):
        return False
    return _assistant_asked_confirmation(_last_assistant_message(recent_history))
