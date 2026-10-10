"""Shared delay caps for UBT module settings (seconds)."""
from typing import Any

DELAY_MAX_SECONDS = 90 * 60
JOIN_DELAY_MIN_DEFAULT = 180
JOIN_DELAY_MAX_DEFAULT = 240
JOIN_DELAY_FLOOR = 30


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
    lo = max(JOIN_DELAY_FLOOR, min(DELAY_MAX_SECONDS, lo))
    hi = max(lo, min(DELAY_MAX_SECONDS, hi))
    return lo, hi
