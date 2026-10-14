"""Shared delay caps for UBT module settings (seconds)."""
from typing import Any

DELAY_MAX_SECONDS = 90 * 60
# Anti-bot pause after a post/message. 90 minutes was leaking from the join cap
# and produced hour-long "антибот-пауза" holds.
ACTION_DELAY_MAX_SECONDS = 15 * 60
JOIN_DELAY_MIN_DEFAULT = 20 * 60
JOIN_DELAY_MAX_DEFAULT = 40 * 60
JOIN_DELAY_FLOOR = 30
COMMENT_GAP_MIN_DEFAULT = 20 * 60
COMMENT_GAP_MAX_DEFAULT = 40 * 60
_OLD_JOIN_PRESET_SECONDS = {60, 120, 180, 240, 300, 520}


def format_delay_ru(seconds: float | int) -> str:
    total = max(0, int(round(float(seconds))))
    if total < 60:
        return f"{total} с"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} мин {secs} с" if secs else f"{minutes} мин"
    hours, minutes = divmod(minutes, 60)
    if minutes:
        return f"{hours} ч {minutes} мин"
    return f"{hours} ч"


def clamp_action_delay_pair(incoming: Any, *, default_min: int, default_max: int) -> tuple[int, int]:
    data = incoming if isinstance(incoming, dict) else {}
    try:
        lo = int(data["delay_before_min"]) if data.get("delay_before_min") is not None else int(default_min)
    except (TypeError, ValueError):
        lo = int(default_min)
    try:
        hi = int(data["delay_before_max"]) if data.get("delay_before_max") is not None else int(default_max)
    except (TypeError, ValueError):
        hi = int(default_max)
    lo = max(0, min(ACTION_DELAY_MAX_SECONDS, lo))
    hi = max(lo, min(ACTION_DELAY_MAX_SECONDS, hi))
    return lo, hi


def clamp_join_delay_pair(incoming: Any) -> tuple[int, int]:
    """Independent pause between chat joins. Never reuse comment/reply delays."""
    data = incoming if isinstance(incoming, dict) else {}
    try:
        lo = int(data["join_delay_min"]) if data.get("join_delay_min") is not None else JOIN_DELAY_MIN_DEFAULT
    except (TypeError, ValueError):
        lo = JOIN_DELAY_MIN_DEFAULT
    try:
        hi = int(data["join_delay_max"]) if data.get("join_delay_max") is not None else JOIN_DELAY_MAX_DEFAULT
    except (TypeError, ValueError):
        hi = JOIN_DELAY_MAX_DEFAULT
    if lo in _OLD_JOIN_PRESET_SECONDS and hi in _OLD_JOIN_PRESET_SECONDS:
        lo, hi = JOIN_DELAY_MIN_DEFAULT, JOIN_DELAY_MAX_DEFAULT
    lo = max(JOIN_DELAY_FLOOR, min(DELAY_MAX_SECONDS, lo))
    hi = max(lo, min(DELAY_MAX_SECONDS, hi))
    return lo, hi


def clamp_comment_gap_pair(incoming: Any) -> tuple[int, int]:
    """Pause between two comments from the same account."""
    data = incoming if isinstance(incoming, dict) else {}
    try:
        lo = int(data["comment_delay_min"]) if data.get("comment_delay_min") is not None else COMMENT_GAP_MIN_DEFAULT
    except (TypeError, ValueError):
        lo = COMMENT_GAP_MIN_DEFAULT
    try:
        hi = int(data["comment_delay_max"]) if data.get("comment_delay_max") is not None else COMMENT_GAP_MAX_DEFAULT
    except (TypeError, ValueError):
        hi = COMMENT_GAP_MAX_DEFAULT
    lo = max(60, min(DELAY_MAX_SECONDS, lo))
    hi = max(lo, min(DELAY_MAX_SECONDS, hi))
    return lo, hi
