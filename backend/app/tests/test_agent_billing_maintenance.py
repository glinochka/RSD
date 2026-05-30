from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent_template_pricing import (
    MAINTENANCE_GRACE_DAYS,
    initial_maintenance_paid_until_for_template,
)
from app.services.agent_billing import is_maintenance_current
from app.services.agent_billing_maintenance import deactivate_expired_agent_maintenance_once


class _FakeAgent:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.template_type = kwargs.get("template_type", "crm_admin")
        self.is_active = kwargs.get("is_active", True)
        self.registered = kwargs.get("registered", date.today())
        self.maintenance_paid_until = kwargs.get("maintenance_paid_until")


@pytest.mark.asyncio
async def test_cron_deactivates_expired_agent(monkeypatch):
    created = date.today() - timedelta(days=MAINTENANCE_GRACE_DAYS + 1)
    agent = _FakeAgent(
        id=42,
        template_type="crm_admin",
        is_active=True,
        registered=created,
        maintenance_paid_until=initial_maintenance_paid_until_for_template(
            "crm_admin",
            from_date=created,
        ),
    )
    assert is_maintenance_current(agent) is False

    agent_dao = MagicMock()
    agent_dao.list_scalars = AsyncMock(return_value=[agent])
    agent_dao.update = AsyncMock()

    session = MagicMock()
    session.begin = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock()))

    class _SessionMaker:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(
        "app.services.agent_billing_maintenance.async_session_maker",
        lambda: _SessionMaker(),
    )
    monkeypatch.setattr(
        "app.services.agent_billing_maintenance.AgentDAO",
        lambda _session: agent_dao,
    )
    monkeypatch.setattr(
        "app.services.agent_billing_maintenance._disable_telegram_bot_webhook_for_agent",
        AsyncMock(),
    )

    count = await deactivate_expired_agent_maintenance_once()
    assert count == 1
    agent_dao.update.assert_awaited_once()
    assert agent.is_active is False


@pytest.mark.asyncio
async def test_cron_skips_agent_still_in_trial(monkeypatch):
    created = date.today()
    agent = _FakeAgent(
        template_type="sales_manager",
        is_active=True,
        registered=created,
        maintenance_paid_until=initial_maintenance_paid_until_for_template(
            "sales_manager",
            from_date=created,
        ),
    )

    agent_dao = MagicMock()
    agent_dao.list_scalars = AsyncMock(return_value=[agent])
    agent_dao.update = AsyncMock()

    session = MagicMock()
    session.begin = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock()))

    class _SessionMaker:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(
        "app.services.agent_billing_maintenance.async_session_maker",
        lambda: _SessionMaker(),
    )
    monkeypatch.setattr(
        "app.services.agent_billing_maintenance.AgentDAO",
        lambda _session: agent_dao,
    )

    count = await deactivate_expired_agent_maintenance_once()
    assert count == 0
    agent_dao.update.assert_not_awaited()
