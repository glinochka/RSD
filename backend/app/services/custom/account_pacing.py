"""Per-account rest after writes, night sleep, and delayed retries.

Two independent timers:
  • TARGET rest      – next_action_at: 40-70 min after neurocommenting,
                       shilling, discussion, DM.
  • HUMANIZATION rest – next_humanization_at: 15-30 min after warmup,
                        peer_dialog, idle-browse, reactions.

TARGET and HUMANIZATION never block each other. Night hours block both.

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
TRUSTED_AGE_DAYS = 30
STAGE_CAUTIOUS = "cautious"   # 0–7 days on the platform
STAGE_NORMAL = "normal"       # 7–30 days
STAGE_TRUSTED = "trusted"     # 30+ days
RAMP_FULL_DAYS = 7
RAMP_START_FACTOR = 0.30      # day 1 ≈ 30% of the mature budget, day 7 = 100%

# ---------------------------------------------------------------------------
# Humanization rest  (warmup DMs, peer dialog, idle browse, reactions)
# ---------------------------------------------------------------------------
HUMANIZATION_REST_MIN_SECONDS = 15 * 60    # 15 min
HUMANIZATION_REST_MAX_SECONDS = 30 * 60    # 30 min
CAUTIOUS_HUMANIZATION_REST_MIN_SECONDS = 20 * 60
CAUTIOUS_HUMANIZATION_REST_MAX_SECONDS = 40 * 60
CAUTIOUS_TARGET_REST_MIN_SECONDS = 55 * 60
CAUTIOUS_TARGET_REST_MAX_SECONDS = 85 * 60

# One connected Telegram session (not a connect/disconnect flash).
_SESSION_SECONDS = {
    STAGE_CAUTIOUS: (90, 180),
    STAGE_NORMAL: (180, 360),
    STAGE_TRUSTED: (240, 420),
}
_SESSION_ACTION_BUDGET = {
    STAGE_CAUTIOUS: (3, 5),
    STAGE_NORMAL: (5, 8),
    STAGE_TRUSTED: (7, 10),
}

# ---------------------------------------------------------------------------
# Shared: retry after failed write
# ---------------------------------------------------------------------------
ACCOUNT_RETRY_MIN_SECONDS = 3 * 60
ACCOUNT_RETRY_MAX_SECONDS = 5 * 60
FLOOD_QUARANTINE_MIN_SECONDS = 12 * 60 * 60
FLOOD_QUARANTINE_MAX_SECONDS = 24 * 60 * 60

# ---------------------------------------------------------------------------
# Active-hours window (Moscow)
# ---------------------------------------------------------------------------
ACTIVE_START_HOUR = 8
ACTIVE_END_HOUR = 20
FARM_EARLIEST_START = 7.0
FARM_LATEST_END = 21.5

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
        "lead_delivery",
        "dmp_outreach",
        "chat_broadcast",
        "dm_broadcast",
    }
)

_HUMANIZATION_ACTIONS = frozenset(
    {
        "account_warmup",
        "peer_dialog",      # inter-account messaging for humanization
        "inbound_dm",       # private replies must not park comments/shills
        "idle_browse",
        "humanization_session",
        "masslooking",
        "masspriming",
        "parser",
        "reaction",
        "comment_contact",
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
    """Stable per-account Moscow window inside the global work hours."""
    from .work_mode import current_work_mode, work_span_hours

    start, end = work_span_hours(current_work_mode())
    aid = account_id if account_id is not None else getattr(account, "id", None)
    if not aid:
        return start, min(end, 24.0)
    stagger = (int(hashlib.sha256(f"wake:{int(aid)}".encode()).hexdigest()[:6], 16) % 900) / 3600.0
    return start + stagger, min(end, 24.0)


def in_account_active_hours(
    now: datetime | None = None,
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
) -> bool:
    """Public writes run inside the global Moscow work window."""
    from .work_mode import in_configured_work_hours

    aid = account_id if account_id is not None else getattr(account, "id", None)
    return in_configured_work_hours(now, account_id=aid)


def farm_overlap_active_hours(now: datetime | None = None) -> bool:
    """True when at least some accounts may be awake."""
    if now is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    from .work_mode import farm_work_overlap

    return farm_work_overlap(now)


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


def account_age_days(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """Days since the pool row was created. Unknown age is treated as new."""
    created = account_created_at(account)
    if created is None:
        return 0.0
    current = now or _utc_now()
    return max(0.0, (current - created).total_seconds() / 86400.0)


def account_humanization_stage(account: SocialAccount | None, *, now: datetime | None = None) -> str:
    """Cautious / normal / trusted by time in the pool, same bands as typical warmup products."""
    if account is None:
        return STAGE_NORMAL
    created = account_created_at(account)
    if created is None:
        return STAGE_CAUTIOUS
    days = account_age_days(account, now=now)
    if days < FIRST_WEEK_DAYS:
        return STAGE_CAUTIOUS
    if days < TRUSTED_AGE_DAYS:
        return STAGE_NORMAL
    return STAGE_TRUSTED


def humanization_ramp_factor(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """Progressive cap: ~30% on day 0, 100% from day 7."""
    days = account_age_days(account, now=now)
    if days >= RAMP_FULL_DAYS:
        return 1.0
    return RAMP_START_FACTOR + (1.0 - RAMP_START_FACTOR) * (days / RAMP_FULL_DAYS)


def humanization_session_seconds(account: SocialAccount | None, *, now: datetime | None = None, stage: str | None = None) -> float:
    """How long to keep the MTProto socket open for one humanization pass."""
    resolved = stage or account_humanization_stage(account, now=now)
    low, high = _SESSION_SECONDS.get(resolved) or _SESSION_SECONDS[STAGE_NORMAL]
    return random.uniform(float(low), float(high))


def humanization_session_action_budget(account: SocialAccount | None, *, now: datetime | None = None, stage: str | None = None) -> int:
    """How many in-session gestures (read/react/stories/…) this pass may run."""
    resolved = stage or account_humanization_stage(account, now=now)
    low, high = _SESSION_ACTION_BUDGET.get(resolved) or _SESSION_ACTION_BUDGET[STAGE_NORMAL]
    raw = random.randint(low, high) * humanization_ramp_factor(account, now=now)
    return max(2, int(round(raw)))


def post_join_mute_chance(account: SocialAccount | None, *, now: datetime | None = None) -> float:
    """New accounts mute more often after joining — people do, comment-bots don't."""
    stage = account_humanization_stage(account, now=now)
    if stage == STAGE_CAUTIOUS:
        return 0.72
    if stage == STAGE_NORMAL:
        return 0.48
    return 0.32


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
    """40–70 min rest; first week sits out longer (55–85 min)."""
    if account_humanization_stage(account, now=now) == STAGE_CAUTIOUS:
        return random.uniform(CAUTIOUS_TARGET_REST_MIN_SECONDS, CAUTIOUS_TARGET_REST_MAX_SECONDS)
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


def account_is_flood_quarantined(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    """True while a FloodWait / too-many-attempts quarantine is in force."""
    if not account:
        return False
    until = getattr(account, "flood_quarantined_until", None)
    if until is None:
        return False
    return until > (now or _utc_now())


def schedule_flood_quarantine(account: SocialAccount, *, now: datetime | None = None) -> datetime:
    """Park the account globally for 12–24 hours. Does not shorten an existing quarantine."""
    current = now or _utc_now()
    delay = random.uniform(FLOOD_QUARANTINE_MIN_SECONDS, FLOOD_QUARANTINE_MAX_SECONDS)
    until = current + timedelta(seconds=delay)
    existing = getattr(account, "flood_quarantined_until", None)
    if existing is not None and existing > until:
        until = existing
    account.flood_quarantined_until = until
    if getattr(account, "next_action_at", None) is None or account.next_action_at < until:
        account.next_action_at = until
    if getattr(account, "next_humanization_at", None) is None or account.next_humanization_at < until:
        account.next_humanization_at = until
    account.updated_at = current
    return until


def looks_like_flood_quarantine(exc: BaseException | None) -> bool:
    """FloodWait and Telegram's 'too many attempts, try later' — not a one-chat slow mode."""
    if exc is None:
        return False
    text = str(exc).lower()
    name = type(exc).__name__.lower()
    if "too many attempts" in text:
        return True
    if "try later" in text and ("too many" in text or "attempt" in text or "flood" in text):
        return True
    if "floodwait" in name or "flooderror" in name or "flood" in name:
        seconds = getattr(exc, "seconds", None)
        try:
            return int(seconds or 0) > 20 or seconds is None
        except (TypeError, ValueError):
            return True
    return "floodwait" in text


def account_should_idle(
    account: SocialAccount | None,
    *,
    now: datetime | None = None,
    ignore_hours: bool = False,
) -> bool:
    """True when the account must not send a TARGET action."""
    from .work_mode import in_configured_work_hours, in_daily_idle_gap

    if account_is_flood_quarantined(account, now=now):
        return True
    if account_in_target_rest_day(account, now=now):
        # Weekends still rest unless the global work_mode includes that weekday.
        from .work_mode import current_work_mode

        if moscow_now(now).weekday() not in current_work_mode()["weekdays"]:
            return True
    if in_daily_idle_gap(getattr(account, "id", None), now=now):
        return True
    if account_is_resting(account, now=now):
        wait = 0.0
        nxt = getattr(account, "next_action_at", None)
        if nxt is not None:
            wait = (nxt - (now or _utc_now())).total_seconds()
        # Long 40–70 min flashes no longer park work; keep short retries (fail/flood).
        if wait <= 15 * 60:
            return True
    if ignore_hours:
        return False
    if not in_configured_work_hours(now, account_id=getattr(account, "id", None)):
        return True
    return False


def account_membership_should_idle(
    account: SocialAccount | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Join/leave hygiene: respect flood quarantine and the global work window."""
    from .work_mode import in_configured_work_hours

    if account_is_flood_quarantined(account, now=now):
        return True
    return not in_configured_work_hours(now, account_id=getattr(account, "id", None))


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

def humanization_rest_seconds(account: SocialAccount | None = None, *, now: datetime | None = None) -> float:
    """15–30 min rest after a warmup DM, idle-browse or reaction; 20–40 in week one."""
    if account_humanization_stage(account, now=now) == STAGE_CAUTIOUS:
        return random.uniform(CAUTIOUS_HUMANIZATION_REST_MIN_SECONDS, CAUTIOUS_HUMANIZATION_REST_MAX_SECONDS)
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
    from .work_mode import in_configured_work_hours, in_daily_idle_gap

    if account_is_flood_quarantined(account, now=now):
        return True
    if in_daily_idle_gap(getattr(account, "id", None), now=now):
        return True
    if account_humanization_is_resting(account, now=now):
        wait = 0.0
        nxt = getattr(account, "next_humanization_at", None)
        if nxt is not None:
            wait = (nxt - (now or _utc_now())).total_seconds()
        if wait <= 8 * 60:
            return True
    if ignore_hours:
        return False
    if not in_configured_work_hours(now, account_id=getattr(account, "id", None)):
        return True
    return False


def schedule_account_humanization_rest(account: SocialAccount, *, seconds: float | None = None) -> None:
    """Block warmup / idle-browse slot for 15–30 minutes after a humanization send."""
    delay = humanization_rest_seconds(account) if seconds is None else seconds
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
