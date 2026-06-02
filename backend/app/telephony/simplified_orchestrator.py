"""Simplified telephony orchestrator - uses Voximplant native TTS + ASR.

This module replaces the complex streaming architecture with a simpler
request/response model using Voximplant's built-in TTS and ASR.

Key changes:
- No media gateway WebSocket server
- No streaming TTS/PCM16/ulaw conversion
- No Redis pub/sub for audio chunks
- Uses Voximplant's call.say() for TTS
- Uses Voximplant's call.startASR() for STT
- Backend simply returns text responses to be spoken
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentTelephonyCall
from ..channels.telephony_dialogue import process_phone_turn, PhoneTurnResult
from ..config import settings
from ..services.telephony_orchestrator import (
    CallDialogContext,
    DialogState,
    OrchestratorEventType,
    handle_orchestrator_event,
    sync_context_to_call,
)
from ..router_telephony.service import resolve_telephony_channel
from ..telephony.routing import resolve_agent_by_extension
from .redis_store import (
    append_dialog_turn,
    build_compressed_history,
    get_dialog_meta,
    hgetall_session,
    set_dialog_meta,
)
from .session_cache import cache_resolve_payload

logger = logging.getLogger(__name__)

DEFAULT_WELCOME = "Здравствуйте! Чем могу помочь?"


@dataclass
class ActiveCall:
    """In-memory call state (lightweight, no audio streaming state)."""

    call_id: str
    connection_id: int
    caller_e164: str
    call_db_id: int | None = None
    agent_id: int | None = None
    agent: Any = None  # Agent model
    call: Any = None  # AgentTelephonyCall model
    ctx: CallDialogContext = field(default_factory=CallDialogContext)
    postgres_loaded: bool = False
    awaiting_extension: bool = False
    extension_buffer: str = ""
    routed_by: str = "webhook"


class SimplifiedOrchestrator:
    """Simplified orchestrator without streaming complexity."""

    def __init__(self) -> None:
        self._calls: dict[str, ActiveCall] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, call_id: str) -> asyncio.Lock:
        if call_id not in self._locks:
            self._locks[call_id] = asyncio.Lock()
        return self._locks[call_id]

    def get_call(self, call_id: str) -> ActiveCall | None:
        return self._calls.get(call_id)

    def register_call(
        self,
        call_id: str,
        connection_id: int,
        caller_e164: str,
    ) -> ActiveCall:
        call = ActiveCall(
            call_id=call_id,
            connection_id=connection_id,
            caller_e164=caller_e164,
        )
        self._calls[call_id] = call
        logger.info("simplified_orch: call registered call_id=%s", call_id)
        return call

    def unregister_call(self, call_id: str) -> None:
        if call_id in self._calls:
            del self._calls[call_id]
            self._locks.pop(call_id, None)
            logger.info("simplified_orch: call unregistered call_id=%s", call_id)

    async def _ensure_postgres(self, call: ActiveCall) -> None:
        """Load agent and call data from Postgres once."""
        if call.postgres_loaded:
            return
        if not call.call_db_id:
            return

        async with async_session_maker() as session:
            async with session.begin():
                call_record = await session.scalar(
                    select(AgentTelephonyCall).where(
                        AgentTelephonyCall.id == call.call_db_id,
                        AgentTelephonyCall.connection_id == call.connection_id,
                    )
                )
                if call_record is None:
                    logger.warning("simplified_orch: call not found db_id=%s", call.call_db_id)
                    return

                agent = await session.scalar(
                    select(Agent).where(Agent.id == call_record.agent_id, Agent.is_active.is_(True))
                )
                if agent is None:
                    logger.warning("simplified_orch: agent not found agent_id=%s", call_record.agent_id)
                    return

                call.call = call_record
                call.agent = agent
                call.agent_id = int(agent.id)

                # Load dialog context
                meta = await get_dialog_meta(call.call_id)
                if meta:
                    call.ctx = CallDialogContext.from_meta(meta)

        call.postgres_loaded = True

    async def handle_inbound(
        self,
        call_id: str,
        connection_id: int,
        caller_e164: str,
        called_e164: str | None = None,
    ) -> dict[str, Any]:
        """Handle incoming call - return greeting configuration."""
        async with self._lock(call_id):
            call = self.register_call(call_id, connection_id, caller_e164)

            # Try to resolve agent by DID (dedicated number)
            session_row = await hgetall_session(connection_id)

            # Check if this is a pool call (requires extension) or DID call
            if session_row.get("require_extension", "false").lower() == "true":
                call.awaiting_extension = True
                return {
                    "greeting_text": None,  # Pool greeting is handled by VoxEngine
                    "voice_id": session_row.get("voice_id", "Tatyana"),
                }

            # DID routing - agent already assigned
            welcome_message = session_row.get("welcome_message", DEFAULT_WELCOME)
            call.awaiting_extension = False
            call.routed_by = "did"

            return {
                "greeting_text": welcome_message,
                "voice_id": session_row.get("voice_id", "Tatyana"),
            }

    async def handle_call_answered(
        self,
        call_id: str,
        connection_id: int,
        caller_e164: str,
        extension: str | None = None,
    ) -> dict[str, Any] | None:
        """Handle call answered - resolve agent if needed."""
        async with self._lock(call_id):
            call = self._calls.get(call_id)
            if not call:
                logger.warning("simplified_orch: answered unknown call_id=%s", call_id)
                return None

            if extension and call.awaiting_extension:
                # Resolve agent by extension
                agent_id = await resolve_agent_by_extension(extension)
                if agent_id is None:
                    logger.warning("simplified_orch: extension not found ext=%s", extension)
                    return {
                        "action": "say",
                        "text": "Агент не найден. Попробуйте позже.",
                        "voice_id": "Tatyana",
                    }

                # Assign agent
                call.agent_id = int(agent_id)
                call.extension_buffer = extension
                call.awaiting_extension = False
                call.routed_by = "dtmf"

                # Cache resolution
                async with async_session_maker() as session:
                    async with session.begin():
                        resolved = await resolve_telephony_channel(
                            session,
                            connection_id=connection_id,
                            caller_e164=caller_e164,
                            routed_agent_id=int(agent_id),
                        )

                await cache_resolve_payload(
                    connection_id=connection_id,
                    agent_id=int(agent_id),
                    resolved=resolved,
                    external_call_id=call_id,
                    caller_e164=caller_e164,
                    call_db_id=call.call_db_id,
                )

                # Load from DB
                await self._ensure_postgres(call)

                welcome = str(resolved.get("welcome_message") or DEFAULT_WELCOME)

                # Record greeting as agent turn
                await append_dialog_turn(
                    call_id,
                    role="agent",
                    text=welcome,
                    max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
                    ttl_sec=int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC),
                )

                return {
                    "action": "say",
                    "text": welcome,
                    "voice_id": resolved.get("voice_id", "Tatyana"),
                }

            # DID call - just ensure DB is loaded
            await self._ensure_postgres(call)
            return None

    async def handle_asr_result(
        self,
        call_id: str,
        connection_id: int,
        caller_e164: str,
        transcript: str,
        confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Process ASR result and return next action."""
        async with self._lock(call_id):
            call = self._calls.get(call_id)
            if not call:
                logger.warning("simplified_orch: ASR for unknown call_id=%s", call_id)
                return {"action": "say", "text": "Повторите, пожалуйста."}

            # Ensure DB is loaded
            await self._ensure_postgres(call)

            if not call.agent or not call.call:
                logger.warning("simplified_orch: no agent for call_id=%s", call_id)
                return {"action": "say", "text": "Сервис временно недоступен."}

            # Get compressed history
            compressed = await build_compressed_history(
                call_id,
                max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
            )

            # Handle orchestrator event
            decision = handle_orchestrator_event(
                call.ctx,
                OrchestratorEventType.STT_FINAL,
                transcript=transcript,
                compressed_history=compressed,
            )

            # Process the turn (LLM)
            async with async_session_maker() as session:
                result = await process_phone_turn(
                    session,
                    call=call.call,
                    agent=call.agent,
                    user_transcript=transcript,
                    caller_e164=caller_e164,
                    runtime_context=decision.runtime_context if decision else {},
                    orchestrator_decision=decision,
                )

            # Save dialog turns
            if transcript:
                await append_dialog_turn(
                    call_id,
                    role="user",
                    text=transcript,
                    max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
                    ttl_sec=int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC),
                )

            if result.reply_text:
                await append_dialog_turn(
                    call_id,
                    role="agent",
                    text=result.reply_text,
                    max_turns=int(settings.TELEPHONY_DIALOG_MAX_TURNS),
                    ttl_sec=int(settings.TELEPHONY_REDIS_SESSION_TTL_SEC),
                )

            # Save context
            await set_dialog_meta(
                call_id,
                call.ctx.to_meta(),
                ttl_sec=settings.TELEPHONY_REDIS_SESSION_TTL_SEC,
            )

            # Determine action
            if result.requires_transfer:
                return {
                    "action": "transfer",
                    "text": result.reply_text or "Соединяю с оператором.",
                    "destination": "operator",
                }

            for action in result.actions:
                if action.get("type") == "hangup":
                    return {
                        "action": "hangup",
                        "text": result.reply_text or "До свидания!",
                    }

            return {
                "action": "say",
                "text": result.reply_text,
                "voice_id": "Tatyana",  # Could be mapped from config
            }

    async def handle_hangup(self, call_id: str) -> None:
        """Clean up call state."""
        self.unregister_call(call_id)
        # Dialog history remains in Redis for persistence

    async def get_next_response(
        self,
        call_id: str,
    ) -> dict[str, Any] | None:
        """Poll for next response (for future async support)."""
        call = self._calls.get(call_id)
        if not call:
            return None
        # Currently synchronous - response is immediate
        return None


# Singleton instance
_orchestrator: SimplifiedOrchestrator | None = None


def get_simplified_orchestrator() -> SimplifiedOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SimplifiedOrchestrator()
    return _orchestrator
