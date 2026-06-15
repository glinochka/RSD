"""Outreach ИИ МОП через userbot (Telegram / WhatsApp) — как у sales_manager Excel."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentChannelConnection, AiMopLead
from ..sales.contact_target_resolver import pick_outreach_channel
from ..sales.dm_queue_service import get_dm_queue_service
from ..sales.fsm import SalesFSMService
from ..sales.sales_playbook import EXCEL_COLD_OUTREACH_EXTRA
from ..template_runtime import TemplateRuntimeService

logger = logging.getLogger(__name__)

AI_MOP_SOURCE_CHAT_ID = "ai_mop"


async def _agent_has_channel(agent_id: int, provider: str) -> bool:
    async with async_session_maker() as session:
        row = await session.scalar(
            select(AgentChannelConnection.id).where(
                AgentChannelConnection.agent_id == agent_id,
                AgentChannelConnection.provider == provider,
                AgentChannelConnection.is_active.is_(True),
            )
        )
        return row is not None


async def resolve_lead_outreach_channel(
    *,
    agent_id: int,
    lead: AiMopLead,
) -> tuple[str, str, dict[str, Any]]:
    wa_ok = await _agent_has_channel(agent_id, "whatsapp_userbot")
    tg_ok = await _agent_has_channel(agent_id, "telegram_userbot")
    if not wa_ok and not tg_ok:
        raise ValueError(
            "У агента нет активного Telegram userbot и/или WhatsApp userbot для outreach"
        )

    row = {
        "org_name": lead.org_name,
        "lpr_name": lead.lpr_name,
        "lpr_phone": lead.phone,
        "org_phone": lead.phone,
        "org_mobile": lead.phone,
        "telegram": lead.telegram,
        "whatsapp": lead.whatsapp,
    }
    channel, target, hint = pick_outreach_channel(
        row,
        whatsapp_available=wa_ok,
        telegram_available=tg_ok,
    )
    if not channel or not target:
        raise ValueError(
            "Не удалось определить контакт Telegram/WhatsApp для лида (проверьте колонки в базе)"
        )
    return channel, target, hint


def _ai_mop_outreach_user_message(
    *,
    lead: AiMopLead,
    website_url: str,
    login_email: str,
    temp_password: str,
) -> str:
    parts = [
        f"Компания: {lead.org_name}",
        f"Демо-сайт: {website_url}",
        f"Логин в личный кабинет: {login_email}",
        f"Временный пароль: {temp_password}",
    ]
    if lead.lpr_name:
        parts.append(f"Контакт: {lead.lpr_name}")
    if lead.phone:
        parts.append(f"Телефон: {lead.phone}")
    if lead.address:
        parts.append(f"Адрес: {lead.address}")
    if lead.category:
        parts.append(f"Категория: {lead.category}")
    parts.append(
        "Задача: первое холодное сообщение в мессенджер. Мы бесплатно сделали демо-сайт с ИИ-чатом; "
        "первый месяц бесплатно. Обязательно дай ссылку на сайт и данные для входа. Тон — мягкий, по делу."
    )
    parts.append(EXCEL_COLD_OUTREACH_EXTRA)
    return "\n".join(parts)


async def compose_ai_mop_dm(
    *,
    agent: Agent,
    lead: AiMopLead,
    website_url: str,
    login_email: str,
    temp_password: str,
) -> str:
    runtime = TemplateRuntimeService()
    raw_config = agent.template_config
    if isinstance(raw_config, str):
        try:
            template_config = json.loads(raw_config)
        except json.JSONDecodeError:
            template_config = {}
    elif isinstance(raw_config, dict):
        template_config = raw_config
    else:
        template_config = {}

    knowledge_scope_id = int(agent.bot_id if agent.bot_id is not None else agent.id)
    system_prompt = str(agent.system_prompt or "").strip()
    user_message = _ai_mop_outreach_user_message(
        lead=lead,
        website_url=website_url,
        login_email=login_email,
        temp_password=temp_password,
    )

    qualification = {
        "decision": "engage",
        "intent": "target_warm",
        "confidence": 1.0,
        "reason": "ai_mop_demo_outreach",
        "lead_temperature": "warm",
        "stage_hint": "discovery",
        "handoff_ready": False,
        "workflow_outcome": "continue",
        "lead_heat_score": 60,
        "resilience_score": 50,
        "engagement_score": 40,
    }

    context_list, _sources = await runtime.retrieve_offer_context(
        user_message=user_message,
        knowledge_scope_id=knowledge_scope_id,
        enable_smart_search=runtime._is_smart_search_enabled(template_config),
    )
    message_text = await runtime.compose_dm(
        prompt=system_prompt,
        user_message=user_message,
        qualification=qualification,
        context_list=context_list,
        template_config=template_config,
        current_sales_state="DISCOVERED",
        recent_history=[],
    )
    text = (message_text or "").strip()
    if not text:
        raise RuntimeError("Пустой текст сообщения для outreach")
    return text


async def enqueue_ai_mop_outreach(
    *,
    agent_id: int,
    lead_id: int,
    channel: str,
    target: str,
    hint: dict[str, Any],
    message_text: str,
) -> int:
    queue = get_dm_queue_service()
    fsm = SalesFSMService()

    meta: dict[str, Any] = {
        "channel": channel,
        "ai_mop_lead_id": lead_id,
        "org_name": "",
        "source": "ai_mop",
    }
    if hint:
        meta["target_resolve_hint"] = hint

    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
        if lead:
            meta["org_name"] = lead.org_name

    item = await queue.enqueue_dm(
        agent_id=agent_id,
        target_user_external_id=target,
        source_chat_id=AI_MOP_SOURCE_CHAT_ID,
        message_text=message_text.strip(),
        scheduled_for=None,
        metadata=meta,
    )

    await fsm.get_or_create_contact(
        agent_id=agent_id,
        user_external_id=target,
        source_chat_id=AI_MOP_SOURCE_CHAT_ID,
    )
    try:
        await fsm.transition_contact(
            agent_id=agent_id,
            user_external_id=target,
            source_chat_id=AI_MOP_SOURCE_CHAT_ID,
            to_state="QUALIFIED",
            reason="ai_mop_outreach",
        )
        await fsm.transition_contact(
            agent_id=agent_id,
            user_external_id=target,
            source_chat_id=AI_MOP_SOURCE_CHAT_ID,
            to_state="QUEUED",
            reason="ai_mop_outreach",
        )
    except Exception:
        logger.debug("FSM transition skipped ai_mop lead_id=%s", lead_id, exc_info=True)

    return int(item.id)
