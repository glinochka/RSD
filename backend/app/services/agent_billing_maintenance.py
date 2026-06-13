"""Background maintenance: deactivate agents with expired paid subscriptions."""

from __future__ import annotations

from logging import getLogger

from sqlalchemy import select

from ..agent_template_pricing import get_paid_agent_template_types
from ..alembic.database import async_session_maker
from ..alembic.models import Agent
from ..router_agents.dao import AgentDAO
from .agent_billing import enforce_expired_maintenance, should_auto_deactivate_for_expired_maintenance

logger = getLogger(__name__)

async def _disable_telegram_bot_webhook_for_agent(session, agent_id: int) -> None:
    """Best-effort webhook removal when cron deactivates an agent."""
    try:
        from fastapi import HTTPException

        from ..router_agents.router import (
            _get_telegram_bot_channel_for_agent,
            _sync_telegram_bot_webhook,
        )
        from ..utils.crypto import decrypt_token

        channel = await _get_telegram_bot_channel_for_agent(session, agent_id)
        if not channel or not channel.encrypted_credentials:
            return
        bot_token = decrypt_token(channel.encrypted_credentials)
        try:
            await _sync_telegram_bot_webhook(
                bot_token,
                int(channel.external_id),
                enabled=False,
            )
        except HTTPException as exc:
            if exc.status_code == 502:
                logger.warning(
                    "Agent billing cron: telegram webhook delete failed agent_id=%s: %s",
                    agent_id,
                    exc.detail,
                )
                return
            raise
    except Exception:
        logger.exception(
            "Agent billing cron: failed to disable telegram webhook for agent_id=%s",
            agent_id,
        )


async def deactivate_expired_agent_maintenance_once() -> int:
    """
    Deactivate active paid-template agents whose trial or subscription has expired.
    Returns the number of agents deactivated.
    """
    paid_template_types = get_paid_agent_template_types()
    if not paid_template_types:
        return 0

    deactivated_count = 0

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            query = select(Agent).where(
                Agent.is_active.is_(True),
                Agent.template_type.in_(paid_template_types),
            )
            candidates = await agent_dao.list_scalars(query)

            for agent in candidates:
                if not should_auto_deactivate_for_expired_maintenance(agent):
                    continue
                if await enforce_expired_maintenance(agent_dao, agent):
                    deactivated_count += 1
                    await _disable_telegram_bot_webhook_for_agent(session, agent.id)

    if deactivated_count:
        logger.info(
            "Agent billing cron: deactivated %s agents with expired maintenance",
            deactivated_count,
        )
    return deactivated_count
