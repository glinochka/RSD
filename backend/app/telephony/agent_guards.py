"""Shared agent availability checks for telephony turns."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import Agent, AgentFrozenUser, User
from ..services.agent_availability import agent_availability_allows_now
from ..utils.agent_template_config import parse_agent_template_config

logger = logging.getLogger(__name__)


async def is_subscription_valid(session: AsyncSession, agent_id: int) -> bool:
    try:
        row = await session.execute(
            select(User.subscription_end_date).join(Agent, Agent.user_id == User.id).where(Agent.id == agent_id)
        )
        subscription_end = row.scalar_one_or_none()
        if not subscription_end:
            return True
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return subscription_end >= now
    except Exception:
        logger.exception("Subscription check failed for agent_id=%s", agent_id)
        return True


async def is_user_frozen(session: AsyncSession, agent_id: int, caller_e164: str) -> bool:
    uid = (caller_e164 or "").strip()
    if not uid:
        return False
    try:
        frozen_id = await session.scalar(
            select(AgentFrozenUser.id).where(
                AgentFrozenUser.agent_id == agent_id,
                AgentFrozenUser.user_external_id == uid,
            )
        )
        return bool(frozen_id)
    except Exception:
        logger.warning("Frozen check failed for agent_id=%s", agent_id)
        return False


def parse_template_config(raw: str | None) -> dict | None:
    return parse_agent_template_config(raw, none_if_empty=True)


def availability_allows(template_config: dict | None) -> bool:
    return agent_availability_allows_now(template_config)
