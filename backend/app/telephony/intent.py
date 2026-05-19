"""Keyword intent detection for telephony MVP (stage 2)."""

from __future__ import annotations

_HANGUP_PHRASES = (
    "до свидания",
    "до свиданья",
    "пока",
    "завершить звонок",
    "положите трубку",
    "можно закончить",
    "на этом всё",
    "на этом все",
)

_OPERATOR_TRANSFER_PHRASES = (
    "соедините с человеком",
    "соедините с оператором",
    "переведите на оператора",
    "нужен оператор",
    "живой человек",
    "позовите оператора",
    "хочу оператора",
)


def _normalized(text: str) -> str:
    return " ".join((text or "").lower().split())


def detect_hangup_intent(text: str) -> bool:
    normalized = _normalized(text)
    if not normalized:
        return False
    return any(phrase in normalized for phrase in _HANGUP_PHRASES)


def detect_operator_transfer_intent(text: str) -> bool:
    normalized = _normalized(text)
    if not normalized:
        return False
    return any(phrase in normalized for phrase in _OPERATOR_TRANSFER_PHRASES)
