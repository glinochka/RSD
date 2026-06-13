"""Load telephony call + agent (shared by turn/partial/cancel handlers)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentTelephonyCall


async def load_call_and_agent(
    session: AsyncSession,
    *,
    connection_id: int,
    call_db_id: int,
) -> tuple[AgentTelephonyCall, Agent]:
    call = await session.scalar(
        select(AgentTelephonyCall).where(
            AgentTelephonyCall.id == call_db_id,
            AgentTelephonyCall.connection_id == connection_id,
        )
    )
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
    agent = await session.scalar(select(Agent).where(Agent.id == call.agent_id, Agent.is_active.is_(True)))
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found or inactive")
    return call, agent
