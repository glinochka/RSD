"""Per-account chat membership: stable account↔chat assignment and join queue.

Design change (2026-09-25):
  • Accounts JOIN the channels/chats they are assigned to, then receive
    updates naturally instead of polling public channels from outside.
  • Each account gets a stable subset of chats (50–100) sharded by hash.
  • Joins happen slowly: one per account, 1–5 hours apart, during active hours.
  • Public-readable pull mode is kept as fallback only for chats that cannot
    be joined (invite links not available) — not as the default strategy.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_active_window, account_humanization_should_idle, farm_overlap_active_hours
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

# ---------------------------------------------------------------------------
# Join throttling — very slow and human-like
# ---------------------------------------------------------------------------
JOIN_DELAY_MIN_SECONDS = 1 * 60 * 60      # 1 hour
JOIN_DELAY_MAX_SECONDS = 5 * 60 * 60      # 5 hours
MAX_CHATS_PER_ACCOUNT = 100               # cap per account
MAX_JOINS_PER_TICK = 1                    # scheduler processes one join per tick
ACTION_JOIN_PRIORITY = 100
WATCHER_REPLACE_PRIORITY = 80
WATCHER_PURPOSE = MembershipPurpose.WATCHER.value
ACTOR_PURPOSE = MembershipPurpose.ACTOR.value

# How many chats each account should actively monitor.
TARGET_CHATS_PER_ACCOUNT = 50
MIN_CHATS_PER_ACCOUNT = 30
MAX_TARGET_CHATS_PER_ACCOUNT = 100
REJOIN_COOLDOWN_DAYS = 21

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
_OCCUPIED_STATUSES = {
    ChatJoinStatus.PENDING.value,
    ChatJoinStatus.JOINING.value,
    ChatJoinStatus.RATE_LIMITED.value,
    ChatJoinStatus.ERROR.value,
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


async def account_occupied_count(session: AsyncSession, account_id: int) -> int:
    count = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status.in_(list(_OCCUPIED_STATUSES)),
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
    """A chat is watchable when there is an assigned account that has joined it.

    Public-readable fallback is preserved only for channels without an assignable
    watcher (e.g. missing invite/username-only).
    """
    if is_paused(chat_target):
        return False
    if chat_target.mod_status == "moderated":
        return False
    has_joined = await has_live_joined_member(session, chat_target.id)
    if has_joined:
        return True
    return is_public_readable(chat_target)


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


# ---------------------------------------------------------------------------
# Stable chat↔account sharding
# ---------------------------------------------------------------------------

def _account_chat_hash(account_id: int, chat_target_id: int, salt: int = 0) -> float:
    """Stable 0-1 value deciding whether a chat belongs to an account's subset."""
    import hashlib
    digest = hashlib.sha256(f"{account_id}:{chat_target_id}:{salt}".encode()).hexdigest()
    return int(digest[:8], 16) / (2**32)


def _target_chat_count_for_account(account_id: int) -> int:
    """Stable per-account target between MIN and MAX."""
    import hashlib
    digest = hashlib.sha256(f"account_target_count:{account_id}".encode()).hexdigest()
    frac = int(digest[:8], 16) / (2**32)
    return MIN_CHATS_PER_ACCOUNT + int(frac * (MAX_TARGET_CHATS_PER_ACCOUNT - MIN_CHATS_PER_ACCOUNT))


async def _active_assignable_chats(session: AsyncSession, automation_id: int) -> list[ChatTarget]:
    result = await session.execute(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.is_active.is_(True),
            ChatTarget.provider == "telegram",
            ChatTarget.source != ChatSource.TEST.value,
            ChatTarget.mod_status != "moderated",
        )
    )
    return list(result.scalars().all())


async def _blocked_chat_ids_for_account(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> set[int]:
    """Chats this account already occupies, was banned from, or left recently."""
    now = _utc_now()
    rows = (
        await session.execute(
            select(AccountChatMembership).where(
                AccountChatMembership.custom_automation_id == automation_id,
                AccountChatMembership.social_account_id == account_id,
            )
        )
    ).scalars().all()
    blocked: set[int] = set()
    cooldown = timedelta(days=REJOIN_COOLDOWN_DAYS)
    for membership in rows:
        status = membership.join_status
        if status in _OCCUPIED_STATUSES:
            blocked.add(membership.chat_target_id)
        elif status == ChatJoinStatus.BANNED.value:
            blocked.add(membership.chat_target_id)
        elif status == ChatJoinStatus.LEFT.value:
            left_at = membership.updated_at or membership.joined_at
            if left_at is not None and (now - left_at) < cooldown:
                blocked.add(membership.chat_target_id)
    return blocked


async def reuse_or_queue_membership(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    account_id: int,
    *,
    purpose: str = WATCHER_PURPOSE,
    priority: int = 0,
) -> AccountChatMembership | None:
    """Create or revive a membership row so the account can join this chat."""
    existing = await get_membership(session, chat_target_id, account_id)
    now = _utc_now()
    if existing:
        if existing.join_status == ChatJoinStatus.BANNED.value:
            return None
        if existing.join_status == ChatJoinStatus.JOINED.value:
            return existing
        existing.purpose = existing.purpose or purpose
        existing.priority = max(int(existing.priority or 0), int(priority))
        existing.join_status = ChatJoinStatus.PENDING.value
        existing.join_attempts = 0
        existing.next_join_attempt_at = None
        existing.last_join_error = None
        existing.updated_at = now
        return existing
    membership = _new_membership(
        automation_id,
        chat_target_id,
        account_id,
        purpose=purpose,
        priority=priority,
    )
    session.add(membership)
    return membership


async def release_membership(
    membership: AccountChatMembership,
    *,
    reason: str | None = None,
) -> None:
    now = _utc_now()
    membership.join_status = ChatJoinStatus.LEFT.value
    if reason:
        membership.last_join_error = reason[:500]
    membership.updated_at = now


async def release_memberships_for_chat(
    session: AsyncSession,
    chat_target: ChatTarget,
    *,
    reason: str = "released",
) -> int:
    """Free watcher slots on a chat (black box / rotation) without deleting rows."""
    result = await session.execute(
        select(AccountChatMembership).where(
            AccountChatMembership.chat_target_id == chat_target.id,
            AccountChatMembership.join_status.in_(list(_OCCUPIED_STATUSES)),
        )
    )
    released = 0
    for membership in result.scalars().all():
        await release_membership(membership, reason=reason)
        released += 1
    return released


async def _assign_chats_to_account(
    session: AsyncSession,
    automation_id: int,
    account: SocialAccount,
    all_chats: list[ChatTarget],
) -> int:
    """Ensure account has its stable subset of chats assigned (not necessarily joined yet)."""
    blocked_ids = await _blocked_chat_ids_for_account(session, automation_id, account.id)
    target_count = _target_chat_count_for_account(account.id)
    scored = sorted(all_chats, key=lambda chat: _account_chat_hash(account.id, chat.id))

    added = 0
    for chat in scored:
        if chat.id in blocked_ids:
            continue
        occupied = await account_occupied_count(session, account.id)
        if occupied >= min(MAX_CHATS_PER_ACCOUNT, target_count):
            break
        queued = await reuse_or_queue_membership(
            session,
            automation_id,
            chat.id,
            account.id,
            purpose=WATCHER_PURPOSE,
        )
        if queued is None:
            continue
        blocked_ids.add(chat.id)
        added += 1
    return added


async def _release_moderated_slots(session: AsyncSession, automation_id: int) -> int:
    result = await session.execute(
        select(AccountChatMembership)
        .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
        .where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.join_status.in_(list(_OCCUPIED_STATUSES)),
            ChatTarget.mod_status == "moderated",
        )
    )
    released = 0
    for membership in result.scalars().all():
        await release_membership(membership, reason="moderated_blackbox")
        released += 1
    return released


async def _redistribute_moderated_chats(session: AsyncSession, automation_id: int) -> int:
    """Free black-boxed slots, then assign fresh chats so no account sits idle."""
    await _release_moderated_slots(session, automation_id)
    all_chats = await _active_assignable_chats(session, automation_id)
    accounts = await list_alive_session_accounts(session, automation_id)
    total_replaced = 0
    for account in accounts:
        if not _account_can_open_session(account):
            continue
        current_count = await account_occupied_count(session, account.id)
        target_count = _target_chat_count_for_account(account.id)
        if current_count >= target_count:
            continue
        added = await _assign_chats_to_account(session, automation_id, account, all_chats)
        if added:
            total_replaced += added
    return total_replaced


# ---------------------------------------------------------------------------
# Watcher selection / assignment
# ---------------------------------------------------------------------------

async def _least_loaded_watcher_account(
    session: AsyncSession,
    automation_id: int,
    *,
    exclude_account_ids: set[int] | None = None,
) -> SocialAccount | None:
    """Deprecated: sharding assigns chats explicitly. Kept for compatibility."""
    excluded = exclude_account_ids or set()
    accounts = await list_alive_session_accounts(session, automation_id)
    eligible = [a for a in accounts if a.id not in excluded and _account_can_open_session(a)]
    if not eligible:
        return None
    scored: list[tuple[int, int, SocialAccount]] = []
    for account in eligible:
        scored.append((await account_slot_count(session, account.id), account.id, account))
    scored.sort()
    return scored[0][2]


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
    """Ensures a chat has an assigned watcher account (via sharding, not ad-hoc).

    For pull-only channels this returns 0 because is_public_readable handles them.
    """
    if is_lab_chat(chat_target=chat_target) and not include_lab:
        return 0
    if is_public_readable(chat_target):
        return 0
    if chat_target.mod_status == "moderated":
        return 0
    excluded = await _lost_reader_ids(session, chat_target.id)
    if await _chat_has_active_watcher(session, chat_target.id):
        return 0
    if await _promote_live_member_to_watcher(session, chat_target, exclude_account_ids=excluded):
        return 0
    # Sharding should have already assigned someone.  If not, assign via least-loaded fallback.
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
        row[0]
        for row in (
            await session.execute(
                select(AccountChatMembership.social_account_id).where(
                    AccountChatMembership.custom_automation_id == automation_id,
                    AccountChatMembership.chat_target_id == chat_target.id,
                )
            )
        ).all()
    )
    created = 0
    for account_id in ids:
        if account_id in existing:
            continue
        if await account_slot_count(session, account_id) >= MAX_CHATS_PER_ACCOUNT:
            continue
        session.add(
            _new_membership(
                automation_id,
                chat_target.id,
                account_id,
                purpose=purpose or ACTOR_PURPOSE,
                priority=priority,
            )
        )
        created += 1
    if created:
        if chat_target.join_status == ChatJoinStatus.JOINED.value:
            chat_target.join_status = ChatJoinStatus.PARTIAL.value
            chat_target.updated_at = _utc_now()
        await session.flush()
    return created


async def ensure_memberships_for_account(
    session: AsyncSession,
    automation_id: int,
    account_id: int,
) -> int:
    """Assign a stable chat subset to a single account after upload/warmup."""
    account = await session.get(SocialAccount, account_id)
    if not account or not _account_can_open_session(account):
        return 0
    all_chats = await _active_assignable_chats(session, automation_id)
    return await _assign_chats_to_account(session, automation_id, account, all_chats)


async def ensure_memberships_for_automation(session: AsyncSession, automation_id: int) -> int:
    """Every active account gets a stable subset of chats; moderated chats get replacements."""
    await _redistribute_moderated_chats(session, automation_id)

    all_chats = await _active_assignable_chats(session, automation_id)
    accounts = await list_alive_session_accounts(session, automation_id)
    total_added = 0
    for account in accounts:
        if not _account_can_open_session(account):
            continue
        added = await _assign_chats_to_account(session, automation_id, account, all_chats)
        if added:
            total_added += added
    if total_added:
        await session.commit()
    return total_added


async def membership_counts(
    session: AsyncSession,
    chat_target_id: int,
) -> tuple[int, int]:
    total = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.join_status.notin_(
                [ChatJoinStatus.BANNED.value, ChatJoinStatus.LEFT.value]
            ),
        )
    )
    joined = await session.scalar(
        select(func.count(AccountChatMembership.id)).where(
            AccountChatMembership.chat_target_id == chat_target_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
        )
    )
    return int(joined or 0), int(total or 0)


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
        if status in {ChatJoinStatus.BANNED.value, ChatJoinStatus.LEFT.value}:
            continue
        out[chat_id]["total"] += int(count)
        if status == ChatJoinStatus.JOINED.value:
            out[chat_id]["joined"] += int(count)
    return out


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
    chat_target.updated_at = now
    return status


async def replace_watcher_for_chat(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    dead_account_id: int | None = None,
) -> bool:
    """Pick a replacement watcher when the current one was banned/frozen/revoked."""
    excluded = await _lost_reader_ids(session, chat_target.id)
    if dead_account_id:
        excluded.add(dead_account_id)
    if await _promote_live_member_to_watcher(session, chat_target, exclude_account_ids=excluded):
        chat_target.updated_at = _utc_now()
        return True
    if await ensure_watcher_membership(session, automation_id, chat_target, replace=True):
        chat_target.updated_at = _utc_now()
        return True
    return False


async def retire_reader_and_replace(
    session: AsyncSession,
    chat_target: ChatTarget,
    account_id: int,
    error: str | None = None,
) -> bool:
    membership = await get_membership(session, chat_target.id, account_id)
    now = _utc_now()
    if membership:
        membership.join_status = ChatJoinStatus.BANNED.value
        membership.last_join_error = (error or "read_lost")[:500]
        membership.updated_at = now
    chat_target.updated_at = now
    await session.commit()
    replacement_ok = await replace_watcher_for_chat(
        session, chat_target.custom_automation_id, chat_target, dead_account_id=account_id
    )
    await session.commit()
    return replacement_ok


async def replace_watchers_for_dead_account(
    session: AsyncSession,
    account_id: int,
) -> int:
    result = await session.execute(
        select(AccountChatMembership).where(
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.purpose == WATCHER_PURPOSE,
        )
    )
    replaced = 0
    for membership in result.scalars().all():
        chat_target = await session.get(ChatTarget, membership.chat_target_id)
        if not chat_target:
            continue
        membership.join_status = ChatJoinStatus.BANNED.value
        membership.updated_at = _utc_now()
        await session.commit()
        if await replace_watcher_for_chat(
            session, membership.custom_automation_id, chat_target, dead_account_id=account_id
        ):
            replaced += 1
        await session.commit()
    return replaced


# ---------------------------------------------------------------------------
# Join cooldown and selection
# ---------------------------------------------------------------------------

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
    blocked = set(extra_ids or set())
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
        ChatTarget.mod_status != "moderated",
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
    if not include_lab:
        filters.append(ChatTarget.source != ChatSource.TEST.value)
    if chat_target_ids:
        filters.append(AccountChatMembership.chat_target_id.in_(chat_target_ids))
    blocked = set(exclude_account_ids or set())
    if not ignore_retry_delay:
        blocked |= await _account_ids_on_cooldown(session, automation_id)
    if blocked:
        filters.append(AccountChatMembership.social_account_id.notin_(blocked))
    result = await session.execute(
        select(AccountChatMembership)
        .join(ChatTarget, ChatTarget.id == AccountChatMembership.chat_target_id)
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


async def get_reader_account(
    session: AsyncSession,
    chat_target: ChatTarget,
    *,
    exclude_account_ids: set[int] | None = None,
) -> SocialAccount | None:
    """Return an account that has actually joined this chat.

    With the new joined-watcher model, reading is done by the assigned watcher.
    Public-readable fallback is kept only as a last resort.
    """
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
    return None


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


async def list_watchable_chats(
    session: AsyncSession,
    automation_id: int,
    *,
    include_lab: bool = False,
    limit: int | None = None,
) -> list[ChatTarget]:
    """Chats that have at least one live JOINED watcher.

    Public-readable channels are included as fallback only when no watcher exists.
    """
    joined_ids = live_joined_chat_ids(automation_id)
    filters = [
        ChatTarget.custom_automation_id == automation_id,
        ChatTarget.is_active.is_(True),
        ChatTarget.mode != "inactive",
        ChatTarget.mod_status != "moderated",
        ChatTarget.id.in_(joined_ids),
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
            AccountChatMembership.updated_at < cutoff,
        )
    )
    fixed = 0
    for membership in result.scalars().all():
        membership.join_status = ChatJoinStatus.PENDING.value
        membership.updated_at = _utc_now()
        fixed += 1
    return fixed
