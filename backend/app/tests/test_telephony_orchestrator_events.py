from app.services.telephony_orchestrator import (
    CallDialogContext,
    DialogState,
    OrchestratorEventType,
    apply_barge_in,
    decide_from_context,
    handle_orchestrator_event,
)


def test_session_start_resets_context():
    ctx = CallDialogContext(state=DialogState.ACT, clarify_count=2, stt_fail_count=1)
    assert handle_orchestrator_event(ctx, OrchestratorEventType.SESSION_START) is None
    assert ctx.state == DialogState.GREET
    assert ctx.clarify_count == 0


def test_barge_in_then_stt_final():
    ctx = CallDialogContext(state=DialogState.LISTEN)
    handle_orchestrator_event(
        ctx,
        OrchestratorEventType.BARGE_IN,
        interrupted_agent_text="Мы работаем с девяти",
    )
    decision = handle_orchestrator_event(
        ctx,
        OrchestratorEventType.STT_FINAL,
        transcript="Нет, другой вопрос",
    )
    assert decision is not None
    assert "перебил" in decision.prompt_addon.lower()
    assert ctx.barged_in is False


def test_decide_from_context_without_call_row():
    ctx = CallDialogContext(state=DialogState.GREET)
    decision = decide_from_context(ctx, transcript="Хочу записаться на завтра")
    assert decision.state == DialogState.ACT
    assert ctx.state == DialogState.ACT


def test_apply_barge_in_sets_flag():
    ctx = CallDialogContext()
    apply_barge_in(ctx, interrupted_agent_text="Привет")
    assert ctx.barged_in is True
    assert ctx.interrupted_agent_text == "Привет"
