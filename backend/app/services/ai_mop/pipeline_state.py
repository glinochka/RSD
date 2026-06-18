"""Глобальная пауза пайплайна ИИ МОП (генерация + рассылка)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...alembic.database import async_session_maker
from ...alembic.models import AiMopPipelineState

_PIPELINE_STATE_ID = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def is_ai_mop_pipeline_paused() -> bool:
    async with async_session_maker() as session:
        row = await session.get(AiMopPipelineState, _PIPELINE_STATE_ID)
        return bool(row and row.is_paused)


async def get_ai_mop_pipeline_state() -> dict[str, Any]:
    async with async_session_maker() as session:
        row = await session.get(AiMopPipelineState, _PIPELINE_STATE_ID)
        if row is None:
            return {"is_paused": False, "updated_at": None}
        return {
            "is_paused": bool(row.is_paused),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


async def set_ai_mop_pipeline_paused(*, paused: bool) -> dict[str, Any]:
    now = _utc_now()
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.get(AiMopPipelineState, _PIPELINE_STATE_ID)
            if row is None:
                row = AiMopPipelineState(id=_PIPELINE_STATE_ID, is_paused=paused, updated_at=now)
                session.add(row)
            else:
                row.is_paused = paused
                row.updated_at = now
            await session.flush()
            return {
                "is_paused": bool(row.is_paused),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
