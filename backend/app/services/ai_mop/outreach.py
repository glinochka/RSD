"""Outreach ИИ МОП: email с предложением + userbot (Telegram / WhatsApp)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentChannelConnection, AiMopLead
from ..sales.contact_target_resolver import collect_all_messenger_channels
from ..sales.dm_queue_service import get_dm_queue_service
from ..sales.fsm import SalesFSMService
from ..sales.sales_playbook import EXCEL_COLD_OUTREACH_EXTRA
from ..template_runtime import TemplateRuntimeService
from .email_outreach import send_ai_mop_outreach_email
from .llm_helpers import build_lead_context, compose_outreach_email

logger = logging.getLogger(__name__)

AI_MOP_SOURCE_CHAT_ID = "ai_mop"
OUTREACH_CHANNEL_EMAIL = "email"


def resolve_lead_contact_email(lead: AiMopLead) -> str | None:
    """Контактный email компании для холодного письма (не login @rsd-ai.ru)."""
    extra: dict[str, Any] = {}
    if lead.extra_json:
        try:
            parsed = json.loads(lead.extra_json)
            if isinstance(parsed, dict):
                extra = parsed
        except json.JSONDecodeError:
            pass

    contact = str(extra.get("contact_email") or "").strip()
    if contact and "@" in contact:
        return contact[:255]

    if extra.get("account_email_generated") is True:
        return None

    email = str(lead.email or "").strip()
    if email and "@" in email:
        return email[:255]
    return None


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


async def resolve_all_lead_messenger_channels(
    *,
    agent_id: int,
    lead: AiMopLead,
) -> list[tuple[str, str, dict[str, Any]]]:
    wa_ok = await _agent_has_channel(agent_id, "whatsapp_userbot")
    tg_ok = await _agent_has_channel(agent_id, "telegram_userbot")
    if not wa_ok and not tg_ok:
        return []

    row = {
        "org_name": lead.org_name,
        "lpr_name": lead.lpr_name,
        "lpr_phone": lead.phone,
        "org_phone": lead.phone,
        "org_mobile": lead.phone,
        "telegram": lead.telegram,
        "whatsapp": lead.whatsapp,
    }
    return collect_all_messenger_channels(
        row,
        whatsapp_available=wa_ok,
        telegram_available=tg_ok,
    )


async def resolve_lead_outreach_channel(
    *,
    agent_id: int,
    lead: AiMopLead,
) -> tuple[str, str, dict[str, Any]]:
    """Один канал (legacy). Предпочитайте resolve_all_lead_messenger_channels."""
    channels = await resolve_all_lead_messenger_channels(agent_id=agent_id, lead=lead)
    if not channels:
        raise ValueError(
            "У агента нет активного Telegram userbot и/или WhatsApp userbot для outreach"
        )
    channel, target, hint = channels[0]
    return channel, target, hint


async def send_ai_mop_proposal_email(
    *,
    lead: AiMopLead,
    provision: dict[str, Any],
    to_email: str,
) -> None:
    lead_context = str(provision.get("lead_context") or "").strip()
    if not lead_context:
        lead_context = build_lead_context(
            org_name=lead.org_name,
            email=to_email,
            lpr_name=lead.lpr_name,
            phone=lead.phone,
            address=lead.address,
            category=lead.category,
        )
    email_content = await compose_outreach_email(
        lead_context=lead_context,
        website_url=str(provision["website_url"]),
        login_email=str(provision.get("login_email") or ""),
        temp_password=str(provision.get("temp_password") or ""),
    )
    await send_ai_mop_outreach_email(
        to_email=to_email,
        subject=email_content["subject"],
        text=email_content["text"],
        html_body=email_content["html_body"],
    )
    logger.info("AI MOP outreach email sent lead_id=%s to=%s", lead.id, to_email)


def _ai_mop_outreach_user_message(
    *,
    lead: AiMopLead,
    website_url: str,
) -> str:
    parts = [
        f"Компания: {lead.org_name}",
        f"Демо-сайт: {website_url}",
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
        "первый месяц бесплатно, далее ежемесячная оплата. "
        "Обязательно дай ссылку на демо-сайт и кратко опиши условия. "
        "НЕ указывай логин, пароль и данные для входа в личный кабинет — это выглядит как фишинг. "
        "Вместо этого мягко спроси, интересно ли получить доступ для управления сайтом. "
        "Тон — мягкий, по делу, без давления."
    )
    parts.append(EXCEL_COLD_OUTREACH_EXTRA)
    return "\n".join(parts)


async def compose_ai_mop_dm(
    *,
    agent: Agent,
    lead: AiMopLead,
    website_url: str,
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


def format_outreach_channels_label(channels: list[tuple[str, str, dict[str, Any]]]) -> str:
    parts: list[str] = []
    for channel, target, _ in channels:
        if channel == OUTREACH_CHANNEL_EMAIL:
            parts.append(f"email→{target}")
        else:
            parts.append(f"{channel}→{target}")
    return ", ".join(parts)


async def run_outreach_for_lead(
    *,
    lead_id: int,
    agent_id: int,
    provision: dict[str, Any],
) -> dict[str, Any]:
    """Отправить предложение по email и во все доступные мессенджеры."""
    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
        agent = await session.get(Agent, agent_id)
        if lead is None or agent is None:
            raise ValueError("Lead or agent not found")

    contact_email = resolve_lead_contact_email(lead)
    messengers = await resolve_all_lead_messenger_channels(agent_id=agent_id, lead=lead)
    if not contact_email and not messengers:
        raise ValueError("Нет email и нет контактов Telegram/WhatsApp для outreach")

    sent_channels: list[str] = []
    if contact_email:
        await send_ai_mop_proposal_email(
            lead=lead,
            provision=provision,
            to_email=contact_email,
        )
        sent_channels.append(f"email:{contact_email}")

    queue_ids: list[int] = []
    dm_channels: list[tuple[str, str]] = []
    if messengers:
        message_text = await compose_ai_mop_dm(
            agent=agent,
            lead=lead,
            website_url=str(provision["website_url"]),
        )
        for channel, target, hint in messengers:
            queue_id = await enqueue_ai_mop_outreach(
                agent_id=agent_id,
                lead_id=lead_id,
                channel=channel,
                target=target,
                hint=hint,
                message_text=message_text,
            )
            queue_ids.append(queue_id)
            dm_channels.append((channel, target))
            sent_channels.append(f"{channel}:{target}")

    from .lead_status import mark_lead_email_outreach_sent, mark_lead_outreach_queued

    if dm_channels:
        primary_channel, primary_target = dm_channels[0]
        if len(dm_channels) > 1 or contact_email:
            channel_label = "multi"
        else:
            channel_label = primary_channel
        await mark_lead_outreach_queued(
            lead_id=lead_id,
            agent_id=agent_id,
            channel=channel_label,
            target=primary_target,
            dm_queue_id=queue_ids[0] if queue_ids else None,
            provision=provision,
        )
    elif contact_email:
        await mark_lead_email_outreach_sent(
            lead_id=lead_id,
            agent_id=agent_id,
            contact_email=contact_email,
            provision=provision,
        )

    return {
        "sent_channels": sent_channels,
        "dm_queue_ids": queue_ids,
        "email_sent": bool(contact_email),
    }
