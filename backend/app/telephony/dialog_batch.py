"""Batch persistence of telephony turns to PostgreSQL (stage 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import AgentTelephonyTurn
from ..utils.pii import redact_pii_text


@dataclass
class PendingTurn:
    role: str
    transcript: str
    latency_ms: int | None = None


async def flush_turn_batch(
    session: AsyncSession,
    *,
    call_db_id: int,
    turns: list[PendingTurn],
) -> int:
    if not turns:
        return 0
    for turn in turns:
        session.add(
            AgentTelephonyTurn(
                call_id=call_db_id,
                role=turn.role,
                transcript=redact_pii_text(turn.transcript),
                latency_ms=turn.latency_ms,
            )
        )
    await session.flush()
    return len(turns)
