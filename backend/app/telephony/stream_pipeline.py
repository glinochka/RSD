"""Stage 5: LLM syntagma stream → streaming TTS → media gateway."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentTelephonyCall
from ..channels.telephony_dialogue import (
    MSG_CRM_FILLER,
    PhoneTurnResult,
    _apply_prosody_to_chunks,
    _crm_tools_slow,
    _filler_for_turn,
    _prepend_opening_ack,
    _resolve_chat_portrait,
    apply_phone_style_instructions,
    process_phone_turn,
)
from ..config import settings
from ..qdrant.search_service import search_knowledge_base
from ..services.telephony_orchestrator import OrchestratorDecision
from ..services.template_runtime import get_template_runtime
from .agent_guards import parse_template_config
from .outbound_publish import (
    publish_agent_audio_chunk,
    publish_agent_audio_end,
    publish_agent_audio_start,
    publish_play_filler,
)
from .redis_store import clear_agent_spoken_text, set_agent_spoken_text
from .stream_cancel import is_cancelled, is_cancelled_call_id, telephony_turn_scope
from .stream_tts import assert_stream_tts_configured, stream_syntagma_pcm16
from .streaming import split_syntagmas, stream_answer_sentences

logger = logging.getLogger(__name__)


@dataclass
class StreamTurnMetrics:
    llm_first_token_ms: int | None = None
    tts_first_byte_ms: int | None = None
    crm_execute_ms: int | None = None
    syntagma_count: int = 0
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm_first_token_ms": self.llm_first_token_ms,
            "tts_first_byte_ms": self.tts_first_byte_ms,
            "crm_execute_ms": self.crm_execute_ms,
            "syntagma_count": self.syntagma_count,
            "cancelled": self.cancelled,
        }


@dataclass
class _ExecutionBundle:
    answer: str = ""
    sources: list = field(default_factory=list)
    tool_events: list = field(default_factory=list)
    requires_owner_handoff: bool = False


async def _iter_qa_syntagmas(
    *,
    transcript: str,
    prompt: str,
    knowledge_scope_id: int,
    call_db_id: int,
    external_call_id: str,
    metrics: StreamTurnMetrics,
) -> AsyncIterator[str]:
    context = await search_knowledge_base(transcript, agent_id=knowledge_scope_id, limit=6)
    llm_started = time.perf_counter()
    first = True
    async for syntagma in stream_answer_sentences(
        question=transcript,
        context_list=context,
        system_prompt=prompt,
        call_db_id=call_db_id,
        external_call_id=external_call_id,
    ):
        if first:
            metrics.llm_first_token_ms = int((time.perf_counter() - llm_started) * 1000)
            first = False
        yield syntagma


async def _run_execute_bundle(
    *,
    template_type: str,
    prompt: str,
    transcript: str,
    agent: Agent,
    caller_e164: str,
    template_config: dict,
    merged_ctx: dict,
    chat_portrait: str,
) -> _ExecutionBundle:
    execution = await get_template_runtime().execute(
        template_type=template_type,
        prompt=prompt,
        user_message=transcript,
        knowledge_scope_id=agent.bot_id or agent.id,
        agent_id=agent.id,
        user_external_id=caller_e164.strip(),
        template_config=template_config,
        source_channel="phone",
        chat_portrait=chat_portrait,
        runtime_context=merged_ctx,
    )
    return _ExecutionBundle(
        answer=(execution.answer or "").strip(),
        sources=list(execution.sources or []),
        tool_events=list(execution.tool_events or []),
        requires_owner_handoff=bool(execution.requires_owner_handoff),
    )


async def stream_fixed_phrase(
    *,
    call_id: str,
    connection_id: int,
    call_db_id: int | None,
    text: str,
    voice_id: str,
    language: str,
) -> StreamTurnMetrics:
    """Stream pre-written text to gateway (routing prompts, DTMF errors) without LLM."""
    metrics = StreamTurnMetrics()
    plain = text.strip()
    if not plain:
        return metrics

    ttl = int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC)
    audio_started = False
    seq = 0
    tts_started = time.perf_counter()

    for syntagma in split_syntagmas(plain):
        if call_db_id is not None and is_cancelled(call_db_id):
            metrics.cancelled = True
            break
        if is_cancelled_call_id(call_id):
            metrics.cancelled = True
            break
        chunk = syntagma.strip()
        if not chunk:
            continue
        metrics.syntagma_count += 1
        await set_agent_spoken_text(call_id, chunk, ttl_sec=ttl)

        if not audio_started:
            await publish_agent_audio_start(call_id=call_id, connection_id=connection_id)
            audio_started = True

        async for frame in stream_syntagma_pcm16(chunk, voice_id=voice_id, language=language):
            if metrics.tts_first_byte_ms is None:
                metrics.tts_first_byte_ms = int((time.perf_counter() - tts_started) * 1000)
            if call_db_id is not None and is_cancelled(call_db_id):
                metrics.cancelled = True
                break
            if is_cancelled_call_id(call_id):
                metrics.cancelled = True
                break
            await publish_agent_audio_chunk(
                call_id=call_id,
                connection_id=connection_id,
                sequence=seq,
                audio_pcm16=frame,
            )
            seq += 1
        if metrics.cancelled:
            break

    if audio_started:
        await publish_agent_audio_end(
            call_id=call_id,
            connection_id=connection_id,
            reason="cancelled" if metrics.cancelled else "complete",
        )
    await clear_agent_spoken_text(call_id)
    return metrics


async def _filler_watch(
    *,
    task: asyncio.Task[_ExecutionBundle],
    call_id: str,
    connection_id: int,
    filler_text: str,
    voice_id: str,
    language: str,
    threshold_ms: int,
) -> None:
    from .filler_audio import get_filler_pcm16

    started = time.perf_counter()
    sent = False
    while not task.done():
        if (time.perf_counter() - started) * 1000 >= threshold_ms:
            if not sent:
                sent = True
                pcm16 = await get_filler_pcm16(filler_text, voice_id=voice_id, language=language)
                await publish_play_filler(
                    call_id=call_id,
                    connection_id=connection_id,
                    text=filler_text,
                    audio_pcm16=pcm16,
                )
            return
        await asyncio.sleep(0.05)


async def stream_agent_reply(
    session: AsyncSession,
    *,
    call: AgentTelephonyCall,
    agent: Agent,
    caller_e164: str,
    transcript: str,
    orchestrator_decision: OrchestratorDecision,
    external_call_id: str,
    connection_id: int,
    voice_id: str,
    language: str,
    compressed_history: str,
) -> tuple[PhoneTurnResult, StreamTurnMetrics]:
    """Streaming LLM + TTS to gateway (blocking CRM path uses filler + crm_execute_ms)."""
    assert_stream_tts_configured()
    if not settings.TELEPHONY_STREAMING_ENABLED:
        raise RuntimeError("TELEPHONY_STREAMING_ENABLED must be true for PSTN orchestrator")

    prep = await process_phone_turn(
        session,
        call=call,
        agent=agent,
        user_transcript=transcript,
        caller_e164=caller_e164,
        runtime_context=orchestrator_decision.runtime_context,
        orchestrator_decision=orchestrator_decision,
        compressed_history_override=compressed_history,
        persist_turns=False,
        skip_llm_execution=True,
    )
    if not prep.llm_deferred:
        return prep, StreamTurnMetrics()

    started = time.perf_counter()
    metrics = StreamTurnMetrics()
    template_type = str(agent.template_type or "qa").strip().lower()
    if template_type == "function_calling":
        template_type = "crm_admin"

    template_config = parse_template_config(agent.template_config)
    compressed = compressed_history
    merged_ctx = dict(orchestrator_decision.runtime_context)
    history_block = f"\n\n[История звонка — последние реплики]\n{compressed}" if compressed else ""
    prompt = apply_phone_style_instructions(
        (agent.system_prompt or "") + history_block,
        state_addon=orchestrator_decision.prompt_addon,
    )
    chat_portrait = await _resolve_chat_portrait(
        session,
        agent_id=agent.id,
        user_external_id=caller_e164.strip(),
        user_message=transcript,
        template_config=template_config,
    )

    call_db_id = int(call.id)
    bundle = _ExecutionBundle()
    syntagma_iter: AsyncIterator[str] | None = None

    ttl = int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC)
    await clear_agent_spoken_text(external_call_id)

    async with telephony_turn_scope(call_db_id, external_call_id=external_call_id):
        if template_type == "qa":
            syntagma_iter = _iter_qa_syntagmas(
                transcript=transcript,
                prompt=prompt,
                knowledge_scope_id=agent.bot_id or agent.id,
                call_db_id=call_db_id,
                external_call_id=external_call_id,
                metrics=metrics,
            )
        else:
            crm_started = time.perf_counter()
            exec_task = asyncio.create_task(
                _run_execute_bundle(
                    template_type=template_type,
                    prompt=prompt,
                    transcript=transcript,
                    agent=agent,
                    caller_e164=caller_e164,
                    template_config=template_config,
                    merged_ctx=merged_ctx,
                    chat_portrait=chat_portrait,
                )
            )
            asyncio.create_task(
                _filler_watch(
                    task=exec_task,
                    call_id=external_call_id,
                    connection_id=connection_id,
                    filler_text=MSG_CRM_FILLER,
                    voice_id=voice_id,
                    language=language,
                    threshold_ms=int(settings.TELEPHONY_CRM_FILLER_THRESHOLD_MS),
                )
            )
            bundle = await exec_task
            metrics.crm_execute_ms = int((time.perf_counter() - crm_started) * 1000)
            if bundle.answer and metrics.llm_first_token_ms is None:
                metrics.llm_first_token_ms = int((time.perf_counter() - started) * 1000)

            async def _crm_chunks() -> AsyncIterator[str]:
                for chunk in split_syntagmas(bundle.answer):
                    if is_cancelled(call_db_id) or is_cancelled_call_id(external_call_id):
                        metrics.cancelled = True
                        break
                    yield chunk

            syntagma_iter = _crm_chunks()

        audio_started = False
        seq = 0
        chunks_plain: list[str] = []
        tts_started = time.perf_counter()

        async for syntagma in syntagma_iter:
            if is_cancelled(call_db_id) or is_cancelled_call_id(external_call_id):
                metrics.cancelled = True
                break
            text = syntagma.strip()
            if not text:
                continue
            chunks_plain.append(text)
            metrics.syntagma_count += 1
            await set_agent_spoken_text(
                external_call_id,
                " ".join(chunks_plain),
                ttl_sec=ttl,
            )

            if not audio_started:
                await publish_agent_audio_start(call_id=external_call_id, connection_id=connection_id)
                audio_started = True

            async for frame in stream_syntagma_pcm16(text, voice_id=voice_id, language=language):
                if metrics.tts_first_byte_ms is None:
                    metrics.tts_first_byte_ms = int((time.perf_counter() - tts_started) * 1000)
                if is_cancelled(call_db_id) or is_cancelled_call_id(external_call_id):
                    metrics.cancelled = True
                    break
                await publish_agent_audio_chunk(
                    call_id=external_call_id,
                    connection_id=connection_id,
                    sequence=seq,
                    audio_pcm16=frame,
                )
                seq += 1
            if metrics.cancelled:
                break

        if audio_started:
            await publish_agent_audio_end(
                call_id=external_call_id,
                connection_id=connection_id,
                reason="cancelled" if metrics.cancelled else "complete",
            )
        await clear_agent_spoken_text(external_call_id)

    answer = " ".join(chunks_plain).strip() or bundle.answer
    use_ssml = settings.TELEPHONY_SSML_ENABLED
    reply_chunks = _apply_prosody_to_chunks(chunks_plain, use_ssml=use_ssml)
    reply_chunks = _prepend_opening_ack(reply_chunks, call_id=call_db_id)

    result = PhoneTurnResult(
        reply_text=answer,
        reply_chunks=reply_chunks,
        actions=[],
        requires_transfer=bundle.requires_owner_handoff,
        play_filler=False,
        dialog_state=prep.dialog_state,
        use_ssml=use_ssml,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    return result, metrics
