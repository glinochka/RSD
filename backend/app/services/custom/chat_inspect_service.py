"""Read-only Telegram inspect: comments, members, last activity.

Accounts pull chat ids from a shared queue so each chat is checked once.
Nothing is written to Telegram (no test comments).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import apply_entity_metadata, entity_chat_type, unwrap_telegram_chat
from .rotation_service import list_alive_session_accounts
from .telegram_account_client import TelegramAccountClient
from .telegram_invite import chat_entity_key
from ...alembic.database import async_session_maker
from ...alembic.models import ChatTarget, SocialAccount

logger = logging.getLogger(__name__)

MAX_PARALLEL_INSPECT = 8
_ACCOUNT_RESTRICTED = {
    "UserBannedInChannelError",
    "UserBlockedError",
    "ChatWriteForbiddenError",
    "UserDeactivatedBanError",
}

_JOBS: dict[int, dict[str, Any]] = {}


@dataclass
class CommentProbe:
    comments_open: bool | None
    members_count: int | None = None
    last_activity_at: datetime | None = None
    error: str | None = None
    retry_account: bool = False
    account_blocked: bool = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _job(automation_id: int) -> dict[str, Any]:
    return _JOBS.setdefault(
        automation_id,
        {
            "status": "idle",
            "total": 0,
            "checked": 0,
            "comments_open": 0,
            "comments_closed": 0,
            "errors": 0,
            "error": None,
        },
    )


def get_inspect_status(automation_id: int) -> dict[str, Any]:
    return dict(_job(automation_id))


def mark_inspect_running(automation_id: int) -> dict[str, Any]:
    state = _job(automation_id)
    if state.get("status") == "running":
        return dict(state)
    state.update(
        {
            "status": "running",
            "total": 0,
            "checked": 0,
            "comments_open": 0,
            "comments_closed": 0,
            "errors": 0,
            "error": None,
        }
    )
    return dict(state)


def is_account_restricted_error(exc: BaseException) -> bool:
    return type(exc).__name__ in _ACCOUNT_RESTRICTED


def derive_comments_open(
    *,
    is_broadcast: bool,
    linked_chat_id: int | None,
    discussion_send_banned: bool | None = None,
    message_has_comment_replies: bool | None = None,
) -> bool | None:
    """Infer comment availability without sending a message."""
    if is_broadcast:
        if linked_chat_id:
            if discussion_send_banned is True:
                return False
            return True
        if message_has_comment_replies is True:
            return True
        return False
    if discussion_send_banned is True:
        return False
    return True


def _message_has_comment_replies(message: Any) -> bool | None:
    replies = getattr(message, "replies", None)
    if replies is None:
        return None
    if getattr(replies, "comments", False):
        return True
    count = getattr(replies, "replies", None)
    if count:
        return True
    return False


def _send_banned(rights: Any) -> bool | None:
    if rights is None:
        return None
    return bool(getattr(rights, "send_messages", False))


async def probe_comments_readonly(client: TelegramAccountClient, chat_target: ChatTarget) -> CommentProbe:
    """Inspect a chat/channel via Telegram API without writing."""
    try:
        entity = await client.get_entity(chat_entity_key(chat_target))
    except Exception as exc:
        if is_account_restricted_error(exc):
            return CommentProbe(
                comments_open=None,
                error=str(exc)[:255],
                retry_account=True,
                account_blocked=True,
            )
        name = type(exc).__name__
        if name in {"ChannelPrivateError", "ChatAdminRequiredError"}:
            return CommentProbe(comments_open=False, error=str(exc)[:255])
        return CommentProbe(comments_open=None, error=str(exc)[:255], retry_account=True)

    apply_entity_metadata(chat_target, entity)
    target = unwrap_telegram_chat(entity)
    is_broadcast = (entity_chat_type(entity) == "channel") or bool(getattr(target, "broadcast", False))
    members = getattr(target, "participants_count", None)
    linked_id = None
    discussion_send_banned = _send_banned(getattr(target, "default_banned_rights", None))
    last_activity = None
    message_replies = None

    try:
        from telethon.tl.functions.channels import GetFullChannelRequest

        full = await client(GetFullChannelRequest(target))
        full_chat = getattr(full, "full_chat", None)
        if full_chat is not None:
            members = getattr(full_chat, "participants_count", None) or members
            linked_id = getattr(full_chat, "linked_chat_id", None)
            if discussion_send_banned is None:
                discussion_send_banned = _send_banned(getattr(full_chat, "default_banned_rights", None))
            if linked_id:
                for nested in getattr(full, "chats", None) or []:
                    if getattr(nested, "id", None) == linked_id:
                        nested_banned = _send_banned(getattr(nested, "default_banned_rights", None))
                        if nested_banned is not None:
                            discussion_send_banned = nested_banned
                        break
    except Exception as exc:
        if is_account_restricted_error(exc):
            return CommentProbe(
                comments_open=None,
                members_count=int(members) if members else None,
                error=str(exc)[:255],
                retry_account=True,
                account_blocked=True,
            )
        logger.info("GetFullChannel failed for chat %s: %s", chat_target.id, exc)

    try:
        history = await client.client.get_messages(entity, limit=1)
        if history:
            msg = history[0]
            date = getattr(msg, "date", None)
            if date is not None:
                last_activity = date.replace(tzinfo=None) if getattr(date, "tzinfo", None) else date
            message_replies = _message_has_comment_replies(msg)
    except Exception as exc:
        if is_account_restricted_error(exc):
            return CommentProbe(
                comments_open=None,
                members_count=int(members) if members else None,
                last_activity_at=last_activity,
                error=str(exc)[:255],
                retry_account=True,
                account_blocked=True,
            )
        logger.info("get_messages failed for chat %s: %s", chat_target.id, exc)

    comments_open = derive_comments_open(
        is_broadcast=is_broadcast,
        linked_chat_id=linked_id,
        discussion_send_banned=discussion_send_banned,
        message_has_comment_replies=message_replies,
    )
    return CommentProbe(
        comments_open=comments_open,
        members_count=int(members) if members else None,
        last_activity_at=last_activity,
    )


async def ensure_comment_access(
    session: AsyncSession,
    chat_target: ChatTarget,
    account: SocialAccount,
) -> CommentProbe:
    """Live read-only check used before an LLM call."""
    if chat_target.comments_open is False:
        return CommentProbe(comments_open=False, error=chat_target.comments_check_error)
    if not account.session_file_path and not getattr(account, "encrypted_session", None):
        return CommentProbe(comments_open=None, error="no session", retry_account=True, account_blocked=True)
    try:
        async with TelegramAccountClient.for_account(account) as client:
            probe = await probe_comments_readonly(client, chat_target)
    except Exception as exc:
        if is_account_restricted_error(exc):
            return CommentProbe(comments_open=None, error=str(exc)[:255], retry_account=True, account_blocked=True)
        return CommentProbe(comments_open=None, error=str(exc)[:255], retry_account=True)

    chat_target.comments_open = probe.comments_open
    if probe.members_count:
        chat_target.members_count = probe.members_count
    if probe.last_activity_at:
        chat_target.last_activity_at = probe.last_activity_at
    chat_target.comments_checked_at = _utc_now()
    chat_target.comments_check_error = probe.error
    chat_target.updated_at = _utc_now()
    await session.commit()
    return probe


def _apply_probe(chat: ChatTarget, probe: CommentProbe) -> None:
    now = _utc_now()
    if probe.comments_open is not None:
        chat.comments_open = probe.comments_open
    if probe.members_count:
        chat.members_count = probe.members_count
    if probe.last_activity_at:
        chat.last_activity_at = probe.last_activity_at
    chat.comments_checked_at = now
    chat.comments_check_error = probe.error
    chat.updated_at = now


async def _inspect_worker(
    automation_id: int,
    account: SocialAccount,
    queue: asyncio.Queue[int],
    session_factory,
) -> None:
    try:
        async with TelegramAccountClient.for_account(account) as client:
            while True:
                try:
                    chat_id = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                async with session_factory() as session:
                    chat = await session.get(ChatTarget, chat_id)
                    if not chat or chat.custom_automation_id != automation_id:
                        queue.task_done()
                        continue
                    try:
                        probe = await probe_comments_readonly(client, chat)
                    except Exception as exc:
                        probe = CommentProbe(
                            comments_open=None,
                            error=str(exc)[:255],
                            retry_account=is_account_restricted_error(exc),
                            account_blocked=is_account_restricted_error(exc),
                        )
                    if probe.retry_account:
                        await queue.put(chat_id)
                        queue.task_done()
                        return
                    _apply_probe(chat, probe)
                    await session.commit()
                    state = _job(automation_id)
                    state["checked"] = int(state.get("checked") or 0) + 1
                    if probe.comments_open is True:
                        state["comments_open"] = int(state.get("comments_open") or 0) + 1
                    elif probe.comments_open is False:
                        state["comments_closed"] = int(state.get("comments_closed") or 0) + 1
                    elif probe.error:
                        state["errors"] = int(state.get("errors") or 0) + 1
                queue.task_done()
    except Exception as exc:
        logger.warning("Inspect worker account %s stopped: %s", account.id, exc)


async def inspect_chats_comments(
    automation_id: int,
    *,
    force: bool = False,
    session_factory=None,
) -> dict[str, Any]:
    factory = session_factory or async_session_maker
    state = _job(automation_id)

    async with factory() as session:
        accounts = await list_alive_session_accounts(session, automation_id)
        stmt = select(ChatTarget.id).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.is_active.is_(True),
        )
        if not force:
            stmt = stmt.where(ChatTarget.comments_checked_at.is_(None))
        chat_ids = [row[0] for row in (await session.execute(stmt)).all()]

    state.update(
        {
            "status": "running",
            "total": len(chat_ids),
            "checked": 0,
            "comments_open": 0,
            "comments_closed": 0,
            "errors": 0,
            "error": None,
        }
    )
    if not chat_ids:
        state["status"] = "completed"
        return dict(state)
    if not accounts:
        state["status"] = "error"
        state["error"] = "Нет живых аккаунтов для проверки"
        return dict(state)

    queue: asyncio.Queue[int] = asyncio.Queue()
    for chat_id in chat_ids:
        queue.put_nowait(chat_id)

    workers = accounts[: min(len(accounts), len(chat_ids), MAX_PARALLEL_INSPECT)]
    try:
        await asyncio.gather(*[_inspect_worker(automation_id, account, queue, factory) for account in workers])
        leftover = []
        while True:
            try:
                leftover.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if leftover:
            state["errors"] = int(state.get("errors") or 0) + len(leftover)
            async with factory() as session:
                for chat_id in leftover:
                    chat = await session.get(ChatTarget, chat_id)
                    if not chat:
                        continue
                    chat.comments_checked_at = _utc_now()
                    chat.comments_check_error = "Не осталось аккаунтов для проверки"
                    chat.updated_at = _utc_now()
                await session.commit()
        state["status"] = "completed"
        async with factory() as session:
            open_count = await session.scalar(
                select(func.count(ChatTarget.id)).where(
                    ChatTarget.custom_automation_id == automation_id,
                    ChatTarget.comments_open.is_(True),
                )
            )
            closed_count = await session.scalar(
                select(func.count(ChatTarget.id)).where(
                    ChatTarget.custom_automation_id == automation_id,
                    ChatTarget.comments_open.is_(False),
                )
            )
            state["comments_open"] = int(open_count or 0)
            state["comments_closed"] = int(closed_count or 0)
    except Exception as exc:
        logger.exception("Comment inspect failed for automation %s: %s", automation_id, exc)
        state["status"] = "error"
        state["error"] = str(exc)[:255]
    return dict(state)


async def run_inspect_comments(automation_id: int, force: bool = False) -> dict[str, Any]:
    return await inspect_chats_comments(automation_id, force=force)
