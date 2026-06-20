"""Восстановление лидов после ошибок LLM (402 Insufficient Balance и аналоги)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import or_, select

from ...alembic.database import async_session_maker
from ...alembic.models import AiMopAgentAssignment, AiMopLead, Website
_OUTREACH_SENT_KEY = "outreach_sent_channels"

logger = logging.getLogger(__name__)

_LLM_BALANCE_MARKERS = (
    "402",
    "insufficient balance",
    "недостаточно средств",
    "insufficient_balance",
)


def is_llm_balance_error(error: str | None) -> bool:
    low = (error or "").casefold()
    return any(marker in low for marker in _LLM_BALANCE_MARKERS)


async def lead_has_completed_website(*, lead: AiMopLead) -> bool:
    website_id = lead.provisioned_website_id
    if not website_id:
        return False
    async with async_session_maker() as session:
        website = await session.get(Website, int(website_id))
    if website is None:
        return False
    return str(website.generation_status or "").strip().lower() == "completed"


def _clear_outreach_tracking_from_extra(extra_json: str | None) -> str | None:
    if not extra_json:
        return extra_json
    try:
        data = json.loads(extra_json)
    except (json.JSONDecodeError, TypeError):
        return extra_json
    if not isinstance(data, dict):
        return extra_json
    if _OUTREACH_SENT_KEY not in data:
        return extra_json
    data = dict(data)
    data.pop(_OUTREACH_SENT_KEY, None)
    return json.dumps(data, ensure_ascii=False) if data else None


async def rollback_lead_after_llm_balance_error(*, lead_id: int) -> dict[str, Any]:
    """Откат лида после исчерпания баланса LLM.

    — Сайт не собран → pending (как новый лид в базе).
    — Сайт готов, упала только рассылка/текст → provisioned (без пересборки сайта).
    """
    async with async_session_maker() as session:
        lead = await session.get(AiMopLead, lead_id)
        if lead is None:
            raise ValueError("Лид не найден")

    has_site = await lead_has_completed_website(lead=lead)
    mode = "provisioned" if has_site else "pending"

    async with async_session_maker() as session:
        async with session.begin():
            db_lead = await session.get(AiMopLead, lead_id)
            if db_lead is None:
                raise ValueError("Лид не найден")

            previous_status = db_lead.status
            previous_error = db_lead.last_error
            agent_id = db_lead.assigned_agent_id

            db_lead.failure_stage = None
            db_lead.last_error = None
            db_lead.dm_queue_id = None

            if has_site:
                db_lead.status = "provisioned"
                db_lead.outreach_channel = None
                db_lead.outreach_target = None
            else:
                db_lead.status = "pending"
                db_lead.assigned_agent_id = None
                db_lead.provisioned_user_id = None
                db_lead.provisioned_agent_id = None
                db_lead.provisioned_website_id = None
                db_lead.website_url = None
                db_lead.temp_password = None
                db_lead.outreach_channel = None
                db_lead.outreach_target = None
                db_lead.outreach_sent_at = None
                db_lead.extra_json = _clear_outreach_tracking_from_extra(db_lead.extra_json)

            if agent_id:
                assignment = await session.scalar(
                    select(AiMopAgentAssignment).where(
                        AiMopAgentAssignment.agent_id == int(agent_id)
                    )
                )
                if assignment and assignment.is_busy:
                    assignment.is_busy = False
                    assignment.last_error = None

    logger.info(
        "AI MOP lead %s recovered after LLM balance error: %s -> %s (had_completed_website=%s)",
        lead_id,
        previous_status,
        mode,
        has_site,
    )
    return {
        "lead_id": lead_id,
        "mode": mode,
        "had_completed_website": has_site,
        "previous_status": previous_status,
        "previous_error": (previous_error or "")[:200],
    }


async def recover_all_llm_balance_errors() -> dict[str, Any]:
    """Массовый откат лидов с ошибкой 402 / Insufficient Balance."""
    async with async_session_maker() as session:
        rows = (
            await session.scalars(
                select(AiMopLead).where(
                    or_(
                        AiMopLead.status == "failed",
                        AiMopLead.status == "processing",
                    ),
                    AiMopLead.last_error.is_not(None),
                )
            )
        ).all()

    candidates = [lead for lead in rows if is_llm_balance_error(lead.last_error)]
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for lead in candidates:
        try:
            results.append(await rollback_lead_after_llm_balance_error(lead_id=int(lead.id)))
        except Exception as exc:
            logger.warning("Failed to recover lead_id=%s: %s", lead.id, exc)
            errors.append({"lead_id": int(lead.id), "error": str(exc)[:300]})

    summary = {
        "ok": True,
        "candidates": len(candidates),
        "recovered": len(results),
        "failed": len(errors),
        "to_pending": sum(1 for item in results if item.get("mode") == "pending"),
        "to_provisioned": sum(1 for item in results if item.get("mode") == "provisioned"),
        "items": results,
        "errors": errors,
    }
    logger.info(
        "AI MOP LLM balance recovery: candidates=%s recovered=%s pending=%s provisioned=%s",
        summary["candidates"],
        summary["recovered"],
        summary["to_pending"],
        summary["to_provisioned"],
    )
    return summary
