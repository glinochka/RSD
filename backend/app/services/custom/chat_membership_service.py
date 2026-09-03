"""Per-account chat membership queue and aggregate join status."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import is_lab_chat
from .rotation_service import list_alive_session_accounts
from ...alembic.models import AccountChatMembership, ChatJoinStatus, ChatTarget, ChatSource

logger = logging.getLogger(__name__)

_PENDING_STATUSES = {
    ChatJoinStatus.PENDING.value,
    ChatJoinStatus.JOINING.value,
    ChatJoinStatus.RATE_LIMITED.value,
    ChatJoinStatus.ERROR.value,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _pool_account_ids(session: AsyncSession, automation_id: int) -> list[int]:
    accounts = await list_alive_session_accounts(session, automation_id)
    return [account.id for account in accounts]


async def ensure_memberships_for_chat(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    account_ids: list[int] | None = None,
) -> int:
    if is_lab_chat(chat_target=chat_target):
        return 0
    ids = account_ids or await _pool_account_ids(session, automation_id)
    if not ids:
        return 0
    existing = set(
        (
            await session.execute(
                select(AccountChatMembership.social_account_id).where(
                    AccountChatMembership.chat_target_id == chat_target.id,
                    AccountChatMembership.social_account_id.in_(ids),
                )
            )
        ).scalars().all()
    )
    now = _utc_now()
    created = 0
    for account_id in ids:
        if account_id in existing:
            continue
        session.add(
            AccountChatMembership(
                custom_automation_id=automation_id,
                social_account_id=account_id,
                chat_target_id=chat_target.id,
                join_status=ChatJoinStatus.PENDING.value,
                join_attempts=0,
                created_at=now,
                updated_at=now,
            )
        )
        created += 1
    if created:
        chat_target.join_status = ChatJoinStatus.PENDING.value
        chat_target.updated_at = now
    return created


async def ensure_memberships_for_account(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    chat_ids: list[int] | None = None,
) -> int:
    filters = [
        ChatTarget.custom_automation_id == automation_id,
        ChatTarget.is_active.is_(True),
        ChatTarget.provider == "telegram",
        ChatTarget.source != ChatSource.TEST.value,
    ]
    if chat_ids:
        filters.append(ChatTarget.id.in_(chat_ids))
    chats = (await session.execute(select(ChatTarget).where(*filters))).scalars().all()
    created = 0
    for chat in chats:
        created += await ensure_memberships_for_chat(
            session,
            automation_id,
            chat,
            account_ids=[account_id],
        )
    return created


async def ensure_memberships_for_automation(session: AsyncSession, automation_id: int) -> int:
    account_ids = await _pool_account_ids(session, automation_id)
    chats = (
        await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.is_active.is_(True),
                ChatTarget.provider == "telegram",
                ChatTarget.source != ChatSource.TEST.value,
            )
        )
    ).scalars().all()
    created = 0
    for chat in chats:
        created += await ensure_memberships_for_chat(session, automation_id, chat, account_ids=account_ids)
    return created


async def membership_counts(
    session: AsyncSession,
    chat_target_id: int,
) -> tuple[int, int]:
    total = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.chat_target_id == chat_target_id,
        )
    )
    joined = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
        )
    )
    return int(joined or 0), int(total or 0)


async def sync_chat_join_status(session: AsyncSession, chat_target: ChatTarget) -> str:
    joined, total = await membership_counts(session, chat_target.id)
    now = _utc_now()
    if total == 0:
        return chat_target.join_status
    if joined >= total:
        status = ChatJoinStatus.JOINED.value
    elif joined > 0:
        status = ChatJoinStatus.PARTIAL.value
    else:
        pending = await session.scalar(
            select(func.count(AccountChatMembership.id)).where(
                AccountChatMembership.chat_target_id == chat_target.id,
                AccountChatMembership.join_status.in_(list(_PENDING_STATUSES)),
            )
        )
        status = ChatJoinStatus.PENDING.value if pending else ChatJoinStatus.ERROR.value
    chat_target.join_status = status
    if joined > 0 and not chat_target.joined_at:
        first = await session.scalar(
            select(AccountChatMembership.joined_at)
            .where(
                AccountChatMembership.chat_target_id == chat_target.id,
                AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
            )
            .order_by(AccountChatMembership.joined_at.asc())
            .limit(1)
        )
        chat_target.joined_at = first
    if joined == 1 and not chat_target.joined_by_account_id:
        account_id = await session.scalar(
            select(AccountChatMembership.social_account_id)
            .where(
                AccountChatMembership.chat_target_id == chat_target.id,
                AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
            )
            .order_by(AccountChatMembership.joined_at.asc())
            .limit(1)
        )
        chat_target.joined_by_account_id = account_id
    chat_target.updated_at = now
    return status


async def pick_next_pending_membership(
    session: AsyncSession,
    automation_id: int,
    *,
    max_attempts: int = 5,
) -> AccountChatMembership | None:
    now = _utc_now()
    result = await session.execute(
        select(AccountChatMembership)
        .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
        .where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.join_status.in_(
                [
                    ChatJoinStatus.PENDING.value,
                    ChatJoinStatus.RATE_LIMITED.value,
                    ChatJoinStatus.ERROR.value,
                ]
            ),
            AccountChatMembership.join_attempts < max_attempts,
            (AccountChatMembership.next_join_attempt_at.is_(None))
            | (AccountChatMembership.next_join_attempt_at <= now),
            ChatTarget.is_active.is_(True),
            ChatTarget.source != ChatSource.TEST.value,
        )
        .order_by(AccountChatMembership.id.asc())
        .limit(20)
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return None
    import random

    random.shuffle(candidates)
    return candidates[0]


async def recover_stale_joining_memberships(
    session: AsyncSession,
    automation_id: int,
    *,
    stale_minutes: int = 15,
) -> int:
    cutoff = _utc_now() - timedelta(minutes=stale_minutes)
    result = await session.execute(
        select(AccountChatMembership).where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINING.value,
            AccountChatMembership.last_join_attempt_at.is_not(None),
            AccountChatMembership.last_join_attempt_at < cutoff,
        )
    )
    recovered = 0
    for membership in result.scalars().all():
        membership.join_status = ChatJoinStatus.PENDING.value
        membership.updated_at = _utc_now()
        recovered += 1
    if recovered:
        await session.commit()
    return recovered


async def bulk_membership_counts(
    session: AsyncSession,
    chat_target_ids: list[int],
) -> dict[int, dict[str, int]]:
    if not chat_target_ids:
        return {}
    rows = (
        await session.execute(
            select(
                AccountChatMembership.chat_target_id,
                AccountChatMembership.join_status,
                func.count(AccountChatMembership.id),
            )
            .where(AccountChatMembership.chat_target_id.in_(chat_target_ids))
            .group_by(AccountChatMembership.chat_target_id, AccountChatMembership.join_status)
        )
    ).all()
    out: dict[int, dict[str, int]] = {cid: {"joined": 0, "total": 0} for cid in chat_target_ids}
    for chat_id, status, count in rows:
        out[chat_id]["total"] += int(count)
        if status == ChatJoinStatus.JOINED.value:
            out[chat_id]["joined"] += int(count)
    return out
