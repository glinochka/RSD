"""Activity feed: one Telegram action = one block for the /custom UI."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatMessage,
    ChatTarget,
    CustomLead,
    CustomLeadMessage,
    SocialAccount,
)

FEED_ACTIVITY_TYPES = (
    "neurocommenting",
    "chat_monitoring",
    "shilling",
    "discussion",
    "dmp",
)

_LOG_TYPES = {
    "neurocommenting": ("neurocommenting",),
    "shilling": ("shilling_chat", "shilling_post"),
    "discussion": ("discussion",),
}

_SOURCE_LIMIT = 250
_MESSAGES_LIMIT = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _payload(log: AutomationActionLog) -> dict[str, Any]:
    data = log.payload if isinstance(log.payload, dict) else {}
    return data or {}


def _account_label(account: SocialAccount | None) -> str | None:
    if not account:
        return None
    return account.display_name or account.username or account.phone_number or f"#{account.id}"


def _chat_preview(chat: ChatTarget | None, fallback_title: str | None = None) -> dict[str, Any] | None:
    title = (chat.title if chat else None) or fallback_title
    if not chat and not title:
        return None
    return {
        "id": chat.id if chat else None,
        "title": title,
        "chat_type": chat.chat_type if chat else None,
    }


def _message_preview(message: CustomLeadMessage) -> dict[str, Any]:
    return {
        "direction": message.direction,
        "text": message.text,
        "sent_at": message.sent_at,
        "author": "Мы" if message.direction == "outgoing" else "Лид",
    }


async def _load_accounts(session: AsyncSession, ids: set[int]) -> dict[int, SocialAccount]:
    clean = {item for item in ids if item}
    if not clean:
        return {}
    result = await session.execute(select(SocialAccount).where(SocialAccount.id.in_(clean)))
    return {row.id: row for row in result.scalars().all()}


async def _load_chats(session: AsyncSession, ids: set[int]) -> dict[int, ChatTarget]:
    clean = {item for item in ids if item}
    if not clean:
        return {}
    result = await session.execute(select(ChatTarget).where(ChatTarget.id.in_(clean)))
    return {row.id: row for row in result.scalars().all()}


async def _load_lead_messages(
    session: AsyncSession,
    lead_ids: list[int],
) -> dict[int, list[CustomLeadMessage]]:
    if not lead_ids:
        return {}
    result = await session.execute(
        select(CustomLeadMessage)
        .where(CustomLeadMessage.custom_lead_id.in_(lead_ids))
        .order_by(CustomLeadMessage.sent_at.asc())
    )
    grouped: dict[int, list[CustomLeadMessage]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.custom_lead_id, []).append(row)
    return grouped


async def _from_logs(
    session: AsyncSession,
    automation_id: int,
    wanted: set[str],
) -> list[dict[str, Any]]:
    log_types: list[str] = []
    for key in wanted:
        log_types.extend(_LOG_TYPES.get(key) or ())
    if not log_types:
        return []

    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.result == "success",
            AutomationActionLog.action_type.in_(tuple(log_types)),
        )
        .order_by(AutomationActionLog.created_at.desc())
        .limit(_SOURCE_LIMIT)
    )
    logs = list(result.scalars().all())
    chat_ids: set[int] = set()
    account_ids: set[int] = set()
    parsed: list[tuple[AutomationActionLog, dict[str, Any], str]] = []
    for log in logs:
        payload = _payload(log)
        if log.action_type == "neurocommenting":
            activity_type = "neurocommenting"
        elif log.action_type in ("shilling_chat", "shilling_post"):
            if not payload.get("setup"):
                continue
            activity_type = "shilling"
        elif log.action_type == "discussion":
            activity_type = "discussion"
        else:
            continue
        if activity_type not in wanted:
            continue
        parsed.append((log, payload, activity_type))
        chat_id = _as_int(payload.get("chat_target_id"))
        if chat_id:
            chat_ids.add(chat_id)
        if log.social_account_id:
            account_ids.add(log.social_account_id)
        for key in ("setup_account_id", "reply_account_id"):
            account_id = _as_int(payload.get(key))
            if account_id:
                account_ids.add(account_id)

    chats = await _load_chats(session, chat_ids)
    accounts = await _load_accounts(session, account_ids)
    items: list[dict[str, Any]] = []
    for log, payload, activity_type in parsed:
        chat_id = _as_int(payload.get("chat_target_id"))
        chat = chats.get(chat_id) if chat_id else None
        setup_id = _as_int(payload.get("setup_account_id"))
        reply_id = _as_int(payload.get("reply_account_id"))
        item: dict[str, Any] = {
            "id": f"log:{log.id}",
            "activity_type": activity_type,
            "created_at": log.created_at or _utc_now(),
            "chat": _chat_preview(chat, payload.get("chat_title")),
            "lead_id": None,
            "post_id": _as_int(payload.get("post_id") or payload.get("comment_to")),
            "post_text": payload.get("post_text"),
            "comment": payload.get("text") if activity_type == "neurocommenting" else None,
            "user_message": None,
            "user_name": payload.get("source_author") if activity_type == "discussion" else None,
            "dm_reply": None,
            "source_text": payload.get("source_text") if activity_type == "discussion" else None,
            "reply": payload.get("reply") if activity_type == "shilling" else (
                payload.get("text") if activity_type == "discussion" else None
            ),
            "setup": payload.get("setup") if activity_type == "shilling" else None,
            "setup_author": _account_label(accounts.get(setup_id)) if setup_id else None,
            "reply_author": _account_label(accounts.get(reply_id)) if reply_id else (
                _account_label(accounts.get(log.social_account_id)) if activity_type == "discussion" else None
            ),
            "lead_name": None,
            "lead_contact": None,
            "lead_company": None,
            "messages": [],
            "shilling_kind": "post" if log.action_type == "shilling_post" else (
                "chat" if log.action_type == "shilling_chat" else None
            ),
        }
        items.append(item)
    return items


async def _from_leads(
    session: AsyncSession,
    automation_id: int,
    *,
    source: str,
    activity_type: str,
) -> list[dict[str, Any]]:
    result = await session.execute(
        select(CustomLead)
        .where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.source == source,
        )
        .order_by(CustomLead.created_at.desc())
        .limit(_SOURCE_LIMIT)
    )
    leads = list(result.scalars().all())
    if not leads:
        return []

    chat_message_ids = [lead.chat_message_id for lead in leads if lead.chat_message_id]
    chat_messages: dict[int, ChatMessage] = {}
    if chat_message_ids:
        rows = await session.execute(select(ChatMessage).where(ChatMessage.id.in_(chat_message_ids)))
        chat_messages = {row.id: row for row in rows.scalars().all()}

    chat_ids = {row.chat_target_id for row in chat_messages.values()}
    chats = await _load_chats(session, chat_ids)
    messages_by_lead = await _load_lead_messages(session, [lead.id for lead in leads])

    items: list[dict[str, Any]] = []
    for lead in leads:
        chat_message = chat_messages.get(lead.chat_message_id) if lead.chat_message_id else None
        chat = chats.get(chat_message.chat_target_id) if chat_message else None
        thread = messages_by_lead.get(lead.id) or []
        incoming = next((row for row in thread if row.direction == "incoming"), None)
        outgoing = next((row for row in thread if row.direction == "outgoing"), None)
        user_message = (chat_message.text if chat_message else None) or (incoming.text if incoming else None)
        items.append({
            "id": f"lead:{lead.id}",
            "activity_type": activity_type,
            "created_at": lead.last_message_at or lead.created_at or _utc_now(),
            "chat": _chat_preview(chat),
            "lead_id": lead.id,
            "post_id": None,
            "post_text": None,
            "comment": None,
            "user_message": user_message if activity_type == "chat_monitoring" else None,
            "user_name": (chat_message.sender_name or chat_message.sender_username) if chat_message else lead.full_name,
            "dm_reply": outgoing.text if outgoing and activity_type == "chat_monitoring" else None,
            "source_text": None,
            "reply": None,
            "setup": None,
            "setup_author": None,
            "reply_author": None,
            "lead_name": lead.full_name,
            "lead_contact": lead.contact_value,
            "lead_company": lead.company,
            "messages": [_message_preview(row) for row in thread[:_MESSAGES_LIMIT]],
            "shilling_kind": None,
        })
    return items


async def list_activity_feed(
    session: AsyncSession,
    automation_id: int,
    *,
    activity_type: str | None = None,
    sort: str = "newest",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    wanted = {activity_type} if activity_type else set(FEED_ACTIVITY_TYPES)
    items: list[dict[str, Any]] = []
    items.extend(await _from_logs(session, automation_id, wanted))
    if "chat_monitoring" in wanted:
        items.extend(await _from_leads(
            session, automation_id, source="chat_monitoring", activity_type="chat_monitoring"
        ))
    if "dmp" in wanted:
        items.extend(await _from_leads(session, automation_id, source="dmp_one", activity_type="dmp"))

    reverse = sort != "oldest"
    items.sort(key=lambda row: row.get("created_at") or datetime.min, reverse=reverse)
    total = len(items)
    page = items[offset:offset + max(1, min(limit, 100))]
    return {"items": page, "total": total}
