"""Фоновый воркер ИИ МОП: провижининг + outreach (email + userbot)."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AiMopAgentAssignment, AiMopLead
from ...config import settings
from ..sales.outreach_scheduling import EXCEL_STAGGER_MAX_MINUTES, EXCEL_STAGGER_MIN_MINUTES
from .lead_status import mark_lead_failed
from .outreach import resolve_all_lead_messenger_channels, resolve_lead_contact_email, run_outreach_for_lead
from .pipeline_state import is_ai_mop_pipeline_paused
from .provisioning import provision_lead_demo

logger = logging.getLogger(__name__)

_STAGGER_MIN = EXCEL_STAGGER_MIN_MINUTES
_STAGGER_MAX = EXCEL_STAGGER_MAX_MINUTES


class AiMopPipelineError(RuntimeError):
    def __init__(self, stage: str, message: str, *, provision: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.provision = provision


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _next_cooldown_until() -> datetime:
    minutes = random.uniform(_STAGGER_MIN, _STAGGER_MAX)
    return _utc_now() + timedelta(minutes=minutes)


_worker_singleton: "AiMopWorker | None" = None


class AiMopWorker:
    def __init__(self, *, poll_interval_seconds: int | None = None) -> None:
        self.poll_interval_seconds = max(
            10,
            int(poll_interval_seconds or settings.AI_MOP_POLL_INTERVAL_SECONDS),
        )
        self._stop = asyncio.Event()

    async def shutdown(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        logger.info("AiMopWorker starting (poll=%ss)", self.poll_interval_seconds)
        try:
            while not self._stop.is_set():
                try:
                    processed = await self.process_once()
                except Exception as exc:
                    logger.exception("AiMopWorker loop error: %s", exc)
                    processed = False
                if processed:
                    await asyncio.sleep(0)
                    continue
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("AiMopWorker cancelled")
            raise
        finally:
            logger.info("AiMopWorker stopped")

    async def process_once(self) -> bool:
        if await is_ai_mop_pipeline_paused():
            return False

        now = _utc_now()
        async with async_session_maker() as session:
            assignment = await session.scalar(
                select(AiMopAgentAssignment)
                .where(
                    AiMopAgentAssignment.is_enabled.is_(True),
                    AiMopAgentAssignment.is_busy.is_(False),
                )
                .where(
                    (AiMopAgentAssignment.cooldown_until.is_(None))
                    | (AiMopAgentAssignment.cooldown_until <= now)
                )
                .order_by(AiMopAgentAssignment.last_run_at.asc().nullsfirst())
                .limit(1)
            )
            if assignment is None:
                return False

            lead = await session.scalar(
                select(AiMopLead)
                .where(AiMopLead.status == "pending")
                .order_by(AiMopLead.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if lead is None:
                return False

            agent = await session.get(Agent, assignment.agent_id)
            if agent is None or not agent.is_active or agent.template_type != "sales_manager":
                assignment.is_enabled = False
                assignment.last_error = "Agent inactive or wrong template"
                await session.commit()
                return False

            assignment.is_busy = True
            lead.status = "processing"
            lead.assigned_agent_id = assignment.agent_id
            lead.updated_at = now
            assignment.updated_at = now
            lead_id = int(lead.id)
            agent_id = int(assignment.agent_id)
            await session.commit()

        try:
            await self._process_lead(lead_id=lead_id, agent_id=agent_id)
        except AiMopPipelineError as exc:
            logger.warning("AI MOP lead %s failed at %s: %s", lead_id, exc.stage, exc)
            await mark_lead_failed(
                lead_id=lead_id,
                stage=exc.stage,
                error=str(exc)[:2000],
                provision=exc.provision,
            )
            async with async_session_maker() as session:
                async with session.begin():
                    assignment = await session.scalar(
                        select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
                    )
                    if assignment:
                        assignment.is_busy = False
                        assignment.last_run_at = _utc_now()
                        assignment.cooldown_until = _next_cooldown_until()
                        assignment.last_error = str(exc)[:500]
                        assignment.updated_at = _utc_now()
            return True
        except Exception as exc:
            logger.exception("AI MOP lead %s unexpected error: %s", lead_id, exc)
            await mark_lead_failed(lead_id=lead_id, stage="provisioning", error=str(exc)[:2000])
            async with async_session_maker() as session:
                async with session.begin():
                    assignment = await session.scalar(
                        select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
                    )
                    if assignment:
                        assignment.is_busy = False
                        assignment.last_run_at = _utc_now()
                        assignment.cooldown_until = _next_cooldown_until()
                        assignment.last_error = str(exc)[:500]
                        assignment.updated_at = _utc_now()
            return True

        async with async_session_maker() as session:
            async with session.begin():
                assignment = await session.scalar(
                    select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
                )
                if assignment:
                    assignment.is_busy = False
                    assignment.last_run_at = _utc_now()
                    assignment.cooldown_until = _next_cooldown_until()
                    assignment.last_error = None
                    assignment.updated_at = _utc_now()
        return True

    async def _process_lead(self, *, lead_id: int, agent_id: int) -> None:
        async with async_session_maker() as session:
            lead = await session.get(AiMopLead, lead_id)
            agent = await session.get(Agent, agent_id)
            if lead is None or agent is None:
                raise AiMopPipelineError("provisioning", "Lead or agent not found")

        contact_email = resolve_lead_contact_email(lead)
        messengers = await resolve_all_lead_messenger_channels(agent_id=agent_id, lead=lead)

        if not contact_email and not messengers:
            raise AiMopPipelineError(
                "no_messenger",
                "Нет email для рассылки и нет контактов Telegram/WhatsApp",
            )

        try:
            result = await provision_lead_demo(lead=lead, sales_agent=agent)
        except Exception as exc:
            raise AiMopPipelineError("website", str(exc)) from exc

        try:
            await run_outreach_for_lead(
                lead_id=lead_id,
                agent_id=agent_id,
                provision=result,
            )
        except Exception as exc:
            raise AiMopPipelineError("outreach_send", str(exc), provision=result) from exc


def get_ai_mop_worker() -> AiMopWorker:
    global _worker_singleton
    if _worker_singleton is None:
        _worker_singleton = AiMopWorker()
    return _worker_singleton
