"""Admin-only test lab: join targets, shill, neurocomment, fake DMP — no delays."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_roles import effective_roles
from .chat_join_service import create_chat_from_link, join_loaded_chats_for_accounts
from .chat_scope import is_broadcast_channel, is_lab_chat
from .dmp_one_service import process_dmp_lead
from .neurocommenting_service import process_chat_target
from .shilling_service import process_shilling_chat
from .telegram_account_client import normalize_telegram_phone
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import (
    AccountRole,
    ChatJoinStatus,
    ChatMode,
    ChatSource,
    ChatTarget,
    CustomAutomation,
    CustomLead,
    LeadStatus,
    PoolAccount,
    SocialAccount,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_target_username(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    try:
        parsed = parse_telegram_chat_ref(value)
        if parsed.kind == "username":
            return parsed.value.lstrip("@")
        return parsed.canonical
    except TelegramChatRefError:
        return value.lstrip("@").split("/")[-1].strip()


def serialize_lab(automation: CustomAutomation, chats: list[ChatTarget] | None = None) -> dict[str, Any]:
    chats = chats or []
    channel = next((chat for chat in chats if is_lab_chat(chat) and is_broadcast_channel(chat)), None)
    group = next((chat for chat in chats if is_lab_chat(chat) and not is_broadcast_channel(chat)), None)
    return {
        "channel_username": automation.test_channel_username or "",
        "chat_username": automation.test_chat_username or "",
        "channel": _chat_payload(channel),
        "chat": _chat_payload(group),
    }


def _chat_payload(chat: ChatTarget | None) -> dict[str, Any] | None:
    if not chat:
        return None
    return {
        "id": chat.id,
        "title": chat.title,
        "username": chat.invite_link or chat.external_chat_id,
        "chat_type": chat.chat_type,
        "join_status": chat.join_status,
        "last_join_error": chat.last_join_error,
    }


async def list_lab_chats(session: AsyncSession, automation_id: int) -> list[ChatTarget]:
    result = await session.execute(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.source == ChatSource.TEST.value,
        )
    )
    return list(result.scalars().all())


async def _upsert_lab_chat(
    session: AsyncSession,
    automation_id: int,
    username: str,
    *,
    mode: str,
) -> ChatTarget:
    parsed = parse_telegram_chat_ref(username)
    existing = await session.scalar(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.invite_link == parsed.canonical,
        )
    )
    if existing:
        existing.source = ChatSource.TEST.value
        existing.mode = mode
        existing.is_active = True
        await session.commit()
        await session.refresh(existing)
        return existing
    previous = await session.scalar(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.source == ChatSource.TEST.value,
            ChatTarget.mode == mode,
        )
    )
    if previous and (previous.invite_link or "") != parsed.canonical:
        previous.is_active = False
        previous.mode = ChatMode.INACTIVE.value
        await session.commit()
    chat = await create_chat_from_link(session, automation_id, username, mode=mode)
    chat.source = ChatSource.TEST.value
    chat.is_active = True
    await session.commit()
    await session.refresh(chat)
    return chat


async def save_lab_targets(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    channel_username: str | None,
    chat_username: str | None,
) -> dict[str, Any]:
    channel_username = normalize_target_username(channel_username)
    chat_username = normalize_target_username(chat_username)
    automation.test_channel_username = channel_username or None
    automation.test_chat_username = chat_username or None
    automation.updated_at = _utc_now()
    await session.commit()
    await session.refresh(automation)

    if channel_username:
        await _upsert_lab_chat(session, automation.id, channel_username, mode=ChatMode.NEUROCOMMENTING.value)
    if chat_username:
        await _upsert_lab_chat(session, automation.id, chat_username, mode=ChatMode.SHILLING.value)
    chats = await list_lab_chats(session, automation.id)
    return serialize_lab(automation, chats)


async def join_lab_targets(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    chats = await list_lab_chats(session, automation_id)
    if not chats:
        return {"status": "skipped", "reason": "no_targets", "joined_chats": 0}
    result = await join_loaded_chats_for_accounts(
        session,
        automation_id,
        chat_ids=[chat.id for chat in chats],
        include_lab=True,
        rate_limit=False,
    )
    return {"status": "ok", **result}


async def activate_lab_shilling(session: AsyncSession, automation: CustomAutomation) -> dict[str, Any]:
    chats = [chat for chat in await list_lab_chats(session, automation.id) if not is_broadcast_channel(chat)]
    if not chats:
        return {"status": "skipped", "reason": "no_chat"}
    sent = 0
    results = []
    for chat in chats:
        if chat.join_status != ChatJoinStatus.JOINED.value:
            results.append({"chat_id": chat.id, "status": "not_joined"})
            continue
        outcome = await process_shilling_chat(
            session,
            automation,
            chat,
            include_lab=True,
            skip_schedule=True,
            delay_seconds=0,
        )
        results.append({"chat_id": chat.id, **outcome})
        if outcome.get("status") == "ok":
            sent += 1
    return {"status": "ok" if sent else "skipped", "dialogues_sent": sent, "results": results}


async def run_lab_neurocommenting(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    chats = [
        chat
        for chat in await list_lab_chats(session, automation_id)
        if is_broadcast_channel(chat)
    ]
    if not chats:
        return {"status": "skipped", "reason": "no_channel"}
    sent = 0
    results = []
    for chat in chats:
        outcome = await process_chat_target(
            session,
            automation_id,
            chat,
            lab_mode=True,
            max_comments_per_run=10,
        )
        results.append({"chat_id": chat.id, **outcome})
        sent += int(outcome.get("sent") or 0)
    return {"status": "ok", "comments_sent": sent, "results": results}


async def simulate_dmp(
    session: AsyncSession,
    automation: CustomAutomation,
    phone: str,
) -> dict[str, Any]:
    phone = normalize_telegram_phone(phone) or (phone or "").strip()
    if not phone:
        return {"status": "error", "reason": "empty_phone"}

    result = await session.execute(
        select(SocialAccount, PoolAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(PoolAccount.custom_automation_id == automation.id)
    )
    target_account = None
    for social, _pool in result.all():
        number = normalize_telegram_phone(social.phone_number or "") or (social.phone_number or "")
        if number and number == phone:
            target_account = social
            break

    contact_value = phone
    contact_type = "phone"
    if target_account:
        if target_account.username:
            contact_type = "telegram"
            contact_value = target_account.username.lstrip("@")
        elif target_account.phone_number:
            contact_type = "phone"
            contact_value = target_account.phone_number

    dmp_accounts = await session.execute(
        select(SocialAccount, PoolAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation.id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
        )
    )
    has_dmp_role = False
    for social, pool in dmp_accounts.all():
        if AccountRole.DMP.value in effective_roles(pool, social):
            has_dmp_role = True
            break
    if not has_dmp_role:
        return {"status": "skipped", "reason": "no_dmp_account"}

    lead = CustomLead(
        custom_automation_id=automation.id,
        source="dmp_one",
        contact_type=contact_type,
        contact_value=contact_value,
        full_name=target_account.display_name if target_account else None,
        dmp_raw_data={"phone": phone, "lab": True, "found_account_id": target_account.id if target_account else None},
        status=LeadStatus.NEW.value,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(lead)
    await session.flush()
    outcome = await process_dmp_lead(session, automation, lead)
    return {
        "status": "ok",
        "lead_id": lead.id,
        "found_account_id": target_account.id if target_account else None,
        "contact_type": lead.contact_type,
        "contact_value": lead.contact_value,
        **outcome,
    }
