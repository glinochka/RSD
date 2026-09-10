"""Folders of chats/channels created from Excel imports."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import ChatFolder, ChatTarget


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def folder_name_from_filename(filename: str | None) -> str:
    stem = Path(filename or "").name
    stem = Path(stem).stem.strip()
    stem = re.sub(r"^\d{9,}_", "", stem).strip()
    return (stem or "Импорт")[:255]


async def get_or_create_folder(
    session: AsyncSession,
    automation_id: int,
    name: str,
) -> ChatFolder:
    label = (name or "Импорт").strip()[:255] or "Импорт"
    folder = await session.scalar(
        select(ChatFolder).where(
            ChatFolder.custom_automation_id == automation_id,
            ChatFolder.name == label,
        )
    )
    if folder:
        return folder
    now = _utc_now()
    folder = ChatFolder(
        custom_automation_id=automation_id,
        name=label,
        created_at=now,
        updated_at=now,
    )
    session.add(folder)
    await session.flush()
    return folder


async def list_folders(session: AsyncSession, automation_id: int) -> list[tuple[ChatFolder, int]]:
    rows = (
        await session.execute(
            select(ChatFolder, func.count(ChatTarget.id))
            .outerjoin(ChatTarget, ChatTarget.folder_id == ChatFolder.id)
            .where(ChatFolder.custom_automation_id == automation_id)
            .group_by(ChatFolder.id)
            .order_by(ChatFolder.created_at.desc())
        )
    ).all()
    return [(folder, int(count or 0)) for folder, count in rows]


async def delete_folder(session: AsyncSession, automation_id: int, folder_id: int) -> bool:
    folder = await session.get(ChatFolder, folder_id)
    if not folder or folder.custom_automation_id != automation_id:
        return False
    chats = (
        await session.execute(select(ChatTarget).where(ChatTarget.folder_id == folder.id))
    ).scalars().all()
    for chat in chats:
        await session.delete(chat)
    await session.delete(folder)
    await session.commit()
    return True
