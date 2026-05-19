"""Partial STT webhook handler (stage 5)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ..telephony.logging import redact_telephony_log_message
from ..config import settings
from ..telephony.partial_store import (
    clear_partial,
    get_partial,
    mark_backchannel_sent,
    record_partial,
    should_suggest_backchannel,
)
from .schemas import TelephonyPartialRequest, TelephonyPartialResponse
from .call_loader import load_call_and_agent

logger = logging.getLogger(__name__)


async def handle_telephony_partial(
    session: AsyncSession,
    payload: TelephonyPartialRequest,
) -> TelephonyPartialResponse:
    await load_call_and_agent(
        session,
        connection_id=payload.connection_id,
        call_db_id=payload.call_db_id,
    )

    snap = record_partial(
        int(payload.call_db_id),
        transcript=payload.transcript,
        is_final=payload.is_final,
        confidence=payload.confidence,
    )

    if payload.is_final:
        logger.info(
            "telephony partial accepted final connection_id=%s call_db_id=%s msg=%s",
            payload.connection_id,
            payload.call_db_id,
            redact_telephony_log_message(payload.transcript[:120]),
        )
    else:
        logger.debug(
            "telephony partial chunk connection_id=%s call_db_id=%s len=%s",
            payload.connection_id,
            payload.call_db_id,
            len(payload.transcript),
        )

    suggest_backchannel = False
    if not payload.is_final and should_suggest_backchannel(
        int(payload.call_db_id),
        min_ms=int(settings.TELEPHONY_BACKCHANNEL_MIN_MS),
    ):
        suggest_backchannel = True
        mark_backchannel_sent(int(payload.call_db_id))

    return TelephonyPartialResponse(
        accepted=True,
        transcript=snap.transcript,
        partial_count=snap.partial_count,
        is_final=payload.is_final,
        suggest_backchannel=suggest_backchannel,
    )


def resolve_transcript_with_partials(
    call_db_id: int,
    explicit_transcript: str,
) -> str:
    """Prefer explicit final transcript; fall back to accumulated partials."""
    explicit = (explicit_transcript or "").strip()
    if explicit:
        clear_partial(call_db_id)
        return explicit
    snap = get_partial(call_db_id)
    if snap and snap.transcript.strip():
        text = snap.transcript.strip()
        clear_partial(call_db_id)
        return text
    return ""
