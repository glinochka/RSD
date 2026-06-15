"""Обновление статусов лидов ИИ МОП (ошибки, очередь, отправка)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from ...alembic.database import async_session_maker
from ...alembic.models import AiMopAgentAssignment, AiMopLead


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


FAILURE_STAGE_LABELS: dict[str, str] = {
    "no_messenger": "Нет канала / контакта мессенджера",
    "account": "Ошибка создания аккаунта",
    "agent": "Ошибка создания ИИ-агента",
    "website": "Ошибка генерации сайта",
    "outreach_compose": "Ошибка генерации текста",
    "outreach_queue": "Ошибка постановки в очередь",
    "outreach_send": "Ошибка отправки в мессенджер",
    "provisioning": "Ошибка провижининга",
}


async def mark_lead_failed(
    *,
    lead_id: int,
    stage: str,
    error: str,
    provision: dict[str, Any] | None = None,
) -> None:
    now = _utc_now()
    async with async_session_maker() as session:
        async with session.begin():
            lead = await session.get(AiMopLead, lead_id)
            if lead is None:
                return
            lead.status = "failed"
            lead.failure_stage = stage
            lead.last_error = error[:2000]
            lead.updated_at = now
            if provision:
                for key in (
                    "provisioned_user_id",
                    "provisioned_agent_id",
                    "provisioned_website_id",
                    "website_url",
                    "temp_password",
                ):
                    if key in provision and provision[key] is not None:
                        setattr(lead, key, provision[key])
            agent_id = lead.assigned_agent_id
            if agent_id:
                assignment = await session.scalar(
                    select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
                )
                if assignment:
                    assignment.leads_failed += 1
                    assignment.last_error = error[:500]
                    assignment.updated_at = now


async def mark_lead_outreach_queued(
    *,
    lead_id: int,
    agent_id: int,
    channel: str,
    target: str,
    dm_queue_id: int,
    provision: dict[str, Any],
) -> None:
    now = _utc_now()
    async with async_session_maker() as session:
        async with session.begin():
            lead = await session.get(AiMopLead, lead_id)
            if lead is None:
                return
            lead.status = "outreach_queued"
            lead.outreach_channel = channel
            lead.outreach_target = target[:256]
            lead.dm_queue_id = dm_queue_id
            lead.failure_stage = None
            lead.last_error = None
            lead.provisioned_user_id = provision.get("provisioned_user_id")
            lead.provisioned_agent_id = provision.get("provisioned_agent_id")
            lead.provisioned_website_id = provision.get("provisioned_website_id")
            lead.website_url = provision.get("website_url")
            lead.temp_password = provision.get("temp_password")
            lead.updated_at = now
            assignment = await session.scalar(
                select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
            )
            if assignment:
                assignment.leads_processed += 1
                assignment.last_error = None
                assignment.updated_at = now


async def mark_lead_outreach_sent(*, lead_id: int, agent_id: int) -> None:
    now = _utc_now()
    async with async_session_maker() as session:
        async with session.begin():
            lead = await session.get(AiMopLead, lead_id)
            if lead is None:
                return
            lead.status = "outreach_sent"
            lead.outreach_sent_at = now
            lead.failure_stage = None
            lead.last_error = None
            lead.updated_at = now
            assignment = await session.scalar(
                select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
            )
            if assignment:
                assignment.leads_sent += 1
                assignment.last_error = None
                assignment.updated_at = now


async def mark_lead_outreach_send_failed(*, lead_id: int, agent_id: int, error: str) -> None:
    await mark_lead_failed(lead_id=lead_id, stage="outreach_send", error=error)
