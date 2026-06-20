"""Импорт Excel-базы контактов для sales_manager (per-agent)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AgentChannelConnection, AgentSalesImportedContact
from ..sales_excel_import import extras_to_json, parse_sales_excel
from .contact_target_resolver import (
    build_import_dedup_key,
    hint_to_json,
    pick_outreach_channel,
)

EXCEL_IMPORT_SOURCE_CHAT_ID = "excel_import"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _agent_has_channel(session: AsyncSession, agent_id: int, provider: str) -> bool:
    row = await session.scalar(
        select(AgentChannelConnection.id).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == provider,
            AgentChannelConnection.is_active.is_(True),
        )
    )
    return row is not None


async def import_agent_contacts_from_excel(
    session: AsyncSession,
    *,
    agent_id: int,
    file_bytes: bytes,
) -> dict[str, Any]:
    """
    Разобрать Excel и сохранить контакты агента.
    Возвращает статистику и import_batch_id для фонового outreach.
    """
    try:
        rows = parse_sales_excel(file_bytes)
    except Exception as e:
        raise ValueError(f"Не удалось разобрать файл Excel: {e}") from e

    wa_ok = await _agent_has_channel(session, agent_id, "whatsapp_userbot")
    tg_ok = await _agent_has_channel(session, agent_id, "telegram_userbot")
    max_ok = await _agent_has_channel(session, agent_id, "max_userbot")
    if not wa_ok and not tg_ok and not max_ok:
        raise ValueError(
            "Подключите канал WhatsApp userbot, Telegram userbot и/или MAX userbot, "
            "чтобы отправлять сообщения по базе."
        )

    batch_id = uuid.uuid4().hex
    now = _utc_now()
    imported = 0
    updated = 0
    skipped_no_messenger = 0
    skipped_duplicate = 0

    for r in rows:
        org_name = (str(r.get("org_name") or "").strip())[:512]
        if not org_name:
            continue

        channel, target, hint = pick_outreach_channel(
            r,
            whatsapp_available=wa_ok,
            telegram_available=tg_ok,
            max_available=max_ok,
        )
        if not channel or not target:
            skipped_no_messenger += 1
            continue

        dedup = build_import_dedup_key(
            org_name=org_name,
            channel=channel,
            target_external_id=target,
        )
        existing = await session.scalar(
            select(AgentSalesImportedContact).where(
                AgentSalesImportedContact.agent_id == agent_id,
                AgentSalesImportedContact.dedup_key == dedup,
            )
        )
        payload = {
            "org_name": org_name,
            "lpr_name": r.get("lpr_name"),
            "lpr_phone": r.get("lpr_phone"),
            "org_phone": r.get("org_phone"),
            "org_mobile": r.get("org_mobile"),
            "email": r.get("email"),
            "website": r.get("website"),
            "whatsapp": r.get("whatsapp"),
            "telegram": r.get("telegram"),
            "extra_json": extras_to_json(r.get("extras") or {}),
            "channel": channel,
            "target_external_id": target[:256],
            "target_resolve_hint": hint_to_json(hint),
            "import_batch_id": batch_id,
            "updated_at": now,
        }
        if existing:
            if existing.outreach_status in {"sent", "queued"}:
                skipped_duplicate += 1
                continue
            for key, val in payload.items():
                if key != "import_batch_id":
                    setattr(existing, key, val)
            existing.import_batch_id = batch_id
            existing.outreach_status = "pending"
            existing.last_error = None
            updated += 1
        else:
            session.add(
                AgentSalesImportedContact(
                    agent_id=agent_id,
                    outreach_status="pending",
                    dedup_key=dedup,
                    created_at=now,
                    **payload,
                )
            )
            imported += 1

    return {
        "import_batch_id": batch_id,
        "imported": imported,
        "updated": updated,
        "skipped_no_messenger": skipped_no_messenger,
        "skipped_duplicate": skipped_duplicate,
        "total_parsed": len(rows),
        "channels": {
            "whatsapp_userbot": wa_ok,
            "telegram_userbot": tg_ok,
            "max_userbot": max_ok,
        },
    }
