"""DTMF digit → synthetic user transcript (stage 6 fallback)."""

from __future__ import annotations

_DTMF_MENU_PROMPT = (
    "Не расслышал. Нажмите 1 — запись на приём, 2 — оператор, или скажите запрос голосом."
)

_DTMF_MAP: dict[str, str] = {
    "1": "Хочу записаться на приём",
    "2": "Соедините с оператором",
    "0": "Соедините с оператором",
}


def dtmf_transcript(digit: str) -> str | None:
    d = str(digit or "").strip()
    if not d:
        return None
    return _DTMF_MAP.get(d)


def dtmf_menu_prompt() -> str:
    return _DTMF_MENU_PROMPT
