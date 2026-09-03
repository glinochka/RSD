"""Shared deduplication helpers for ChatTarget create/import/discovery."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import ChatTarget


def dedup_keys(invite_link: str | None, external_chat_id: str | None) -> set[str]:
    keys: set[str] = set()
    if external_chat_id:
        raw = str(external_chat_id).strip().lower()
        keys.add(f"id:{raw}")
        if raw.lstrip("-").isdigit():
            keys.add(f"id:{raw.lstrip('-')}")
    if invite_link:
        link = invite_link.strip()
        keys.add(f"link:{link.lower()}")
        try:
            parsed = parse_telegram_chat_ref(link)
            keys.add(f"link:{parsed.canonical.lower()}")
            if parsed.kind == "username":
                keys.add(f"user:{parsed.value.lower()}")
        except TelegramChatRefError:
            pass
    return {key for key in keys if key}


async def find_existing_chat_target(
    session: AsyncSession,
    automation_id: int,
    *,
    invite_link: str | None = None,
    external_chat_id: str | None = None,
    title: str | None = None,
) -> ChatTarget | None:
    keys = dedup_keys(invite_link, external_chat_id)
    if keys:
        result = await session.execute(
            select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
        )
        for chat in result.scalars().all():
            if dedup_keys(chat.invite_link, chat.external_chat_id) & keys:
                return chat

    username = None
    if invite_link:
        try:
            parsed = parse_telegram_chat_ref(invite_link)
            if parsed.kind == "username":
                username = parsed.value
        except TelegramChatRefError:
            pass
    if username:
        needle = f"/{username.lstrip('@').lower()}"
        existing = await session.scalar(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.invite_link.is_not(None),
                ChatTarget.invite_link.ilike(f"%{needle}%"),
            ).limit(1)
        )
        if existing:
            return existing

    if title and not invite_link and not external_chat_id:
        return await session.scalar(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.title == title.strip(),
                ChatTarget.invite_link.is_(None),
                ChatTarget.external_chat_id.is_(None),
            ).limit(1)
        )
    return None


async def load_existing_dedup_keys(session: AsyncSession, automation_id: int) -> set[str]:
    result = await session.execute(
        select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
    )
    keys: set[str] = set()
    for chat in result.scalars().all():
        keys.update(dedup_keys(chat.invite_link, chat.external_chat_id))
    return keys
