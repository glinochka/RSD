"""Напоминания ИИ МОП без ответа: 1 день, 1 неделя, 1 месяц."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select, update

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentSalesDmQueue, AiMopLead
from ...prompts.system_prompts import FOLLOW_UP_TIER_HINTS
from ...utils.agent_template_config import parse_agent_template_config
from ..sales.contact_pool import external_id_lookup_variants
from ..sales.dm_queue_service import get_dm_queue_service
from ..sales.outreach_scheduling import FOLLOW_UP_DELAYS, utc_now_naive
from ..sales.sales_followup_service import COMPOSE_AT_SEND_PLACEHOLDER
from ..template_runtime import TemplateRuntimeService
from .lead_lookup import find_lead_for_contact
from .outreach import AI_MOP_SOURCE_CHAT_ID

logger = logging.getLogger(__name__)


async def cancel_pending_ai_mop_follow_ups(
    *,
    agent_id: int,
    target_user_external_id: str,
) -> int:
    """Отменить запланированные follow-up в очереди после ответа клиента."""
    variants = external_id_lookup_variants((target_user_external_id or "").strip())
    if not variants:
        return 0
    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                await session.execute(
                    select(AgentSalesDmQueue).where(
                        AgentSalesDmQueue.agent_id == agent_id,
                        AgentSalesDmQueue.target_user_external_id.in_(variants),
                        AgentSalesDmQueue.status == "pending",
                        AgentSalesDmQueue.source_chat_id == AI_MOP_SOURCE_CHAT_ID,
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


async def mark_ai_mop_reply_if_any(
    *,
    agent_id: int,
    user_external_id: str,
) -> bool:
    """Зафиксировать ответ по лиду ИИ МОП и отменить follow-up."""
    lead = await find_lead_for_contact(agent_id=agent_id, user_external_id=user_external_id)
    if lead is None:
        return False
    if lead.reply_received_at is not None:
        return False
    if lead.outreach_sent_at is None:
        return False

    now = utc_now_naive()
    matched_target = (lead.outreach_target or user_external_id or "").strip()
    async with async_session_maker() as session:
        async with session.begin():
            db_lead = await session.get(AiMopLead, int(lead.id))
            if db_lead is None or db_lead.reply_received_at is not None:
                return False
            db_lead.reply_received_at = now
            db_lead.updated_at = now

    await cancel_pending_ai_mop_follow_ups(
        agent_id=agent_id,
        target_user_external_id=matched_target or user_external_id,
    )
    return True


async def enqueue_ai_mop_follow_up_reminders(
    *,
    lead_id: int,
    agent_id: int,
    first_sent_at: datetime | None = None,
) -> int:
    """Поставить в очередь 3 напоминания (день / неделя / месяц), если клиент не ответит."""
    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
    if lead is None:
        return 0
    target = (lead.outreach_target or "").strip()
    channel = (lead.outreach_channel or "telegram_userbot").strip()
    if not target:
        return 0

    base = first_sent_at or lead.outreach_sent_at or utc_now_naive()
    queue = get_dm_queue_service()
    count = 0
    for tier, delta in FOLLOW_UP_DELAYS.items():
        scheduled = base + delta
        await queue.enqueue_dm(
            agent_id=agent_id,
            target_user_external_id=target,
            source_chat_id=AI_MOP_SOURCE_CHAT_ID,
            message_text=COMPOSE_AT_SEND_PLACEHOLDER,
            scheduled_for=scheduled,
            metadata={
                "channel": channel,
                "message_kind": "follow_up",
                "follow_up_tier": tier,
                "ai_mop_lead_id": lead_id,
                "compose_at_send": True,
                "source": "ai_mop_follow_up",
            },
        )
        count += 1
    return count


async def compose_ai_mop_follow_up_message(
    *,
    agent: Agent,
    lead: AiMopLead,
    tier: str,
) -> str:
    runtime = TemplateRuntimeService()
    template_config = parse_agent_template_config(agent.template_config)
    knowledge_scope_id = int(agent.bot_id if agent.bot_id is not None else agent.id)
    system_prompt = str(agent.system_prompt or "").strip()
    tier_hint = FOLLOW_UP_TIER_HINTS.get(tier, FOLLOW_UP_TIER_HINTS["day"])
    user_message = (
        f"Компания: {lead.org_name}\n"
        f"Демо-сайт: {lead.website_url or '—'}\n"
        f"{tier_hint}\n"
        "Клиент не ответил на предыдущие сообщения."
    )
    qualification = {
        "decision": "engage",
        "intent": "target_warm",
        "confidence": 1.0,
        "reason": f"ai_mop_follow_up_{tier}",
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
    text = await runtime.compose_dm(
        prompt=system_prompt,
        user_message=user_message,
        qualification=qualification,
        context_list=context_list,
        template_config=template_config,
        current_sales_state="SENT",
        recent_history=[],
    )
    return (text or "").strip()


async def should_send_ai_mop_follow_up(
    *,
    agent_id: int,
    lead_id: int,
) -> bool:
    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
        if lead is None or int(lead.assigned_agent_id or 0) != int(agent_id):
            return False
        if lead.reply_received_at is not None:
            return False
        return lead.outreach_sent_at is not None


async def mark_ai_mop_follow_up_sent(*, lead_id: int, tier: str) -> None:
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
            await session.execute(
                update(AiMopLead)
                .where(AiMopLead.id == lead_id)
                .values(**{col: now, "updated_at": now})
            )
