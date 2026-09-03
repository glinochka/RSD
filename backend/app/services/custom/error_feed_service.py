"""Error feed for /custom automations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog, ChatTarget, SocialAccount

ERROR_RESULTS = ("error", "banned", "rate_limited")

ACTION_LABELS = {
    "join_chat": "Вступление в чат",
    "neurocommenting": "Нейрокомментинг",
    "shilling_chat": "Шиллинг в чате",
    "shilling_post": "Шиллинг в комментариях",
    "discussion": "Цифровой след",
    "dm": "Перехват заявок",
    "dmp_outreach": "DMP.one",
    "lead_warmup": "Прогрев лида",
    "inbound_dm": "Входящее ЛС",
    "post_engagement": "Пост в канале",
    "chat_import": "Импорт чатов",
}


def _account_label(account: SocialAccount | None) -> str | None:
    if not account:
        return None
    return account.display_name or account.username or account.phone_number or f"#{account.id}"


async def list_error_feed(
    session: AsyncSession,
    automation_id: int,
    *,
    action_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    filters = [
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.result.in_(ERROR_RESULTS),
    ]
    if action_type:
        filters.append(AutomationActionLog.action_type == action_type)
    from sqlalchemy import func

    total = await session.scalar(select(func.count()).select_from(AutomationActionLog).where(*filters))
    result = await session.execute(
        select(AutomationActionLog)
        .where(*filters)
        .order_by(AutomationActionLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = list(result.scalars().all())
    account_ids = {log.social_account_id for log in logs}
    accounts: dict[int, SocialAccount] = {}
    if account_ids:
        rows = await session.execute(select(SocialAccount).where(SocialAccount.id.in_(account_ids)))
        accounts = {row.id: row for row in rows.scalars().all()}

    chat_ids: set[int] = set()
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        raw = payload.get("chat_target_id")
        if raw is not None:
            try:
                chat_ids.add(int(raw))
            except (TypeError, ValueError):
                pass
        if log.target_type == "chat" and log.target_id:
            try:
                chat_ids.add(int(log.target_id))
            except (TypeError, ValueError):
                pass
    chats: dict[int, ChatTarget] = {}
    if chat_ids:
        rows = await session.execute(select(ChatTarget).where(ChatTarget.id.in_(chat_ids)))
        chats = {row.id: row for row in rows.scalars().all()}

    items: list[dict[str, Any]] = []
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        chat_id = payload.get("chat_target_id")
        chat = None
        if chat_id is not None:
            try:
                chat = chats.get(int(chat_id))
            except (TypeError, ValueError):
                chat = None
        if chat is None and log.target_type == "chat" and log.target_id:
            try:
                chat = chats.get(int(log.target_id))
            except (TypeError, ValueError):
                chat = None
        account = accounts.get(log.social_account_id)
        items.append(
            {
                "id": log.id,
                "created_at": log.created_at,
                "action_type": log.action_type,
                "action_label": ACTION_LABELS.get(log.action_type, log.action_type),
                "result": log.result,
                "error_message": log.error_message,
                "target_id": log.target_id,
                "target_type": log.target_type,
                "account": _account_label(account),
                "account_id": log.social_account_id,
                "chat_title": chat.title if chat else None,
                "chat_id": chat.id if chat else None,
                "context": payload,
            }
        )
    return {"items": items, "total": int(total or 0)}
