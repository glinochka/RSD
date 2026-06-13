from app.services.telephony_orchestrator import (
    CallDialogContext,
    DialogState,
    decide_orchestrator,
    load_dialog_state,
    persist_dialog_state,
)


class _FakeCall:
    def __init__(self) -> None:
        self.metadata_: dict = {}
        self.id = 1


def test_dialog_state_greet_to_listen():
    call = _FakeCall()
    persist_dialog_state(call, DialogState.GREET)
    decision = decide_orchestrator(
        call,
        transcript="Хочу записаться на завтра",
        compressed_history="",
    )
    assert decision.state == DialogState.ACT
    assert load_dialog_state(call) == DialogState.ACT


def test_barge_in_prompt_addon():
    call = _FakeCall()
    persist_dialog_state(call, DialogState.LISTEN)
    decision = decide_orchestrator(
        call,
        transcript="Нет, другой вопрос",
        barged_in=True,
        interrupted_agent_text="Мы работаем с девяти",
    )
    assert "перебил" in decision.prompt_addon.lower()
    assert decision.runtime_context.get("barged_in") is True


def test_context_stt_empty_suggests_dtmf():
    ctx = CallDialogContext()
    from app.services.telephony_orchestrator import decide_from_context

    decide_from_context(ctx, transcript="", stt_empty=True)
    decision = decide_from_context(ctx, transcript="", stt_empty=True)
    assert decision.suggest_dtmf_menu is True


def test_stt_empty_suggests_dtmf_after_two_fails():
    call = _FakeCall()
    decide_orchestrator(call, transcript="", stt_empty=True)
    decision = decide_orchestrator(call, transcript="", stt_empty=True)
    assert decision.suggest_dtmf_menu is True
