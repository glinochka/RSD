"""Account selection (rotation) and daily limits for /custom automations."""
import random
from datetime import datetime, timezone
from logging import getLogger
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AccountClass, AccountPool, CustomAutomation, CustomLead, PoolAccount, SocialAccount

logger = getLogger(__name__)

ACTION_ALLOWED_CLASSES = {
    "commenting": {AccountClass.ONE_DAY.value, AccountClass.MID.value, AccountClass.TRUSTED.value},
    "dm": {AccountClass.TRUSTED.value, AccountClass.MID.value},
    "discussion": {AccountClass.ONE_DAY.value, AccountClass.MID.value, AccountClass.TRUSTED.value},
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _local_today(tz_name: str = "Europe/Moscow") -> datetime.date:
    return datetime.now(ZoneInfo(tz_name)).date()


def _needs_reset(reset_at: datetime | None, tz_name: str = "Europe/Moscow") -> bool:
    if not reset_at:
        return True
    try:
        reset_date = reset_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name)).date()
    except Exception:
        reset_date = reset_at.date()
    return reset_date != _local_today(tz_name)


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


def _reset_counters_if_needed(accounts: list[SocialAccount]) -> None:
    now = _utc_now()
    for account in accounts:
        if _needs_reset(account.daily_messages_reset_at):
            account.daily_messages_sent = 0
            account.daily_messages_reset_at = now


def _filter_eligible(
    rows: list[tuple[PoolAccount, SocialAccount]],
    allowed_classes: set[str],
    max_daily: int,
    exclude_banned: bool,
) -> list[tuple[PoolAccount, SocialAccount]]:
    eligible = []
    for pool_account, social_account in rows:
        if not social_account.is_active:
            continue
        if exclude_banned and social_account.is_banned:
            continue
        if social_account.account_class not in allowed_classes:
            continue
        if not social_account.session_file_path:
            continue
        if social_account.daily_messages_sent >= max_daily:
            continue
        eligible.append((pool_account, social_account))
    return eligible


def _select_round_robin(eligible: list[tuple[PoolAccount, SocialAccount]]) -> SocialAccount:
    def sort_key(item: tuple[PoolAccount, SocialAccount]) -> datetime:
        return item[1].last_used_at or datetime.min

    eligible.sort(key=sort_key)
    return eligible[0][1]


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


async def select_account_for_action(
    session: AsyncSession,
    automation: CustomAutomation | int,
    action_type: str,
    thread_id: int | None = None,
    exclude_banned: bool = True,
) -> SocialAccount | None:
    """Pick an account from the default pool respecting class, rotation strategy and daily limits.

    Args:
        session: active async SQLAlchemy session.
        automation: CustomAutomation instance or its id.
        action_type: one of "commenting", "dm", "discussion".
        thread_id: optional lead/thread id. For ``dm`` and ``discussion`` an already assigned
            account is returned if it is still eligible.
        exclude_banned: skip banned accounts.

    Returns:
        A SocialAccount instance or None if no eligible account exists.
    """
    automation_id = automation.id if isinstance(automation, CustomAutomation) else int(automation)
    automation_obj = automation if isinstance(automation, CustomAutomation) else None

    if not automation_obj:
        automation_obj = await session.get(CustomAutomation, automation_id)
    if not automation_obj:
        logger.warning("Automation %s not found for rotation", automation_id)
        return None

    allowed_classes = ACTION_ALLOWED_CLASSES.get(action_type)
    if allowed_classes is None:
        logger.warning("Unknown action type %s", action_type)
        return None

    pool = await _default_pool(session, automation_id)
    if not pool:
        logger.warning("No default pool for automation %s", automation_id)
        return None

    rows = await _load_pool_accounts(session, pool.id)
    accounts = [social for _, social in rows]
    _reset_counters_if_needed(accounts)

    eligible = _filter_eligible(rows, allowed_classes, automation_obj.max_daily_messages_per_account, exclude_banned)
    if not eligible:
        logger.info("No eligible accounts for automation %s action %s", automation_id, action_type)
        return None

    if thread_id:
        lead = await session.get(CustomLead, thread_id)
        if lead and lead.assigned_account_id:
            assigned = await session.get(SocialAccount, lead.assigned_account_id)
            if assigned and assigned.is_active and not (exclude_banned and assigned.is_banned):
                if assigned.account_class in allowed_classes and assigned.daily_messages_sent < automation_obj.max_daily_messages_per_account:
                    assigned.daily_messages_sent += 1
                    assigned.last_used_at = _utc_now()
                    return assigned
                logger.info(
                    "Assigned account %s for thread %s is not eligible (class=%s, sent=%s)",
                    assigned.id,
                    thread_id,
                    assigned.account_class,
                    assigned.daily_messages_sent,
                )

    strategy = (automation_obj.rotation_strategy or "round_robin").strip().lower()
    if strategy == "least_used":
        selected = _select_least_used(eligible)
    elif strategy == "risk_weighted":
        selected = _select_risk_weighted(eligible)
    else:
        selected = _select_round_robin(eligible)

    selected.daily_messages_sent += 1
    selected.last_used_at = _utc_now()

    if thread_id and lead:
        lead.assigned_account_id = selected.id

    return selected
