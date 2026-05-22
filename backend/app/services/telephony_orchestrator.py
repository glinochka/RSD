"""Dialog state machine for phone turns (stage 6)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import AgentTelephonyCall, AgentTelephonyTurn
from ..telephony.intent import detect_hangup_intent, detect_operator_transfer_intent

_DIALOG_STATE_KEY = "dialog_state"
_CLARIFY_COUNT_KEY = "clarify_count"
_STT_FAIL_COUNT_KEY = "stt_fail_count"

_MAX_COMPRESSED_TURNS = 8
_MIN_CLARIFY_WORDS = 3

_BOOKING_RE = re.compile(
    r"\b(запис|запиш|приём|прием|бронь|встреч|appointment|book)\w*",
    re.IGNORECASE,
)
_CONFIRM_DATA_RE = re.compile(
    r"\b(\d{1,2}[./-]\d{1,2}|завтра|послезавтра|понедельник|вторник|"
    r"сред|четверг|пятниц|суббот|воскресенье|\+?\d{10,14})\b",
    re.IGNORECASE,
)
_CLOSE_RE = re.compile(
    r"\b(больше не нужно|всё|все|хватит|ничего|не надо|нет вопросов)\b",
    re.IGNORECASE,
)


class DialogState(str, Enum):
    GREET = "GREET"
    LISTEN = "LISTEN"
    CLARIFY = "CLARIFY"
    ACT = "ACT"
    CONFIRM = "CONFIRM"
    CLOSE = "CLOSE"
    HANDOFF = "HANDOFF"


@dataclass(frozen=True)
class OrchestratorDecision:
    state: DialogState
    runtime_context: dict[str, Any]
    prompt_addon: str
    suggest_dtmf_menu: bool = False


def _metadata(call: AgentTelephonyCall) -> dict[str, Any]:
    raw = call.metadata_ or {}
    return raw if isinstance(raw, dict) else {}


def _save_metadata(call: AgentTelephonyCall, patch: dict[str, Any]) -> None:
    meta = dict(_metadata(call))
    meta.update(patch)
    call.metadata_ = meta


def load_dialog_state(call: AgentTelephonyCall) -> DialogState:
    raw = str(_metadata(call).get(_DIALOG_STATE_KEY) or DialogState.GREET.value).strip().upper()
    try:
        return DialogState(raw)
    except ValueError:
        return DialogState.GREET


def persist_dialog_state(call: AgentTelephonyCall, state: DialogState) -> None:
    _save_metadata(call, {_DIALOG_STATE_KEY: state.value})


def increment_stt_fail(call: AgentTelephonyCall) -> int:
    meta = _metadata(call)
    count = int(meta.get(_STT_FAIL_COUNT_KEY) or 0) + 1
    _save_metadata(call, {_STT_FAIL_COUNT_KEY: count})
    return count


def reset_stt_fail(call: AgentTelephonyCall) -> None:
    _save_metadata(call, {_STT_FAIL_COUNT_KEY: 0})


def increment_clarify(call: AgentTelephonyCall) -> int:
    meta = _metadata(call)
    count = int(meta.get(_CLARIFY_COUNT_KEY) or 0) + 1
    _save_metadata(call, {_CLARIFY_COUNT_KEY: count})
    return count


def reset_clarify(call: AgentTelephonyCall) -> None:
    _save_metadata(call, {_CLARIFY_COUNT_KEY: 0})


async def build_compressed_turn_context(
    session: AsyncSession,
    call_db_id: int,
    *,
    max_turns: int = _MAX_COMPRESSED_TURNS,
) -> str:
    rows = (
        await session.scalars(
            select(AgentTelephonyTurn)
            .where(
                AgentTelephonyTurn.call_id == call_db_id,
                AgentTelephonyTurn.role.in_(("user", "agent")),
            )
            .order_by(desc(AgentTelephonyTurn.id))
            .limit(max(2, max_turns))
        )
    ).all()
    if not rows:
        return ""
    lines: list[str] = []
    for row in reversed(rows):
        label = "Абонент" if row.role == "user" else "Оператор"
        text = (row.transcript or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _needs_clarify(transcript: str) -> bool:
    words = [w for w in transcript.split() if w.strip()]
    if len(words) >= _MIN_CLARIFY_WORDS:
        return False
    if _BOOKING_RE.search(transcript) or detect_operator_transfer_intent(transcript):
        return False
    return True


def _next_state(
    current: DialogState,
    *,
    transcript: str,
    barged_in: bool,
    requires_transfer: bool,
    clarify_count: int,
) -> DialogState:
    if requires_transfer or detect_operator_transfer_intent(transcript):
        return DialogState.HANDOFF
    if detect_hangup_intent(transcript) or _CLOSE_RE.search(transcript):
        return DialogState.CLOSE
    if current == DialogState.GREET:
        if _BOOKING_RE.search(transcript):
            return DialogState.ACT
        return DialogState.LISTEN
    if _BOOKING_RE.search(transcript):
        return DialogState.ACT
    if _CONFIRM_DATA_RE.search(transcript) and current in (DialogState.ACT, DialogState.LISTEN):
        return DialogState.CONFIRM
    if _needs_clarify(transcript) and clarify_count < 1:
        return DialogState.CLARIFY
    if barged_in:
        return DialogState.LISTEN
    if current in (DialogState.CLARIFY, DialogState.CONFIRM):
        return DialogState.LISTEN
    return current if current != DialogState.HANDOFF else DialogState.LISTEN


_STATE_PROMPTS: dict[DialogState, str] = {
    DialogState.GREET: "Поприветствуй по-живому и одной фразой спроси, чем помочь — без официоза.",
    DialogState.LISTEN: "Ответь по сути разговорным языком; максимум один уточняющий вопрос, если без него нельзя.",
    DialogState.CLARIFY: "Один короткий вопрос своими словами — как в обычном звонке, не анкета.",
    DialogState.ACT: "Сделай шаг (запись, CRM) или объясни, что дальше — просто и по делу.",
    DialogState.CONFIRM: "Своими словами переспроси дату, время или телефон одной фразой («так, на завтра в три — верно?»).",
    DialogState.CLOSE: "Мягко предложи помощь ещё («что-то ещё подсказать?»); если не нужно — тепло попрощайся.",
    DialogState.HANDOFF: "Коротко скажи, что переключаешь на живого оператора, без длинных объяснений.",
}


def decide_orchestrator(
    call: AgentTelephonyCall,
    *,
    transcript: str,
    barged_in: bool = False,
    interrupted_agent_text: str | None = None,
    requires_transfer: bool = False,
    stt_empty: bool = False,
    compressed_history: str = "",
) -> OrchestratorDecision:
    current = load_dialog_state(call)
    clarify_count = int(_metadata(call).get(_CLARIFY_COUNT_KEY) or 0)

    if stt_empty:
        fail_count = increment_stt_fail(call)
        suggest_dtmf = fail_count >= 2
        return OrchestratorDecision(
            state=current,
            runtime_context={
                "dialog_state": current.value,
                "stt_fail_count": fail_count,
                "suggest_dtmf_menu": suggest_dtmf,
            },
            prompt_addon="",
            suggest_dtmf_menu=suggest_dtmf,
        )

    reset_stt_fail(call)
    if _needs_clarify(transcript):
        clarify_count = increment_clarify(call)
    else:
        reset_clarify(call)
        clarify_count = 0

    next_state = _next_state(
        current,
        transcript=transcript,
        barged_in=barged_in,
        requires_transfer=requires_transfer,
        clarify_count=clarify_count,
    )
    persist_dialog_state(call, next_state)

    runtime: dict[str, Any] = {
        "dialog_state": next_state.value,
        "phone_channel": True,
    }
    if compressed_history:
        runtime["compressed_call_history"] = compressed_history
    if barged_in:
        runtime["barged_in"] = True
        if interrupted_agent_text:
            runtime["interrupted_agent_text"] = interrupted_agent_text.strip()

    prompt_addon = _STATE_PROMPTS.get(next_state, "")
    if barged_in:
        prompt_addon = (
            "Абонент перебил. Начни по-разговорному («да, слышу…», «понял, вы про…») и ответь на новую мысль."
            + (f" Ты успел сказать: «{interrupted_agent_text[:200]}»." if interrupted_agent_text else "")
        )

    return OrchestratorDecision(
        state=next_state,
        runtime_context=runtime,
        prompt_addon=prompt_addon,
    )
