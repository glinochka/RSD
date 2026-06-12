"""Integration-style tests: orchestrator + mock STT metrics (no Voximplant)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.telephony_orchestrator import CallDialogContext, DialogState
from app.telephony.latency_budget import LATENCY_BUDGET_META_KEY
from app.telephony.orchestrator_worker import OrchestratorWorker


@pytest.mark.asyncio
async def test_stt_final_records_latency_budget_in_metadata():
    worker = OrchestratorWorker()
    call = MagicMock()
    call.id = 42
    call.agent_id = 7
    call.metadata_ = {}
    agent = MagicMock()
    agent.id = 7
    agent.is_active = True

    slot = worker._slot("call-int-1", 1, "+79001112233")
    slot.call_db_id = 42
    slot.call = call
    slot.agent = agent
    slot.postgres_loaded = True
    slot.ctx = CallDialogContext(state=DialogState.LISTEN)
    slot.awaiting_extension = False

    reply = MagicMock()
    reply.reply_text = "Ответ"
    reply.reply_chunks = ["Ответ"]
    reply.actions = []
    reply.dialog_state = "LISTEN"
    reply.stt_empty = False
    reply.requires_transfer = False
    reply.play_filler = False

    stream_metrics = MagicMock()
    stream_metrics.llm_first_token_ms = 210
    stream_metrics.tts_first_byte_ms = 95
    stream_metrics.syntagma_count = 1
    stream_metrics.to_dict.return_value = {
        "llm_first_token_ms": 210,
        "tts_first_byte_ms": 95,
    }

    session = AsyncMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    session.get = AsyncMock(return_value=call)
    session.merge = AsyncMock(side_effect=lambda obj: obj)

    patches = [
        patch.object(worker, "_ensure_call_mapping", AsyncMock()),
        patch.object(worker, "_warm_session_cache", AsyncMock()),
        patch("app.telephony.orchestrator_worker.build_compressed_history", AsyncMock(return_value="")),
        patch("app.telephony.orchestrator_worker.hgetall_session", AsyncMock(return_value={})),
        patch(
            "app.telephony.orchestrator_worker.stream_agent_reply",
            AsyncMock(return_value=(reply, stream_metrics)),
        ),
        patch("app.telephony.orchestrator_worker.assert_stream_tts_configured"),
        patch("app.telephony.orchestrator_worker.append_dialog_turn", AsyncMock()),
        patch("app.telephony.orchestrator_worker.flush_turn_batch", AsyncMock(return_value=2)),
        patch("app.telephony.orchestrator_worker.publish_orch_reply", AsyncMock()),
        patch("app.telephony.orchestrator_worker.set_dialog_meta", AsyncMock()),
    ]
    for item in patches:
        item.start()
    try:
        with patch("app.telephony.orchestrator_worker.settings") as mock_settings:
            mock_settings.TELEPHONY_STREAMING_ENABLED = True
            mock_settings.TELEPHONY_DIALOG_MAX_TURNS = 16
            mock_settings.TELEPHONY_REDIS_SESSION_TTL_SEC = 3600
            with patch("app.telephony.orchestrator_worker.async_session_maker") as session_maker:
                session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
                session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
                await worker.handle_stt_final(
                    {
                        "call_id": "call-int-1",
                        "connection_id": 1,
                        "caller_e164": "+79001112233",
                        "payload": {
                            "text": "привет",
                            "metrics": {"stt_final_ms": 380, "vad_speech_ratio": 0.55},
                        },
                    }
                )
    finally:
        for item in reversed(patches):
            item.stop()

    assert LATENCY_BUDGET_META_KEY in call.metadata_
    budget = call.metadata_["latency_budget"]
    assert budget.get("stt_final_ms") == 380
    assert budget.get("llm_ttft_ms") == 210
    assert budget.get("tts_ttfa_ms") == 95
    assert budget.get("e2r_ms") is not None
