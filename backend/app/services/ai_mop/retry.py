"""Повторная генерация сайта и повторная отправка outreach для лидов ИИ МОП."""

from __future__ import annotations

import logging
from typing import Any

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AiMopLead, Website
from .lead_status import mark_lead_failed
from .outreach import run_outreach_for_lead
from .provisioning import regenerate_lead_website

logger = logging.getLogger(__name__)

GENERATION_RETRY_STAGES = frozenset({"website", "provisioning", "account", "agent"})
OUTREACH_RETRY_STAGES = frozenset({"outreach_send", "outreach_queue", "outreach_compose", "no_messenger"})


def _provision_snapshot(lead: AiMopLead) -> dict[str, Any]:
    return {
        "provisioned_user_id": lead.provisioned_user_id,
        "provisioned_agent_id": lead.provisioned_agent_id,
        "provisioned_website_id": lead.provisioned_website_id,
        "website_url": lead.website_url,
        "temp_password": lead.temp_password,
        "login_email": lead.email,
        "lead_context": None,
    }


async def retry_lead_generation(*, lead_id: int) -> dict[str, Any]:
    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
        if lead is None:
            raise ValueError("Лид не найден")
        if lead.status != "failed":
            raise ValueError("Повтор доступен только для лидов со статусом failed")
        stage = str(lead.failure_stage or "")
        if stage not in GENERATION_RETRY_STAGES:
            raise ValueError(f"Повторная генерация недоступна для этапа: {stage or '—'}")
        agent_id = lead.assigned_agent_id
        if agent_id is None:
            raise ValueError("У лида не назначен агент")

    if stage == "website" and lead.provisioned_website_id and lead.provisioned_agent_id:
        try:
            provision = await regenerate_lead_website(lead_id=lead_id)
            outreach = await run_outreach_for_lead(
                lead_id=lead_id,
                agent_id=int(agent_id),
                provision=provision,
            )
            return {"ok": True, "mode": "website_regen", "outreach": outreach}
        except Exception as exc:
            await mark_lead_failed(
                lead_id=lead_id,
                stage="website",
                error=str(exc)[:2000],
                provision=_provision_snapshot(lead),
            )
            raise

    async with async_session_maker() as session:
        async with session.begin():
            db_lead = await session.get(AiMopLead, lead_id)
            if db_lead is None:
                raise ValueError("Лид не найден")
            if stage in ("account", "agent", "provisioning"):
                db_lead.provisioned_user_id = None
                db_lead.provisioned_agent_id = None
                db_lead.provisioned_website_id = None
                db_lead.website_url = None
                db_lead.temp_password = None
                db_lead.dm_queue_id = None
            db_lead.status = "pending"
            db_lead.failure_stage = None
            db_lead.last_error = None
    return {"ok": True, "mode": "pending"}


async def retry_lead_outreach(*, lead_id: int) -> dict[str, Any]:
    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
        if lead is None:
            raise ValueError("Лид не найден")
        if lead.status != "failed":
            raise ValueError("Повтор доступен только для лидов со статусом failed")
        stage = str(lead.failure_stage or "")
        if stage not in OUTREACH_RETRY_STAGES:
            raise ValueError(f"Повторная отправка недоступна для этапа: {stage or '—'}")
        if not lead.website_url or not lead.provisioned_website_id:
            raise ValueError("Сначала нужна успешная генерация сайта")
        agent_id = lead.assigned_agent_id
        if agent_id is None:
            raise ValueError("У лида не назначен агент")
        agent = await session.get(Agent, agent_id)
        if agent is None:
            raise ValueError("Агент не найден")

    provision = _provision_snapshot(lead)
    async with async_session_maker() as session:
        website = await session.get(Website, int(lead.provisioned_website_id))
        if website and website.slug:
            from .provisioning import _website_public_url

            provision["website_url"] = _website_public_url(str(website.slug))

    try:
        outreach = await run_outreach_for_lead(
            lead_id=lead_id,
            agent_id=int(agent_id),
            provision=provision,
        )
    except Exception as exc:
        await mark_lead_failed(
            lead_id=lead_id,
            stage="outreach_send",
            error=str(exc)[:2000],
            provision=provision,
        )
        raise
    return {"ok": True, "mode": "outreach", "outreach": outreach}
