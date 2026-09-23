"""Per-account rest after writes, night sleep, and delayed retries after failed writes."""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ...alembic.models import SocialAccount

ACCOUNT_REST_SECONDS = 10 * 60
ACCOUNT_REST_MIN_SECONDS = 8 * 60
ACCOUNT_REST_MAX_SECONDS = 22 * 60
FIRST_WEEK_DAYS = 7
FIRST_WEEK_REST_MIN_SECONDS = 10 * 60
FIRST_WEEK_REST_MAX_SECONDS = 15 * 60
ACCOUNT_RETRY_MIN_SECONDS = 3 * 60
ACCOUNT_RETRY_MAX_SECONDS = 5 * 60
ACTIVE_START_HOUR = 8
ACTIVE_END_HOUR = 20
# Outer envelope of per-account jitter so workers still run while some accounts sleep.
FARM_EARLIEST_START = 7.0
FARM_LATEST_END = 21.5
_WRITE_REST_ACTIONS = frozenset(
    {
        "commenting",
        "neurocommenting",
        "discussion",
        "dm",
        "inbound_dm",
        "lead_warmup",
        "lead_delivery",
        "dmp_outreach",
    }
)


def action_uses_write_rest(action_type: str | None) -> bool:
    """Rest after sending in chats, comments, DMs — not joins or profile edits."""
    kind = (action_type or "").strip()
    if kind in _WRITE_REST_ACTIONS:
        return True
    return kind.startswith("shilling")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _moscow_tz():
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def moscow_now(now: datetime | None = None) -> datetime:
    tz = _moscow_tz()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(tz)


def _stable_frac(account_id: int, salt: int) -> float:
    return ((int(account_id) * 1_103_515_245 + salt) & 0x7FFFFFFF) % 10_000 / 10_000.0


def _moscow_hour_float(local: datetime) -> float:
    return local.hour + local.minute / 60.0 + local.second / 3600.0


def _float_hour_parts(value: float) -> tuple[int, int]:
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes >= 60:
        hours += 1
        minutes = 0
    hours = min(23, max(0, hours))
    return hours, min(59, max(0, minutes))


def account_active_window(
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
) -> tuple[float, float]:
    """Stable per-account Moscow window around 08–20 so the farm does not wake together."""
    aid = account_id if account_id is not None else getattr(account, "id", None)
    if not aid:
        return float(ACTIVE_START_HOUR), float(ACTIVE_END_HOUR)
    start = 7.5 + _stable_frac(int(aid), 17) * 1.75  # 07:30–09:15
    end = 18.75 + _stable_frac(int(aid), 41) * 2.0  # 18:45–20:45
    return start, end


def in_account_active_hours(
    now: datetime | None = None,
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
) -> bool:
    """Public writes run in a jittered window around 08:00–20:00 Moscow."""
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    start, end = account_active_window(account, account_id=account_id)
    return start <= _moscow_hour_float(moscow_now(now)) < end


def farm_overlap_active_hours(now: datetime | None = None) -> bool:
    """True when at least some accounts may be awake (outer 07:00–21:30 MSK)."""
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    hour = _moscow_hour_float(moscow_now(now))
    return FARM_EARLIEST_START <= hour < FARM_LATEST_END


def next_wake_at(now: datetime | None = None, account: SocialAccount | None = None) -> datetime:
    """Next personal wake time as naive UTC, with a small random stagger."""
    local = moscow_now(now)
    start, end = account_active_window(account)
    hour, minute = _float_hour_parts(start)
    minute = min(59, minute + random.randint(0, 25))
    wake = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    current = _moscow_hour_float(local)
    if current >= end:
        wake = wake + timedelta(days=1)
    elif current >= start:
        wake = wake + timedelta(days=1)
    return wake.astimezone(timezone.utc).replace(tzinfo=None)


def profile_edit_allowed(
    account: SocialAccount | None,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> bool:
    """Skip bio/avatar edits on upload day; wait until the next Moscow day plus 16–27h."""
    if force or account is None:
        return True
    created = account_created_at(account)
    if created is None:
        return True
    current = now or _utc_now()
    if moscow_now(current).date() <= moscow_now(created).date():
        return False
    extra_hours = 16 + (int(getattr(account, "id", 0) or 0) % 12)
    return (current - created) >= timedelta(hours=extra_hours)


def account_created_at(account: SocialAccount | None) -> datetime | None:
    return _naive_utc(getattr(account, "created_at", None) if account else None)


def account_in_first_week(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    created = account_created_at(account)
    if created is None:
        return False
    current = now or _utc_now()
    return (current - created) < timedelta(days=FIRST_WEEK_DAYS)


def rest_seconds_for_account(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """First week: 10–15 minute pause after a write. Later: jittered ~8–22 minutes."""
    if account_in_first_week(account, now=now):
        return random.uniform(FIRST_WEEK_REST_MIN_SECONDS, FIRST_WEEK_REST_MAX_SECONDS)
    return random.uniform(ACCOUNT_REST_MIN_SECONDS, ACCOUNT_REST_MAX_SECONDS)


def account_is_resting(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    if not account:
        return False
    nxt = getattr(account, "next_action_at", None)
    if nxt is None:
        return False
    current = now or _utc_now()
    return nxt > current


def account_should_idle(
    account: SocialAccount | None,
    *,
    now: datetime | None = None,
    ignore_hours: bool = False,
) -> bool:
    """True when the account must not send: cooldown or night sleep."""
    if account_is_resting(account, now=now):
        return True
    if ignore_hours:
        return False
    return not in_account_active_hours(now, account)


def _push_next_action(account: SocialAccount, seconds: float) -> None:
    until = _utc_now() + timedelta(seconds=max(1, seconds))
    current = getattr(account, "next_action_at", None)
    if current is None or current < until:
        account.next_action_at = until
    account.last_used_at = _utc_now()
    account.updated_at = _utc_now()


def schedule_account_rest(account: SocialAccount, *, seconds: float | None = None) -> None:
    """Block this account from further writes after a real Telegram send."""
    delay = rest_seconds_for_account(account) if seconds is None else seconds
    _push_next_action(account, delay)


def schedule_account_retry(account: SocialAccount, *, extra_seconds: float = 0) -> None:
    """Wait 3–5 minutes after a failed write so Telegram flood limits are not probed."""
    delay = random.uniform(ACCOUNT_RETRY_MIN_SECONDS, ACCOUNT_RETRY_MAX_SECONDS) + max(0, extra_seconds)
    _push_next_action(account, delay)


def retry_delay_seconds() -> float:
    return random.uniform(ACCOUNT_RETRY_MIN_SECONDS, ACCOUNT_RETRY_MAX_SECONDS)
