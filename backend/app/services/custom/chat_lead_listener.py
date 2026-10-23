"""Live group-message listener for lead intercept on keep-alive sessions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import CustomAutomation
from .channel_post_listener import _find_task_chat

logger = logging.getLogger(__name__)

_HANDLER_FLAG = "_rsd_lead_listener"


def is_group_user_message(event: Any) -> bool:
    message = getattr(event, "message", None)
    if message is None:
        return False
    if getattr(event, "out", False) or getattr(message, "out", False):
        return False
    if not (getattr(message, "text", None) or "").strip():
        return False
    if getattr(message, "post", False):
        return False
    if bool(getattr(event, "is_channel", False)) and not bool(getattr(event, "is_group", False)):
        return False
    return bool(getattr(event, "is_group", False) or getattr(event, "is_channel", False))


def attach_lead_listener(wrapper: Any, *, account_id: int, automation_id: int) -> bool:
    client = getattr(wrapper, "client", None)
    if client is None:
        return False
    if getattr(client, _HANDLER_FLAG, False):
        return False
    try:
        from telethon import events
    except Exception:
        return False

    async def _on_new_message(event: Any) -> None:
        if not is_group_user_message(event):
            return
        message = getattr(event, "message", None)
        sender = getattr(message, "sender", None)
        if sender is None:
            getter = getattr(event, "get_sender", None)
            if callable(getter):
                try:
                    sender = await getter()
                except Exception:
                    sender = None
        try:
            await handle_listened_group_message(
                automation_id=automation_id,
                account_id=account_id,
                chat_id=getattr(event, "chat_id", None),
                username=getattr(getattr(event, "chat", None), "username", None),
                message_id=getattr(message, "id", None),
                text=getattr(message, "text", None) or "",
                sent_at=getattr(message, "date", None),
                sender_id=getattr(sender, "id", None),
                sender_username=getattr(sender, "username", None),
                sender_name=" ".join(
                    filter(
                        None,
                        [
                            getattr(sender, "first_name", None),
                            getattr(sender, "last_name", None),
                        ],
                    )
                ).strip(),
            )
        except Exception:
            logger.exception(
                "Lead intercept listener failed automation=%s account=%s",
                automation_id,
                account_id,
            )

    client.add_event_handler(_on_new_message, events.NewMessage(incoming=True))
    setattr(client, _HANDLER_FLAG, True)
    logger.info("Listening for lead intercept automation=%s account=%s", automation_id, account_id)
    return True


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


async def handle_listened_group_message(
    *,
    automation_id: int,
    account_id: int,
    chat_id: int | None,
    username: str | None,
    message_id: Any,
    text: str,
    sent_at: datetime | None,
    sender_id: Any,
    sender_username: str | None,
    sender_name: str | None,
) -> dict[str, Any] | None:
    del account_id
    if not str(text or "").strip() or not message_id:
        return None
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if automation is None or not automation.is_chat_monitoring_enabled:
            return None
        chat = await _find_task_chat(session, automation_id, chat_id=chat_id, username=username)
        if chat is None:
            return None
        from .chat_monitoring_module_service import runtime_monitor_cfg
        from .chat_scope import is_group_chat, is_paused
        from .task_targets import load_work_pool

        if is_paused(chat) or not is_group_chat(chat):
            return None
        cfg = runtime_monitor_cfg(automation)
        pool = await load_work_pool(session, automation_id, cfg, task_key="chat_monitoring")
        if pool.active and chat.id not in pool.chat_ids:
            return None
        saved = await _persist_and_maybe_process(
            session,
            chat,
            {
                "external_message_id": str(message_id),
                "external_chat_id": str(chat_id or chat.external_chat_id or ""),
                "sender_id": str(sender_id) if sender_id else None,
                "sender_username": sender_username,
                "sender_name": sender_name or sender_username,
                "text": text,
                "sent_at": _naive_utc(sent_at),
            },
        )
        return {"status": "saved" if saved else "skip"}


async def _persist_and_maybe_process(session: AsyncSession, chat: Any, data: dict[str, Any]) -> bool:
    from .chat_monitoring_service import process_unprocessed_messages, save_chat_message

    row = await save_chat_message(session, chat, data)
    if row is None:
        return False
    try:
        await process_unprocessed_messages(session, chat.custom_automation_id)
    except Exception:
        logger.debug("Lead intercept process after listen skipped", exc_info=True)
    return True
