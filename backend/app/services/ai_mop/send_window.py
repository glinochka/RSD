"""Окно работы ИИ МОП: 08:00–20:00 по Москве (провижининг, email, мессенджеры)."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_MSK = ZoneInfo("Europe/Moscow")
_WINDOW_START_MINUTE = 8 * 60
_WINDOW_END_MINUTE = 20 * 60


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _local_moscow_minute(*, now: datetime) -> int:
    aware = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    local = aware.astimezone(_MSK)
    return local.hour * 60 + local.minute


def ai_mop_first_message_allowed_now(*, now: datetime | None = None) -> bool:
    """True, если сейчас можно отправлять первое исходящее сообщение ИИ МОП."""
    current = now if now is not None else _utc_now()
    minute = _local_moscow_minute(now=current)
    return _WINDOW_START_MINUTE <= minute <= _WINDOW_END_MINUTE


def next_ai_mop_first_message_at(*, now: datetime | None = None) -> datetime:
    """UTC-naive момент ближайшего начала окна 08:00 МСК."""
    current = now if now is not None else _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(_MSK)
    minute = local.hour * 60 + local.minute

    if _WINDOW_START_MINUTE <= minute <= _WINDOW_END_MINUTE:
        return _to_utc_naive(current)

    if minute < _WINDOW_START_MINUTE:
        candidate = datetime.combine(local.date(), time(8, 0), tzinfo=_MSK)
    else:
        candidate = datetime.combine(local.date() + timedelta(days=1), time(8, 0), tzinfo=_MSK)
    return _to_utc_naive(candidate)
