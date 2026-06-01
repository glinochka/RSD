"""Stateful dialog orchestrator — Redis events + call affinity (stage 4)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentTelephonyCall
from ..channels.telephony_dialogue import PhoneTurnResult
from .stream_cancel import cancel_turn, cancel_turn_by_call_id
from .stream_pipeline import StreamTurnMetrics, stream_agent_reply, stream_fixed_phrase
from .outbound_publish import (
    publish_agent_audio_chunk,
    publish_agent_audio_end,
    publish_agent_audio_start,
    publish_call_transfer,
)
from .stream_tts import assert_stream_tts_configured
from ..config import settings
from ..telephony import metrics as telephony_metrics
from ..telephony.latency_budget import (
    apply_budget_to_call_metadata,
    budget_from_gateway,
    budget_from_stream_metrics,
    merge_budget,
)
from ..router_telephony.service import resolve_telephony_channel
from ..telephony.routing import resolve_agent_by_extension, routing_summary_for_call
from ..services.telephony_orchestrator import (
    CallDialogContext,
    DialogState,
    OrchestratorEventType,
    handle_orchestrator_event,
    sync_context_to_call,
)
from .dialog_batch import PendingTurn, flush_turn_batch
from .redis_store import (
    append_dialog_turn,
    build_compressed_history,
    clear_agent_spoken_text,
    close_redis,
    get_agent_spoken_text,
    get_call_mapping,
    get_dialog_meta,
    hgetall_session,
    purge_hot_dialog,
    redis_enabled,
    set_dialog_meta,
    subscribe_orch_events,
)
from .session_cache import cache_call_mapping, cache_resolve_payload
from .stream_tts import stream_syntagma_pcm16

logger = logging.getLogger(__name__)

DEFAULT_TELEPHONY_WELCOME = "Здравствуйте! Чем могу помочь?"
TELEPHONY_AGENT_NOT_FOUND_PHRASE = "Агент не найден"


def resolve_telephony_welcome_text(raw: str | None) -> str:
    text = str(raw or "").strip()
    return text or DEFAULT_TELEPHONY_WELCOME


@dataclass
class CallSlot:
    call_id: str
    connection_id: int
    caller_e164: str
    call_db_id: int | None = None
    agent_id: int | None = None
    ctx: CallDialogContext = field(default_factory=CallDialogContext)
    call: AgentTelephonyCall | None = None
    agent: Agent | None = None
    postgres_loaded: bool = False
    pending_db_turns: list[PendingTurn] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    awaiting_extension: bool = False
    dtmf_buffer: str = ""
    routed_by: str = "webhook"


class OrchestratorWorker:
    def __init__(self) -> None:
        self._slots: dict[str, CallSlot] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._running = False

    def _lock_for(self, call_id: str) -> asyncio.Lock:
        if call_id not in self._locks:
            self._locks[call_id] = asyncio.Lock()
        return self._locks[call_id]

    def _slot(self, call_id: str, connection_id: int, caller_e164: str) -> CallSlot:
        slot = self._slots.get(call_id)
        if slot is None:
            slot = CallSlot(call_id=call_id, connection_id=connection_id, caller_e164=caller_e164)
            self._slots[call_id] = slot
        slot.last_activity = time.time()
        return slot

    async def _warm_session_cache(self, slot: CallSlot) -> dict[str, str]:
        cached = await hgetall_session(slot.connection_id)
        if cached:
            return cached
        async with async_session_maker() as session:
            async with session.begin():
                resolved = await resolve_telephony_channel(
                    session,
                    connection_id=slot.connection_id,
                    caller_e164=slot.caller_e164,
                )
        await cache_resolve_payload(
            connection_id=slot.connection_id,
            agent_id=int(resolved["agent_id"]),
            resolved=resolved,
            external_call_id=slot.call_id,
            caller_e164=slot.caller_e164,
            call_db_id=slot.call_db_id,
        )
        return await hgetall_session(slot.connection_id)

    async def _ensure_call_mapping(self, slot: CallSlot) -> None:
        if slot.call_db_id is not None:
            return
        mapping = await get_call_mapping(slot.call_id)
        if mapping:
            slot.call_db_id = int(mapping.get("call_db_id") or 0) or None
            slot.agent_id = int(mapping.get("agent_id") or 0) or None
            if mapping.get("caller_e164"):
                slot.caller_e164 = str(mapping["caller_e164"])

    async def _load_postgres_once(self, slot: CallSlot) -> None:
        if slot.postgres_loaded:
            return
        await self._ensure_call_mapping(slot)
        if not slot.call_db_id:
            logger.warning("orchestrator missing call_db_id call_id=%s", slot.call_id)
            return
        async with async_session_maker() as session:
            call = await session.scalar(
                select(AgentTelephonyCall).where(
                    AgentTelephonyCall.id == slot.call_db_id,
                    AgentTelephonyCall.connection_id == slot.connection_id,
                )
            )
            if call is None:
                logger.warning("orchestrator call not found db_id=%s", slot.call_db_id)
                return
            agent = await session.scalar(
                select(Agent).where(Agent.id == call.agent_id, Agent.is_active.is_(True))
            )
            if agent is None:
                logger.warning("orchestrator agent not found agent_id=%s", call.agent_id)
                return
            slot.call = call
            slot.agent = agent
            slot.agent_id = int(agent.id)
            meta = await get_dialog_meta(slot.call_id)
            if meta:
                slot.ctx = CallDialogContext.from_meta(meta)
            else:
                slot.ctx = CallDialogContext.from_meta(call.metadata_ if isinstance(call.metadata_, dict) else {})
        slot.postgres_loaded = True

    async def _flush_pending_turns(
        self,
        slot: CallSlot,
        *,
        stream_metrics: StreamTurnMetrics | None = None,
        gateway_inner: dict[str, Any] | None = None,
        wall_ms: int | None = None,
    ) -> None:
        if not slot.pending_db_turns or not slot.call_db_id:
            return
        batch = list(slot.pending_db_turns)
        slot.pending_db_turns.clear()
        gw_budget = budget_from_gateway(gateway_inner or {})
        st_budget = budget_from_stream_metrics(stream_metrics)
        async with async_session_maker() as session:
            async with session.begin():
                await flush_turn_batch(session, call_db_id=int(slot.call_db_id), turns=batch)
                call = await session.get(AgentTelephonyCall, int(slot.call_db_id))
                sip_ms = None
                if call is not None and isinstance(call.metadata_, dict):
                    raw_sip = call.metadata_.get("sip_ms")
                    if raw_sip is not None:
                        try:
                            sip_ms = int(raw_sip)
                        except (TypeError, ValueError):
                            sip_ms = None
                latency_budget = merge_budget(gw_budget, st_budget, sip_ms=sip_ms, wall_ms=wall_ms)
                if call is not None:
                    sync_context_to_call(call, slot.ctx)
                    meta = dict(call.metadata_ or {}) if isinstance(call.metadata_, dict) else {}
                    if stream_metrics is not None:
                        meta["stream_metrics"] = stream_metrics.to_dict()
                        if stream_metrics.llm_first_token_ms is not None:
                            meta["llm_first_token_ms"] = stream_metrics.llm_first_token_ms
                        if stream_metrics.tts_first_byte_ms is not None:
                            meta["tts_first_byte_ms"] = stream_metrics.tts_first_byte_ms
                    meta = apply_budget_to_call_metadata(meta, latency_budget)
                    call.metadata_ = meta
                    telephony_metrics.record_latency_budget(latency_budget)
        await set_dialog_meta(slot.call_id, slot.ctx.to_meta(), ttl_sec=settings.TELEPHONY_REDIS_SESSION_TTL_SEC)

    async def _routing_flags_from_call(self, slot: CallSlot) -> None:
        if not slot.call_db_id:
            return
        async with async_session_maker() as session:
            call = await session.get(AgentTelephonyCall, int(slot.call_db_id))
            if call is None:
                return
            meta = call.metadata_ if isinstance(call.metadata_, dict) else {}
            routing = meta.get("routing") if isinstance(meta.get("routing"), dict) else {}
            slot.routed_by = str(routing.get("routed_by") or "webhook")
            slot.awaiting_extension = slot.routed_by != "did"

    async def _stream_routing_phrase(
        self,
        slot: CallSlot,
        text: str,
        *,
        log_label: str,
        record_agent_turn: bool = False,
        set_greet_state: bool = False,
    ) -> None:
        plain = str(text or "").strip()
        logger.info(
            "orchestrator _stream_routing_phrase call_id=%s log_label=%s text=%r plain=%r empty=%s",
            slot.call_id,
            log_label,
            text,
            plain,
            not plain,
        )
        if not plain:
            logger.warning(
                "orchestrator %s SKIPPED (empty text) call_id=%s",
                log_label,
                slot.call_id,
            )
            return
        session_row = await hgetall_session(slot.connection_id)
        voice_id = str(session_row.get("voice_id") or "default")
        language = str(session_row.get("language") or "ru-RU")
        logger.info(
            "orchestrator %s starting TTS call_id=%s voice=%s lang=%s text_len=%d",
            log_label,
            slot.call_id,
            voice_id,
            language,
            len(plain),
        )

        async def _mark_phrase_delivered() -> None:
            if record_agent_turn:
                await append_dialog_turn(
                    slot.call_id,
                    role="agent",
                    text=plain,
                    max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
                    ttl_sec=int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC),
                )
            if set_greet_state:
                slot.ctx.state = DialogState.GREET
                await set_dialog_meta(
                    slot.call_id,
                    slot.ctx.to_meta(),
                    ttl_sec=settings.TELEPHONY_REDIS_SESSION_TTL_SEC,
                )

        async def _publish_batch_fallback() -> bool:
            sent = False
            await publish_agent_audio_start(
                call_id=slot.call_id,
                connection_id=slot.connection_id,
            )
            seq = 0
            async for frame in stream_syntagma_pcm16(
                plain,
                voice_id=voice_id,
                language=language,
            ):
                await publish_agent_audio_chunk(
                    call_id=slot.call_id,
                    connection_id=slot.connection_id,
                    sequence=seq,
                    audio_pcm16=frame,
                )
                sent = True
                seq += 1
            if not sent:
                return False
            await publish_agent_audio_end(
                call_id=slot.call_id,
                connection_id=slot.connection_id,
                reason="complete",
            )
            return True

        try:
            assert_stream_tts_configured()
            metrics = await stream_fixed_phrase(
                call_id=slot.call_id,
                connection_id=slot.connection_id,
                call_db_id=slot.call_db_id,
                text=plain,
                voice_id=voice_id,
                language=language,
            )
            # If stream TTS path produced no first-byte timestamp, force a batch fallback.
            if metrics.syntagma_count > 0 and metrics.tts_first_byte_ms is None:
                raise RuntimeError("stream_tts_no_audio_frames")
            logger.info(
                "orchestrator %s TTS completed call_id=%s",
                log_label,
                slot.call_id,
            )
            if log_label == "welcome":
                logger.info(
                    "[orchestrator] welcome guaranteed path=stream call_id=%s",
                    slot.call_id,
                )
            await _mark_phrase_delivered()
        except Exception as exc:
            logger.error(
                "orchestrator %s TTS failed call_id=%s: %s",
                log_label,
                slot.call_id,
                exc,
            )
            try:
                if await _publish_batch_fallback():
                    logger.info(
                        "orchestrator %s batch fallback TTS completed call_id=%s",
                        log_label,
                        slot.call_id,
                    )
                    if log_label == "welcome":
                        logger.info(
                            "[orchestrator] welcome guaranteed path=fallback call_id=%s",
                            slot.call_id,
                        )
                    await _mark_phrase_delivered()
                else:
                    logger.error(
                        "orchestrator %s batch fallback produced empty audio call_id=%s",
                        log_label,
                        slot.call_id,
                    )
            except Exception as fb_exc:
                logger.error(
                    "orchestrator %s batch fallback failed call_id=%s: %s",
                    log_label,
                    slot.call_id,
                    fb_exc,
                )

    async def _play_agent_welcome(self, slot: CallSlot, *, welcome_raw: str | None) -> None:
        welcome_text = resolve_telephony_welcome_text(welcome_raw)
        logger.info(
            "orchestrator _play_agent_welcome call_id=%s welcome_raw=%r welcome_text=%r",
            slot.call_id,
            welcome_raw,
            welcome_text,
        )
        await self._stream_routing_phrase(
            slot,
            welcome_text,
            log_label="welcome",
            record_agent_turn=True,
            set_greet_state=True,
        )

    async def _apply_routed_agent(self, slot: CallSlot, agent_id: int, *, extension: str) -> None:
        slot.agent_id = int(agent_id)
        slot.awaiting_extension = False
        slot.dtmf_buffer = ""
        slot.postgres_loaded = False
        async with async_session_maker() as session:
            async with session.begin():
                agent = await session.scalar(
                    select(Agent).where(Agent.id == int(agent_id), Agent.is_active.is_(True))
                )
                if agent is None:
                    logger.warning("orchestrator dtmf route agent missing id=%s", agent_id)
                    await self._stream_routing_phrase(
                        slot,
                        TELEPHONY_AGENT_NOT_FOUND_PHRASE,
                        log_label="route_agent_missing",
                    )
                    return
                if slot.call_db_id:
                    call = await session.get(AgentTelephonyCall, int(slot.call_db_id))
                    if call is not None:
                        call.agent_id = int(agent.id)
                        meta = dict(call.metadata_ or {}) if isinstance(call.metadata_, dict) else {}
                        meta["routing"] = routing_summary_for_call(
                            routed_by="dtmf",
                            called_e164="",
                            routing_extension=extension,
                        )
                        call.metadata_ = meta
                resolved = await resolve_telephony_channel(
                    session,
                    connection_id=slot.connection_id,
                    caller_e164=slot.caller_e164,
                    routed_agent_id=int(agent.id),
                )
        await cache_resolve_payload(
            connection_id=slot.connection_id,
            agent_id=int(agent_id),
            resolved=resolved,
            external_call_id=slot.call_id,
            caller_e164=slot.caller_e164,
            call_db_id=slot.call_db_id,
        )
        # Play greeting as soon as routing is resolved (do not wait for extra DB hydration).
        await self._play_agent_welcome(
            slot,
            welcome_raw=str(resolved.get("welcome_message") or ""),
        )
        await self._load_postgres_once(slot)
        logger.info(
            "orchestrator dtmf routed call_id=%s extension=%s agent_id=%s",
            slot.call_id,
            extension,
            agent_id,
        )

    async def handle_dtmf(self, payload: dict[str, Any]) -> None:
        call_id = str(payload.get("call_id") or "").strip()
        connection_id = int(payload.get("connection_id") or 0)
        caller_e164 = str(payload.get("caller_e164") or "").strip()
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        digit = str(inner.get("digit") or "").strip()
        if not call_id or not digit or not digit.isdigit():
            return
        slot = self._slots.get(call_id) or self._slot(call_id, connection_id, caller_e164)
        async with self._lock_for(call_id):
            await self._ensure_call_mapping(slot)
            if not slot.awaiting_extension and slot.routed_by == "did":
                return
            if not slot.awaiting_extension:
                await self._routing_flags_from_call(slot)
            if not slot.awaiting_extension:
                return
            slot.dtmf_buffer = f"{slot.dtmf_buffer}{digit}"[-4:]
            if len(slot.dtmf_buffer) < 4:
                return
            agent_id = await resolve_agent_by_extension(slot.dtmf_buffer)
            if agent_id is None:
                slot.dtmf_buffer = ""
                await self._stream_routing_phrase(
                    slot,
                    TELEPHONY_AGENT_NOT_FOUND_PHRASE,
                    log_label="dtmf_agent_not_found",
                )
                return
            await self._apply_routed_agent(slot, int(agent_id), extension=slot.dtmf_buffer)

    async def handle_session_start(self, payload: dict[str, Any]) -> None:
        call_id = str(payload.get("call_id") or "").strip()
        connection_id = int(payload.get("connection_id") or 0)
        caller_e164 = str(payload.get("caller_e164") or "").strip()
        if not call_id or connection_id <= 0:
            return
        slot = self._slot(call_id, connection_id, caller_e164)
        async with self._lock_for(call_id):
            await self._ensure_call_mapping(slot)
            await self._routing_flags_from_call(slot)
            await self._warm_session_cache(slot)
            handle_orchestrator_event(slot.ctx, OrchestratorEventType.SESSION_START)
            await set_dialog_meta(slot.call_id, slot.ctx.to_meta(), ttl_sec=settings.TELEPHONY_REDIS_SESSION_TTL_SEC)
            if not slot.awaiting_extension:
                session_row = await hgetall_session(connection_id)
                await self._play_agent_welcome(
                    slot,
                    welcome_raw=str(session_row.get("welcome_message") or ""),
                )
            logger.info(
                "orchestrator session.start call_id=%s connection_id=%s redis_session=%s awaiting_ext=%s",
                call_id,
                connection_id,
                bool(await hgetall_session(connection_id)),
                slot.awaiting_extension,
            )

    async def handle_barge_in(self, payload: dict[str, Any]) -> None:
        call_id = str(payload.get("call_id") or "").strip()
        if not call_id:
            return
        slot = self._slots.get(call_id)
        if slot is None:
            return
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        interrupted = str(inner.get("interrupted_agent_text") or "").strip() or None
        if not interrupted:
            interrupted = await get_agent_spoken_text(call_id)
        async with self._lock_for(call_id):
            if slot.call_db_id:
                cancel_turn(int(slot.call_db_id))
            cancel_turn_by_call_id(call_id)
            await publish_agent_audio_end(
                call_id=call_id,
                connection_id=slot.connection_id,
                reason="barge_in",
            )
            handle_orchestrator_event(
                slot.ctx,
                OrchestratorEventType.BARGE_IN,
                interrupted_agent_text=interrupted,
            )
            await clear_agent_spoken_text(call_id)
            await set_dialog_meta(slot.call_id, slot.ctx.to_meta(), ttl_sec=settings.TELEPHONY_REDIS_SESSION_TTL_SEC)
            logger.info(
                "orchestrator barge_in call_id=%s interrupted_len=%s at_ms=%s",
                call_id,
                len(interrupted or ""),
                inner.get("at_ms"),
            )

    async def handle_stt_final(self, payload: dict[str, Any]) -> None:
        call_id = str(payload.get("call_id") or "").strip()
        connection_id = int(payload.get("connection_id") or 0)
        caller_e164 = str(payload.get("caller_e164") or "").strip()
        inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        transcript = str(inner.get("text") or "").strip()
        if not call_id or connection_id <= 0:
            return

        slot = self._slot(call_id, connection_id, caller_e164)
        async with self._lock_for(call_id):
            started = time.perf_counter()
            await self._ensure_call_mapping(slot)
            await self._warm_session_cache(slot)
            await self._load_postgres_once(slot)
            if slot.call is None or slot.agent is None:
                logger.warning("orchestrator stt.final skipped — no postgres call call_id=%s", call_id)
                return

            compressed = await build_compressed_history(
                call_id,
                max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
            )
            decision = handle_orchestrator_event(
                slot.ctx,
                OrchestratorEventType.STT_FINAL,
                transcript=transcript,
                compressed_history=compressed,
            )
            if decision is None:
                return

            stream_metrics: StreamTurnMetrics | None = None
            if decision.suggest_dtmf_menu and not transcript:
                msg = "Не расслышал. Наберите добавочный номер на клавиатуре."
                session_row = await hgetall_session(connection_id)
                voice_id = str(session_row.get("voice_id") or "default")
                language = str(session_row.get("language") or "ru-RU")
                assert_stream_tts_configured()
                stream_metrics = await stream_fixed_phrase(
                    call_id=call_id,
                    connection_id=connection_id,
                    call_db_id=slot.call_db_id,
                    text=msg,
                    voice_id=voice_id,
                    language=language,
                )
                reply = PhoneTurnResult(
                    reply_text=msg,
                    stt_empty=True,
                    dialog_state=decision.state.value,
                )
            else:
                session_row = await hgetall_session(connection_id)
                voice_id = str(session_row.get("voice_id") or "default")
                language = str(session_row.get("language") or "ru-RU")
                async with async_session_maker() as session:
                    async with session.begin():
                        call = await session.merge(slot.call)  # type: ignore[arg-type]
                        agent = await session.merge(slot.agent)  # type: ignore[arg-type]
                        assert_stream_tts_configured()
                        if not settings.TELEPHONY_STREAMING_ENABLED:
                            raise RuntimeError("TELEPHONY_STREAMING_ENABLED must be true for PSTN")
                        reply, stream_metrics = await stream_agent_reply(
                            session,
                            call=call,
                            agent=agent,
                            caller_e164=slot.caller_e164,
                            transcript=transcript,
                            orchestrator_decision=decision,
                            external_call_id=call_id,
                            connection_id=connection_id,
                            voice_id=voice_id,
                            language=language,
                            compressed_history=compressed,
                        )

            if transcript:
                await append_dialog_turn(
                    call_id,
                    role="user",
                    text=transcript,
                    max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
                    ttl_sec=int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC),
                )
                slot.pending_db_turns.append(PendingTurn(role="user", transcript=transcript))
            if reply.reply_text.strip():
                await append_dialog_turn(
                    call_id,
                    role="agent",
                    text=reply.reply_text,
                    max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
                    ttl_sec=int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC),
                )
                slot.pending_db_turns.append(
                    PendingTurn(
                        role="agent",
                        transcript=reply.reply_text,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                )

            wall_ms = int((time.perf_counter() - started) * 1000)
            await self._flush_pending_turns(
                slot,
                stream_metrics=stream_metrics,
                gateway_inner=inner,
                wall_ms=wall_ms,
            )
            if reply.requires_transfer:
                session_row = await hgetall_session(connection_id)
                operator_e164 = str(session_row.get("operator_transfer_e164") or "operator").strip()
                await publish_call_transfer(
                    call_id=call_id,
                    connection_id=connection_id,
                    e164=operator_e164,
                )

            logger.info(
                "orchestrator stt.final ok call_id=%s db_id=%s latency_ms=%s redis_history_len=%s",
                call_id,
                slot.call_db_id,
                int((time.perf_counter() - started) * 1000),
                len(compressed.splitlines()) if compressed else 0,
            )

    async def handle_session_end(self, payload: dict[str, Any]) -> None:
        call_id = str(payload.get("call_id") or "").strip()
        if not call_id:
            return
        async with self._lock_for(call_id):
            slot = self._slots.pop(call_id, None)
        self._locks.pop(call_id, None)
        if slot is None:
            return
        await self._flush_pending_turns(slot)
        await purge_hot_dialog(call_id)
        logger.info("orchestrator session.end call_id=%s", call_id)

    async def dispatch(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("orchestrator invalid json event")
            return
        if not isinstance(msg, dict):
            return
        event_type = str(msg.get("type") or "").strip()
        try:
            if event_type == OrchestratorEventType.SESSION_START.value:
                await self.handle_session_start(msg)
            elif event_type == OrchestratorEventType.STT_FINAL.value:
                await self.handle_stt_final(msg)
            elif event_type == OrchestratorEventType.BARGE_IN.value:
                await self.handle_barge_in(msg)
            elif event_type == OrchestratorEventType.DTMF.value:
                await self.handle_dtmf(msg)
            elif event_type == OrchestratorEventType.SESSION_END.value:
                await self.handle_session_end(msg)
        except Exception:
            logger.exception("orchestrator handler failed type=%s", event_type)

    async def run_forever(self) -> None:
        if not redis_enabled():
            raise RuntimeError("REDIS_URL is required for telephony orchestrator worker")
        self._running = True
        pubsub = await subscribe_orch_events()
        logger.info("orchestrator worker subscribed to Redis events")
        try:
            while self._running:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.05)
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                if isinstance(data, str) and data:
                    await self.dispatch(data)
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()
            await close_redis()

    def stop(self) -> None:
        self._running = False


_worker: OrchestratorWorker | None = None


def get_worker() -> OrchestratorWorker:
    global _worker
    if _worker is None:
        _worker = OrchestratorWorker()
    return _worker
