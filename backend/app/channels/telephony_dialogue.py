"""Phone turn dialogue — template runtime without bot_id channel managers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentAnalyticsMessage, AgentTelephonyCall, AgentTelephonyTurn
from ..services.qa_handoff_service import EscalationType as QAEscalationType, get_qa_handoff_service
from ..services.template_runtime import EscalationType, get_template_runtime
from ..telephony.agent_guards import (
    availability_allows,
    is_subscription_valid,
    is_user_frozen,
    parse_template_config,
)
from ..config import settings
from ..services.telephony_orchestrator import (
    DialogState,
    build_compressed_turn_context,
    decide_orchestrator,
    load_dialog_state,
)
from ..telephony.dtmf import dtmf_menu_prompt
from ..telephony.intent import detect_hangup_intent, detect_operator_transfer_intent
from ..telephony.prompt import apply_phone_style_instructions
from ..telephony.prosody import format_spoken_numbers, wrap_ssml_prosody
from ..telephony.stream_cancel import telephony_turn_scope
from ..telephony.streaming import split_sentences
from ..utils.pii import redact_pii_text

logger = logging.getLogger(__name__)

PHONE_CHANNEL = "phone"
MSG_STT_EMPTY = "Не расслышал, повторите, пожалуйста."
MSG_SERVICE_UNAVAILABLE = "Сервис временно недоступен. Сейчас соединю с оператором."
MSG_LLM_ERROR = "Извините, техническая ошибка. Сейчас соединю с оператором."
MSG_LLM_FILLER = "Секунду, думаю над ответом."
MSG_CRM_FILLER = "Секунду, смотрю в расписании…"
MSG_RAG_FILLER = "Да, сейчас уточню, подождите пожалуйста."
_OPENING_ACKS = ("Угу.", "Так.", "Эм…", "Понял.", "Да-да.")


@dataclass
class PhoneTurnResult:
    reply_text: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    reply_chunks: list[str] = field(default_factory=list)
    latency_ms: int = 0
    requires_transfer: bool = False
    stt_empty: bool = False
    partial: bool = False
    end_of_turn: bool = True
    confidence: float | None = None
    play_filler: bool = False
    dialog_state: str = "LISTEN"
    use_ssml: bool = True


async def _log_analytics(
    session: AsyncSession,
    *,
    agent_id: int,
    analytics_namespace_id: int,
    role: str,
    message_text: str,
    caller_e164: str,
) -> None:
    session.add(
        AgentAnalyticsMessage(
            agent_id=agent_id,
            bot_id=analytics_namespace_id,
            role=role,
            channel=PHONE_CHANNEL,
            user_external_id=caller_e164.strip(),
            user_display_name=None,
            telegram_peer_access_hash=None,
            message_text=redact_pii_text(message_text),
        )
    )


async def _persist_turn(
    session: AsyncSession,
    *,
    call_db_id: int,
    role: str,
    transcript: str,
    latency_ms: int | None,
) -> None:
    session.add(
        AgentTelephonyTurn(
            call_id=call_db_id,
            role=role,
            transcript=redact_pii_text(transcript),
            latency_ms=latency_ms,
        )
    )


def _crm_tools_slow(tool_events: list[dict[str, Any]]) -> bool:
    threshold = max(500, int(settings.TELEPHONY_CRM_FILLER_THRESHOLD_MS))
    for event in tool_events:
        if not isinstance(event, dict):
            continue
        latency = int(event.get("latency_ms") or 0)
        if latency >= threshold and event.get("crm_provider"):
            return True
    return False


def _prepend_opening_ack(chunks: list[str], *, call_id: int) -> list[str]:
    if not chunks:
        return chunks
    ack = _OPENING_ACKS[int(call_id) % len(_OPENING_ACKS)]
    first = (chunks[0] or "").strip()
    prefix = ack.lower().rstrip(".…")
    if first.lower().startswith(prefix):
        return chunks
    out = list(chunks)
    out[0] = f"{ack} {first}"
    return out


def _filler_for_turn(*, used_rag: bool, crm_slow: bool) -> tuple[str | None, bool]:
    if crm_slow:
        return MSG_CRM_FILLER, True
    if used_rag:
        return MSG_RAG_FILLER, True
    return None, False


def _apply_prosody_to_chunks(chunks: list[str], *, use_ssml: bool) -> list[str]:
    if not chunks:
        return chunks
    out: list[str] = []
    for chunk in chunks:
        text = format_spoken_numbers(chunk)
        out.append(wrap_ssml_prosody(text) if use_ssml else text)
    return out


def _phone_portrait_enabled(template_config: dict[str, Any]) -> bool:
    if template_config.get("enable_phone_portrait") is True:
        return True
    if template_config.get("enable_phone_portrait") is False:
        return False
    return bool(template_config.get("enable_chat_portrait", False))


async def _resolve_chat_portrait(
    session: AsyncSession,
    *,
    agent_id: int,
    user_external_id: str,
    user_message: str,
    template_config: dict[str, Any],
) -> str:
    if not _phone_portrait_enabled(template_config):
        return ""
    try:
        return await get_template_runtime().update_chat_portrait(
            agent_id=agent_id,
            user_external_id=user_external_id,
            user_message=user_message,
            template_config=template_config,
        )
    except Exception:
        logger.exception("telephony phone portrait update failed agent_id=%s", agent_id)
        return ""


async def process_phone_turn(
    session: AsyncSession,
    *,
    call: AgentTelephonyCall,
    agent: Agent,
    user_transcript: str,
    caller_e164: str,
    runtime_context: dict[str, Any] | None = None,
    use_streaming: bool | None = None,
    barged_in: bool = False,
    interrupted_agent_text: str | None = None,
    persist_turns: bool = True,
    compressed_history_override: str | None = None,
) -> PhoneTurnResult:
    base_ctx = dict(runtime_context or {})
    transcript = (user_transcript or "").strip()
    if not transcript:
        orch = decide_orchestrator(call, transcript="", stt_empty=True)
        if orch.suggest_dtmf_menu:
            return PhoneTurnResult(
                reply_text=dtmf_menu_prompt(),
                stt_empty=True,
                dialog_state=orch.state.value,
                actions=[{"type": "enable_dtmf", "digits": "120"}],
            )
        return PhoneTurnResult(reply_text=MSG_STT_EMPTY, stt_empty=True, dialog_state=orch.state.value)

    if not await is_subscription_valid(session, agent.id):
        return PhoneTurnResult(
            reply_text="Извините, сервис временно недоступен.",
            actions=[{"type": "hangup", "reason": "subscription_expired"}],
        )

    if await is_user_frozen(session, agent.id, caller_e164):
        return PhoneTurnResult(
            reply_text="Доступ к сервису для вас ограничён.",
            actions=[{"type": "hangup", "reason": "blocked"}],
        )

    template_config = parse_template_config(agent.template_config)
    if not availability_allows(template_config):
        return PhoneTurnResult(
            reply_text="Сейчас мы не принимаем звонки. Попробуйте позже.",
            actions=[{"type": "hangup", "reason": "outside_hours"}],
        )

    if detect_hangup_intent(transcript):
        return PhoneTurnResult(
            reply_text="До свидания! Хорошего дня.",
            actions=[{"type": "hangup", "reason": "user_goodbye"}],
        )

    keyword_transfer = detect_operator_transfer_intent(transcript)

    analytics_ns = agent.bot_id or agent.id
    await _log_analytics(
        session,
        agent_id=agent.id,
        analytics_namespace_id=analytics_ns,
        role="user",
        message_text=transcript,
        caller_e164=caller_e164,
    )
    if persist_turns:
        await _persist_turn(session, call_db_id=int(call.id), role="user", transcript=transcript, latency_ms=None)

    if compressed_history_override is not None:
        compressed = compressed_history_override
    else:
        compressed = await build_compressed_turn_context(session, int(call.id))
    orch = decide_orchestrator(
        call,
        transcript=transcript,
        barged_in=barged_in,
        interrupted_agent_text=interrupted_agent_text,
        compressed_history=compressed,
    )
    merged_ctx = {**base_ctx, **orch.runtime_context}

    if compressed and not _phone_portrait_enabled(template_config):
        history_block = f"\n\n[История звонка — последние реплики]\n{compressed}"
    else:
        history_block = ""

    prompt = apply_phone_style_instructions(
        (agent.system_prompt or "") + history_block,
        state_addon=orch.prompt_addon,
    )
    streaming_on = settings.TELEPHONY_STREAMING_ENABLED if use_streaming is None else bool(use_streaming)
    normalized_template = str(agent.template_type or "qa").strip().lower()
    reply_chunks: list[str] = []
    play_filler = False
    filler_text: str | None = None
    chat_portrait = await _resolve_chat_portrait(
        session,
        agent_id=agent.id,
        user_external_id=caller_e164.strip(),
        user_message=transcript,
        template_config=template_config,
    )

    async with telephony_turn_scope(int(call.id)):
        execution = await get_template_runtime().execute(
            template_type=agent.template_type,
            prompt=prompt,
            user_message=transcript,
            knowledge_scope_id=agent.bot_id or agent.id,
            agent_id=agent.id,
            user_external_id=caller_e164.strip(),
            template_config=template_config,
            source_channel=PHONE_CHANNEL,
            chat_portrait=chat_portrait,
            runtime_context=merged_ctx,
        )
        answer = (execution.answer or "").strip()
        crm_slow = _crm_tools_slow(list(execution.tool_events or []))
        filler_text, play_filler = _filler_for_turn(
            used_rag=bool(execution.sources),
            crm_slow=crm_slow,
        )
        if streaming_on and answer:
            reply_chunks = split_sentences(answer)
        requires_owner_handoff = bool(execution.requires_owner_handoff)
        escalation_type = execution.escalation_type
        owner_handoff_reason = execution.owner_handoff_reason

    if not reply_chunks and answer:
        reply_chunks = split_sentences(answer)

    use_ssml = settings.TELEPHONY_SSML_ENABLED
    reply_chunks = _apply_prosody_to_chunks(reply_chunks, use_ssml=use_ssml)
    reply_chunks = _prepend_opening_ack(reply_chunks, call_id=int(call.id))
    if answer and not reply_chunks:
        answer = wrap_ssml_prosody(format_spoken_numbers(answer)) if use_ssml else format_spoken_numbers(answer)

    actions: list[dict[str, Any]] = []
    if orch.state == DialogState.HANDOFF:
        keyword_transfer = True
    if orch.state == DialogState.CLOSE and not detect_hangup_intent(answer):
        actions.append({"type": "hangup", "reason": "dialog_close"})
    if play_filler and filler_text:
        actions.append({"type": "play_filler", "text": filler_text})

    requires_transfer = requires_owner_handoff or keyword_transfer

    if detect_hangup_intent(answer):
        await _log_analytics(
            session,
            agent_id=agent.id,
            analytics_namespace_id=analytics_ns,
            role="agent",
            message_text=answer or "До свидания!",
            caller_e164=caller_e164,
        )
        if persist_turns:
            await _persist_turn(
                session,
                call_db_id=int(call.id),
                role="agent",
                transcript=answer or "До свидания!",
                latency_ms=None,
            )
        return PhoneTurnResult(
            reply_text=answer or "До свидания! Хорошего дня.",
            actions=[{"type": "hangup", "reason": "agent_goodbye"}],
        )

    if requires_transfer:
        if normalized_template == "qa":
            qa_type = (
                QAEscalationType.FREEZE_CHAT
                if escalation_type == EscalationType.FREEZE_CHAT
                else QAEscalationType.NOTIFY_ONLY
            )
            handoff_reason = owner_handoff_reason or (
                "keyword_operator_request" if keyword_transfer else None
            )
            await get_qa_handoff_service().escalate_to_operator(
                agent_id=agent.id,
                user_external_id=caller_e164.strip(),
                user_message=transcript,
                answer=answer,
                reason=handoff_reason,
                channel=PHONE_CHANNEL,
                escalation_type=qa_type,
            )
        if "оператор" not in answer.lower():
            answer = (answer + " Сейчас соединю с оператором.").strip()
        actions.append({"type": "transfer", "e164": "operator"})

    await _log_analytics(
        session,
        agent_id=agent.id,
        analytics_namespace_id=analytics_ns,
        role="agent",
        message_text=answer,
        caller_e164=caller_e164,
    )
    if persist_turns:
        await _persist_turn(session, call_db_id=int(call.id), role="agent", transcript=answer, latency_ms=None)

    logger.info(
        "telephony turn agent_id=%s call_db_id=%s transcript_len=%s",
        agent.id,
        call.id,
        len(transcript),
    )

    return PhoneTurnResult(
        reply_text=answer,
        reply_chunks=reply_chunks,
        actions=actions,
        requires_transfer=requires_transfer,
        play_filler=play_filler,
        dialog_state=load_dialog_state(call).value,
        use_ssml=use_ssml,
    )


def service_unavailable_result() -> PhoneTurnResult:
    return PhoneTurnResult(
        reply_text=MSG_SERVICE_UNAVAILABLE,
        actions=[{"type": "transfer", "e164": "operator"}],
        requires_transfer=True,
    )


def llm_timeout_result(*, retry: bool) -> PhoneTurnResult:
    if retry:
        return PhoneTurnResult(reply_text=MSG_LLM_FILLER, actions=[])
    return PhoneTurnResult(
        reply_text=MSG_LLM_ERROR,
        actions=[{"type": "transfer", "e164": "operator"}],
        requires_transfer=True,
    )


def llm_error_result() -> PhoneTurnResult:
    return PhoneTurnResult(
        reply_text=MSG_LLM_ERROR,
        actions=[{"type": "transfer", "e164": "operator"}],
        requires_transfer=True,
    )
