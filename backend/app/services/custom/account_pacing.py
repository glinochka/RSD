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
FIRST_WEEK_REST_MIN_SECONDS = 60 * 60
FIRST_WEEK_REST_MAX_SECONDS = 2 * 60 * 60
ACCOUNT_RETRY_MIN_SECONDS = 3 * 60
ACCOUNT_RETRY_MAX_SECONDS = 5 * 60
ACTIVE_START_HOUR = 8
ACTIVE_END_HOUR = 20
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
        "account_warmup",
        "peer_dialog",
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


def in_account_active_hours(now: datetime | None = None) -> bool:
    """Public writes run 08:00–20:00 Moscow; accounts sleep the rest of the day."""
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    hour = moscow_now(now).hour
    return ACTIVE_START_HOUR <= hour < ACTIVE_END_HOUR


def next_wake_at(now: datetime | None = None) -> datetime:
    """Next 08:00–08:40 Moscow as naive UTC, with a small random stagger."""
    local = moscow_now(now)
    wake = local.replace(hour=ACTIVE_START_HOUR, minute=random.randint(0, 40), second=0, microsecond=0)
    if local.hour >= ACTIVE_END_HOUR:
        wake = wake + timedelta(days=1)
    elif local.hour < ACTIVE_START_HOUR:
        pass
    else:
        wake = wake + timedelta(days=1)
    return wake.astimezone(timezone.utc).replace(tzinfo=None)


def account_created_at(account: SocialAccount | None) -> datetime | None:
    return _naive_utc(getattr(account, "created_at", None) if account else None)


def account_in_first_week(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    created = account_created_at(account)
    if created is None:
        return False
    current = now or _utc_now()
    return (current - created) < timedelta(days=FIRST_WEEK_DAYS)


def rest_seconds_for_account(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """First week: 1–2 hour pause after a write. Later: jittered ~8–22 minutes."""
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
    return not in_account_active_hours(now)


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
