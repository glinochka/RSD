"""Queue an action until the responsible account has joined the chat, then run it."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_should_idle, in_account_active_hours, next_wake_at, retry_delay_seconds
from .chat_membership_service import account_is_joined, get_membership, queue_actor_for_chat
from ...alembic.models import (
    AccountChatMembership,
    ChatJoinStatus,
    ChatMessage,
    ChatTarget,
    PendingChatAction,
    PendingChatActionStatus,
    SocialAccount,
)

logger = logging.getLogger(__name__)

PENDING = PendingChatActionStatus.PENDING.value
DONE = PendingChatActionStatus.DONE.value
FAILED = PendingChatActionStatus.FAILED.value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _account_ids_from_payload(action: PendingChatAction) -> list[int]:
    raw = (action.payload or {}).get("account_ids") or [action.social_account_id]
    ids: list[int] = []
    for item in raw:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value not in ids:
            ids.append(value)
    if action.social_account_id not in ids:
        ids.insert(0, action.social_account_id)
    return ids


async def has_pending_action(
    session: AsyncSession,
    automation_id: int,
    action_type: str,
    target_id: str,
) -> bool:
    found = await session.scalar(
        select(PendingChatAction.id).where(
            PendingChatAction.custom_automation_id == automation_id,
            PendingChatAction.action_type == action_type,
            PendingChatAction.target_id == str(target_id),
            PendingChatAction.status == PENDING,
        )
    )
    return found is not None


async def enqueue_pending_action(
    session: AsyncSession,
    *,
    automation_id: int,
    chat_target: ChatTarget,
    account: SocialAccount,
    action_type: str,
    target_id: str,
    payload: dict[str, Any] | None = None,
    extra_account_ids: Iterable[int] | None = None,
) -> PendingChatAction | None:
    existing = await session.scalar(
        select(PendingChatAction).where(
            PendingChatAction.custom_automation_id == automation_id,
            PendingChatAction.action_type == action_type,
            PendingChatAction.target_id == str(target_id),
        )
    )
    account_ids = [account.id]
    for extra in extra_account_ids or []:
        if extra not in account_ids:
            account_ids.append(int(extra))
    body = dict(payload or {})
    body["account_ids"] = account_ids
    body["chat_target_id"] = chat_target.id
    now = _utc_now()
    if existing:
        if existing.status == DONE:
            return existing
        existing.status = PENDING
        existing.social_account_id = account.id
        existing.payload = body
        existing.updated_at = now
        return existing
    action = PendingChatAction(
        custom_automation_id=automation_id,
        chat_target_id=chat_target.id,
        social_account_id=account.id,
        action_type=action_type,
        target_id=str(target_id),
        payload=body,
        status=PENDING,
        attempts=0,
        created_at=now,
        updated_at=now,
    )
    session.add(action)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        return await session.scalar(
            select(PendingChatAction).where(
                PendingChatAction.custom_automation_id == automation_id,
                PendingChatAction.action_type == action_type,
                PendingChatAction.target_id == str(target_id),
            )
        )
    return action


async def ensure_accounts_ready(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    accounts: list[SocialAccount],
    *,
    action_type: str,
    target_id: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    """True when every account is already in the chat. Otherwise queue joins + pending action."""
    if not accounts:
        return False
    from .chat_scope import is_public_readable

    if is_public_readable(chat_target):
        return True
    missing: list[SocialAccount] = []
    for account in accounts:
        if await account_is_joined(session, chat_target.id, account.id):
            continue
        membership = await queue_actor_for_chat(session, automation_id, chat_target, account)
        if membership is None:
            logger.warning(
                "Cannot queue %s for chat %s action %s: no join slot",
                account.id,
                chat_target.id,
                action_type,
            )
            return False
        missing.append(account)
    if not missing:
        return True
    await enqueue_pending_action(
        session,
        automation_id=automation_id,
        chat_target=chat_target,
        account=accounts[0],
        action_type=action_type,
        target_id=target_id,
        payload=payload,
        extra_account_ids=[item.id for item in accounts[1:]],
    )
    return False


async def fail_pending_requiring_account(
    session: AsyncSession,
    *,
    chat_target_id: int,
    account_id: int,
    error: str | None = None,
) -> int:
    """Cancel queued actions that cannot complete because this account lost the chat."""
    result = await session.execute(
        select(PendingChatAction).where(
            PendingChatAction.chat_target_id == chat_target_id,
            PendingChatAction.status == PENDING,
        )
    )
    now = _utc_now()
    message = (error or "chat_banned")[:500]
    failed = 0
    for action in result.scalars().all():
        if account_id not in _account_ids_from_payload(action):
            continue
        action.status = FAILED
        action.last_error = message
        action.updated_at = now
        failed += 1
    return failed


def _defer_pending(action: PendingChatAction, *, until: datetime | None = None) -> None:
    delay_until = until or (_utc_now() + timedelta(seconds=retry_delay_seconds()))
    current = getattr(action, "next_attempt_at", None)
    if current is None or current < delay_until:
        action.next_attempt_at = delay_until
    action.updated_at = _utc_now()


async def _accounts_blocking_pending(
    session: AsyncSession,
    action: PendingChatAction,
    membership: AccountChatMembership,
) -> tuple[bool, bool, datetime | None]:
    """Return (ready, lost, rest_until)."""
    needed = _account_ids_from_payload(action)
    if membership.social_account_id not in needed:
        return False, False, None
    rest_until: datetime | None = None
    for account_id in needed:
        row = await get_membership(session, membership.chat_target_id, account_id)
        if row is not None and row.join_status == ChatJoinStatus.BANNED.value:
            action.status = FAILED
            action.last_error = (row.last_join_error or "chat_banned")[:500]
            action.updated_at = _utc_now()
            return False, True, None
        if not await account_is_joined(session, membership.chat_target_id, account_id):
            return False, False, None
        account = await session.get(SocialAccount, account_id)
        if account_should_idle(account):
            nxt = getattr(account, "next_action_at", None)
            if not in_account_active_hours():
                wake = next_wake_at()
                if rest_until is None or wake > rest_until:
                    rest_until = wake
            elif nxt is not None and (rest_until is None or nxt > rest_until):
                rest_until = nxt
    return True, False, rest_until


async def process_pending_for_membership(
    session: AsyncSession,
    membership: AccountChatMembership,
) -> int:
    if membership.join_status != ChatJoinStatus.JOINED.value:
        return 0
    now = _utc_now()
    result = await session.execute(
        select(PendingChatAction).where(
            PendingChatAction.custom_automation_id == membership.custom_automation_id,
            PendingChatAction.chat_target_id == membership.chat_target_id,
            PendingChatAction.status == PENDING,
        )
    )
    done = 0
    for action in result.scalars().all():
        nxt = getattr(action, "next_attempt_at", None)
        if nxt is not None and nxt > now:
            continue
        ready, lost, rest_until = await _accounts_blocking_pending(session, action, membership)
        if lost:
            await session.commit()
            continue
        if rest_until is not None:
            _defer_pending(action, until=rest_until)
            continue
        if not ready:
            continue
        if await _execute_pending(session, action):
            done += 1
    return done


async def process_due_pending_actions(session: AsyncSession, automation_id: int, *, limit: int = 10) -> int:
    now = _utc_now()
    result = await session.execute(
        select(PendingChatAction)
        .where(
            PendingChatAction.custom_automation_id == automation_id,
            PendingChatAction.status == PENDING,
            or_(
                PendingChatAction.next_attempt_at.is_(None),
                PendingChatAction.next_attempt_at <= now,
            ),
        )
        .order_by(PendingChatAction.id.asc())
        .limit(limit)
    )
    done = 0
    for action in result.scalars().all():
        membership = await get_membership(session, action.chat_target_id, action.social_account_id)
        if membership is None or membership.join_status != ChatJoinStatus.JOINED.value:
            continue
        ready, lost, rest_until = await _accounts_blocking_pending(session, action, membership)
        if lost:
            await session.commit()
            continue
        if rest_until is not None:
            _defer_pending(action, until=rest_until)
            await session.commit()
            continue
        if not ready:
            continue
        if await _execute_pending(session, action):
            done += 1
    return done


async def _execute_pending(session: AsyncSession, action: PendingChatAction) -> bool:
    action.attempts += 1
    action.updated_at = _utc_now()
    try:
        ok = await _run_action(session, action)
    except Exception as exc:
        logger.warning("Pending action %s (%s) failed: %s", action.id, action.action_type, exc)
        action.last_error = str(exc)[:500]
        if action.attempts >= 5:
            action.status = FAILED
        else:
            _defer_pending(action)
        await session.commit()
        return False
    if ok:
        action.status = DONE
        action.last_error = None
        action.next_attempt_at = None
        await session.commit()
        return True
    action.last_error = action.last_error or "not_ready"
    if action.attempts >= 5:
        action.status = FAILED
    else:
        _defer_pending(action)
    await session.commit()
    return False


async def _run_action(session: AsyncSession, action: PendingChatAction) -> bool:
    chat = await session.get(ChatTarget, action.chat_target_id)
    if not chat:
        return False
    payload = action.payload or {}
    if action.action_type == "neurocommenting":
        from .chat_inspect_service import ensure_comment_access
        from .neurocommenting_service import _generate_comment, _send_comment

        account = await session.get(SocialAccount, action.social_account_id)
        if not account:
            return False
        probe = await ensure_comment_access(session, chat, account)
        if probe.comments_open is False:
            action.last_error = "comments_closed"
            action.status = FAILED
            return False
        if probe.account_blocked:
            action.last_error = "account_blocked"
            return False
        post_id = int(payload.get("post_id") or str(action.target_id).rsplit(":", 1)[-1])
        post_text = str(payload.get("post_text") or "")
        comment = await _generate_comment(
            session,
            action.custom_automation_id,
            post_text=post_text,
            chat_title=chat.title or "",
        )
        if not comment:
            return False
        return await _send_comment(
            session,
            action.custom_automation_id,
            chat,
            account,
            post_id,
            comment,
            post_text=post_text,
        )
    if action.action_type == "shilling_post":
        from .shilling_service import perform_post_shilling
        from ...alembic.models import CustomAutomation

        automation = await session.get(CustomAutomation, action.custom_automation_id)
        if not automation:
            return False
        post_id = int(payload.get("post_id") or str(action.target_id).rsplit(":", 1)[-1])
        result = await perform_post_shilling(
            session,
            automation,
            chat,
            post_id,
            post_text=str(payload.get("post_text") or ""),
        )
        return result.get("status") == "ok"
    if action.action_type == "shilling_chat":
        from .shilling_service import process_shilling_chat
        from ...alembic.models import CustomAutomation

        automation = await session.get(CustomAutomation, action.custom_automation_id)
        if not automation:
            return False
        result = await process_shilling_chat(
            session,
            automation,
            chat,
            skip_schedule=True,
            delay_seconds=0,
        )
        return result.get("status") == "ok"
    if action.action_type == "dm":
        from .chat_monitoring_service import _send_dm_and_create_lead

        message = await session.get(ChatMessage, int(action.target_id))
        if not message or message.is_processed:
            return True
        classification = payload.get("classification") or {
            "contact_type": "telegram",
            "contact_value": message.sender_username or message.sender_id,
            "confidence": message.trigger_confidence or 0.7,
        }
        return await _send_dm_and_create_lead(
            session, action.custom_automation_id, message, classification
        )
    if action.action_type == "discussion":
        return True
    logger.warning("Unknown pending action type %s", action.action_type)
    return False
