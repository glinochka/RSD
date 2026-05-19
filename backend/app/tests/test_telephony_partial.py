from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.router_telephony.partial_handler import (
    handle_telephony_partial,
    resolve_transcript_with_partials,
)
from app.router_telephony.schemas import TelephonyPartialRequest
from app.telephony.partial_store import clear_partial, record_partial


@pytest.mark.asyncio
async def test_partial_handler_logs_non_final():
    session = AsyncMock()
    call = MagicMock()
    agent = MagicMock()
    agent.is_active = True

    with patch(
        "app.router_telephony.call_loader.load_call_and_agent",
        AsyncMock(return_value=(call, agent)),
    ):
        resp = await handle_telephony_partial(
            session,
            TelephonyPartialRequest(
                connection_id=1,
                call_db_id=42,
                caller_e164="+79001234567",
                transcript="привет",
                is_final=False,
            ),
        )

    assert resp.accepted is True
    assert resp.transcript == "привет"
    assert resp.partial_count == 1


def test_resolve_transcript_prefers_explicit():
    record_partial(99, transcript="partial text", is_final=False)
    assert resolve_transcript_with_partials(99, "final text") == "final text"
    clear_partial(99)


def test_resolve_transcript_uses_partials():
    record_partial(100, transcript="накопленный текст", is_final=True)
    assert resolve_transcript_with_partials(100, "") == "накопленный текст"
