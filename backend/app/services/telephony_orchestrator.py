"""Dialog state machine for phone turns — event-driven (stage 4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import AgentTelephonyCall, AgentTelephonyTurn
from ..prompts.system_prompts import (
    TELEPHONY_DIALOG_STATE_PROMPTS,
    telephony_barge_in_addon,
)
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


class OrchestratorEventType(str, Enum):
    SESSION_START = "session.start"
    STT_FINAL = "stt.final"
    BARGE_IN = "barge_in"
    DTMF = "dtmf"
    SESSION_END = "session.end"


@dataclass
class CallDialogContext:
    """In-RAM dialog state (orchestrator worker affinity slot)."""

    state: DialogState = DialogState.GREET
    clarify_count: int = 0
    stt_fail_count: int = 0
    barged_in: bool = False
    interrupted_agent_text: str | None = None

    def to_meta(self) -> dict[str, Any]:
        return {
            _DIALOG_STATE_KEY: self.state.value,
            _CLARIFY_COUNT_KEY: self.clarify_count,
            _STT_FAIL_COUNT_KEY: self.stt_fail_count,
        }

    @classmethod
    def from_meta(cls, meta: dict[str, Any] | None) -> CallDialogContext:
        raw = meta or {}
        state_raw = str(raw.get(_DIALOG_STATE_KEY) or DialogState.GREET.value).strip().upper()
        try:
            state = DialogState(state_raw)
        except ValueError:
            state = DialogState.GREET
        return cls(
            state=state,
            clarify_count=int(raw.get(_CLARIFY_COUNT_KEY) or 0),
            stt_fail_count=int(raw.get(_STT_FAIL_COUNT_KEY) or 0),
        )


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
    return CallDialogContext.from_meta(_metadata(call)).state


def persist_dialog_state(call: AgentTelephonyCall, state: DialogState) -> None:
    _save_metadata(call, {_DIALOG_STATE_KEY: state.value})


def sync_context_to_call(call: AgentTelephonyCall, ctx: CallDialogContext) -> None:
    _save_metadata(call, ctx.to_meta())


def increment_stt_fail(call: AgentTelephonyCall) -> int:
    ctx = CallDialogContext.from_meta(_metadata(call))
    ctx.stt_fail_count += 1
    sync_context_to_call(call, ctx)
    return ctx.stt_fail_count


def reset_stt_fail(call: AgentTelephonyCall) -> None:
    ctx = CallDialogContext.from_meta(_metadata(call))
    ctx.stt_fail_count = 0
    sync_context_to_call(call, ctx)


def increment_clarify(call: AgentTelephonyCall) -> int:
    ctx = CallDialogContext.from_meta(_metadata(call))
    ctx.clarify_count += 1
    sync_context_to_call(call, ctx)
    return ctx.clarify_count


def reset_clarify(call: AgentTelephonyCall) -> None:
    ctx = CallDialogContext.from_meta(_metadata(call))
    ctx.clarify_count = 0
    sync_context_to_call(call, ctx)


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


def apply_barge_in(
    ctx: CallDialogContext,
    *,
    interrupted_agent_text: str | None = None,
) -> None:
    ctx.barged_in = True
    if interrupted_agent_text:
        ctx.interrupted_agent_text = interrupted_agent_text.strip()


def decide_from_context(
    ctx: CallDialogContext,
    *,
    transcript: str,
    requires_transfer: bool = False,
    stt_empty: bool = False,
    compressed_history: str = "",
) -> OrchestratorDecision:
    """Event-driven decision without waiting for full LLM response."""
    barged_in = ctx.barged_in
    interrupted = ctx.interrupted_agent_text

    if stt_empty:
        ctx.stt_fail_count += 1
        suggest_dtmf = ctx.stt_fail_count >= 2
        return OrchestratorDecision(
            state=ctx.state,
            runtime_context={
                "dialog_state": ctx.state.value,
                "stt_fail_count": ctx.stt_fail_count,
                "suggest_dtmf_menu": suggest_dtmf,
            },
            prompt_addon="",
            suggest_dtmf_menu=suggest_dtmf,
        )

    ctx.stt_fail_count = 0
    if _needs_clarify(transcript):
        ctx.clarify_count += 1
    else:
        ctx.clarify_count = 0

    next_state = _next_state(
        ctx.state,
        transcript=transcript,
        barged_in=barged_in,
        requires_transfer=requires_transfer,
        clarify_count=ctx.clarify_count,
    )
    ctx.state = next_state
    ctx.barged_in = False
    ctx.interrupted_agent_text = None

    runtime: dict[str, Any] = {
        "dialog_state": next_state.value,
        "phone_channel": True,
    }
    if compressed_history:
        runtime["compressed_call_history"] = compressed_history
    if barged_in:
        runtime["barged_in"] = True
        if interrupted:
            runtime["interrupted_agent_text"] = interrupted

    prompt_addon = TELEPHONY_DIALOG_STATE_PROMPTS.get(next_state.value, "")
    if barged_in:
        prompt_addon = telephony_barge_in_addon(interrupted_agent_text=interrupted)

    return OrchestratorDecision(
        state=next_state,
        runtime_context=runtime,
        prompt_addon=prompt_addon,
    )


def handle_orchestrator_event(
    ctx: CallDialogContext,
    event: OrchestratorEventType,
    *,
    transcript: str = "",
    interrupted_agent_text: str | None = None,
    requires_transfer: bool = False,
    compressed_history: str = "",
) -> OrchestratorDecision | None:
    """Apply control-plane event; returns decision only when a turn should run."""
    if event == OrchestratorEventType.SESSION_START:
        ctx.state = DialogState.GREET
        ctx.clarify_count = 0
        ctx.stt_fail_count = 0
        ctx.barged_in = False
        ctx.interrupted_agent_text = None
        return None
    if event == OrchestratorEventType.BARGE_IN:
        apply_barge_in(ctx, interrupted_agent_text=interrupted_agent_text)
        return None
    if event == OrchestratorEventType.SESSION_END:
        return None
    if event == OrchestratorEventType.STT_FINAL:
        text = (transcript or "").strip()
        if not text:
            return decide_from_context(ctx, transcript="", stt_empty=True, compressed_history=compressed_history)
        return decide_from_context(
            ctx,
            transcript=text,
            requires_transfer=requires_transfer,
            compressed_history=compressed_history,
        )
    return None


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
    """Backward-compatible wrapper over DB metadata (preview / HTTP turn)."""
    ctx = CallDialogContext.from_meta(_metadata(call))
    if barged_in:
        apply_barge_in(ctx, interrupted_agent_text=interrupted_agent_text)
    decision = decide_from_context(
        ctx,
        transcript=transcript,
        requires_transfer=requires_transfer,
        stt_empty=stt_empty,
        compressed_history=compressed_history,
    )
    sync_context_to_call(call, ctx)
    return decision
