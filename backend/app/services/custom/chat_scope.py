"""How modules apply to a chat target: groups vs channels, pause, own posts."""
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AccountPool,
    AutomationActionLog,
    ChatMode,
    ChatTarget,
    PoolAccount,
    SocialAccount,
)

CHANNEL_TYPES = {"channel", "broadcast"}
SHILLING_ACTIONS = ("shilling_chat", "shilling_post")


def is_paused(chat_target: ChatTarget) -> bool:
    if not chat_target.is_active:
        return True
    return (chat_target.mode or "").strip().lower() == ChatMode.INACTIVE.value


def is_broadcast_channel(chat_target: ChatTarget) -> bool:
    return (chat_target.chat_type or "").strip().lower() in CHANNEL_TYPES


def is_group_chat(chat_target: ChatTarget) -> bool:
    """Lead intercept, chat shilling and discussion run in groups, not channels."""
    return not is_broadcast_channel(chat_target)


def entity_chat_type(entity: Any) -> str | None:
    target = entity
    chats = getattr(entity, "chats", None)
    if chats:
        target = chats[0]
    if target is None:
        return None
    if getattr(target, "broadcast", False):
        return "channel"
    return "chat"


def apply_entity_metadata(chat_target: ChatTarget, entity: Any) -> None:
    target = entity
    chats = getattr(entity, "chats", None)
    if chats:
        target = chats[0]
    if target is None:
        return
    chat_id = getattr(target, "id", None)
    if chat_id:
        chat_target.external_chat_id = str(chat_id)
    title = getattr(target, "title", None) or getattr(target, "username", None)
    if title and not chat_target.title:
        chat_target.title = str(title)[:255]
    detected = entity_chat_type(entity)
    if detected:
        chat_target.chat_type = detected


async def load_own_sender_keys(session: AsyncSession, automation_id: int) -> set[str]:
    result = await session.execute(
        select(SocialAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .join(AccountPool, PoolAccount.account_pool_id == AccountPool.id)
        .where(AccountPool.custom_automation_id == automation_id)
    )
    keys: set[str] = set()
    for account in result.scalars().all():
        if account.username:
            keys.add(account.username.strip().lstrip("@").lower())
        if account.display_name:
            keys.add(account.display_name.strip().lower())
        if account.phone_number:
            keys.add(account.phone_number.strip())
    return keys


async def load_shilling_message_ids(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
) -> set[str]:
    result = await session.execute(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type.in_(SHILLING_ACTIONS),
            AutomationActionLog.result == "success",
        )
    )
    ids: set[str] = set()
    chat_id = str(chat_target_id)
    prefix = f"{chat_target_id}:"
    for log in result.scalars().all():
        target = str(log.target_id or "")
        payload = log.payload or {}
        belongs = (
            target == chat_id
            or target.startswith(prefix)
            or payload.get("chat_target_id") in (chat_target_id, chat_id)
        )
        if not belongs:
            continue
        for key in ("setup_message_id", "reply_message_id"):
            value = payload.get(key)
            if value is not None:
                ids.add(str(value))
    return ids


def message_is_own_activity(
    data: dict[str, Any],
    own_keys: Iterable[str],
    shilling_message_ids: Iterable[str],
) -> bool:
    keys = {str(item).strip().lower() for item in own_keys if item}
    shill_ids = {str(item) for item in shilling_message_ids if item}
    external_id = str(data.get("external_message_id") or "")
    if external_id and external_id in shill_ids:
        return True
    username = str(data.get("sender_username") or "").strip().lstrip("@").lower()
    if username and username in keys:
        return True
    sender_name = str(data.get("sender_name") or "").strip().lower()
    if sender_name and sender_name in keys:
        return True
    sender_id = str(data.get("sender_id") or "").strip()
    if sender_id and sender_id.lower() in keys:
        return True
    return False
