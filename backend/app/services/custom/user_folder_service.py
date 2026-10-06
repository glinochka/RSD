"""Folders of parsed users: one parser job → one reusable target list."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import ParserUser, UserFolder, UserFolderMember
from .account_pacing import moscow_now


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _folder_label(name: str | None) -> str:
    stamp = moscow_now().strftime("%d.%m %H:%M:%S")
    raw = (name or "").strip()[:255]
    return raw or f"Парсинг {stamp}"


async def list_user_folders(session: AsyncSession, automation_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(UserFolder, func.count(UserFolderMember.id))
            .outerjoin(UserFolderMember, UserFolderMember.user_folder_id == UserFolder.id)
            .where(UserFolder.custom_automation_id == automation_id)
            .group_by(UserFolder.id)
            .order_by(UserFolder.created_at.desc())
        )
    ).all()
    return [
        {
            "id": folder.id,
            "name": folder.name,
            "source": folder.source,
            "count": int(count or 0),
            "created_at": folder.created_at.isoformat() if folder.created_at else None,
        }
        for folder, count in rows
    ]


async def snapshot_parser_users(
    session: AsyncSession,
    automation_id: int,
    *,
    name: str | None = None,
    job_id: int | None = None,
) -> UserFolder | None:
    users = (
        await session.execute(
            select(ParserUser).where(ParserUser.custom_automation_id == automation_id)
        )
    ).scalars().all()
    if not users:
        return None
    label = _folder_label(name)
    if job_id:
        try:
            label = f"{label} · #{int(job_id)}"[:255]
        except (TypeError, ValueError):
            pass
    base = label
    suffix = 2
    while await session.scalar(
        select(UserFolder.id).where(
            UserFolder.custom_automation_id == automation_id,
            UserFolder.name == label,
        )
    ):
        label = f"{base} · {suffix}"[:255]
        suffix += 1
    now = _utc_now()
    folder = UserFolder(
        custom_automation_id=automation_id,
        name=label[:255],
        source="parser",
        job_id=job_id,
        created_at=now,
        updated_at=now,
    )
    session.add(folder)
    await session.flush()
    seen: set[int] = set()
    for user in users:
        uid = int(user.telegram_user_id or 0)
        if not uid or uid in seen:
            continue
        seen.add(uid)
        session.add(
            UserFolderMember(
                user_folder_id=folder.id,
                custom_automation_id=automation_id,
                telegram_user_id=uid,
                username=(user.username or None),
                first_name=user.first_name,
                last_name=user.last_name,
                source_title=user.source_title,
                created_at=now,
            )
        )
    folder.updated_at = now
    return folder
