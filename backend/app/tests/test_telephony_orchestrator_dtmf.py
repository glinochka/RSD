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
    assert stream_phrase.await_args.kwargs["text"] == "Агент не найден"


@pytest.mark.asyncio
async def test_dtmf_routed_agent_plays_default_welcome_when_empty():
    worker = OrchestratorWorker()
    slot = worker._slot("call-dtmf-2", 1, "+79001112233")
    slot.call_db_id = 5
    slot.awaiting_extension = True
    slot.dtmf_buffer = "123"

    resolved = {
        "welcome_message": "",
        "system_prompt": "test",
        "template_type": "qa",
        "template_config": {},
    }

    with (
        patch.object(worker, "_ensure_call_mapping", AsyncMock()),
        patch.object(worker, "_routing_flags_from_call", AsyncMock()),
        patch("app.telephony.orchestrator_worker.resolve_agent_by_extension", AsyncMock(return_value=37)),
        patch.object(worker, "_apply_routed_agent", AsyncMock()) as apply_route,
    ):
        await worker.handle_dtmf(
            {
                "call_id": "call-dtmf-2",
                "connection_id": 1,
                "caller_e164": "+79001112233",
                "payload": {"digit": "4"},
            }
        )

    apply_route.assert_awaited_once_with(slot, 37, extension="1234")


@pytest.mark.asyncio
async def test_apply_routed_agent_streams_default_welcome():
    worker = OrchestratorWorker()
    slot = worker._slot("call-dtmf-3", 1, "+79001112233")
    slot.call_db_id = 5

    agent = MagicMock()
    agent.id = 37
    agent.is_active = True

    session = AsyncMock()
    session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    session.scalar = AsyncMock(return_value=agent)
    session.get = AsyncMock(return_value=None)

    with (
        patch("app.telephony.orchestrator_worker.async_session_maker") as session_maker,
        patch(
            "app.telephony.orchestrator_worker.resolve_telephony_channel",
            AsyncMock(return_value={"welcome_message": None}),
        ),
        patch("app.telephony.orchestrator_worker.cache_resolve_payload", AsyncMock()),
        patch.object(worker, "_load_postgres_once", AsyncMock()),
        patch.object(worker, "_play_agent_welcome", AsyncMock()) as play_welcome,
    ):
        session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
        session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
        await worker._apply_routed_agent(slot, 37, extension="1234")

    play_welcome.assert_awaited_once_with(slot, welcome_raw="")
