"""Account selection (rotation) and daily limits for /custom automations.

Account classes are no longer used for feature gating — roles are.  Every
action checks the PoolAccount.roles set directly.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AccountPool, CustomAutomation, CustomLead, PoolAccount, SocialAccount
from .account_pacing import account_should_idle, effective_daily_target_max
from .account_roles import account_matches_action

logger = getLogger(__name__)

_DM_ACTIONS = {"dm", "dmp_outreach"}
_UNLIMITED_QUOTA_ACTIONS = _DM_ACTIONS | {"lead_warmup"}
_KNOWN_ACTIONS = {
    "commenting",
    "dm",
    "dmp_outreach",
    "discussion",
    "shilling",
    "shilling_question",
    "shilling_answer",
    "inspect",
    "prepare_join",
    "discovery",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _tz(tz_name: str = "Europe/Moscow"):
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone(timedelta(hours=3))


def _local_today(tz_name: str = "Europe/Moscow") -> datetime.date:
    return datetime.now(_tz(tz_name)).date()


def _needs_reset(reset_at: datetime | None, tz_name: str = "Europe/Moscow") -> bool:
    if not reset_at:
        return True
    try:
        reset_date = reset_at.replace(tzinfo=timezone.utc).astimezone(_tz(tz_name)).date()
    except Exception:
        reset_date = reset_at.date()
    return reset_date != _local_today(tz_name)


def moscow_day_start_utc_naive(tz_name: str = "Europe/Moscow") -> datetime:
    local_midnight = datetime.now(_tz(tz_name)).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


async def _default_pool(session: AsyncSession, automation_id: int) -> AccountPool | None:
    return await session.scalar(
        select(AccountPool).where(
            AccountPool.custom_automation_id == automation_id,
            AccountPool.is_default.is_(True),
        )
    )


async def _load_pool_accounts(session: AsyncSession, pool_id: int) -> list[tuple[PoolAccount, SocialAccount]]:
    result = await session.execute(
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(PoolAccount.account_pool_id == pool_id)
        .order_by(PoolAccount.added_at.asc())
    )
    return list(result.all())


def current_daily_messages_sent(account: SocialAccount | None) -> int:
    """Messages sent today in Moscow time. Yesterday's leftover is shown as 0."""
    if account is None:
        return 0
    if _needs_reset(account.daily_messages_reset_at):
        return 0
    return int(account.daily_messages_sent or 0)


def _reset_counters_if_needed(accounts: list[SocialAccount]) -> None:
    now = _utc_now()
    for account in accounts:
        if _needs_reset(account.daily_messages_reset_at):
            account.daily_messages_sent = 0
            account.daily_messages_reset_at = now


def _filter_eligible(
    rows: list[tuple[PoolAccount, SocialAccount]],
    action_type: str,
    max_daily: int,
    exclude_banned: bool,
    *,
    exclude_spamblocked: bool = False,
    ignore_rest: bool = False,
) -> list[tuple[PoolAccount, SocialAccount]]:
    eligible = []
    for pool_account, social_account in rows:
        if not social_account.is_active:
            continue
        if exclude_banned and social_account.is_banned:
            continue
        if getattr(social_account, "is_frozen", False):
            continue
        if action_type not in _DM_ACTIONS | {"lead_warmup"} and getattr(social_account, "is_channel_banned", False):
            continue
        if not ignore_rest and account_should_idle(social_account):
            continue
        if exclude_spamblocked and social_account.is_spamblocked:
            continue
        if not account_matches_action(pool_account, social_account, action_type):
            continue
        if not social_account.session_file_path:
            continue
        if action_type not in _UNLIMITED_QUOTA_ACTIONS and social_account.daily_messages_sent >= max_daily:
            continue
        eligible.append((pool_account, social_account))
    return eligible


def _select_round_robin(eligible: list[tuple[PoolAccount, SocialAccount]]) -> SocialAccount:
    def sort_key(item: tuple[PoolAccount, SocialAccount]) -> datetime:
        return item[1].last_used_at or datetime.min

    eligible.sort(key=sort_key)
    pool = eligible[: min(3, len(eligible))]
    return random.choice(pool)[1]


def _select_least_used(eligible: list[tuple[PoolAccount, SocialAccount]]) -> SocialAccount:
    def sort_key(item: tuple[PoolAccount, SocialAccount]) -> tuple[int, datetime]:
        social = item[1]
        return (social.daily_messages_sent, social.last_used_at or datetime.min)

    eligible.sort(key=sort_key)
    return eligible[0][1]


def _select_risk_weighted(eligible: list[tuple[PoolAccount, SocialAccount]]) -> SocialAccount:
    weights = []
    for _, social in eligible:
        trust = social.trust_score
        if trust is None or trust <= 0:
            trust = 1.0
        weights.append(trust)

    total = sum(weights)
    if total <= 0:
        return random.choice(eligible)[1]

    threshold = random.uniform(0, total)
    cumulative = 0.0
    for idx, weight in enumerate(weights):
        cumulative += weight
        if cumulative >= threshold:
            return eligible[idx][1]
    return eligible[-1][1]


async def list_alive_session_accounts(
    session: AsyncSession,
    automation_id: int,
    *,
    exclude_banned: bool = True,
) -> list[SocialAccount]:
    """All connected pool accounts, any role. Used for inspect and preparation joins."""
    pool = await _default_pool(session, automation_id)
    if not pool:
        return []
    rows = await _load_pool_accounts(session, pool.id)
    alive: list[SocialAccount] = []
    for pool_account, social in rows:
        if not social.is_active:
            continue
        if exclude_banned and social.is_banned:
            continue
        if getattr(social, "is_frozen", False):
            continue
        if not social.session_file_path and not getattr(social, "encrypted_session", None):
            continue
        alive.append(social)
    return alive


def record_successful_send(account: SocialAccount) -> None:
    """Count a TARGET message only after Telegram actually accepted it."""
    _reset_counters_if_needed([account])
    account.daily_messages_sent = (account.daily_messages_sent or 0) + 1
    account.last_used_at = _utc_now()


def record_successful_humanization(account: SocialAccount) -> None:
    """Mark a humanization action (warmup, discussion, peer_dialog) as done.

    Does NOT increment daily_messages_sent so humanization never consumes the
    target-action daily budget.
    """
    account.last_used_at = _utc_now()
    account.updated_at = _utc_now()


async def select_account_for_action(
    session: AsyncSession,
    automation: CustomAutomation | int,
    action_type: str,
    thread_id: int | None = None,
    exclude_banned: bool = True,
    exclude_account_ids: set[int] | None = None,
    consume_quota: bool = False,
    ignore_rest: bool = False,
) -> SocialAccount | None:
    """Pick an account from the default pool respecting roles, rotation strategy and daily limits.

    Args:
        session: active async SQLAlchemy session.
        automation: CustomAutomation instance or its id.
        action_type: one of "commenting", "dm", "discussion", "shilling", etc.
        thread_id: optional lead/thread id. For ``dm`` and ``discussion`` an already assigned
            account is returned if it is still eligible.
        exclude_banned: skip banned accounts.
        exclude_account_ids: never return these account ids.
        consume_quota: legacy flag; daily_messages_sent grows only via record_successful_send.
        ignore_rest: lab/manual paths may pick an account that is cooling down.
    """
    automation_id = automation.id if isinstance(automation, CustomAutomation) else int(automation)
    automation_obj = automation if isinstance(automation, CustomAutomation) else None

    if not automation_obj:
        automation_obj = await session.get(CustomAutomation, automation_id)
    if not automation_obj:
        logger.warning("Automation %s not found for rotation", automation_id)
        return None

    if action_type not in _KNOWN_ACTIONS:
        logger.warning("Unknown action type %s", action_type)
        return None

    pool = await _default_pool(session, automation_id)
    if not pool:
        logger.warning("No default pool for automation %s", automation_id)
        return None

    rows = await _load_pool_accounts(session, pool.id)
    accounts = [social for _, social in rows]
    _reset_counters_if_needed(accounts)

    exclude_spamblocked = action_type in _DM_ACTIONS
    skip_write_rest = ignore_rest or action_type == "inspect"

    # Per-account per-day randomized target max
    daily_maxes: dict[int, int] = {}
    for _, social in rows:
        daily_maxes[social.id] = effective_daily_target_max(social, automation_obj)

    eligible = _filter_eligible(
        rows,
        action_type,
        # Use the highest current max as the conservative filter; real check below.
        max(daily_maxes.values()) if daily_maxes else 0,
        exclude_banned,
        exclude_spamblocked=exclude_spamblocked,
        ignore_rest=skip_write_rest,
    )

    # Re-apply per-account randomized daily cap
    eligible = [
        row
        for row in eligible
        if action_type in _UNLIMITED_QUOTA_ACTIONS or row[1].daily_messages_sent < daily_maxes.get(row[1].id, 0)
    ]

    if exclude_account_ids:
        eligible = [row for row in eligible if row[1].id not in exclude_account_ids]
    if not eligible:
        logger.info("No eligible accounts for automation %s action %s", automation_id, action_type)
        return None

    if thread_id:
        lead = await session.get(CustomLead, thread_id)
        if lead and lead.assigned_account_id:
            assigned = await session.get(SocialAccount, lead.assigned_account_id)
            assigned_row = next((row for row in rows if assigned and row[1].id == assigned.id), None)
            assigned_pool = assigned_row[0] if assigned_row else None
            assigned_ok = bool(
                assigned
                and assigned.is_active
                and not (exclude_banned and assigned.is_banned)
                and not getattr(assigned, "is_frozen", False)
                and not (exclude_spamblocked and assigned.is_spamblocked)
                and (ignore_rest or not account_should_idle(assigned))
                and account_matches_action(assigned_pool, assigned, action_type)
                and (
                    action_type in _UNLIMITED_QUOTA_ACTIONS
                    or assigned.daily_messages_sent < daily_maxes.get(assigned.id, 0)
                )
            )
            if assigned_ok:
                if exclude_account_ids and assigned.id in exclude_account_ids:
                    pass
                else:
                    return assigned
            logger.info(
                "Assigned account %s for thread %s is not eligible (roles=%s, sent=%s)",
                assigned.id,
                thread_id,
                getattr(assigned_pool, "roles", None),
                assigned.daily_messages_sent,
            )

    strategy = (automation_obj.rotation_strategy or "round_robin").strip().lower()
    if strategy == "least_used":
        selected = _select_least_used(eligible)
    elif strategy == "risk_weighted":
        selected = _select_risk_weighted(eligible)
    else:
        selected = _select_round_robin(eligible)

    _ = consume_quota

    if thread_id and lead:
        lead.assigned_account_id = selected.id

    return selected


def accounts_are_distinct(*accounts: SocialAccount) -> bool:
    """True when every account is a different userbot (id, session file, phone)."""
    live = [account for account in accounts if account is not None]
    if len(live) < 2:
        return False
    ids = [account.id for account in live]
    if len(ids) != len(set(ids)):
        return False
    sessions = [account.session_file_path for account in live if account.session_file_path]
    if len(sessions) != len(set(sessions)):
        return False
    phones = [account.phone_number for account in live if account.phone_number]
    if len(phones) != len(set(phones)):
        return False
    return True


async def select_distinct_accounts_for_action(
    session: AsyncSession,
    automation: CustomAutomation | int,
    action_type: str,
    count: int = 2,
    exclude_banned: bool = True,
    exclude_account_ids: set[int] | None = None,
    consume_quota: bool = False,
    ignore_rest: bool = False,
) -> list[SocialAccount]:
    """Pick ``count`` distinct accounts. Returns [] if a full distinct set cannot be formed."""
    selected: list[SocialAccount] = []
    excluded = set(exclude_account_ids or set())
    for _ in range(count):
        account = await select_account_for_action(
            session,
            automation,
            action_type,
            exclude_banned=exclude_banned,
            exclude_account_ids=excluded,
            consume_quota=consume_quota,
            ignore_rest=ignore_rest,
        )
        if account is None:
            return []
        selected.append(account)
        excluded.add(account.id)
    if len(selected) < count or not accounts_are_distinct(*selected):
        return []
    return selected
