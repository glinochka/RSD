"""Deliver qualified leads to the configured manager contact.

Supports:
  - Telegram username/id via a pool account
  - email via Mailopost
  - generic webhook URL
"""
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import AutomationActionLog, CustomAutomation, CustomLead, LeadStatus
from ...config import settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}$")
_TELEGRAM_RE = re.compile(r"^(?:https?://t\.me/|@)?([a-zA-Z0-9_]{5,32})$|^(-?\d+)$")
_URL_RE = re.compile(r"^https?://")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_contact(contact: str) -> tuple[str, str]:
    contact = (contact or "").strip()
    if not contact:
        return ("", "")
    if _EMAIL_RE.match(contact):
        return ("email", contact)
    if _URL_RE.match(contact):
        return ("url", contact)
    tg_match = _TELEGRAM_RE.match(contact)
    if tg_match:
        value = tg_match.group(1) or tg_match.group(2)
        return ("telegram", value)
    return ("unknown", contact)


def _render_lead_message(lead: CustomLead, automation: CustomAutomation) -> str:
    parts = [
        f"Новый лид из автоматизации «{automation.name}»",
        f"Источник: {lead.source}",
        f"Контакт: {lead.contact_value}",
    ]
    if lead.full_name:
        parts.append(f"Имя: {lead.full_name}")
    if lead.company:
        parts.append(f"Компания: {lead.company}")
    if lead.position:
        parts.append(f"Должность: {lead.position}")
    parts.append(f"Статус: {lead.status}")
    return "\n".join(parts)


async def _send_telegram(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
    recipient: str,
) -> bool:
    account = await select_account_for_action(session, automation_id, "dm")
    if not account or not account.session_file_path:
        logger.warning("No trusted account to deliver lead %s to Telegram", lead.id)
        return False
    session_path = Path(settings.MEDIA_ROOT).resolve() / account.session_file_path
    if not session_path.exists():
        logger.warning("Session file missing for delivery account %s", account.id)
        return False

    text = _render_lead_message(lead, await session.get(CustomAutomation, automation_id))
    try:
        async with TelegramAccountClient(str(session_path)) as client:
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.send_message(recipient, text),
                action_type="lead_delivery",
                target_id=f"lead:{lead.id}",
                target_type="lead",
                payload={"recipient": recipient, "text": text},
                automation_id=automation_id,
            )
        return True
    except Exception as exc:
        logger.warning("Telegram lead delivery failed for lead %s: %s", lead.id, exc)
        return False


async def _send_email(lead: CustomLead, automation: CustomAutomation, email: str) -> bool:
    token = settings.MAILOPOST_API_TOKEN.strip()
    from_email = settings.MAILOPOST_FROM_EMAIL.strip()
    base_url = settings.MAILOPOST_API_URL.strip().rstrip("/")
    if not token or not from_email or not base_url:
        logger.warning("Mailopost not configured; cannot email lead %s", lead.id)
        return False

    subject = f"Новый лид из автоматизации «{automation.name}»"
    body = _render_lead_message(lead, automation)
    payload = {
        "from_email": from_email,
        "to": email,
        "subject": subject,
        "text": body,
    }
    from_name = settings.MAILOPOST_FROM_NAME.strip()
    if from_name:
        payload["from_name"] = from_name

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.MAILOPOST_SEND_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{base_url}/email/messages", json=payload, headers=headers)
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Email lead delivery failed for lead %s: %s", lead.id, exc)
        return False


async def _send_webhook(lead: CustomLead, automation: CustomAutomation, url: str) -> bool:
    payload = {
        "automation_id": automation.id,
        "automation_name": automation.name,
        "lead_id": lead.id,
        "source": lead.source,
        "contact_type": lead.contact_type,
        "contact_value": lead.contact_value,
        "full_name": lead.full_name,
        "company": lead.company,
        "position": lead.position,
        "status": lead.status,
        "transferred_at": _utc_now().isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Webhook lead delivery failed for lead %s to %s: %s", lead.id, url, exc)
        return False


async def deliver_lead_to_manager(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
) -> dict[str, Any]:
    """Deliver the lead to the automation's lead_manager_contact if configured."""
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return {"delivered": False, "reason": "automation_not_found"}

    contact = (automation.lead_manager_contact or "").strip()
    if not contact:
        return {"delivered": False, "reason": "no_manager_contact"}

    contact_type, value = _parse_contact(contact)
    if not contact_type or not value:
        return {"delivered": False, "reason": "invalid_contact", "contact": contact}

    delivered = False
    if contact_type == "telegram":
        delivered = await _send_telegram(session, automation_id, lead, value)
    elif contact_type == "email":
        delivered = await _send_email(lead, automation, value)
    elif contact_type == "url":
        delivered = await _send_webhook(lead, automation, value)
    else:
        return {"delivered": False, "reason": "unsupported_contact_type", "contact": contact}

    if delivered:
        lead.status = LeadStatus.TRANSFERRED.value
        lead.transferred_at = _utc_now()
        lead.status_history = (lead.status_history or []) + [
            {"status": LeadStatus.TRANSFERRED.value, "changed_at": lead.transferred_at.isoformat(), "channel": contact_type}
        ]
        lead.updated_at = _utc_now()
        await session.commit()

    return {"delivered": delivered, "channel": contact_type, "contact": value}
