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
            caller_e164="+79001234567",
        )
        resp = await handle_telephony_turn(session, payload)

    assert resp.stage == "stt_empty"
    assert "Не расслышал" in resp.reply_text
    session.add.assert_called()
