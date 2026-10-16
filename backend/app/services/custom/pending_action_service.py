"""Queue an action until the responsible account has joined the chat, then run it."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_should_idle, next_target_wake_at, retry_delay_seconds
from .chat_membership_service import account_is_joined, get_membership, queue_actor_for_chat
from ...alembic.models import (
    AccountChatMembership,
    ChatJoinStatus,
    ChatMessage,
    ChatTarget,
    PendingChatAction,
    PendingChatActionStatus,
    PoolAccount,
    SocialAccount,
)

logger = logging.getLogger(__name__)

PENDING = PendingChatActionStatus.PENDING.value
DONE = PendingChatActionStatus.DONE.value
FAILED = PendingChatActionStatus.FAILED.value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pending_account_block(account: SocialAccount | None, action_type: str) -> tuple[bool, datetime | None]:
    """Queued comments already waited the post delay — do not park them until tomorrow.

    Idle gaps / short target rest still block new work, but a due neurocomment
    should send. Night, flood, settle, and day-1 accounts still wait.
    """
    from .account_pacing import (
        account_in_settle_rest,
        account_is_flood_quarantined,
        account_may_do_work,
        farm_overlap_active_hours,
        next_wake_at,
    )

    if account is None:
        return True, None
    if getattr(account, "is_banned", False) or getattr(account, "is_frozen", False):
        return True, None
    if action_type != "neurocommenting":
        if account_should_idle(account):
            wake = next_target_wake_at(account=account)
            nxt = getattr(account, "next_action_at", None)
            if nxt is not None and nxt > wake:
                wake = nxt
            return True, wake
        return False, None
    if account_in_settle_rest(account) or not account_may_do_work(account):
        return True, next_wake_at(account=account)
    if account_is_flood_quarantined(account):
        return True, getattr(account, "flood_quarantined_until", None)
    if not farm_overlap_active_hours():
        return True, next_wake_at(account=account)
    from .account_pacing import account_is_resting

    if account_is_resting(account):
        return True, getattr(account, "next_action_at", None)
    return False, None


_PENDING_FAIL_RU = {
    "not_ready": "ещё не готов",
    "send_failed": "Telegram отклонил отправку",
    "no_discussion": "у поста нет ветки комментариев",
    "discussion_private": "не смог зайти в чат комментариев",
    "comments_closed": "комментарии закрыты",
    "empty_comment": "пустой текст комментария",
    "account_blocked": "аккаунт не может писать в канал",
    "account_cannot_write": "аккаунт не может писать",
    "no_session": "нет файла сессии",
}


async def _unstick_comment_queue(session: AsyncSession, automation_id: int) -> None:
    """Retry comments that failed as not_ready or were parked until the next morning."""
    from .chat_membership_service import reopen_false_comment_blackbox

    await reopen_false_comment_blackbox(session, automation_id)
    now = _utc_now()
    cutoff = now - timedelta(hours=36)
    parked_after = now + timedelta(hours=2)
    rows = (
        await session.execute(
            select(PendingChatAction).where(
                PendingChatAction.custom_automation_id == automation_id,
                PendingChatAction.action_type == "neurocommenting",
                PendingChatAction.updated_at >= cutoff,
                PendingChatAction.status.in_((PENDING, FAILED)),
            )
        )
    ).scalars().all()
    changed = False
    for action in rows:
        err = str(action.last_error or "")
        parked = action.next_attempt_at is not None and action.next_attempt_at > parked_after
        generation_miss = err in {"", "not_ready", "empty_comment"}
        if action.status == FAILED and generation_miss:
            action.status = PENDING
            action.attempts = 0
            action.next_attempt_at = None
            action.last_error = None
            action.updated_at = now
            changed = True
        elif action.status == PENDING and parked:
            action.next_attempt_at = None
            action.updated_at = now
            changed = True
    if changed:
        await session.commit()


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
        existing.attempts = 0
        existing.last_error = None
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
        blocked, until = _pending_account_block(account, action.action_type)
        if blocked:
            if rest_until is None or (until is not None and until > rest_until):
                rest_until = until
            return False, False, rest_until
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


async def _pending_action_runnable(
    session: AsyncSession,
    action: PendingChatAction,
    membership: AccountChatMembership | None,
) -> tuple[bool, bool, datetime | None]:
    """Return (ready, lost, rest_until). Public channel comments do not need a JOINED row."""
    if membership is not None and membership.join_status == ChatJoinStatus.JOINED.value:
        return await _accounts_blocking_pending(session, action, membership)
    from .chat_scope import is_public_readable

    chat = await session.get(ChatTarget, action.chat_target_id)
    if action.action_type == "neurocommenting" and chat is not None and is_public_readable(chat):
        account = await session.get(SocialAccount, action.social_account_id)
        blocked, until = _pending_account_block(account, action.action_type)
        if blocked:
            return False, False, until
        return True, False, None
    return False, False, None


async def process_due_pending_actions(
    session: AsyncSession,
    automation_id: int,
    *,
    limit: int = 40,
    action_types: Iterable[str] | None = None,
) -> int:
    wanted = [str(item) for item in (action_types or []) if item]
    if not wanted or "neurocommenting" in wanted:
        await _unstick_comment_queue(session, automation_id)
    now = _utc_now()
    filters = [
        PendingChatAction.custom_automation_id == automation_id,
        PendingChatAction.status == PENDING,
        or_(
            PendingChatAction.next_attempt_at.is_(None),
            PendingChatAction.next_attempt_at <= now,
        ),
    ]
    if wanted:
        filters.append(PendingChatAction.action_type.in_(wanted))
    result = await session.execute(
        select(PendingChatAction).where(*filters).order_by(PendingChatAction.id.asc()).limit(limit)
    )
    done = 0
    for action in result.scalars().all():
        membership = await get_membership(session, action.chat_target_id, action.social_account_id)
        joined = membership if membership is not None and membership.join_status == ChatJoinStatus.JOINED.value else None
        ready, lost, rest_until = await _pending_action_runnable(session, action, joined)
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
    if action.action_type == "neurocommenting" and (
        action.attempts <= 1 or action.status == FAILED
    ):
        from .job_service import log_active

        detail = _PENDING_FAIL_RU.get(action.last_error or "", action.last_error or "not_ready")
        await log_active(
            action.custom_automation_id,
            "neurocommenting",
            f"Отложенный комментарий не ушёл: {detail}",
            level="error",
        )
    return False


async def _run_action(session: AsyncSession, action: PendingChatAction) -> bool:
    chat = await session.get(ChatTarget, action.chat_target_id)
    if not chat:
        action.last_error = "chat_missing"
        return False
    payload = action.payload or {}
    account = await session.get(SocialAccount, action.social_account_id)
    if account is not None:
        from .account_roles import account_matches_action

        pool = await session.scalar(
            select(PoolAccount).where(
                PoolAccount.social_account_id == account.id,
                PoolAccount.custom_automation_id == action.custom_automation_id,
            )
        )
        action_key = "commenting" if action.action_type == "neurocommenting" else action.action_type
        if not account_matches_action(pool, account, action_key):
            action.last_error = "silent_account"
            action.status = FAILED
            return False
    if action.action_type == "neurocommenting":
        from .chat_inspect_service import ensure_comment_access
        from .chat_scope import count_target_actions_today
        from .neurocommenting_service import _generate_comment, _send_comment

        account = await session.get(SocialAccount, action.social_account_id)
        if not account:
            action.last_error = "account_missing"
            return False
        if getattr(account, "is_channel_banned", False) or getattr(account, "is_frozen", False):
            from .chat_membership_service import get_reader_account

            writer = await get_reader_account(session, chat, require_writable=True)
            if not writer:
                action.last_error = "account_cannot_write"
                action.status = FAILED
                return False
            account = writer
            action.social_account_id = writer.id
        daily_cap = int(getattr(chat, "max_daily_target_actions", 3) or 3)
        if await count_target_actions_today(session, action.custom_automation_id, chat.id) >= daily_cap:
            action.last_error = "chat_daily_target_limit"
            from .account_pacing import next_target_wake_at
            _defer_pending(action, until=next_target_wake_at(account=account))
            return False
        # Drop the pending-row lock before Telegram / DeepSeek. Two loops
        # (join + sessions) otherwise wait on each other for hours.
        await session.commit()
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
        try:
            prompt_id = int(payload["prompt_id"]) if payload.get("prompt_id") else None
        except (TypeError, ValueError):
            prompt_id = None
        comment = await _generate_comment(
            session,
            action.custom_automation_id,
            post_text=post_text,
            chat_title=chat.title or "",
            prompt_id=prompt_id,
        )
        if not comment:
            action.last_error = "empty_comment"
            return False
        send_error = await _send_comment(
            session,
            action.custom_automation_id,
            chat,
            account,
            post_id,
            comment,
            post_text=post_text,
        )
        if send_error:
            action.last_error = send_error
            if send_error in {"no_discussion", "comments_closed", "discussion_private"}:
                action.status = FAILED
            return False
        from .job_service import load_active_job_params
        from .module_delays import action_gap_seconds
        from .account_pacing import schedule_account_target_rest

        cfg = await load_active_job_params(session, action.custom_automation_id, "neurocommenting") or {}
        schedule_account_target_rest(account, seconds=action_gap_seconds(cfg))
        return True
    if action.action_type == "shilling_post":
        from .chat_scope import count_target_actions_today
        from .shilling_service import perform_post_shilling
        from ...alembic.models import CustomAutomation

        automation = await session.get(CustomAutomation, action.custom_automation_id)
        if not automation:
            return False
        daily_cap = int(getattr(chat, "max_daily_target_actions", 3) or 3)
        if await count_target_actions_today(session, action.custom_automation_id, chat.id) >= daily_cap:
            action.last_error = "chat_daily_target_limit"
            _defer_pending(action, until=next_target_wake_at())
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
        # Previously a silent no-op.  Now we actually send the queued reply.
        from pathlib import Path
        from .discussion_service import _generate_reply, _send_reply
        from .telegram_account_client import TelegramAccountClient
        from .telegram_invite import chat_entity_key
        from .account_pacing import account_humanization_should_idle  # discussion is a target action
        from .account_pacing import account_should_idle
        from ...config import settings

        account = await session.get(SocialAccount, action.social_account_id)
        if not account or not account.is_active or account.is_banned:
            return False
        if account_should_idle(account):
            return False

        message_id = int(payload.get("message_id") or 0)
        message_text = str(payload.get("message_text") or "")
        chat_title = str(payload.get("chat_title") or "")
        if not message_id:
            logger.warning("Discussion pending action %s missing message_id", action.id)
            return False

        session_path = Path(settings.MEDIA_ROOT).resolve() / (account.session_file_path or "")
        if not session_path.exists():
            return False

        reply_text = await _generate_reply(
            session,
            action.custom_automation_id,
            message_text=message_text,
            chat_title=chat_title,
        )
        if not reply_text:
            return False

        # Build a minimal message-like object so _send_reply can .id it
        class _MinimalMsg:
            id = message_id
            text = message_text
            sender = None
            reply_to_msg_id = None
            reply_to = None

        try:
            return await _send_reply(
                session,
                action.custom_automation_id,
                chat,
                account,
                _MinimalMsg(),
                reply_text,
            )
        except Exception as exc:
            logger.warning("Discussion pending _run_action failed: %s", exc)
            return False

    logger.warning("Unknown pending action type %s", action.action_type)
    return False
