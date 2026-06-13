"""Agent subscription maintenance: expiry enforcement and contract helpers."""

from __future__ import annotations

from datetime import date

from ..agent_template_pricing import (
    get_agent_template_pricing,
    is_maintenance_current,
)
from ..router_agents.dao import AgentDAO


def agent_requires_paid_maintenance(agent) -> bool:
    pricing = get_agent_template_pricing(getattr(agent, "template_type", None))
    return bool(pricing and pricing.monthly_maintenance_rub_min > 0)


def should_auto_deactivate_for_expired_maintenance(agent, *, today: date | None = None) -> bool:
    if not getattr(agent, "is_active", False):
        return False
    if not agent_requires_paid_maintenance(agent):
        return False
    return not is_maintenance_current(agent, today=today)


async def enforce_expired_maintenance(agent_dao: AgentDAO, agent) -> bool:
    """Deactivate agent when paid maintenance expired. Returns True if deactivated."""
    if not should_auto_deactivate_for_expired_maintenance(agent):
        return False
    await agent_dao.update(agent, {"is_active": False})
    agent.is_active = False
    return True
