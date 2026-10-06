"""Global UBT work window: hours, weekdays, and in-day idle gaps.

Task modules own their own limits. The farm-wide rules that remain:
  • accounts only work inside the configured Moscow window;
  • during that window the session stays on — no 40–70 min write flashes;
  • one long idle (40–60 min) and five short idles (5–10 min) are placed
    stably per account per Moscow day.
"""
from __future__ import annotations

import contextvars
import hashlib
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

FARM_EARLIEST_START = 7.0
FARM_LATEST_END = 21.5

WORK_MODE_KEY = "work_mode"
DEFAULT_HOUR_START = 8
DEFAULT_HOUR_END = 20
DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]
IDLE_SHORT_COUNT = 5
IDLE_SHORT_MIN_SECONDS = 5 * 60
IDLE_SHORT_MAX_SECONDS = 10 * 60
IDLE_LONG_MIN_SECONDS = 40 * 60
IDLE_LONG_MAX_SECONDS = 60 * 60

_work_mode_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "ubt_work_mode", default=None
)


def _as_int_list(raw: Any) -> list[int]:
    items: list[int] = []
    seen: set[int] = set()
    for value in raw or []:
        try:
            day = int(value)
        except (TypeError, ValueError):
            continue
        if day < 0 or day > 6 or day in seen:
            continue
        seen.add(day)
        items.append(day)
    return items


def normalize_work_mode(raw: Any) -> dict[str, Any]:
    incoming = raw if isinstance(raw, dict) else {}
    try:
        start = int(incoming.get("hour_start") if incoming.get("hour_start") is not None else DEFAULT_HOUR_START)
    except (TypeError, ValueError):
        start = DEFAULT_HOUR_START
    try:
        end = int(incoming.get("hour_end") if incoming.get("hour_end") is not None else DEFAULT_HOUR_END)
    except (TypeError, ValueError):
        end = DEFAULT_HOUR_END
    start = max(0, min(23, start))
    end = max(0, min(24, end))
    if start == end:
        end = (start + 12) % 24
        if end == 0:
            end = 24
    weekdays = _as_int_list(incoming.get("weekdays"))
    if not weekdays:
        weekdays = list(DEFAULT_WEEKDAYS)
    return {"hour_start": start, "hour_end": end, "weekdays": weekdays}


def work_mode_from_automation(automation: Any | None) -> dict[str, Any]:
    blob = getattr(automation, "module_settings", None) or {}
    return normalize_work_mode(blob.get(WORK_MODE_KEY) if isinstance(blob, dict) else None)


def apply_work_mode(automation: Any | None) -> contextvars.Token:
    return _work_mode_ctx.set(work_mode_from_automation(automation))


def reset_work_mode(token: contextvars.Token) -> None:
    _work_mode_ctx.reset(token)


def current_work_mode() -> dict[str, Any]:
    return normalize_work_mode(_work_mode_ctx.get())


def _moscow_tz():
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def moscow_now(now: datetime | None = None) -> datetime:
    tz = _moscow_tz()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(tz)


def _hour_float(local: datetime) -> float:
    return local.hour + local.minute / 60.0 + local.second / 3600.0


def _in_hour_span(hour: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def work_span_hours(mode: dict[str, Any] | None = None) -> tuple[float, float]:
    data = normalize_work_mode(mode or current_work_mode())
    start = float(data["hour_start"])
    end = float(data["hour_end"])
    if end == 0 and start > 0:
        end = 24.0
    if end <= start:
        end = start + 12
        if end > 24:
            end -= 24
    return start, end


def in_configured_work_hours(
    now: datetime | None = None,
    *,
    account_id: int | None = None,
    mode: dict[str, Any] | None = None,
) -> bool:
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    data = normalize_work_mode(mode or current_work_mode())
    local = moscow_now(now)
    if local.weekday() not in data["weekdays"]:
        return False
    start, end = work_span_hours(data)
    if account_id:
        digest = hashlib.sha256(f"wake:{int(account_id)}".encode()).hexdigest()
        stagger = (int(digest[:6], 16) % 900) / 3600.0  # 0–15 min
        start += stagger
    return _in_hour_span(_hour_float(local), start, min(end, 24.0))


def farm_work_overlap(now: datetime | None = None, *, mode: dict[str, Any] | None = None) -> bool:
    data = normalize_work_mode(mode or current_work_mode())
    if moscow_now(now).weekday() not in data["weekdays"]:
        return False
    start, end = work_span_hours(data)
    outer_start = min(FARM_EARLIEST_START, start)
    outer_end = max(FARM_LATEST_END, end if end > start else 24.0)
    return _in_hour_span(_hour_float(moscow_now(now)), outer_start, outer_end)


def _stable_rng(account_id: int, day_key: str) -> random.Random:
    seed = int(hashlib.sha256(f"idle:{int(account_id)}:{day_key}".encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def daily_idle_windows(
    account_id: int,
    *,
    now: datetime | None = None,
    mode: dict[str, Any] | None = None,
) -> list[tuple[float, float]]:
    """Moscow-hour floats for 1 long + 5 short gaps inside the work window."""
    data = normalize_work_mode(mode or current_work_mode())
    local = moscow_now(now)
    start, end = work_span_hours(data)
    if end <= start:
        end = start + 12
    span = (end - start) * 3600.0
    rng = _stable_rng(int(account_id or 0), local.strftime("%Y-%m-%d"))
    long_sec = rng.randint(IDLE_LONG_MIN_SECONDS, IDLE_LONG_MAX_SECONDS)
    shorts = [rng.randint(IDLE_SHORT_MIN_SECONDS, IDLE_SHORT_MAX_SECONDS) for _ in range(IDLE_SHORT_COUNT)]
    blocks = [long_sec, *shorts]
    needed = sum(blocks) + 6 * 60
    if span <= needed:
        scale = max(0.4, (span * 0.55) / max(needed, 1))
        blocks = [max(120, int(item * scale)) for item in blocks]
    remaining = max(0.0, span - sum(blocks))
    cuts = sorted(rng.random() for _ in blocks)
    offsets: list[float] = []
    cursor = 0.0
    for index, length in enumerate(blocks):
        pad = remaining * cuts[index] if remaining else 0.0
        remaining = max(0.0, remaining - pad)
        cursor += pad
        offsets.append(cursor)
        cursor += length
    windows = []
    for offset, length in zip(offsets, blocks):
        lo = start + offset / 3600.0
        hi = lo + length / 3600.0
        windows.append((lo, min(hi, end)))
    windows.sort()
    return windows


def in_daily_idle_gap(
    account_id: int | None,
    *,
    now: datetime | None = None,
    mode: dict[str, Any] | None = None,
) -> bool:
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if not account_id:
        return False
    hour = _hour_float(moscow_now(now))
    for lo, hi in daily_idle_windows(int(account_id), now=now, mode=mode):
        if lo <= hour < hi:
            return True
    return False


def seconds_until_idle_or_end(
    account_id: int | None,
    *,
    now: datetime | None = None,
    mode: dict[str, Any] | None = None,
) -> float:
    """How long the session may stay connected before the next planned idle or closing hour."""
    data = normalize_work_mode(mode or current_work_mode())
    local = moscow_now(now)
    hour = _hour_float(local)
    _start, end = work_span_hours(data)
    until_end = max(60.0, (end - hour) * 3600.0) if hour < end else 60.0
    nearest = until_end
    for lo, _hi in daily_idle_windows(int(account_id or 0), now=now, mode=data):
        if lo > hour:
            nearest = min(nearest, (lo - hour) * 3600.0)
    return max(90.0, nearest)


def persist_work_mode(automation: Any, payload: dict[str, Any]) -> dict[str, Any]:
    blob = dict(getattr(automation, "module_settings", None) or {})
    mode = normalize_work_mode(
        {
            "hour_start": payload.get("work_hour_start", payload.get("hour_start")),
            "hour_end": payload.get("work_hour_end", payload.get("hour_end")),
            "weekdays": payload.get("work_weekdays", payload.get("weekdays")),
        }
    )
    blob[WORK_MODE_KEY] = mode
    automation.module_settings = blob
    return mode
