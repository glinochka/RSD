"""Cancel in-flight telephony LLM turn (barge-in)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..telephony.stream_cancel import cancel_turn
from .schemas import TelephonyCancelRequest, TelephonyCancelResponse
from .call_loader import load_call_and_agent


async def handle_telephony_cancel(
    session: AsyncSession,
    payload: TelephonyCancelRequest,
) -> TelephonyCancelResponse:
    await load_call_and_agent(
        session,
        connection_id=payload.connection_id,
        call_db_id=payload.call_db_id,
    )
    cancelled = cancel_turn(int(payload.call_db_id))
    return TelephonyCancelResponse(cancelled=cancelled)
