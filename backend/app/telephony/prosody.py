"""TTS prosody helpers for phone channel (stage 6)."""

from __future__ import annotations

import re

_TIME_COLON = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_PHONE_DIGITS = re.compile(r"\b(\+?\d[\d\s\-()]{8,}\d)\b")
_DATE_DOT = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b")

_ONES = (
    "ноль",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
)
_TENS = ("", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто")


def _digit_word(n: int) -> str:
    if 0 <= n < len(_ONES):
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        if ones == 0:
            return _TENS[tens]
        return f"{_TENS[tens]} {_ONES[ones]}"
    return str(n)


def _time_to_words(hour: int, minute: int) -> str:
    h = _digit_word(hour)
    if minute == 0:
        return f"{h} ноль-ноль"
    if minute < 10:
        return f"{h} ноль {_digit_word(minute)}"
    return f"{h} {_digit_word(minute)}"


def _format_time_match(match: re.Match[str]) -> str:
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return match.group(0)
    return _time_to_words(hour, minute)


def _format_phone_match(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(1))
    if len(digits) < 10:
        return match.group(0)
    spoken_digits = [_digit_word(int(d)) for d in digits]
    return " ".join(spoken_digits)


def format_spoken_numbers(text: str) -> str:
    """Expand times and digit sequences for natural TTS (Russian)."""
    raw = (text or "").strip()
    if not raw:
        return raw
    out = _TIME_COLON.sub(_format_time_match, raw)
    out = _PHONE_DIGITS.sub(_format_phone_match, out)
    return out


def wrap_ssml_prosody(text: str, *, voice_tone: str = "neutral-friendly") -> str:
    """Wrap plain text in minimal SSML for pauses and calm delivery."""
    body = format_spoken_numbers(text)
    if not body:
        return body
    if body.strip().startswith("<speak"):
        return body
    rate = "medium"
    if voice_tone == "neutral-friendly":
        rate = "95%"
    return (
        f'<speak><prosody rate="{rate}" pitch="medium">'
        f"{body}</prosody></speak>"
    )
