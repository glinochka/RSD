from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.router_telephony.turn_handler import handle_telephony_turn
from app.router_telephony.schemas import TelephonyTurnRequest


@pytest.mark.asyncio
async def test_turn_handler_stt_empty_without_transcript():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    call = MagicMock()
    call.id = 10
    agent = MagicMock()
    agent.id = 3
    agent.is_active = True

    with patch(
        "app.router_telephony.call_loader.load_call_and_agent",
        AsyncMock(return_value=(call, agent)),
    ):
        payload = TelephonyTurnRequest(
            connection_id=1,
            call_db_id=10,
            caller_e164="preview:web:1",
        )
        resp = await handle_telephony_turn(session, payload)

    assert resp.stage == "stt_empty"
    assert "Не расслышал" in resp.reply_text
    session.add.assert_called()


@pytest.mark.asyncio
async def test_turn_handler_rejects_pstn_caller():
    session = AsyncMock()
    with patch(
        "app.router_telephony.call_loader.load_call_and_agent",
        AsyncMock(),
    ):
        payload = TelephonyTurnRequest(
            connection_id=1,
            call_db_id=10,
            caller_e164="+79001234567",
            user_transcript="привет",
        )
        with pytest.raises(Exception) as exc:
            await handle_telephony_turn(session, payload)
    assert getattr(exc.value, "status_code", None) == 410


@pytest.mark.asyncio
async def test_turn_handler_ignores_recording_url_for_pstn():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.scalar = AsyncMock(return_value=None)

    call = MagicMock()
    call.id = 10
    call.started_at = None
    agent = MagicMock()
    agent.id = 3
    agent.is_active = True

    with patch(
        "app.router_telephony.call_loader.load_call_and_agent",
        AsyncMock(return_value=(call, agent)),
    ):
        with patch(
            "app.router_telephony.turn_handler._transcribe_audio",
            AsyncMock(return_value="should not run"),
        ) as stt_mock:
            payload = TelephonyTurnRequest(
                connection_id=1,
                call_db_id=10,
                caller_e164="preview:web:1",
                recording_url="https://recordings.example.com/x.ogg",
            )
            resp = await handle_telephony_turn(session, payload)

    stt_mock.assert_not_called()
    assert resp.stage == "stt_empty"
