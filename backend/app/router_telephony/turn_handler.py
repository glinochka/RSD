"""Telephony turn pipeline with fault tolerance (stage 4)."""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentTelephonyCall, AgentTelephonyTurn
from ..channels.telephony_dialogue import (
    PhoneTurnResult,
    llm_error_result,
    llm_timeout_result,
    process_phone_turn,
)
from ..config import settings
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from ..telephony import metrics as telephony_metrics
from ..telephony.logging import redact_telephony_log_message
from ..telephony.dtmf import dtmf_transcript
from ..telephony.partial_store import get_partial
from ..telephony.turn_pool import run_in_telephony_pool
from ..utils.pii import redact_pii_text
from .call_loader import load_call_and_agent
from .partial_handler import resolve_transcript_with_partials
from .schemas import TelephonyTurnRequest, TelephonyTurnResponse

logger = logging.getLogger(__name__)

MSG_MAX_TURNS = "Мы обсудили основные вопросы. До свидания!"
MSG_CALL_TIME_LIMIT = "Время разговора истекло. До свидания!"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _count_user_turns(session: AsyncSession, call_db_id: int) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(AgentTelephonyTurn)
        .where(AgentTelephonyTurn.call_id == call_db_id, AgentTelephonyTurn.role == "user")
    )
    return int(count or 0)


def _call_duration_exceeded(call: AgentTelephonyCall) -> bool:
    started = call.started_at
    if started is None:
        return False
    max_minutes = max(1, int(settings.TELEPHONY_MAX_CALL_MINUTES))
    elapsed = _utc_now() - started
    return elapsed.total_seconds() >= max_minutes * 60


async def _fetch_recording_bytes(recording_url: str) -> bytes:
    timeout = httpx.Timeout(
        max(5.0, min(float(settings.TELEPHONY_MAX_TURN_SECONDS), 30.0)),
    )
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(recording_url.strip())
        response.raise_for_status()
        return response.content


async def _transcribe_audio(audio_base64: str | None, *, recording_url: str | None = None) -> str:
    audio_bytes: bytes | None = None
    if audio_base64:
        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except Exception:
            audio_bytes = None
    elif recording_url:
        try:
            audio_bytes = await _fetch_recording_bytes(recording_url)
        except Exception:
            logger.warning(
                "telephony recording fetch failed url=%s",
                redact_telephony_log_message(recording_url[:80]),
            )
            audio_bytes = None

    if not audio_bytes:
        return ""
    if not is_voice_stt_configured():
        logger.warning("telephony STT not configured")
        return ""
    stt_timeout = min(
        float(settings.VOICE_TRANSCRIPTION_TIMEOUT_SECONDS),
        float(settings.TELEPHONY_MAX_TURN_SECONDS),
    )
    try:
        return await asyncio.wait_for(
            transcribe_voice_bytes(audio_bytes, mime_type="audio/ogg"),
            timeout=stt_timeout,
        )
    except TimeoutError:
        logger.warning("telephony STT timed out after %.1fs", stt_timeout)
        return ""


async def _run_dialogue_with_timeout(
    session: AsyncSession,
    *,
    call: AgentTelephonyCall,
    agent: Agent,
    transcript: str,
    caller_e164: str,
    use_streaming: bool | None = None,
    barged_in: bool = False,
    interrupted_agent_text: str | None = None,
) -> PhoneTurnResult:
    llm_timeout = max(1.0, float(settings.TELEPHONY_LLM_TIMEOUT_SECONDS))

    async def _run() -> PhoneTurnResult:
        return await process_phone_turn(
            session,
            call=call,
            agent=agent,
            user_transcript=transcript,
            caller_e164=caller_e164,
            use_streaming=use_streaming,
            barged_in=barged_in,
            interrupted_agent_text=interrupted_agent_text,
        )

    try:
        return await asyncio.wait_for(
            run_in_telephony_pool(_run()),
            timeout=llm_timeout,
        )
    except TimeoutError:
        logger.warning(
            "telephony LLM timeout after %.1fs call_db_id=%s agent_id=%s",
            llm_timeout,
            call.id,
            agent.id,
        )
        retry_timeout = max(1.0, float(settings.TELEPHONY_LLM_RETRY_TIMEOUT_SECONDS))
        try:
            return await asyncio.wait_for(
                run_in_telephony_pool(_run()),
                timeout=retry_timeout,
            )
        except TimeoutError:
            logger.warning(
                "telephony LLM retry timeout after %.1fs call_db_id=%s",
                retry_timeout,
                call.id,
            )
            return llm_timeout_result(retry=False)
    except Exception:
        logger.exception(
            "telephony dialogue failed call_db_id=%s agent_id=%s",
            call.id,
            agent.id,
        )
        return llm_error_result()


def _limit_response(
    *,
    reply_text: str,
    actions: list[dict],
    stage: str,
    latency_ms: int,
) -> TelephonyTurnResponse:
    return TelephonyTurnResponse(
        reply_text=reply_text,
        actions=actions,
        stage=stage,
        latency_ms=latency_ms,
    )


async def handle_telephony_turn(session: AsyncSession, payload: TelephonyTurnRequest) -> TelephonyTurnResponse:
    started = time.perf_counter()
    call, agent = await load_call_and_agent(
        session,
        connection_id=payload.connection_id,
        call_db_id=payload.call_db_id,
    )

    latency_ms = lambda: int((time.perf_counter() - started) * 1000)

    if _call_duration_exceeded(call):
        return _limit_response(
            reply_text=MSG_CALL_TIME_LIMIT,
            actions=[{"type": "hangup", "reason": "max_call_duration"}],
            stage="call_timeout",
            latency_ms=latency_ms(),
        )

    max_turns = max(1, int(settings.TELEPHONY_MAX_TURNS))
    user_turns = await _count_user_turns(session, int(call.id))
    if user_turns >= max_turns:
        return _limit_response(
            reply_text=MSG_MAX_TURNS,
            actions=[{"type": "hangup", "reason": "max_turns"}],
            stage="max_turns",
            latency_ms=latency_ms(),
        )

    partial_snap = get_partial(int(call.id))
    partial_stt_count = partial_snap.partial_count if partial_snap else 0

    transcript = (payload.user_transcript or "").strip()
    if payload.dtmf_digit:
        dtmf_text = dtmf_transcript(payload.dtmf_digit)
        if dtmf_text:
            transcript = dtmf_text
    transcript = resolve_transcript_with_partials(int(call.id), transcript)
    if not transcript:
        transcript = (
            await _transcribe_audio(
                payload.audio_base64,
                recording_url=payload.recording_url,
            )
        ).strip()

    use_streaming = payload.streaming
    if use_streaming is None:
        use_streaming = settings.TELEPHONY_STREAMING_ENABLED

    if not transcript:
        telephony_metrics.record_stt_empty()
        ms = latency_ms()
        telephony_metrics.record_turn_latency_ms(ms)
        session.add(
            AgentTelephonyTurn(
                call_id=int(call.id),
                role="system",
                transcript=redact_pii_text("stt_empty"),
                latency_ms=ms,
            )
        )
        await session.flush()
        return TelephonyTurnResponse(
            reply_text="Не расслышал, повторите, пожалуйста.",
            actions=[],
            stage="stt_empty",
            latency_ms=ms,
        )

    result = await _run_dialogue_with_timeout(
        session,
        call=call,
        agent=agent,
        transcript=transcript,
        caller_e164=payload.caller_e164,
        use_streaming=use_streaming,
        barged_in=bool(payload.barged_in),
        interrupted_agent_text=payload.interrupted_agent_text,
    )

    ms = latency_ms()
    telephony_metrics.record_turn_latency_ms(ms)

    if result.stt_empty:
        telephony_metrics.record_stt_empty()

    last_agent_turn = await session.scalar(
        select(AgentTelephonyTurn)
        .where(AgentTelephonyTurn.call_id == call.id, AgentTelephonyTurn.role == "agent")
        .order_by(desc(AgentTelephonyTurn.id))
        .limit(1)
    )
    if last_agent_turn is not None:
        last_agent_turn.latency_ms = ms

    await session.flush()

    stage = "ok"
    if result.requires_transfer:
        stage = "transfer"
    elif result.stt_empty:
        stage = "stt_empty"
    elif any(action.get("type") == "hangup" for action in result.actions):
        stage = "hangup"

    if partial_stt_count > 0:
        session.add(
            AgentTelephonyTurn(
                call_id=int(call.id),
                role="debug",
                transcript=redact_pii_text(f"partial_stt_count={partial_stt_count}"),
                latency_ms=ms,
            )
        )

    logger.info(
        "telephony turn ok connection_id=%s call_db_id=%s stage=%s latency_ms=%s partial_stt=%s msg=%s",
        payload.connection_id,
        payload.call_db_id,
        stage,
        ms,
        partial_stt_count,
        redact_telephony_log_message(result.reply_text[:120]),
    )

    reply_chunks = list(result.reply_chunks or [])
    if not reply_chunks and result.reply_text.strip():
        reply_chunks = [result.reply_text.strip()]

    return TelephonyTurnResponse(
        reply_text=result.reply_text,
        reply_chunks=reply_chunks,
        actions=result.actions,
        stage=stage,
        latency_ms=ms,
        play_filler=bool(result.play_filler),
        partial_stt_count=partial_stt_count or None,
        dialog_state=result.dialog_state or None,
        use_ssml=bool(result.use_ssml),
    )
