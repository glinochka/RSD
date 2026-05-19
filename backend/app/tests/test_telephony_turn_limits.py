from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.router_telephony.turn_handler import handle_telephony_turn
from app.router_telephony.schemas import TelephonyTurnRequest


@pytest.mark.asyncio
async def test_turn_handler_rejects_when_max_turns_reached():
    session = AsyncMock()
    session.flush = AsyncMock()

    call = MagicMock()
    call.id = 10
    call.started_at = datetime.utcnow()
    agent = MagicMock()
    agent.id = 3
    agent.is_active = True

    with (
        patch(
            "app.router_telephony.call_loader.load_call_and_agent",
            AsyncMock(return_value=(call, agent)),
        ),
        patch("app.router_telephony.turn_handler._count_user_turns", AsyncMock(return_value=15)),
        patch("app.router_telephony.turn_handler.settings.TELEPHONY_MAX_TURNS", 15),
    ):
        payload = TelephonyTurnRequest(
            connection_id=1,
            call_db_id=10,
            caller_e164="+79001234567",
            user_transcript="ещё один вопрос",
        )
        resp = await handle_telephony_turn(session, payload)

    assert resp.stage == "max_turns"
    assert resp.actions[0]["type"] == "hangup"


@pytest.mark.asyncio
async def test_turn_handler_rejects_when_call_duration_exceeded():
    session = AsyncMock()
    session.flush = AsyncMock()

    call = MagicMock()
    call.id = 10
    call.started_at = datetime.utcnow() - timedelta(minutes=20)
    agent = MagicMock()
    agent.id = 3
    agent.is_active = True

    with (
        patch(
            "app.router_telephony.call_loader.load_call_and_agent",
            AsyncMock(return_value=(call, agent)),
        ),
        patch("app.router_telephony.turn_handler._count_user_turns", AsyncMock(return_value=0)),
        patch("app.router_telephony.turn_handler.settings.TELEPHONY_MAX_CALL_MINUTES", 15),
    ):
        payload = TelephonyTurnRequest(
            connection_id=1,
            call_db_id=10,
            caller_e164="+79001234567",
            user_transcript="вопрос",
        )
        resp = await handle_telephony_turn(session, payload)

    assert resp.stage == "call_timeout"
    assert resp.actions[0]["type"] == "hangup"
