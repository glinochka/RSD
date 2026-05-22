"""Browser voice preview for telephony (ИИ-оператор) — no live PSTN call."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentChannelConnection, AgentTelephonyCall
from ..channels.telephony_dialogue import (
    PhoneTurnResult,
    llm_error_result,
    llm_timeout_result,
    process_phone_turn,
)
from ..config import settings
from ..services.telephony_orchestrator import DialogState, load_dialog_state, persist_dialog_state
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from ..telephony.credentials import TELEPHONY_CHANNEL_PROVIDER
from ..telephony.turn_pool import run_in_telephony_pool

logger = logging.getLogger(__name__)

TELEPHONY_PREVIEW_TEMPLATES = frozenset({"crm_admin", "qa"})
_PREVIEW_EXTERNAL_PREFIX = "web-preview:"
_LOGIC_PREVIEW_PREFIX = "web-logic:"
_DEFAULT_WELCOME = "Здравствуйте! Чем могу помочь?"
_MAX_STATELESS_HISTORY_TURNS = 16

_SSML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class PreviewCallShim:
    """In-memory call stand-in for browser preview without telephony channel."""

    id: int
    caller_e164: str
    metadata_: dict[str, Any] = field(default_factory=dict)


def strip_ssml_for_browser(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    if raw.startswith("<speak"):
        raw = _SSML_TAG_RE.sub("", raw)
    return re.sub(r"\s+", " ", raw).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _preview_caller_e164(user_id: int) -> str:
    return f"preview:web:{int(user_id)}"


def _logic_preview_session_id(owner_user_id: int) -> str:
    return f"{_LOGIC_PREVIEW_PREFIX}{int(owner_user_id)}:{uuid.uuid4().hex}"


def _assert_preview_template(agent: Agent) -> None:
    normalized = str(agent.template_type or "").strip().lower()
    if normalized not in TELEPHONY_PREVIEW_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Голосовой предпросмотр доступен для шаблонов «ИИ оператор» и «Консультант»",
        )


def _validate_logic_preview_session_id(session_id: str, owner_user_id: int) -> None:
    expected_prefix = f"{_LOGIC_PREVIEW_PREFIX}{int(owner_user_id)}:"
    if not str(session_id or "").startswith(expected_prefix):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимая сессия предпросмотра")


def _shim_from_dialog_state(
    *,
    owner_user_id: int,
    dialog_state: str | None,
    metadata_extra: dict[str, Any] | None = None,
) -> PreviewCallShim:
    meta: dict[str, Any] = dict(metadata_extra or {})
    state_raw = str(dialog_state or DialogState.GREET.value).strip().upper()
    try:
        DialogState(state_raw)
        meta["dialog_state"] = state_raw
    except ValueError:
        meta["dialog_state"] = DialogState.GREET.value
    return PreviewCallShim(
        id=int(owner_user_id),
        caller_e164=_preview_caller_e164(owner_user_id),
        metadata_=meta,
    )


def _compress_turn_history(turn_history: list[dict[str, Any]] | None) -> str:
    if not turn_history:
        return ""
    lines: list[str] = []
    for item in turn_history[-_MAX_STATELESS_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        label = "Абонент" if role == "user" else "Оператор"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _append_history(
    turn_history: list[dict[str, Any]] | None,
    *,
    role: str,
    text: str,
) -> list[dict[str, str]]:
    history = [dict(item) for item in (turn_history or []) if isinstance(item, dict)]
    history.append({"role": role, "text": text.strip()})
    return history[-_MAX_STATELESS_HISTORY_TURNS:]


async def _load_telephony_connection(session: AsyncSession, agent_id: int) -> AgentChannelConnection | None:
    return await session.scalar(
        select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
            AgentChannelConnection.is_active.is_(True),
        )
    )


async def _create_preview_call(
    session: AsyncSession,
    *,
    connection: AgentChannelConnection,
    owner_user_id: int,
) -> AgentTelephonyCall:
    external_call_id = f"{_PREVIEW_EXTERNAL_PREFIX}{owner_user_id}:{uuid.uuid4().hex}"
    call = AgentTelephonyCall(
        connection_id=int(connection.id),
        agent_id=int(connection.agent_id),
        external_call_id=external_call_id,
        caller_e164=_preview_caller_e164(owner_user_id),
        status="active",
        started_at=_utc_now(),
        metadata_={"preview": True, "source": "web"},
    )
    session.add(call)
    await session.flush()
    return call


async def _load_preview_call(
    session: AsyncSession,
    *,
    agent_id: int,
    call_db_id: int,
    owner_user_id: int,
) -> AgentTelephonyCall:
    call = await session.scalar(
        select(AgentTelephonyCall).where(
            AgentTelephonyCall.id == int(call_db_id),
            AgentTelephonyCall.agent_id == int(agent_id),
        )
    )
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сессия предпросмотра не найдена")
    if not str(call.external_call_id or "").startswith(_PREVIEW_EXTERNAL_PREFIX):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недопустимая сессия предпросмотра")
    expected_caller = _preview_caller_e164(owner_user_id)
    if (call.caller_e164 or "").strip() != expected_caller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Сессия принадлежит другому пользователю")
    if call.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Сессия предпросмотра уже завершена")
    return call


async def _transcribe_preview_audio(
    audio_base64: str | None,
    *,
    mime_type: str,
) -> str:
    if not (audio_base64 or "").strip():
        return ""
    if not is_voice_stt_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Распознавание речи на сервере не настроено. Введите фразу текстом или включите Web Speech в браузере.",
        )
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Некорректное аудио",
        ) from exc
    if not audio_bytes:
        return ""
    stt_timeout = min(
        float(settings.VOICE_TRANSCRIPTION_TIMEOUT_SECONDS),
        float(settings.TELEPHONY_MAX_TURN_SECONDS),
    )
    try:
        return (
            await asyncio.wait_for(
                transcribe_voice_bytes(audio_bytes, mime_type=(mime_type or "audio/webm").strip()),
                timeout=stt_timeout,
            )
        ).strip()
    except TimeoutError:
        logger.warning("telephony preview STT timed out after %.1fs", stt_timeout)
        return ""


async def _run_preview_dialogue(
    session: AsyncSession,
    *,
    call: AgentTelephonyCall | PreviewCallShim,
    agent: Agent,
    transcript: str,
    persist_turns: bool,
    compressed_history_override: str | None,
) -> PhoneTurnResult:
    llm_timeout = max(1.0, float(settings.TELEPHONY_LLM_TIMEOUT_SECONDS))

    async def _run() -> PhoneTurnResult:
        return await process_phone_turn(
            session,
            call=call,  # type: ignore[arg-type]
            agent=agent,
            user_transcript=transcript,
            caller_e164=call.caller_e164,
            use_streaming=False,
            persist_turns=persist_turns,
            compressed_history_override=compressed_history_override,
        )

    try:
        return await asyncio.wait_for(
            run_in_telephony_pool(_run()),
            timeout=llm_timeout,
        )
    except TimeoutError:
        retry_timeout = max(1.0, float(settings.TELEPHONY_LLM_RETRY_TIMEOUT_SECONDS))
        try:
            return await asyncio.wait_for(
                run_in_telephony_pool(_run()),
                timeout=retry_timeout,
            )
        except TimeoutError:
            return llm_timeout_result(retry=False)
    except Exception:
        logger.exception("telephony preview dialogue failed call_id=%s", getattr(call, "id", None))
        return llm_error_result()


def _serialize_turn_result(
    result: PhoneTurnResult,
    *,
    latency_ms: int,
    extra: dict[str, Any] | None = None,
) -> dict:
    reply_text = (result.reply_text or "").strip()
    reply_plain = strip_ssml_for_browser(reply_text)
    chunks_plain = [strip_ssml_for_browser(c) for c in (result.reply_chunks or []) if strip_ssml_for_browser(c)]
    if not chunks_plain and reply_plain:
        chunks_plain = [reply_plain]
    ended = any(action.get("type") in {"hangup", "transfer"} for action in (result.actions or []))
    payload = {
        "reply_text": reply_text,
        "reply_plain": reply_plain,
        "reply_chunks_plain": chunks_plain,
        "actions": list(result.actions or []),
        "stage": "transfer" if result.requires_transfer else ("hangup" if ended else "ok"),
        "ended": ended,
        "latency_ms": latency_ms,
        "dialog_state": result.dialog_state,
    }
    if extra:
        payload.update(extra)
    return payload


async def start_telephony_preview_session(
    session: AsyncSession,
    *,
    agent: Agent,
    owner_user_id: int,
) -> dict:
    _assert_preview_template(agent)
    welcome = (agent.welcome_message or "").strip() or _DEFAULT_WELCOME
    welcome_plain = strip_ssml_for_browser(welcome) or welcome

    connection = await _load_telephony_connection(session, int(agent.id))
    if connection is not None:
        call = await _create_preview_call(session, connection=connection, owner_user_id=owner_user_id)
        return {
            "call_db_id": int(call.id),
            "preview_session_id": None,
            "welcome_text": welcome,
            "welcome_plain": welcome_plain,
            "mode": "telephony_pipeline",
            "requires_telephony_channel": False,
        }

    return {
        "call_db_id": None,
        "preview_session_id": _logic_preview_session_id(owner_user_id),
        "welcome_text": welcome,
        "welcome_plain": welcome_plain,
        "mode": "voice_logic",
        "requires_telephony_channel": False,
        "turn_history": [],
        "dialog_state": DialogState.GREET.value,
    }


async def run_telephony_preview_turn(
    session: AsyncSession,
    *,
    agent: Agent,
    owner_user_id: int,
    call_db_id: int | None,
    preview_session_id: str | None,
    dialog_state: str | None,
    turn_history: list[dict[str, Any]] | None,
    user_transcript: str | None,
    audio_base64: str | None,
    audio_mime_type: str | None,
) -> dict:
    _assert_preview_template(agent)
    started = time.perf_counter()

    transcript = (user_transcript or "").strip()
    if not transcript:
        transcript = await _transcribe_preview_audio(audio_base64, mime_type=audio_mime_type or "audio/webm")

    if not transcript:
        ms = int((time.perf_counter() - started) * 1000)
        empty = {
            "reply_text": "Не расслышал, повторите, пожалуйста.",
            "reply_plain": "Не расслышал, повторите, пожалуйста.",
            "reply_chunks_plain": ["Не расслышал, повторите, пожалуйста."],
            "actions": [],
            "stage": "stt_empty",
            "ended": False,
            "latency_ms": ms,
            "dialog_state": dialog_state or DialogState.LISTEN.value,
        }
        if preview_session_id:
            empty["preview_session_id"] = preview_session_id
            empty["turn_history"] = list(turn_history or [])
        return empty

    if call_db_id is not None:
        call = await _load_preview_call(
            session,
            agent_id=int(agent.id),
            call_db_id=int(call_db_id),
            owner_user_id=owner_user_id,
        )
        result = await _run_preview_dialogue(
            session,
            call=call,
            agent=agent,
            transcript=transcript,
            persist_turns=True,
            compressed_history_override=None,
        )
        ms = int((time.perf_counter() - started) * 1000)
        payload = _serialize_turn_result(result, latency_ms=ms)
        if payload["ended"]:
            call.status = "completed" if any(a.get("type") == "hangup" for a in payload["actions"]) else "transferred"
            call.ended_at = _utc_now()
            if call.started_at:
                delta = call.ended_at - call.started_at
                call.duration_sec = max(0, int(delta.total_seconds()))
            await session.flush()
        payload["call_db_id"] = int(call.id)
        return payload

    if not preview_session_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Укажите call_db_id или preview_session_id",
        )
    _validate_logic_preview_session_id(preview_session_id, owner_user_id)

    shim = _shim_from_dialog_state(owner_user_id=owner_user_id, dialog_state=dialog_state)
    compressed = _compress_turn_history(turn_history)
    result = await _run_preview_dialogue(
        session,
        call=shim,
        agent=agent,
        transcript=transcript,
        persist_turns=False,
        compressed_history_override=compressed,
    )
    persist_dialog_state(shim, DialogState(str(result.dialog_state or DialogState.LISTEN.value)))
    ms = int((time.perf_counter() - started) * 1000)
    updated_history = _append_history(turn_history, role="user", text=transcript)
    reply_plain = strip_ssml_for_browser(result.reply_text)
    if reply_plain:
        updated_history = _append_history(updated_history, role="agent", text=reply_plain)
    return _serialize_turn_result(
        result,
        latency_ms=ms,
        extra={
            "call_db_id": None,
            "preview_session_id": preview_session_id,
            "turn_history": updated_history,
            "dialog_state": load_dialog_state(shim).value,
            "mode": "voice_logic",
        },
    )


async def end_telephony_preview_session(
    session: AsyncSession,
    *,
    agent: Agent,
    owner_user_id: int,
    call_db_id: int | None,
    preview_session_id: str | None,
) -> dict:
    if call_db_id is not None:
        call = await _load_preview_call(
            session,
            agent_id=int(agent.id),
            call_db_id=int(call_db_id),
            owner_user_id=owner_user_id,
        )
        if call.ended_at is None:
            call.status = "completed"
            call.ended_at = _utc_now()
            if call.started_at:
                delta = call.ended_at - call.started_at
                call.duration_sec = max(0, int(delta.total_seconds()))
            await session.flush()
        return {"call_db_id": int(call.id), "status": call.status, "mode": "telephony_pipeline"}

    if preview_session_id:
        _validate_logic_preview_session_id(preview_session_id, owner_user_id)
        return {"call_db_id": None, "preview_session_id": preview_session_id, "status": "completed", "mode": "voice_logic"}

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Укажите call_db_id или preview_session_id",
    )
