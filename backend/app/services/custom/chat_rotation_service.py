"""Slow weekly rotation of joined channels/chats between watchers.

Each account leaves 3–5 of its oldest chats per Moscow week (one leave at a
time, 18–36 hours apart). Another account picks those chats up; the leaver
joins a chat someone else has held the longest. Looks like a person cleaning
subscriptions, not a farm swapping the whole list at once.
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import AccountChatMembership, ChatJoinStatus, ChatTarget, SocialAccount
from .account_pacing import account_membership_should_idle, moscow_now
from .chat_membership_service import (
    REJOIN_COOLDOWN_DAYS,
    WATCHER_REPLACE_PRIORITY,
    _account_can_open_session,
    _blocked_chat_ids_for_account,
    _target_chat_count_for_account,
    account_occupied_count,
    apply_account_join_cooldown,
    ensure_memberships_for_automation,
    release_membership,
    reuse_or_queue_membership,
)
from .rotation_service import list_alive_session_accounts

logger = logging.getLogger(__name__)

MIN_TENURE_DAYS = 6
MIN_LEAVE_GAP_HOURS = 18
MAX_LEAVE_GAP_HOURS = 36
MIN_WEEKLY_LEAVES = 3
MAX_WEEKLY_LEAVES = 5


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _moscow_week_start(now: datetime | None = None) -> datetime:
    local = moscow_now(now)
    monday = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local.weekday())
    return monday.astimezone(timezone.utc).replace(tzinfo=None)


def weekly_leave_quota(account_id: int, now: datetime | None = None) -> int:
    week = _moscow_week_start(now).strftime("%Y-%W")
    digest = hashlib.sha256(f"leave-quota:{account_id}:{week}".encode()).hexdigest()
    return MIN_WEEKLY_LEAVES + (int(digest[:8], 16) % (MAX_WEEKLY_LEAVES - MIN_WEEKLY_LEAVES + 1))


async def _leaves_this_week(session: AsyncSession, account_id: int) -> int:
    start = _moscow_week_start()
    count = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status == ChatJoinStatus.LEFT.value,
            AccountChatMembership.updated_at >= start,
            AccountChatMembership.last_join_error == "weekly_rotation",
        )
    )
    return int(count or 0)


async def _last_rotation_leave_at(session: AsyncSession, account_id: int) -> datetime | None:
    return await session.scalar(
        select(func.max(AccountChatMembership.updated_at)).where(
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status == ChatJoinStatus.LEFT.value,
            AccountChatMembership.last_join_error == "weekly_rotation",
        )
    )


async def _oldest_joined_membership(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> AccountChatMembership | None:
    cutoff = _utc_now() - timedelta(days=MIN_TENURE_DAYS)
    return await session.scalar(
        select(AccountChatMembership)
        .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
        .where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
            AccountChatMembership.purpose == "watcher",
            ChatTarget.mod_status != "moderated",
            ChatTarget.is_active.is_(True),
            func.coalesce(AccountChatMembership.joined_at, AccountChatMembership.created_at) <= cutoff,
        )
        .order_by(
            func.coalesce(AccountChatMembership.joined_at, AccountChatMembership.created_at).asc(),
            AccountChatMembership.id.asc(),
        )
        .limit(1)
    )


async def _oldest_foreign_chat_id(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    exclude_chat_ids: set[int],
) -> int | None:
    blocked = await _blocked_chat_ids_for_account(session, automation_id, account_id)
    blocked |= exclude_chat_ids
    row = (
        await session.execute(
            select(
                AccountChatMembership.chat_target_id,
                func.min(func.coalesce(AccountChatMembership.joined_at, AccountChatMembership.created_at)),
            )
            .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
            .where(
                AccountChatMembership.custom_automation_id == automation_id,
                AccountChatMembership.social_account_id != account_id,
                AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
                ChatTarget.mod_status != "moderated",
                ChatTarget.is_active.is_(True),
                ChatTarget.mode != "inactive",
            )
            .group_by(AccountChatMembership.chat_target_id)
            .order_by(
                func.min(func.coalesce(AccountChatMembership.joined_at, AccountChatMembership.created_at)).asc()
            )
        )
    ).first()
    if not row:
        return None
    chat_id = int(row[0])
    if chat_id not in blocked:
        return chat_id
    filters = [
        AccountChatMembership.custom_automation_id == automation_id,
        AccountChatMembership.social_account_id != account_id,
        AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
        ChatTarget.mod_status != "moderated",
        ChatTarget.is_active.is_(True),
        ChatTarget.mode != "inactive",
    ]
    if blocked:
        filters.append(AccountChatMembership.chat_target_id.notin_(blocked))
    rows = (
        await session.execute(
            select(
                AccountChatMembership.chat_target_id,
                func.min(func.coalesce(AccountChatMembership.joined_at, AccountChatMembership.created_at)),
            )
            .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
            .where(*filters)
            .group_by(AccountChatMembership.chat_target_id)
            .order_by(
                func.min(func.coalesce(AccountChatMembership.joined_at, AccountChatMembership.created_at)).asc()
            )
            .limit(1)
        )
    ).first()
    return int(rows[0]) if rows else None


async def _pick_taker_account(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    *,
    exclude_account_id: int,
) -> SocialAccount | None:
    accounts = await list_alive_session_accounts(session, automation_id)
    candidates: list[tuple[int, SocialAccount]] = []
    for account in accounts:
        if account.id == exclude_account_id or not _account_can_open_session(account):
            continue
        if account_membership_should_idle(account):
            continue
        existing = await session.scalar(
            select(AccountChatMembership.join_status).where(
                AccountChatMembership.chat_target_id == chat_target_id,
                AccountChatMembership.social_account_id == account.id,
            )
        )
        if existing in {
            ChatJoinStatus.JOINED.value,
            ChatJoinStatus.JOINING.value,
            ChatJoinStatus.PENDING.value,
            ChatJoinStatus.BANNED.value,
        }:
            continue
        if existing == ChatJoinStatus.LEFT.value:
            left_at = await session.scalar(
                select(AccountChatMembership.updated_at).where(
                    AccountChatMembership.chat_target_id == chat_target_id,
                    AccountChatMembership.social_account_id == account.id,
                )
            )
            if left_at and (_utc_now() - left_at) < timedelta(days=REJOIN_COOLDOWN_DAYS):
                continue
        slots = await account_occupied_count(session, account.id)
        if slots >= _target_chat_count_for_account(account.id):
            continue
        candidates.append((slots, account))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


async def _rotate_one_account(
    session: AsyncSession,
    automation_id: int,
    account: SocialAccount,
) -> dict[str, Any] | None:
    if account_membership_should_idle(account):
        return None
    quota = weekly_leave_quota(account.id)
    if await _leaves_this_week(session, account.id) >= quota:
        return None
    last_leave = await _last_rotation_leave_at(session, account.id)
    if last_leave is not None:
        gap = timedelta(hours=random.uniform(MIN_LEAVE_GAP_HOURS, MAX_LEAVE_GAP_HOURS))
        if _utc_now() < last_leave + gap:
            return None
    membership = await _oldest_joined_membership(session, automation_id, account.id)
    if membership is None:
        return None
    chat_target = await session.get(ChatTarget, membership.chat_target_id)
    if not chat_target:
        return None

    from .chat_join_service import leave_chat_for_account

    outcome = await leave_chat_for_account(session, chat_target, account)
    if outcome.get("status") not in {"left", "failed"}:
        return {"status": outcome.get("status"), "reason": "leave_not_ready", "account_id": account.id}

    # "failed" often means already not a participant — still free the slot.
    await release_membership(membership, reason="weekly_rotation")
    await apply_account_join_cooldown(session, automation_id, account.id)

    taker = await _pick_taker_account(
        session, automation_id, chat_target.id, exclude_account_id=account.id
    )
    if taker:
        await reuse_or_queue_membership(
            session,
            automation_id,
            chat_target.id,
            taker.id,
            priority=WATCHER_REPLACE_PRIORITY,
        )

    replacement_chat_id = await _oldest_foreign_chat_id(
        session,
        automation_id,
        account.id,
        exclude_chat_ids={chat_target.id},
    )
    if replacement_chat_id:
        await reuse_or_queue_membership(
            session,
            automation_id,
            replacement_chat_id,
            account.id,
            priority=WATCHER_REPLACE_PRIORITY,
        )

    await session.commit()
    logger.info(
        "Rotated chat %s off account %s; taker=%s replacement=%s",
        chat_target.id,
        account.id,
        getattr(taker, "id", None),
        replacement_chat_id,
    )
    return {
        "status": "rotated",
        "account_id": account.id,
        "left_chat_id": chat_target.id,
        "taker_id": getattr(taker, "id", None),
        "replacement_chat_id": replacement_chat_id,
    }


async def run_chat_rotation_pass(automation_id: int) -> dict[str, Any]:
    async with async_session_maker() as session:
        await ensure_memberships_for_automation(session, automation_id)
        accounts = [
            account
            for account in await list_alive_session_accounts(session, automation_id)
            if _account_can_open_session(account) and not account_membership_should_idle(account)
        ]
        if not accounts:
            return {"status": "skipped", "reason": "no_eligible_accounts"}
        random.shuffle(accounts)
        for account in accounts:
            result = await _rotate_one_account(session, automation_id, account)
            if result:
                return result
        return {"status": "skipped", "reason": "no_due_rotation"}
