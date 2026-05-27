"""Напоминания без ответа: 1 день, 1 неделя, 1 месяц (Excel outreach)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentSalesDmQueue, AgentSalesImportedContact
from ..template_runtime import TemplateRuntimeService
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID
from .dm_queue_service import get_dm_queue_service
from .outreach_scheduling import FOLLOW_UP_DELAYS, utc_now_naive
from .sales_playbook import FOLLOW_UP_TIER_HINTS

logger = logging.getLogger(__name__)

COMPOSE_AT_SEND_PLACEHOLDER = "__compose_at_send__"


def _parse_template_config(agent: Agent) -> dict[str, Any]:
    raw = agent.template_config
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


async def cancel_pending_follow_ups(
    *,
    agent_id: int,
    target_user_external_id: str,
) -> int:
    """Отменить запланированные follow-up в очереди после ответа клиента."""
    uid = (target_user_external_id or "").strip()
    if not uid:
        return 0
    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(AgentSalesDmQueue).where(
                        AgentSalesDmQueue.agent_id == agent_id,
                        AgentSalesDmQueue.target_user_external_id == uid,
                        AgentSalesDmQueue.status == "pending",
                        AgentSalesDmQueue.source_chat_id == EXCEL_IMPORT_SOURCE_CHAT_ID,
                    )
                )
            ).scalars().all()
            cancelled = 0
            for row in rows:
                try:
                    meta = json.loads(row.metadata_json or "{}")
                except json.JSONDecodeError:
                    meta = {}
                if meta.get("message_kind") != "follow_up":
                    continue
                row.status = "skipped"
                row.updated_at = utc_now_naive()
                cancelled += 1
            return cancelled


async def mark_excel_import_reply_if_any(
    *,
    agent_id: int,
    user_external_id: str,
) -> bool:
    """Зафиксировать ответ по контакту из Excel и отменить follow-up."""
    uid = (user_external_id or "").strip()
    if not uid:
        return False
    now = utc_now_naive()
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.scalar(
                select(AgentSalesImportedContact).where(
                    AgentSalesImportedContact.agent_id == agent_id,
                    AgentSalesImportedContact.target_external_id == uid,
                    AgentSalesImportedContact.sent_at.is_not(None),
                    AgentSalesImportedContact.reply_received_at.is_(None),
                )
            )
            if row is None:
                return False
            row.reply_received_at = now
            row.updated_at = now

    await cancel_pending_follow_ups(agent_id=agent_id, target_user_external_id=uid)
    return True


async def enqueue_follow_up_reminders(
    *,
    agent_id: int,
    imported_contact_id: int,
    target_user_external_id: str,
    channel: str,
    first_sent_at: datetime | None = None,
) -> int:
    """Поставить в очередь 3 напоминания (день / неделя / месяц), если клиент не ответит."""
    base = first_sent_at or utc_now_naive()
    queue = get_dm_queue_service()
    count = 0
    for tier, delta in FOLLOW_UP_DELAYS.items():
        scheduled = base + delta
        await queue.enqueue_dm(
            agent_id=agent_id,
            target_user_external_id=target_user_external_id,
            source_chat_id=EXCEL_IMPORT_SOURCE_CHAT_ID,
            message_text=COMPOSE_AT_SEND_PLACEHOLDER,
            scheduled_for=scheduled,
            metadata={
                "channel": channel,
                "message_kind": "follow_up",
                "follow_up_tier": tier,
                "imported_contact_id": imported_contact_id,
                "compose_at_send": True,
                "source": "excel_import_follow_up",
            },
        )
        count += 1
    return count


async def compose_follow_up_message(
    *,
    agent: Agent,
    row: AgentSalesImportedContact,
    tier: str,
) -> str:
    runtime = TemplateRuntimeService()
    template_config = _parse_template_config(agent)
    knowledge_scope_id = int(agent.bot_id if agent.bot_id is not None else agent.id)
    system_prompt = str(agent.system_prompt or "").strip()
    tier_hint = FOLLOW_UP_TIER_HINTS.get(tier, FOLLOW_UP_TIER_HINTS["day"])
    user_message = (
        f"Компания: {row.org_name}\n"
        f"{tier_hint}\n"
        "Клиент не ответил на предыдущие сообщения."
    )
    qualification = {
        "decision": "engage",
        "intent": "target_warm",
        "confidence": 1.0,
        "reason": f"follow_up_{tier}",
        "lead_temperature": "warm",
        "stage_hint": "discovery",
        "handoff_ready": False,
        "workflow_outcome": "continue",
    }
    context_list, _ = await runtime.retrieve_offer_context(
        user_message=user_message,
        knowledge_scope_id=knowledge_scope_id,
        enable_smart_search=runtime._is_smart_search_enabled(template_config),
    )
    return await runtime.compose_dm(
        prompt=system_prompt,
        user_message=user_message,
        qualification=qualification,
        context_list=context_list,
        template_config=template_config,
        current_sales_state="SENT",
        recent_history=[],
    )


async def should_send_follow_up(
    *,
    agent_id: int,
    imported_contact_id: int,
) -> bool:
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.scalar(
                select(AgentSalesImportedContact).where(
                    AgentSalesImportedContact.id == imported_contact_id,
                    AgentSalesImportedContact.agent_id == agent_id,
                )
            )
            if row is None:
                return False
            if row.reply_received_at is not None:
                return False
            return row.sent_at is not None


async def mark_follow_up_sent(*, imported_contact_id: int, tier: str) -> None:
    column_map = {
        "day": "follow_up_day_sent_at",
        "week": "follow_up_week_sent_at",
        "month": "follow_up_month_sent_at",
    }
    col = column_map.get(tier)
    if not col:
        return
    now = utc_now_naive()
    async with async_session_maker() as session:
        async with session.begin():
            values = {col: now, "updated_at": now}
            await session.execute(
                update(AgentSalesImportedContact)
                .where(AgentSalesImportedContact.id == imported_contact_id)
                .values(**values)
            )
