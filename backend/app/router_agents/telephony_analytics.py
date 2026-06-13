"""Telephony calls listing for agent analytics UI."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..alembic.models import AgentTelephonyCall, AgentTelephonyTurn
from ..telephony.masking import mask_caller_e164


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def serialize_turn(row: AgentTelephonyTurn) -> dict:
    return {
        "id": int(row.id),
        "role": row.role,
        "transcript": row.transcript,
        "latency_ms": row.latency_ms,
        "created_at": _iso(row.created_at),
    }


def serialize_call(row: AgentTelephonyCall, *, include_turns: bool) -> dict:
    data = {
        "id": int(row.id),
        "connection_id": int(row.connection_id),
        "external_call_id": row.external_call_id,
        "caller_e164_masked": mask_caller_e164(row.caller_e164),
        "status": row.status,
        "started_at": _iso(row.started_at),
        "ended_at": _iso(row.ended_at),
        "duration_sec": row.duration_sec,
        "recording_url": row.recording_url,
        "metadata": dict(row.metadata_ or {}),
    }
    if include_turns:
        turns = sorted(row.turns or [], key=lambda t: t.created_at)
        data["turns"] = [serialize_turn(t) for t in turns]
    return data


async def list_agent_telephony_calls(
    session: AsyncSession,
    *,
    agent_id: int,
    limit: int,
    include_turns: bool,
) -> list[dict]:
    query = (
        select(AgentTelephonyCall)
        .where(AgentTelephonyCall.agent_id == agent_id)
        .order_by(AgentTelephonyCall.started_at.desc())
        .limit(limit)
    )
    if include_turns:
        query = query.options(selectinload(AgentTelephonyCall.turns))
    rows = (await session.scalars(query)).all()
    return [serialize_call(row, include_turns=include_turns) for row in rows]
