"""Retention cleanup for agent_telephony_turns."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import AgentTelephonyTurn
from ..config import settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def purge_old_telephony_turns(session: AsyncSession) -> dict:
    days = max(1, int(settings.TELEPHONY_TURNS_RETENTION_DAYS))
    cutoff = _utc_now() - timedelta(days=days)

    count_before = await session.scalar(
        select(func.count()).select_from(AgentTelephonyTurn).where(AgentTelephonyTurn.created_at < cutoff)
    )
    if not count_before:
        return {"deleted": 0, "retention_days": days, "cutoff": cutoff.isoformat()}

    result = await session.execute(delete(AgentTelephonyTurn).where(AgentTelephonyTurn.created_at < cutoff))
    deleted = int(result.rowcount or 0)
    return {"deleted": deleted, "retention_days": days, "cutoff": cutoff.isoformat()}
