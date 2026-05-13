"""Agent working hours (stored in template_config.agent_availability)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

DEFAULT_OUTSIDE_MESSAGE = (
    "Сейчас вне рабочего времени ассистента. Пожалуйста, напишите в рабочие часы — мы обязательно ответим."
)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_TZ_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*/?[A-Za-z0-9_+\-]*$")

_DEFAULT_WEEKDAY = {"enabled": True, "start": "09:00", "end": "18:00"}
_DEFAULT_OFF_DAY = {"enabled": False, "start": "09:00", "end": "18:00"}


def _hhmm_to_minutes(value: str) -> int:
    parts = value.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minute_within_period(local_minute: int, start: int, end: int) -> bool:
    """Inclusive window; supports overnight windows when start > end."""
    if start <= end:
        return start <= local_minute <= end
    return local_minute >= start or local_minute <= end


def normalize_agent_availability_for_storage(raw_block: object | None) -> dict[str, Any]:
    """
    Validate and normalize agent_availability for JSON storage.
    Default when omitted upstream: caller should not persist; runtime treats missing as 24/7.
    """
    if raw_block is None:
        return {
            "always_on": True,
            "timezone": "Europe/Moscow",
            "outside_message": DEFAULT_OUTSIDE_MESSAGE,
        }
    if not isinstance(raw_block, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_availability must be an object",
        )

    always_on = bool(raw_block.get("always_on", True))
    tz_name = str(raw_block.get("timezone") or "Europe/Moscow").strip()
    if not tz_name or not _TZ_RE.fullmatch(tz_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_availability.timezone must be a valid IANA timezone name",
        )

    msg = str(raw_block.get("outside_message") or DEFAULT_OUTSIDE_MESSAGE).strip() or DEFAULT_OUTSIDE_MESSAGE
    if len(msg) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_availability.outside_message is too long (max 500)",
        )

    if always_on:
        return {"always_on": True, "timezone": tz_name, "outside_message": msg}

    weekdays_raw = raw_block.get("weekdays")
    if not isinstance(weekdays_raw, list) or len(weekdays_raw) != 7:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_availability.weekdays must be an array of 7 entries (Mon–Sun)",
        )

    weekdays: list[dict[str, Any]] = []
    for idx, day in enumerate(weekdays_raw):
        if not isinstance(day, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"agent_availability.weekdays[{idx}] must be an object",
            )
        enabled = bool(day.get("enabled", False))
        start = str(day.get("start") or "09:00").strip()
        end = str(day.get("end") or "18:00").strip()
        if not _TIME_RE.fullmatch(start) or not _TIME_RE.fullmatch(end):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"agent_availability.weekdays[{idx}] start/end must be HH:MM",
            )
        start_m = _hhmm_to_minutes(start)
        end_m = _hhmm_to_minutes(end)
        if start_m == end_m:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"agent_availability.weekdays[{idx}] start and end must differ",
            )
        weekdays.append({"enabled": enabled, "start": start, "end": end})

    if not any(d["enabled"] for d in weekdays):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="agent_availability: enable at least one weekday or turn on 24/7 mode",
        )

    return {
        "always_on": False,
        "timezone": tz_name,
        "outside_message": msg,
        "weekdays": weekdays,
    }


def get_agent_availability(template_config: dict | None) -> dict[str, Any]:
    raw = (template_config or {}).get("agent_availability")
    if not isinstance(raw, dict):
        return {"always_on": True}
    out: dict[str, Any] = {"always_on": bool(raw.get("always_on", True))}
    if "timezone" in raw:
        out["timezone"] = str(raw.get("timezone") or "Europe/Moscow")
    if "outside_message" in raw:
        out["outside_message"] = str(raw.get("outside_message") or DEFAULT_OUTSIDE_MESSAGE)
    if "weekdays" in raw and isinstance(raw.get("weekdays"), list):
        out["weekdays"] = raw.get("weekdays")
    return out


def outside_hours_message(template_config: dict | None) -> str:
    raw = (template_config or {}).get("agent_availability")
    if isinstance(raw, dict):
        msg = str(raw.get("outside_message") or "").strip()
        if msg:
            return msg
    return DEFAULT_OUTSIDE_MESSAGE


def agent_availability_allows_now(template_config: dict | None, *, now: datetime | None = None) -> bool:
    """True if the agent should accept LLM processing now (24/7 or inside weekly window)."""
    block = get_agent_availability(template_config)
    if block.get("always_on", True):
        return True

    weekdays = block.get("weekdays")
    if not isinstance(weekdays, list) or len(weekdays) != 7:
        return True

    tz_name = str(block.get("timezone") or "Europe/Moscow").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        logger.warning("agent_availability: invalid timezone %s, allowing messages", tz_name)
        return True

    utc_now = now if now is not None else datetime.now(timezone.utc)
    if utc_now.tzinfo is None:
        utc_now = utc_now.replace(tzinfo=timezone.utc)
    local = utc_now.astimezone(tz)
    weekday = int(local.weekday())
    if weekday < 0 or weekday > 6:
        return True

    spec = weekdays[weekday]
    if not isinstance(spec, dict) or not spec.get("enabled"):
        return False

    start_s = str(spec.get("start") or "09:00").strip()
    end_s = str(spec.get("end") or "18:00").strip()
    if not _TIME_RE.fullmatch(start_s) or not _TIME_RE.fullmatch(end_s):
        return True

    local_minute = local.hour * 60 + local.minute
    return _minute_within_period(local_minute, _hhmm_to_minutes(start_s), _hhmm_to_minutes(end_s))


def default_weekdays_for_ui() -> list[dict[str, Any]]:
    """Mon–Sun: Mon–Fri working 9–18, weekend off (UI default when enabling schedule)."""
    days = []
    for i in range(7):
        base = dict(_DEFAULT_WEEKDAY) if i < 5 else dict(_DEFAULT_OFF_DAY)
        days.append(base)
    return days
