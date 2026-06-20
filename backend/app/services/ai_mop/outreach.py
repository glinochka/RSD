"""Outreach ИИ МОП: email с предложением + userbot (Telegram / WhatsApp / MAX)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AiMopLead
from ..sales.contact_target_resolver import attach_target_hint_to_dm_meta
from ..sales.dm_queue_service import get_dm_queue_service
from ..sales.fsm import SalesFSMService
from .contact_discovery import (
    discover_ai_mop_outreach_targets,
    resolve_all_lead_messenger_channels,
)
from .email_outreach import send_ai_mop_outreach_email
from .llm_helpers import (
    build_lead_context,
    build_lead_context_from_lead,
    compose_outreach_dm,
    compose_outreach_email,
    parse_lead_extra_json,
)
from .outreach_tracking import (
    channel_key,
    get_completed_outreach_channels,
    record_outreach_channel_sent,
)

logger = logging.getLogger(__name__)

AI_MOP_SOURCE_CHAT_ID = "ai_mop"
OUTREACH_CHANNEL_EMAIL = "email"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_PERSONAL_EMAIL_DOMAINS = frozenset({
    "mail.ru",
    "inbox.ru",
    "list.ru",
    "bk.ru",
    "internet.ru",
    "yandex.ru",
    "ya.ru",
    "yandex.com",
    "gmail.com",
    "googlemail.com",
    "rambler.ru",
    "lenta.ru",
    "autorambler.ru",
    "myrambler.ru",
    "ro.ru",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
    "ukr.net",
    "i.ua",
    "meta.ua",
})


def _extract_emails_from_text(text: str) -> list[str]:
    found: list[str] = []
    for match in _EMAIL_RE.finditer(text or ""):
        email = match.group(0).strip().casefold()
        if email and email not in found:
            found.append(email)
    return found


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].casefold().strip()


def _is_personal_email(email: str) -> bool:
    domain = _email_domain(email)
    if domain in _PERSONAL_EMAIL_DOMAINS:
        return True
    return domain.endswith(".mail.ru")


def _is_generated_login_email(lead: AiMopLead, email: str) -> bool:
    extra = parse_lead_extra_json(lead)
    if extra.get("account_email_generated") is True:
        login = str(lead.email or "").strip().casefold()
        if login and email.casefold() == login:
            return True
    domain = (extra.get("account_email_domain") or "rsd-ai.ru").strip().lstrip("@").casefold()
    if email.casefold().endswith(f"@{domain}"):
        if extra.get("account_email_generated") is True:
            return True
    return False


def collect_lead_contact_emails(lead: AiMopLead) -> list[str]:
    """Все контактные email лида: сначала личные (mail.ru, yandex.ru…), кастомные домены — в конце."""
    extra = parse_lead_extra_json(lead)
    candidates: list[str] = []

    for key in ("contact_email", "contact_emails", "email", "Email (полный из выгрузки)"):
        val = extra.get(key)
        if isinstance(val, list):
            for item in val:
                candidates.extend(_extract_emails_from_text(str(item)))
        elif val:
            candidates.extend(_extract_emails_from_text(str(val)))

    for val in extra.values():
        if isinstance(val, str) and "@" in val:
            candidates.extend(_extract_emails_from_text(val))

    lead_email = str(lead.email or "").strip()
    if lead_email and "@" in lead_email:
        candidates.append(lead_email.casefold())

    unique: list[str] = []
    seen: set[str] = set()
    for email in candidates:
        normalized = email.strip().casefold()
        if not normalized or "@" not in normalized or normalized in seen:
            continue
        if _is_generated_login_email(lead, normalized):
            continue
        seen.add(normalized)
        unique.append(normalized)

    personal = [e for e in unique if _is_personal_email(e)]
    custom = [e for e in unique if not _is_personal_email(e)]
    return personal + custom


def _legacy_completed_outreach_channels(lead: AiMopLead) -> set[str]:
    """Лиды до outreach_sent_channels: email при multi/email-ошибке уже мог быть отправлен."""
    from .outreach_tracking import channel_key

    completed: set[str] = set()
    if get_completed_outreach_channels(lead):
        return completed
    stage = str(lead.failure_stage or "")
    channel = str(lead.outreach_channel or "").strip().lower()
    target = str(lead.outreach_target or "").strip()
    if stage != "outreach_send" and lead.status not in ("outreach_sent", "outreach_queued"):
        return completed

    contact_email = resolve_lead_contact_email(lead)
    if contact_email and channel in ("email", "multi"):
        completed.add(channel_key(channel=OUTREACH_CHANNEL_EMAIL, target=contact_email))
    if channel in ("telegram_userbot", "whatsapp_userbot", "max_userbot") and target and lead.outreach_sent_at:
        completed.add(channel_key(channel=channel, target=target))
    return completed


def _effective_completed_channels(lead: AiMopLead) -> set[str]:
    completed = get_completed_outreach_channels(lead)
    if completed:
        return completed
    return _legacy_completed_outreach_channels(lead)


def resolve_lead_contact_email(lead: AiMopLead) -> str | None:
    """Контактный email для холодного письма (только личные почтовики)."""
    personal = [email for email in collect_lead_contact_emails(lead) if _is_personal_email(email)]
    if not personal:
        return None
    return personal[0][:255]


def resolve_lead_contact_email_with_discovery(
    lead: AiMopLead,
    discovery: "AiMopOutreachDiscovery | None" = None,
) -> str | None:
    """Email с учётом OSINT (CRM и др. источники из discovery)."""
    candidates = collect_lead_contact_emails(lead)
    if discovery is not None:
        for raw in discovery.bundle.emails:
            norm = str(raw or "").strip().casefold()
            if norm and "@" in norm and norm not in candidates:
                candidates.append(norm)
    personal = [email for email in candidates if _is_personal_email(email)]
    if not personal:
        return None
    return personal[0][:255]


async def resolve_lead_outreach_channel(
    *,
    agent_id: int,
    lead: AiMopLead,
) -> tuple[str, str, dict[str, Any]]:
    """Один канал (legacy). Предпочитайте resolve_all_lead_messenger_channels."""
    channels = await resolve_all_lead_messenger_channels(agent_id=agent_id, lead=lead)
    if not channels:
        raise ValueError(
            "У агента нет активного Telegram / WhatsApp / MAX userbot для outreach"
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
    await record_outreach_channel_sent(
        lead_id=int(lead.id),
        channel=OUTREACH_CHANNEL_EMAIL,
        target=to_email,
    )


async def compose_ai_mop_dm(
    *,
    agent: Agent,
    lead: AiMopLead,
    website_url: str,
) -> str:
    del agent  # dedicated prompt in llm_helpers; agent kept for API compatibility
    lead_context = build_lead_context_from_lead(lead)
    return await compose_outreach_dm(
        lead_context=lead_context,
        website_url=website_url,
        org_name=lead.org_name,
    )


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

    meta: dict[str, Any] = attach_target_hint_to_dm_meta(
        {
            "channel": channel,
            "ai_mop_lead_id": lead_id,
            "org_name": "",
            "source": "ai_mop",
        },
        hint,
    )

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

    completed = _effective_completed_channels(lead)
    discovery = await discover_ai_mop_outreach_targets(agent_id=agent_id, lead=lead)
    contact_email = resolve_lead_contact_email_with_discovery(lead, discovery)
    messengers = discovery.messengers

    pending_email = (
        contact_email
        and channel_key(channel=OUTREACH_CHANNEL_EMAIL, target=contact_email) not in completed
    )
    pending_messengers = [
        (channel, target, hint)
        for channel, target, hint in messengers
        if channel_key(channel=channel, target=target) not in completed
    ]

    if not pending_email and not pending_messengers:
        if completed:
            from .lead_status import mark_lead_outreach_sent

            await mark_lead_outreach_sent(lead_id=lead_id, agent_id=agent_id)
            return {
                "sent_channels": sorted(completed),
                "dm_queue_ids": [],
                "email_sent": False,
                "skipped_already_sent": sorted(completed),
            }
        raise ValueError("Нет email и нет контактов Telegram / WhatsApp / MAX для outreach")

    sent_channels: list[str] = []
    if pending_email and contact_email:
        await send_ai_mop_proposal_email(
            lead=lead,
            provision=provision,
            to_email=contact_email,
        )
        sent_channels.append(f"email:{contact_email}")

    queue_ids: list[int] = []
    dm_channels: list[tuple[str, str]] = []
    if pending_messengers:
        message_text = await compose_ai_mop_dm(
            agent=agent,
            lead=lead,
            website_url=str(provision["website_url"]),
        )
        for channel, target, hint in pending_messengers:
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
        if len(dm_channels) > 1 or (pending_email and contact_email):
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
    elif pending_email and contact_email:
        await mark_lead_email_outreach_sent(
            lead_id=lead_id,
            agent_id=agent_id,
            contact_email=contact_email,
            provision=provision,
        )

    return {
        "sent_channels": sent_channels,
        "dm_queue_ids": queue_ids,
        "email_sent": bool(pending_email and contact_email),
        "skipped_already_sent": sorted(completed) if completed else [],
    }
