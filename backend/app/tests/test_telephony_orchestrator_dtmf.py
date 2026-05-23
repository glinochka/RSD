"""DTMF routing uses stream TTS (not agent.turn_ready)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.telephony.orchestrator_worker import OrchestratorWorker


@pytest.mark.asyncio
async def test_dtmf_unknown_extension_streams_phrase():
    worker = OrchestratorWorker()
    slot = worker._slot("call-dtmf-1", 1, "+79001112233")
    slot.call_db_id = 5
    slot.awaiting_extension = True
    slot.dtmf_buffer = "999"

    with (
        patch.object(worker, "_ensure_call_mapping", AsyncMock()),
        patch.object(worker, "_routing_flags_from_call", AsyncMock()),
        patch("app.telephony.orchestrator_worker.resolve_agent_by_extension", AsyncMock(return_value=None)),
        patch("app.telephony.orchestrator_worker.hgetall_session", AsyncMock(return_value={"voice_id": "v1", "language": "ru-RU"})),
        patch("app.telephony.orchestrator_worker.assert_stream_tts_configured"),
        patch("app.telephony.orchestrator_worker.stream_fixed_phrase", AsyncMock()) as stream_phrase,
    ):
        await worker.handle_dtmf(
            {
                "call_id": "call-dtmf-1",
                "connection_id": 1,
                "caller_e164": "+79001112233",
                "payload": {"digit": "9"},
            }
        )

    stream_phrase.assert_awaited_once()
    assert "не найден" in stream_phrase.await_args.kwargs["text"].lower()
