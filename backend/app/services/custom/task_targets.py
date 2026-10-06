"""Resolve task chat/user pools from folders selected on a module."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import ChatTarget, UserFolderMember


def as_int_list(raw: Any) -> list[int]:
    items: list[int] = []
    seen: set[int] = set()
    for value in raw or []:
        try:
            ident = int(value)
        except (TypeError, ValueError):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ident)
    return items


def has_chat_pool(settings: dict[str, Any] | None) -> bool:
    data = settings or {}
    return bool(
        as_int_list(data.get("chat_ids"))
        or as_int_list(data.get("folder_ids"))
        or as_int_list(data.get("channel_ids"))
    )


async def resolve_task_chat_ids(
    session: AsyncSession,
    automation_id: int,
    settings: dict[str, Any] | None,
) -> list[int]:
    data = settings or {}
    ids = as_int_list(data.get("chat_ids"))
    ids.extend(as_int_list(data.get("channel_ids")))
    folder_ids = as_int_list(data.get("folder_ids"))
    if folder_ids:
        extra = (
            await session.execute(
                select(ChatTarget.id).where(
                    ChatTarget.custom_automation_id == automation_id,
                    ChatTarget.folder_id.in_(folder_ids),
                    ChatTarget.is_active.is_(True),
                    ChatTarget.black_boxed_at.is_(None),
                )
            )
        ).scalars().all()
        ids.extend(int(item) for item in extra)
    return list(dict.fromkeys(ids))


async def resolve_user_folder_peers(
    session: AsyncSession,
    automation_id: int,
    settings: dict[str, Any] | None,
    *,
    usernames_only: bool = False,
) -> list[str]:
    folder_ids = as_int_list((settings or {}).get("user_folder_ids"))
    if not folder_ids:
        return []
    rows = (
        await session.execute(
            select(UserFolderMember).where(
                UserFolderMember.custom_automation_id == automation_id,
                UserFolderMember.user_folder_id.in_(folder_ids),
            )
        )
    ).scalars().all()
    peers: list[str] = []
    seen: set[str] = set()
    for row in rows:
        username = (row.username or "").strip().lstrip("@")
        if username:
            token = f"@{username}"
        elif usernames_only:
            continue
        elif row.telegram_user_id:
            token = str(row.telegram_user_id)
        else:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        peers.append(token)
    return peers
