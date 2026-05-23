"""SIP trunk routing (variant 7C)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.alembic.models import TelephonySipRoute
from app.telephony.routing import (
    _sip_header_matches,
    resolve_connection_by_sip_headers,
)


def test_sip_header_matches_wildcard():
    assert _sip_header_matches("sip:+79001234567@provider", "*")
    assert _sip_header_matches("sip:user@tenant", "tenant")


@pytest.mark.asyncio
async def test_resolve_connection_by_sip_headers():
    row = TelephonySipRoute(
        id=1,
        connection_id=99,
        match_from="tenant-a",
        match_to=None,
        is_active=True,
    )
    session = AsyncMock()
    session.scalars = AsyncMock(return_value=MagicMock(__iter__=lambda s: iter([row])))

    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = None

    with patch("app.telephony.routing.async_session_maker", return_value=cm):
        resolved = await resolve_connection_by_sip_headers(
            sip_from="sip:pool@tenant-a",
            sip_to="sip:+74951234567@gw",
            fallback_connection_id=1,
        )

    assert resolved == 99
