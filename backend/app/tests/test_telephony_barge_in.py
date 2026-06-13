"""Stage 6: barge-in spoken text + orchestrator context."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.telephony_orchestrator import (
    CallDialogContext,
    DialogState,
    OrchestratorEventType,
    apply_barge_in,
    handle_orchestrator_event,
)
from app.telephony.orchestrator_worker import OrchestratorWorker
from app.telephony.redis_keys import agent_spoken_key


def test_agent_spoken_key_format():
    assert agent_spoken_key("call-1") == "telephony:spoken:call-1"


def test_handle_barge_in_cancels_and_sets_interrupted():
    worker = OrchestratorWorker()
    call_id = "test-call-barge"
    slot = worker._slot(call_id, 1, "+79001234567")
    slot.call_db_id = 99
    slot.ctx = CallDialogContext(state=DialogState.LISTEN)

    with (
        patch(
            "app.telephony.orchestrator_worker.get_agent_spoken_text",
            new_callable=AsyncMock,
            return_value="Мы работаем с девяти",
        ),
        patch(
            "app.telephony.orchestrator_worker.clear_agent_spoken_text",
            new_callable=AsyncMock,
        ),
        patch(
            "app.telephony.orchestrator_worker.publish_agent_audio_end",
            new_callable=AsyncMock,
        ) as mock_end,
        patch("app.telephony.orchestrator_worker.cancel_turn") as mock_cancel_db,
        patch("app.telephony.orchestrator_worker.cancel_turn_by_call_id") as mock_cancel_call,
        patch(
            "app.telephony.orchestrator_worker.set_dialog_meta",
            new_callable=AsyncMock,
        ),
    ):
        asyncio.run(
            worker.handle_barge_in(
                {
                    "call_id": call_id,
                    "connection_id": 1,
                    "payload": {"at_ms": 120},
                }
            )
        )

    mock_cancel_db.assert_called_once_with(99)
    mock_cancel_call.assert_called_once_with(call_id)
    mock_end.assert_awaited_once()
    assert slot.ctx.barged_in is True
    assert slot.ctx.interrupted_agent_text == "Мы работаем с девяти"


def test_barge_in_then_stt_final_uses_interrupted_in_prompt():
    ctx = CallDialogContext()
    apply_barge_in(ctx, interrupted_agent_text="Привет, я оператор")
    decision = handle_orchestrator_event(
        ctx,
        OrchestratorEventType.STT_FINAL,
        transcript="Стоп, другой вопрос",
    )
    assert decision is not None
    assert decision.runtime_context.get("barged_in") is True
    assert decision.runtime_context.get("interrupted_agent_text") == "Привет, я оператор"
    assert "перебил" in decision.prompt_addon.lower()
    assert "Привет" in decision.prompt_addon
