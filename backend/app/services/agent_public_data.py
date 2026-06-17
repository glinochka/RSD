"""Public agent data for published websites (no auth)."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import AdminService, Agent, AgentChannelConnection, Website
from ..utils.crypto import decrypt_token

logger = logging.getLogger(__name__)

ADMIN_TEMPLATE_TYPES = frozenset({"crm_admin", "function_calling"})


def is_admin_booking_agent(agent: Agent) -> bool:
    template_type = (agent.template_type or "qa").strip().lower()
    if template_type == "function_calling":
        template_type = "crm_admin"
    return template_type in ADMIN_TEMPLATE_TYPES


def _agent_workflow_mode(agent: Agent) -> str:
    raw = agent.template_config
    if not raw:
        return "booking"
    try:
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(cfg, dict):
            return str(cfg.get("workflow_mode") or "booking").strip().lower()
    except (json.JSONDecodeError, TypeError):
        pass
    return "booking"


def agent_accepts_website_leads(agent: Agent) -> bool:
    """Any CRM admin agent with a published site can receive website callback requests."""
    return is_admin_booking_agent(agent)


def agent_has_online_booking(agent: Agent) -> bool:
    return is_admin_booking_agent(agent) and _agent_workflow_mode(agent) == "booking"


def _agent_display_name(agent: Agent) -> str:
    if agent.bot_username:
        return agent.bot_username if agent.bot_username.startswith("@") else f"@{agent.bot_username}"
    return f"Агент #{agent.id}"


def _agent_description(agent: Agent, max_len: int = 500) -> str | None:
    text = (agent.welcome_message or "").strip()
    if not text:
        prompt = (agent.system_prompt or "").strip()
        if prompt and prompt != "You are a helpful assistant.":
            text = prompt[:max_len]
    if not text:
        return None
    return text[:max_len] if len(text) > max_len else text


def _agent_logo_url(agent: Agent) -> str | None:
    raw = agent.template_config
    if not raw:
        return None
    try:
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(cfg, dict):
            return cfg.get("logo_url") or cfg.get("logoUrl")
    except (json.JSONDecodeError, TypeError):
        pass
    return None


async def _fetch_channel_contacts(agent_id: int) -> dict[str, str]:
    contacts: dict[str, str] = {}
    async with async_session_maker() as session:
        query = select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.is_active.is_(True),
        )
        result = await session.execute(query)
        for conn in result.scalars().all():
            provider = (conn.provider or "").strip().lower()
            ext = (conn.external_id or "").strip()
            if not ext:
                continue
            if provider == "telegram" and "telegram" not in contacts:
                contacts["telegram"] = ext.lstrip("@")
            elif provider in ("whatsapp", "whatsapp_userbot") and "whatsapp" not in contacts:
                contacts["whatsapp"] = ext.replace("+", "").replace(" ", "")
            elif provider == "phone" and "phone" not in contacts:
                contacts["phone"] = ext
    return contacts


async def _fetch_admin_services(agent_id: int) -> list[dict[str, Any]]:
    async with async_session_maker() as session:
        query = (
            select(AdminService)
            .where(AdminService.agent_id == agent_id, AdminService.is_active.is_(True))
            .order_by(AdminService.id.asc())
        )
        result = await session.execute(query)
        rows = result.scalars().all()
        return [
            {
                "id": s.id,
                "name": s.title,
                "title": s.title,
                "description": f"Длительность: {s.duration_minutes} мин",
                "duration_minutes": int(s.duration_minutes),
                "price_minor": int(s.price_minor or 0),
                "price": (
                    f"{s.price_minor / 100:.0f} ₽"
                    if s.price_minor and s.price_minor > 0
                    else "По запросу"
                ),
                "staff_id": s.staff_id,
            }
            for s in rows
        ]


async def get_agent_public_data(agent_id: int, *, include_widget_key: bool = False) -> dict[str, Any] | None:
    """Build public payload for an agent. Returns None if agent not found or inactive."""
    async with async_session_maker() as session:
        agent = await session.get(Agent, agent_id)
        if not agent or not agent.is_active:
            return None

        contacts = await _fetch_channel_contacts(agent_id)
        admin_template = is_admin_booking_agent(agent)
        workflow_mode = _agent_workflow_mode(agent)
        services = await _fetch_admin_services(agent_id) if admin_template else []

        payload: dict[str, Any] = {
            "id": agent.id,
            "name": _agent_display_name(agent),
            "description": _agent_description(agent),
            "logo_url": _agent_logo_url(agent),
            "template_type": (agent.template_type or "qa").strip().lower(),
            "is_admin_template": admin_template,
            "workflow_mode": workflow_mode,
            "has_booking": agent_has_online_booking(agent) and bool(services),
            "has_applications": agent_accepts_website_leads(agent),
            "services": services,
            "contacts": contacts,
        }

        if include_widget_key and agent.encrypted_external_api_key:
            try:
                payload["widget_api_key"] = decrypt_token(agent.encrypted_external_api_key)
            except Exception:
                logger.warning("Failed to decrypt widget API key for agent %s", agent_id)
                payload["widget_api_key"] = None
        else:
            payload["widget_api_key"] = None

        return payload


async def agent_has_published_website(agent_id: int) -> bool:
    async with async_session_maker() as session:
        query = select(Website.id).where(
            Website.agent_id == agent_id,
            Website.status == "published",
        ).limit(1)
        return (await session.scalar(query)) is not None
