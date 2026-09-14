"""Per-account rest after writes and delayed retries after failed writes."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from ...alembic.models import SocialAccount

ACCOUNT_REST_SECONDS = 10 * 60
ACCOUNT_RETRY_MIN_SECONDS = 3 * 60
ACCOUNT_RETRY_MAX_SECONDS = 5 * 60
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
    }
)


def action_uses_write_rest(action_type: str | None) -> bool:
    """10-minute rest applies to sending in chats, comments, DMs — not joins or profile edits."""
    kind = (action_type or "").strip()
    if kind in _WRITE_REST_ACTIONS:
        return True
    return kind.startswith("shilling")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def account_is_resting(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    if not account:
        return False
    nxt = getattr(account, "next_action_at", None)
    if nxt is None:
        return False
    current = now or _utc_now()
    return nxt > current


def _push_next_action(account: SocialAccount, seconds: float) -> None:
    until = _utc_now() + timedelta(seconds=max(1, seconds))
    current = getattr(account, "next_action_at", None)
    if current is None or current < until:
        account.next_action_at = until
    account.last_used_at = _utc_now()
    account.updated_at = _utc_now()


def schedule_account_rest(account: SocialAccount, *, seconds: float = ACCOUNT_REST_SECONDS) -> None:
    """Block this account from further writes after a real Telegram send."""
    _push_next_action(account, seconds)


def schedule_account_retry(account: SocialAccount, *, extra_seconds: float = 0) -> None:
    """Wait 3–5 minutes after a failed write so Telegram flood limits are not probed."""
    delay = random.uniform(ACCOUNT_RETRY_MIN_SECONDS, ACCOUNT_RETRY_MAX_SECONDS) + max(0, extra_seconds)
    _push_next_action(account, delay)


def retry_delay_seconds() -> float:
    return random.uniform(ACCOUNT_RETRY_MIN_SECONDS, ACCOUNT_RETRY_MAX_SECONDS)
