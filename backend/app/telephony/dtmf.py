"""DTMF digit → synthetic user transcript (stage 6 fallback)."""

from __future__ import annotations

from ..prompts.system_prompts import DTMF_MENU_PROMPT as _DTMF_MENU_PROMPT

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
