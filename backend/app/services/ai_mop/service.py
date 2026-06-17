"""Управление назначениями и статистикой ИИ МОП."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AiMopAgentAssignment, AiMopLead, User
from .lead_status import FAILURE_STAGE_LABELS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_template_config(agent: Agent) -> dict[str, Any]:
    raw = agent.template_config
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


async def get_dashboard_stats() -> dict[str, Any]:
    async with async_session_maker() as session:
        total_leads = await session.scalar(select(func.count(AiMopLead.id))) or 0
        pending = await session.scalar(
            select(func.count(AiMopLead.id)).where(AiMopLead.status == "pending")
        ) or 0
        sent = await session.scalar(
            select(func.count(AiMopLead.id)).where(AiMopLead.status == "outreach_sent")
        ) or 0
        failed = await session.scalar(
            select(func.count(AiMopLead.id)).where(AiMopLead.status == "failed")
        ) or 0
        processing = await session.scalar(
            select(func.count(AiMopLead.id)).where(AiMopLead.status == "processing")
        ) or 0
        queued = await session.scalar(
            select(func.count(AiMopLead.id)).where(AiMopLead.status == "outreach_queued")
        ) or 0
        assignments = (
            await session.scalars(
                select(AiMopAgentAssignment)
                .where(AiMopAgentAssignment.is_enabled.is_(True))
                .order_by(AiMopAgentAssignment.id)
            )
        ).all()
        agents_stats = []
        for row in assignments:
            agent = await session.get(Agent, row.agent_id)
            agents_stats.append(
                {
                    "agent_id": row.agent_id,
                    "agent_name": agent.system_prompt[:80] if agent and agent.system_prompt else f"Agent #{row.agent_id}",
                    "bot_username": agent.bot_username if agent else None,
                    "is_enabled": row.is_enabled,
                    "is_busy": row.is_busy,
                    "leads_processed": row.leads_processed,
                    "leads_sent": row.leads_sent,
                    "leads_failed": row.leads_failed,
                    "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
                    "last_error": row.last_error,
                    "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
                }
            )
    return {
        "leads": {
            "total": int(total_leads),
            "pending": int(pending),
            "processing": int(processing),
            "outreach_queued": int(queued),
            "outreach_sent": int(sent),
            "failed": int(failed),
        },
        "agents": agents_stats,
        "active_agents": len([a for a in agents_stats if a["is_enabled"] and not a["is_busy"]]),
    }


async def list_sales_manager_agents_with_assignment() -> list[dict[str, Any]]:
    async with async_session_maker() as session:
        agents = (
            await session.scalars(
                select(Agent)
                .where(Agent.template_type == "sales_manager")
                .order_by(Agent.id.desc())
            )
        ).all()
        result = []
        for agent in agents:
            assignment = await session.scalar(
                select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent.id)
            )
            owner = await session.get(User, agent.user_id) if agent.user_id else None
            result.append(
                {
                    "id": agent.id,
                    "is_active": agent.is_active,
                    "bot_username": agent.bot_username,
                    "owner_email": owner.email if owner else None,
                    "system_prompt_preview": (agent.system_prompt or "")[:120],
                    "ai_mop_enabled": bool(assignment and assignment.is_enabled),
                    "ai_mop_assigned": assignment is not None,
                    "assignment": {
                        "is_busy": assignment.is_busy if assignment else False,
                        "leads_sent": assignment.leads_sent if assignment else 0,
                        "leads_processed": assignment.leads_processed if assignment else 0,
                        "leads_failed": assignment.leads_failed if assignment else 0,
                    }
                    if assignment
                    else None,
                }
            )
        return result


async def assign_agent_to_ai_mop(*, agent_id: int, enabled: bool = True) -> dict[str, Any]:
    async with async_session_maker() as session:
        async with session.begin():
            agent = await session.get(Agent, agent_id)
            if agent is None or agent.template_type != "sales_manager":
                raise ValueError("Agent not found or not sales_manager")

            config = _parse_template_config(agent)
            config["custom_runtime"] = "ai_mop"
            config["allowed_tools"] = ["send_demo_credentials", "edit_demo_website"]
            agent.template_config = json.dumps(config, ensure_ascii=False)

            assignment = await session.scalar(
                select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
            )
            now = _utc_now()
            if assignment is None:
                assignment = AiMopAgentAssignment(
                    agent_id=agent_id,
                    is_enabled=enabled,
                    created_at=now,
                    updated_at=now,
                )
                session.add(assignment)
            else:
                assignment.is_enabled = enabled
                assignment.updated_at = now
            await session.flush()
            return {"agent_id": agent_id, "ai_mop_enabled": enabled}


async def unassign_agent_from_ai_mop(*, agent_id: int) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            agent = await session.get(Agent, agent_id)
            if agent:
                config = _parse_template_config(agent)
                config.pop("custom_runtime", None)
                if config.get("allowed_tools") == ["send_demo_credentials", "edit_demo_website"]:
                    config.pop("allowed_tools", None)
                agent.template_config = json.dumps(config, ensure_ascii=False)
            assignment = await session.scalar(
                select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
            )
            if assignment:
                await session.delete(assignment)


async def set_agent_ai_mop_enabled(*, agent_id: int, enabled: bool) -> None:
    async with async_session_maker() as session:
        async with session.begin():
            assignment = await session.scalar(
                select(AiMopAgentAssignment).where(AiMopAgentAssignment.agent_id == agent_id)
            )
            if assignment is None:
                raise ValueError("Agent is not assigned to AI MOP")
            assignment.is_enabled = enabled
            assignment.updated_at = _utc_now()


async def clear_ai_mop_leads(*, only_pending: bool = True) -> int:
    async with async_session_maker() as session:
        async with session.begin():
            q = select(AiMopLead)
            if only_pending:
                q = q.where(AiMopLead.status.in_(("pending", "failed")))
            rows = (await session.scalars(q)).all()
            count = len(rows)
            for row in rows:
                await session.delete(row)
            return count


async def list_leads(*, page: int = 1, page_size: int = 20, status: str | None = None) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    async with async_session_maker() as session:
        count_q = select(func.count(AiMopLead.id))
        q = select(AiMopLead).order_by(AiMopLead.id.desc())
        if status:
            count_q = count_q.where(AiMopLead.status == status)
            q = q.where(AiMopLead.status == status)
        total = await session.scalar(count_q) or 0
        rows = (await session.scalars(q.offset(offset).limit(page_size))).all()
        items = [_serialize_lead_row(r) for r in rows]
    return {"items": items, "page": page, "page_size": page_size, "total": int(total)}


def _serialize_lead_row(r: AiMopLead) -> dict[str, Any]:
    stage = r.failure_stage or ""
    return {
        "id": r.id,
        "org_name": r.org_name,
        "email": r.email,
        "status": r.status,
        "website_url": r.website_url,
        "outreach_channel": r.outreach_channel,
        "outreach_target": r.outreach_target,
        "failure_stage": stage,
        "failure_stage_label": FAILURE_STAGE_LABELS.get(stage, stage or "—"),
        "outreach_sent_at": r.outreach_sent_at.isoformat() if r.outreach_sent_at else None,
        "assigned_agent_id": r.assigned_agent_id,
        "provisioned_website_id": r.provisioned_website_id,
        "last_error": r.last_error,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


async def list_errors(*, page: int = 1, page_size: int = 20, stage: str | None = None) -> dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    async with async_session_maker() as session:
        count_q = select(func.count(AiMopLead.id)).where(AiMopLead.status == "failed")
        q = select(AiMopLead).where(AiMopLead.status == "failed").order_by(AiMopLead.updated_at.desc())
        if stage:
            count_q = count_q.where(AiMopLead.failure_stage == stage)
            q = q.where(AiMopLead.failure_stage == stage)
        total = await session.scalar(count_q) or 0
        rows = (await session.scalars(q.offset(offset).limit(page_size))).all()
        by_stage_rows = (
            await session.execute(
                select(AiMopLead.failure_stage, func.count(AiMopLead.id))
                .where(AiMopLead.status == "failed")
                .group_by(AiMopLead.failure_stage)
            )
        ).all()
        by_stage = {
            (row[0] or "unknown"): int(row[1])
            for row in by_stage_rows
        }
        items = [_serialize_lead_row(r) for r in rows]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "by_stage": by_stage,
    }
