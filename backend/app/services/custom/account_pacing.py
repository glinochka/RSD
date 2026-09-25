"""Per-account rest after writes, night sleep, offline-break windows, and delayed retries.

Three independent timers:
  • OFFLINE windows  – 3 stable 50-60 min breaks during the day when the account
                         is completely inactive (no target, no humanization).
  • TARGET rest      – next_action_at: 40-70 min after neurocommenting,
                       shilling, discussion, DM.
  • HUMANIZATION rest – next_humanization_at: 15-30 min after warmup,
                        peer_dialog, idle-browse, reactions.

TARGET and HUMANIZATION never block each other.  OFFLINE windows block both.

Daily max for target actions is also randomized per account per Moscow day
(50-100 % of the automation setting) so the same account does not send the
exact same number of messages every day.

IMPORTANT – IP/session safety rule (do NOT remove this comment):
  A Telethon .session file is bound to the IP address that was used during
  initial auth.  If the same session is used from a DIFFERENT IP address
  (e.g. you swap the proxy, change the VPN exit node, or log in from
  another server), Telegram revokes it with AuthKeyDuplicatedError.
  Always keep one session ↔ one proxy mapping and never reuse a session across
  different proxy IPs.
"""
from __future__ import annotations

import hashlib
import os
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ...alembic.models import CustomAutomation, SocialAccount

# ---------------------------------------------------------------------------
# Target-action rest  (neurocommenting / shilling / discussion / DM)
# ---------------------------------------------------------------------------
TARGET_REST_MIN_SECONDS = 40 * 60   # 40 min
TARGET_REST_MAX_SECONDS = 70 * 60   # 70 min

FIRST_WEEK_DAYS = 7

# ---------------------------------------------------------------------------
# Humanization rest  (warmup DMs, peer dialog, idle browse, reactions)
# ---------------------------------------------------------------------------
HUMANIZATION_REST_MIN_SECONDS = 15 * 60    # 15 min
HUMANIZATION_REST_MAX_SECONDS = 30 * 60    # 30 min

# ---------------------------------------------------------------------------
# Shared: retry after failed write
# ---------------------------------------------------------------------------
ACCOUNT_RETRY_MIN_SECONDS = 3 * 60
ACCOUNT_RETRY_MAX_SECONDS = 5 * 60

# ---------------------------------------------------------------------------
# Active-hours window (Moscow)
# ---------------------------------------------------------------------------
ACTIVE_START_HOUR = 8
ACTIVE_END_HOUR = 20
FARM_EARLIEST_START = 7.0
FARM_LATEST_END = 21.5

# ---------------------------------------------------------------------------
# Offline-break windows: three 50-60 min breaks during the active day.
# ---------------------------------------------------------------------------
OFFLINE_BREAK_BASE_HOURS = (10.0, 13.0, 16.0)  # morning, lunch, afternoon
OFFLINE_BREAK_MIN_MINUTES = 50
OFFLINE_BREAK_MAX_MINUTES = 60

# Target-action rest days (Monday=0): Saturday and Sunday, Moscow.
TARGET_REST_WEEKDAYS = {5, 6}


# ---------------------------------------------------------------------------
# Action classification
# ---------------------------------------------------------------------------
_TARGET_ACTIONS = frozenset(
    {
        "commenting",
        "neurocommenting",
        "discussion",
        "dm",
        "inbound_dm",
        "lead_delivery",
        "dmp_outreach",
    }
)

_HUMANIZATION_ACTIONS = frozenset(
    {
        "account_warmup",
        "peer_dialog",      # inter-account messaging for humanization
        "idle_browse",
        "reaction",
    }
)

# Legacy alias – kept for callers that still reference action_uses_write_rest
_WRITE_REST_ACTIONS = _TARGET_ACTIONS | frozenset({"lead_warmup"})


def action_uses_target_rest(action_type: str | None) -> bool:
    """True for actions that consume the 40-70 min TARGET rest slot."""
    kind = (action_type or "").strip()
    if kind in _TARGET_ACTIONS:
        return True
    return kind.startswith("shilling")


def action_uses_humanization_rest(action_type: str | None) -> bool:
    """True for warmup, idle-browse, reactions – uses the 15-30 min HUMANIZATION slot."""
    return (action_type or "").strip() in _HUMANIZATION_ACTIONS


def action_uses_write_rest(action_type: str | None) -> bool:
    """Backward-compat alias: any action that triggers some rest."""
    return action_uses_target_rest(action_type) or action_uses_humanization_rest(action_type) or (
        (action_type or "").strip() == "lead_warmup"
    )


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

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


def moscow_today_date(now: datetime | None = None) -> datetime:
    return moscow_now(now)


def _stable_frac(account_id: int, salt: int) -> float:
    return ((int(account_id) * 1_103_515_245 + salt) & 0x7FFFFFFF) % 10_000 / 10_000.0


def _daily_stable_frac(account_id: int, salt: int, now: datetime | None = None) -> float:
    """Stable per day, so values change each Moscow day but stay constant for one day."""
    today = moscow_now(now).strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{account_id}:{salt}:{today}".encode()).hexdigest()
    return int(digest[:8], 16) / (2**32)


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


# ---------------------------------------------------------------------------
# Per-account active window
# ---------------------------------------------------------------------------

def account_active_window(
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
) -> tuple[float, float]:
    """Stable per-account Moscow window so the farm does not wake together."""
    aid = account_id if account_id is not None else getattr(account, "id", None)
    if not aid:
        return float(ACTIVE_START_HOUR), float(ACTIVE_END_HOUR)
    start = 7.5 + _stable_frac(int(aid), 17) * 1.75   # 07:30–09:15
    end = 18.75 + _stable_frac(int(aid), 41) * 2.0    # 18:45–20:45
    return start, end


# ---------------------------------------------------------------------------
# Offline-break windows: 3 per day, 50-60 min each, stable per account.
# ---------------------------------------------------------------------------

def account_offline_breaks(
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
    now: datetime | None = None,
) -> list[tuple[float, float]]:
    """Return three (start_hour, end_hour) breaks for today."""
    aid = account_id if account_id is not None else getattr(account, "id", None)
    if not aid:
        return []
    breaks = []
    for idx, base in enumerate(OFFLINE_BREAK_BASE_HOURS):
        # start within ±60 min around the base hour
        start_offset = _daily_stable_frac(int(aid), 100 + idx, now) * 60.0  # 0-60 min
        start = base + (start_offset / 60.0) - 0.5  # ±30 min around base
        duration = OFFLINE_BREAK_MIN_MINUTES + _daily_stable_frac(int(aid), 200 + idx, now) * (
            OFFLINE_BREAK_MAX_MINUTES - OFFLINE_BREAK_MIN_MINUTES
        )
        end = start + duration / 60.0
        breaks.append((start, end))
    return breaks


def account_in_offline_break(
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
    now: datetime | None = None,
) -> bool:
    """True during one of the three daily offline-break windows."""
    hour = _moscow_hour_float(moscow_now(now))
    for start, end in account_offline_breaks(account, account_id=account_id, now=now):
        if start <= hour < end:
            return True
    return False


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


def account_in_target_rest_day(
    account: SocialAccount | None = None,
    *,
    now: datetime | None = None,
) -> bool:
    """True on Saturday and Sunday in Moscow — no comments/shills/DMs."""
    del account
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return moscow_now(now).weekday() in TARGET_REST_WEEKDAYS


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


def next_target_wake_at(now: datetime | None = None, account: SocialAccount | None = None) -> datetime:
    """Next time the account may send a TARGET action, skipping Sat/Sun."""
    local = moscow_now(now)
    start, _end = account_active_window(account)
    hour, minute = _float_hour_parts(start)
    minute = min(59, minute + random.randint(0, 20))
    wake = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    current = _moscow_hour_float(local)
    if account_in_target_rest_day(account, now=now) or current >= start:
        wake = wake + timedelta(days=1)
    while wake.weekday() in TARGET_REST_WEEKDAYS:
        wake = wake + timedelta(days=1)
    return wake.astimezone(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Profile edit guard
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Daily target max: randomized per account per day
# ---------------------------------------------------------------------------

def effective_daily_target_max(
    account: SocialAccount | None,
    automation: CustomAutomation | None,
    *,
    now: datetime | None = None,
) -> int:
    """Return a stable randomized daily target limit for this account today.

    Uses 50-100 % of the automation's max_daily_messages_per_account (min 5).
    The value stays constant for one Moscow day and changes the next day so
    the account never sends the exact same count repeatedly.
    """
    if account is None or automation is None:
        return 0
    raw = int(getattr(automation, "max_daily_messages_per_account", None) or 0)
    if raw <= 0:
        return 0
    if raw <= 2:
        return raw
    aid = int(getattr(account, "id", 0) or 0)
    frac = _daily_stable_frac(aid, 300, now)
    lo = max(5, int(raw * 0.5))
    hi = max(lo, raw)
    return lo + int(frac * (hi - lo))


# ---------------------------------------------------------------------------
# TARGET rest helpers  (next_action_at  – 40-70 min)
# ---------------------------------------------------------------------------

def target_rest_seconds_for_account(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """40–70 min rest for any neurocommenting / shilling / DM action."""
    return random.uniform(TARGET_REST_MIN_SECONDS, TARGET_REST_MAX_SECONDS)


def account_is_resting(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    """True when the TARGET cooldown (next_action_at) is still active."""
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
    """True when the account must not send a TARGET action."""
    if account_in_target_rest_day(account, now=now):
        return True
    if account_in_offline_break(account, now=now):
        return True
    if account_is_resting(account, now=now):
        return True
    if ignore_hours:
        return False
    return not in_account_active_hours(now, account)


def account_membership_should_idle(
    account: SocialAccount | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Join/leave hygiene: respect night and offline windows, not weekend or write rest."""
    if account_in_offline_break(account, now=now):
        return True
    return not in_account_active_hours(now, account)


def schedule_account_target_rest(account: SocialAccount, *, seconds: float | None = None) -> None:
    """Block this account from further TARGET writes for 40–70 minutes."""
    delay = target_rest_seconds_for_account(account) if seconds is None else seconds
    _push_next_target_action(account, delay)


def schedule_account_rest(account: SocialAccount, *, seconds: float | None = None, action_type: str | None = None) -> None:
    """Route to the correct rest queue based on action_type."""
    if action_uses_humanization_rest(action_type) or (action_type or "").strip() == "account_warmup":
        schedule_account_humanization_rest(account, seconds=seconds)
    else:
        schedule_account_target_rest(account, seconds=seconds)


# ---------------------------------------------------------------------------
# HUMANIZATION rest helpers  (next_humanization_at  – 15-30 min)
# ---------------------------------------------------------------------------

def humanization_rest_seconds() -> float:
    """15–30 min rest after a warmup DM, idle-browse or reaction."""
    return random.uniform(HUMANIZATION_REST_MIN_SECONDS, HUMANIZATION_REST_MAX_SECONDS)


def account_humanization_is_resting(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    """True when the HUMANIZATION cooldown (next_humanization_at) is still active."""
    if not account:
        return False
    nxt = getattr(account, "next_humanization_at", None)
    if nxt is None:
        return False
    current = now or _utc_now()
    return nxt > current


def account_humanization_should_idle(
    account: SocialAccount | None,
    *,
    now: datetime | None = None,
    ignore_hours: bool = False,
) -> bool:
    """True when the account should not send a HUMANIZATION action."""
    if account_in_offline_break(account, now=now):
        return True
    if account_humanization_is_resting(account, now=now):
        return True
    if ignore_hours:
        return False
    return not in_account_active_hours(now, account)


def schedule_account_humanization_rest(account: SocialAccount, *, seconds: float | None = None) -> None:
    """Block warmup / idle-browse slot for 15–30 minutes after a humanization send."""
    delay = humanization_rest_seconds() if seconds is None else seconds
    _push_next_humanization_action(account, delay)


# ---------------------------------------------------------------------------
# Shared retry helper
# ---------------------------------------------------------------------------

def schedule_account_retry(account: SocialAccount, *, extra_seconds: float = 0) -> None:
    """Wait 3–5 minutes after a failed write so Telegram flood limits are not probed."""
    delay = random.uniform(ACCOUNT_RETRY_MIN_SECONDS, ACCOUNT_RETRY_MAX_SECONDS) + max(0, extra_seconds)
    _push_next_target_action(account, delay)


def retry_delay_seconds() -> float:
    return random.uniform(ACCOUNT_RETRY_MIN_SECONDS, ACCOUNT_RETRY_MAX_SECONDS)


# ---------------------------------------------------------------------------
# Internal push helpers
# ---------------------------------------------------------------------------

def _push_next_target_action(account: SocialAccount, seconds: float) -> None:
    until = _utc_now() + timedelta(seconds=max(1, seconds))
    current = getattr(account, "next_action_at", None)
    if current is None or current < until:
        account.next_action_at = until
    account.last_used_at = _utc_now()
    account.updated_at = _utc_now()


def _push_next_humanization_action(account: SocialAccount, seconds: float) -> None:
    until = _utc_now() + timedelta(seconds=max(1, seconds))
    current = getattr(account, "next_humanization_at", None)
    if current is None or current < until:
        account.next_humanization_at = until
    # Intentionally do NOT update last_used_at here – humanization activity
    # should not affect the target-action timestamp chain.
    account.updated_at = _utc_now()


# ---------------------------------------------------------------------------
# Legacy shims
# ---------------------------------------------------------------------------

def rest_seconds_for_account(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """Legacy: returns TARGET rest duration."""
    return target_rest_seconds_for_account(account, now=now)
