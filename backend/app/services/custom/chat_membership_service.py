"""Per-account chat membership: one watcher per chat, actors join on demand."""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import is_lab_chat, is_paused, is_public_readable
from .rotation_service import list_alive_session_accounts
from ...alembic.models import (
    AccountChatMembership,
    ChatJoinStatus,
    ChatSource,
    ChatTarget,
    MembershipPurpose,
    SocialAccount,
)

logger = logging.getLogger(__name__)

JOIN_DELAY_MIN_SECONDS = 180
JOIN_DELAY_MAX_SECONDS = 300
MAX_CHATS_PER_ACCOUNT = 450
MAX_JOINS_PER_TICK = 8
ACTION_JOIN_PRIORITY = 100
WATCHER_REPLACE_PRIORITY = 80
WATCHER_PURPOSE = MembershipPurpose.WATCHER.value
ACTOR_PURPOSE = MembershipPurpose.ACTOR.value

_PENDING_STATUSES = {
    ChatJoinStatus.PENDING.value,
    ChatJoinStatus.JOINING.value,
    ChatJoinStatus.RATE_LIMITED.value,
    ChatJoinStatus.ERROR.value,
}
_QUEUE_STATUSES = {
    ChatJoinStatus.PENDING.value,
    ChatJoinStatus.RATE_LIMITED.value,
    ChatJoinStatus.ERROR.value,
}
_SLOT_STATUSES = {
    ChatJoinStatus.JOINED.value,
    ChatJoinStatus.JOINING.value,
}
_ACTIVE_WATCHER_STATUSES = {
    ChatJoinStatus.PENDING.value,
    ChatJoinStatus.JOINING.value,
    ChatJoinStatus.RATE_LIMITED.value,
    ChatJoinStatus.JOINED.value,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _account_can_open_session(account: SocialAccount | None) -> bool:
    if not account or not account.is_active or account.is_banned:
        return False
    if getattr(account, "is_frozen", False):
        return False
    if getattr(account, "encrypted_session", None):
        return True
    return bool((account.session_file_path or "").strip())


async def _pool_account_ids(session: AsyncSession, automation_id: int) -> list[int]:
    accounts = await list_alive_session_accounts(session, automation_id)
    return [account.id for account in accounts]


async def account_slot_count(session: AsyncSession, account_id: int) -> int:
    count = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status.in_(list(_SLOT_STATUSES)),
        )
    )
    return int(count or 0)


async def account_is_joined(session: AsyncSession, chat_target_id: int, account_id: int) -> bool:
    status = await session.scalar(
        select(AccountChatMembership.join_status).where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.social_account_id == account_id,
        )
    )
    return status == ChatJoinStatus.JOINED.value


async def is_chat_watchable(session: AsyncSession, chat_target: ChatTarget) -> bool:
    if is_paused(chat_target):
        return False
    if is_public_readable(chat_target):
        return True
    return await has_live_joined_member(session, chat_target.id)


async def has_live_joined_member(session: AsyncSession, chat_target_id: int) -> bool:
    found = await session.scalar(
        select(AccountChatMembership.id)
        .join(SocialAccount, SocialAccount.id == AccountChatMembership.social_account_id)
        .where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
        )
        .limit(1)
    )
    return found is not None


async def get_membership(
    session: AsyncSession,
    chat_target_id: int,
    account_id: int,
) -> AccountChatMembership | None:
    return await session.scalar(
        select(AccountChatMembership).where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.social_account_id == account_id,
        )
    )


def _new_membership(
    automation_id: int,
    chat_target_id: int,
    account_id: int,
    *,
    purpose: str,
    priority: int = 0,
) -> AccountChatMembership:
    now = _utc_now()
    return AccountChatMembership(
        custom_automation_id=automation_id,
        social_account_id=account_id,
        chat_target_id=chat_target_id,
        join_status=ChatJoinStatus.PENDING.value,
        purpose=purpose,
        priority=priority,
        join_attempts=0,
        created_at=now,
        updated_at=now,
    )


async def _least_loaded_watcher_account(
    session: AsyncSession,
    automation_id: int,
    *,
    exclude_account_ids: set[int] | None = None,
) -> SocialAccount | None:
    accounts = await list_alive_session_accounts(session, automation_id)
    excluded = exclude_account_ids or set()
    best: SocialAccount | None = None
    best_load = 10**9
    for account in accounts:
        if account.id in excluded or not _account_can_open_session(account):
            continue
        load = await account_slot_count(session, account.id)
        if load >= MAX_CHATS_PER_ACCOUNT:
            continue
        if load < best_load:
            best = account
            best_load = load
    return best


async def _lost_reader_ids(session: AsyncSession, chat_target_id: int) -> set[int]:
    rows = (
        await session.execute(
            select(AccountChatMembership.social_account_id).where(
                AccountChatMembership.chat_target_id == chat_target_id,
                AccountChatMembership.join_status == ChatJoinStatus.BANNED.value,
            )
        )
    ).scalars().all()
    return {int(account_id) for account_id in rows}


async def _chat_has_active_watcher(session: AsyncSession, chat_target_id: int) -> bool:
    found = await session.scalar(
        select(AccountChatMembership.id)
        .join(SocialAccount, SocialAccount.id == AccountChatMembership.social_account_id)
        .where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.purpose == WATCHER_PURPOSE,
            AccountChatMembership.join_status.in_(list(_ACTIVE_WATCHER_STATUSES)),
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
        )
        .limit(1)
    )
    return found is not None


def live_joined_chat_ids(automation_id: int):
    return (
        select(AccountChatMembership.chat_target_id)
        .join(SocialAccount, SocialAccount.id == AccountChatMembership.social_account_id)
        .where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
        )
        .distinct()
    )


def _looks_like_private_ref(col):
    return or_(
        col.contains("/+"),
        col.ilike("%joinchat%"),
        col.ilike("%/c/%"),
        col.like("-100%"),
        col.like("-%"),
    )


def _looks_like_username_ref(col):
    return and_(col != "", ~_looks_like_private_ref(col))


def _public_readable_sql():
    """Candidate set for is_public_readable(); Python filter is the source of truth."""
    invite = func.coalesce(ChatTarget.invite_link, "")
    external = func.coalesce(ChatTarget.external_chat_id, "")
    title = func.coalesce(ChatTarget.title, "")
    title_username = or_(
        title.startswith("@"),
        and_(
            or_(title.ilike("%t.me/%"), title.ilike("telegram.me/%")),
            ~_looks_like_private_ref(title),
        ),
    )
    return and_(
        ChatTarget.chat_type.in_(["channel", "broadcast"]),
        ~_looks_like_private_ref(invite),
        or_(
            _looks_like_username_ref(invite),
            and_(invite == "", _looks_like_username_ref(external)),
            and_(invite == "", title_username),
        ),
    )


async def _promote_live_member_to_watcher(
    session: AsyncSession,
    chat_target: ChatTarget,
    *,
    exclude_account_ids: set[int],
) -> bool:
    filters = [
        AccountChatMembership.chat_target_id == chat_target.id,
        AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
        SocialAccount.is_active.is_(True),
        SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
    ]
    if exclude_account_ids:
        filters.append(AccountChatMembership.social_account_id.notin_(exclude_account_ids))
    membership = await session.scalar(
        select(AccountChatMembership)
        .join(SocialAccount, SocialAccount.id == AccountChatMembership.social_account_id)
        .where(*filters)
        .order_by(
            case((AccountChatMembership.purpose == WATCHER_PURPOSE, 0), else_=1),
            AccountChatMembership.id.asc(),
        )
        .limit(1)
    )
    if not membership:
        return False
    membership.purpose = WATCHER_PURPOSE
    membership.priority = max(int(membership.priority or 0), WATCHER_REPLACE_PRIORITY)
    membership.updated_at = _utc_now()
    return True


async def ensure_watcher_membership(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    include_lab: bool = False,
    replace: bool = False,
) -> int:
    if is_lab_chat(chat_target=chat_target) and not include_lab:
        return 0
    if is_public_readable(chat_target):
        return 0
    excluded = await _lost_reader_ids(session, chat_target.id)
    if await _chat_has_active_watcher(session, chat_target.id):
        return 0
    if await _promote_live_member_to_watcher(session, chat_target, exclude_account_ids=excluded):
        return 0
    priority = WATCHER_REPLACE_PRIORITY if replace else 0
    while True:
        account = await _least_loaded_watcher_account(
            session, automation_id, exclude_account_ids=excluded
        )
        if not account:
            logger.warning("No watcher slot left for chat %s automation %s", chat_target.id, automation_id)
            return 0
        existing = await get_membership(session, chat_target.id, account.id)
        if existing and existing.join_status == ChatJoinStatus.BANNED.value:
            excluded.add(account.id)
            continue
        if existing:
            existing.purpose = WATCHER_PURPOSE
            existing.priority = max(int(existing.priority or 0), priority)
            if existing.join_status in {
                ChatJoinStatus.ERROR.value,
                ChatJoinStatus.RATE_LIMITED.value,
            }:
                existing.join_status = ChatJoinStatus.PENDING.value
                existing.next_join_attempt_at = None
            existing.updated_at = _utc_now()
            if existing.join_status != ChatJoinStatus.JOINED.value:
                chat_target.join_status = ChatJoinStatus.PENDING.value
                chat_target.updated_at = _utc_now()
            return 0
        session.add(
            _new_membership(
                automation_id,
                chat_target.id,
                account.id,
                purpose=WATCHER_PURPOSE,
                priority=priority,
            )
        )
        chat_target.join_status = ChatJoinStatus.PENDING.value
        chat_target.updated_at = _utc_now()
        return 1


async def queue_actor_for_chat(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    account: SocialAccount,
    *,
    priority: int = ACTION_JOIN_PRIORITY,
) -> AccountChatMembership | None:
    existing = await get_membership(session, chat_target.id, account.id)
    now = _utc_now()
    if existing and existing.join_status == ChatJoinStatus.BANNED.value:
        logger.info(
            "Account %s is banned in chat %s, skip actor queue",
            account.id,
            chat_target.id,
        )
        return None
    if existing:
        existing.purpose = existing.purpose or ACTOR_PURPOSE
        if existing.purpose == WATCHER_PURPOSE:
            pass
        else:
            existing.purpose = ACTOR_PURPOSE
        existing.priority = max(int(existing.priority or 0), int(priority))
        if existing.join_status in {
            ChatJoinStatus.ERROR.value,
            ChatJoinStatus.RATE_LIMITED.value,
        }:
            existing.join_status = ChatJoinStatus.PENDING.value
        existing.updated_at = now
        return existing
    if await account_slot_count(session, account.id) >= MAX_CHATS_PER_ACCOUNT:
        logger.info(
            "Account %s is at chat cap, cannot join chat %s",
            account.id,
            chat_target.id,
        )
        return None
    membership = _new_membership(
        automation_id,
        chat_target.id,
        account.id,
        purpose=ACTOR_PURPOSE,
        priority=priority,
    )
    session.add(membership)
    await session.flush()
    if chat_target.join_status == ChatJoinStatus.JOINED.value:
        chat_target.join_status = ChatJoinStatus.PARTIAL.value
        chat_target.updated_at = now
    return membership


async def ensure_memberships_for_chat(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    account_ids: list[int] | None = None,
    include_lab: bool = False,
    purpose: str | None = None,
    priority: int = 0,
) -> int:
    if is_lab_chat(chat_target=chat_target) and not include_lab:
        return 0
    if account_ids is None:
        return await ensure_watcher_membership(
            session, automation_id, chat_target, include_lab=include_lab
        )
    ids = list(dict.fromkeys(account_ids))
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
    assigned_purpose = purpose or WATCHER_PURPOSE
    for account_id in ids:
        if account_id in existing:
            continue
        session.add(
            _new_membership(
                automation_id,
                chat_target.id,
                account_id,
                purpose=assigned_purpose,
                priority=priority,
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
    """Fill watcher gaps for chats that still need coverage. Do not join every chat."""
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
        if is_public_readable(chat):
            continue
        if await _chat_has_active_watcher(session, chat.id):
            continue
        if await account_slot_count(session, account_id) >= MAX_CHATS_PER_ACCOUNT:
            break
        created += await ensure_memberships_for_chat(
            session,
            automation_id,
            chat,
            account_ids=[account_id],
            purpose=WATCHER_PURPOSE,
        )
    return created


async def ensure_memberships_for_automation(session: AsyncSession, automation_id: int) -> int:
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
        created += await ensure_watcher_membership(session, automation_id, chat)
    return created


async def membership_counts(
    session: AsyncSession,
    chat_target_id: int,
) -> tuple[int, int]:
    total = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.join_status != ChatJoinStatus.BANNED.value,
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
    if joined > 0 and not chat_target.joined_by_account_id:
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


async def apply_account_join_cooldown(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
    *,
    wait_seconds: float | None = None,
) -> None:
    delay = wait_seconds if wait_seconds is not None else random.uniform(
        JOIN_DELAY_MIN_SECONDS, JOIN_DELAY_MAX_SECONDS
    )
    until = _utc_now() + timedelta(seconds=delay)
    result = await session.execute(
        select(AccountChatMembership).where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status.in_(list(_QUEUE_STATUSES)),
        )
    )
    for membership in result.scalars().all():
        current = membership.next_join_attempt_at
        if current is None or current < until:
            membership.next_join_attempt_at = until
            membership.updated_at = _utc_now()


async def _account_ids_on_cooldown(
    session: AsyncSession,
    automation_id: int,
    extra_ids: set[int] | None = None,
) -> set[int]:
    blocked = set(extra_ids or ())
    cutoff = _utc_now() - timedelta(seconds=JOIN_DELAY_MIN_SECONDS)
    rows = (
        await session.execute(
            select(
                AccountChatMembership.social_account_id,
                func.max(AccountChatMembership.last_join_attempt_at),
            )
            .where(
                AccountChatMembership.custom_automation_id == automation_id,
                AccountChatMembership.last_join_attempt_at.is_not(None),
            )
            .group_by(AccountChatMembership.social_account_id)
        )
    ).all()
    for account_id, last_at in rows:
        if last_at is not None and last_at > cutoff:
            blocked.add(int(account_id))
    return blocked


async def pick_next_pending_membership(
    session: AsyncSession,
    automation_id: int,
    *,
    max_attempts: int = 5,
    include_lab: bool = False,
    chat_target_ids: list[int] | None = None,
    ignore_retry_delay: bool = False,
    exclude_account_ids: set[int] | None = None,
) -> AccountChatMembership | None:
    now = _utc_now()
    filters = [
        AccountChatMembership.custom_automation_id == automation_id,
        AccountChatMembership.join_status.in_(list(_QUEUE_STATUSES)),
        AccountChatMembership.join_attempts < max_attempts,
        ChatTarget.is_active.is_(True),
        or_(
            AccountChatMembership.purpose == WATCHER_PURPOSE,
            AccountChatMembership.priority > 0,
        ),
    ]
    if not ignore_retry_delay:
        filters.append(
            (AccountChatMembership.next_join_attempt_at.is_(None))
            | (AccountChatMembership.next_join_attempt_at <= now)
        )
        filters.append(
            or_(
                SocialAccount.next_action_at.is_(None),
                SocialAccount.next_action_at <= now,
            )
        )
    if not include_lab:
        filters.append(ChatTarget.source != ChatSource.TEST.value)
    if chat_target_ids:
        filters.append(AccountChatMembership.chat_target_id.in_(chat_target_ids))
    blocked = set(exclude_account_ids or ())
    if not ignore_retry_delay:
        blocked |= await _account_ids_on_cooldown(session, automation_id)
    if blocked:
        filters.append(AccountChatMembership.social_account_id.notin_(blocked))
    result = await session.execute(
        select(AccountChatMembership)
        .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
        .join(SocialAccount, SocialAccount.id == AccountChatMembership.social_account_id)
        .where(*filters)
        .order_by(AccountChatMembership.priority.desc(), AccountChatMembership.id.asc())
        .limit(20)
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return None
    top_priority = candidates[0].priority
    same = [item for item in candidates if item.priority == top_priority]
    if top_priority and top_priority > 0:
        return same[0]
    random.shuffle(same)
    return same[0]


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
        if status == ChatJoinStatus.BANNED.value:
            continue
        out[chat_id]["total"] += int(count)
        if status == ChatJoinStatus.JOINED.value:
            out[chat_id]["joined"] += int(count)
    return out


async def list_watchable_chats(
    session: AsyncSession,
    automation_id: int,
    *,
    include_lab: bool = False,
    limit: int | None = None,
) -> list[ChatTarget]:
    joined_ids = live_joined_chat_ids(automation_id)
    filters = [
        ChatTarget.custom_automation_id == automation_id,
        ChatTarget.is_active.is_(True),
        ChatTarget.mode != "inactive",
        or_(
            ChatTarget.id.in_(joined_ids),
            _public_readable_sql(),
        ),
    ]
    if not include_lab:
        filters.append(ChatTarget.source != ChatSource.TEST.value)
    stmt = (
        select(ChatTarget)
        .where(*filters)
        .order_by(
            ChatTarget.last_scanned_at.is_(None).desc(),
            ChatTarget.last_scanned_at.asc(),
            ChatTarget.id.asc(),
        )
    )
    if limit is not None:
        stmt = stmt.limit(max(limit * 5, 40))
    chats: list[ChatTarget] = []
    for chat in (await session.execute(stmt)).scalars().all():
        if not await is_chat_watchable(session, chat):
            continue
        chats.append(chat)
        if limit is not None and len(chats) >= limit:
            break
    return chats


async def get_reader_account(
    session: AsyncSession,
    chat_target: ChatTarget,
    *,
    exclude_account_ids: set[int] | None = None,
) -> SocialAccount | None:
    excluded = set(exclude_account_ids or ())
    excluded |= await _lost_reader_ids(session, chat_target.id)
    filters = [
        AccountChatMembership.chat_target_id == chat_target.id,
        AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
        SocialAccount.is_active.is_(True),
        SocialAccount.is_banned.is_(False),
            SocialAccount.is_frozen.is_(False),
    ]
    if excluded:
        filters.append(AccountChatMembership.social_account_id.notin_(excluded))
    rows = (
        await session.execute(
            select(AccountChatMembership.social_account_id)
            .join(SocialAccount, SocialAccount.id == AccountChatMembership.social_account_id)
            .where(*filters)
            .order_by(
                case((AccountChatMembership.purpose == WATCHER_PURPOSE, 0), else_=1),
                AccountChatMembership.id.asc(),
            )
        )
    ).scalars().all()
    spamblocked_fallback: SocialAccount | None = None
    for account_id in rows:
        account = await session.get(SocialAccount, account_id)
        if not _account_can_open_session(account):
            continue
        if getattr(account, "is_spamblocked", False):
            spamblocked_fallback = spamblocked_fallback or account
            continue
        return account
    if spamblocked_fallback:
        return spamblocked_fallback
    if not is_public_readable(chat_target):
        return None
    from .rotation_service import select_account_for_action

    for action in ("commenting", "prepare_join"):
        fallback = await select_account_for_action(
            session,
            chat_target.custom_automation_id,
            action,
            consume_quota=False,
            exclude_account_ids=excluded or None,
        )
        if _account_can_open_session(fallback) and not getattr(fallback, "is_spamblocked", False):
            return fallback
    return None


async def mark_membership_chat_banned(
    session: AsyncSession,
    chat_target: ChatTarget,
    account_id: int,
    *,
    error: str | None = None,
) -> AccountChatMembership:
    membership = await get_membership(session, chat_target.id, account_id)
    now = _utc_now()
    message = (error or "chat_restricted")[:255]
    if membership is None:
        membership = _new_membership(
            chat_target.custom_automation_id,
            chat_target.id,
            account_id,
            purpose=ACTOR_PURPOSE,
        )
        session.add(membership)
        await session.flush()
    membership.join_status = ChatJoinStatus.BANNED.value
    membership.purpose = ACTOR_PURPOSE
    membership.last_join_error = message
    membership.updated_at = now
    await sync_chat_join_status(session, chat_target)
    from .pending_action_service import fail_pending_requiring_account

    await fail_pending_requiring_account(
        session,
        chat_target_id=chat_target.id,
        account_id=account_id,
        error=message,
    )
    return membership


async def retire_reader_and_replace(
    session: AsyncSession,
    chat_target: ChatTarget,
    account_id: int,
    *,
    error: str | None = None,
) -> int:
    """Mark this account lost in this chat and queue a different watcher if needed."""
    await mark_membership_chat_banned(session, chat_target, account_id, error=error)
    if is_public_readable(chat_target):
        logger.warning(
            "Reader %s lost access to public chat %s; will pick another reader",
            account_id,
            chat_target.id,
        )
        return 0
    created = await ensure_watcher_membership(
        session,
        chat_target.custom_automation_id,
        chat_target,
        replace=True,
    )
    logger.warning(
        "Reader %s lost access to chat %s; queued replacement watcher",
        account_id,
        chat_target.id,
    )
    return created


async def replace_watchers_for_dead_account(session: AsyncSession, account_id: int) -> int:
    """Free watcher slots held by a globally dead account and assign replacements."""
    rows = (
        await session.execute(
            select(AccountChatMembership).where(
                AccountChatMembership.social_account_id == account_id,
                AccountChatMembership.purpose == WATCHER_PURPOSE,
                AccountChatMembership.join_status.in_(list(_ACTIVE_WATCHER_STATUSES)),
            )
        )
    ).scalars().all()
    queued = 0
    for membership in rows:
        membership.purpose = ACTOR_PURPOSE
        if membership.join_status != ChatJoinStatus.BANNED.value:
            membership.join_status = ChatJoinStatus.ERROR.value
            membership.last_join_error = "account_unavailable"
        membership.updated_at = _utc_now()
        chat = await session.get(ChatTarget, membership.chat_target_id)
        if not chat:
            continue
        queued += await ensure_watcher_membership(
            session,
            chat.custom_automation_id,
            chat,
            replace=True,
        )
        await sync_chat_join_status(session, chat)
    if rows:
        logger.warning(
            "Replaced watchers for dead account %s in %s chats",
            account_id,
            len(rows),
        )
    return queued


async def recover_reader_after_error(
    session: AsyncSession,
    chat_target: ChatTarget,
    account: SocialAccount,
    exc: Exception,
) -> bool:
    """True if the caller should retry the read with another account."""
    from .telegram_error_handler import is_account_dead, is_chat_read_lost, update_account_after_telegram_error

    if is_account_dead(exc):
        await update_account_after_telegram_error(session, account, exc)
        await replace_watchers_for_dead_account(session, account.id)
        return True
    if is_chat_read_lost(exc):
        await retire_reader_and_replace(session, chat_target, account.id, error=str(exc)[:255])
        return True
    return False
