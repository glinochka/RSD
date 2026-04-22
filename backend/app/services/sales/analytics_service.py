"""Sales manager analytics and monitoring API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func

from ..alembic.database import async_session_maker
from ..alembic.models import (
    Agent,
    AgentAnalyticsMessage,
    AgentSalesContact,
    AgentSalesDmQueue,
)


async def get_sales_manager_stats(*, agent_id: int) -> dict[str, Any]:
    """Get comprehensive sales_manager agent statistics."""
    async with async_session_maker() as session:
        async with session.begin():
            # Check if agent has sales_manager template
            agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
            if agent is None or agent.template_type != "sales_manager":
                return {"error": "Agent not found or is not sales_manager template"}

            # DM Queue stats
            dm_queue_stats = await session.execute(
                select(
                    AgentSalesDmQueue.status,
                    func.count(AgentSalesDmQueue.id).label("count"),
                )
                .where(AgentSalesDmQueue.agent_id == agent_id)
                .group_by(AgentSalesDmQueue.status)
            )
            queue_counts = {row[0]: row[1] for row in dm_queue_stats}

            # Sales contact states
            contact_states = await session.execute(
                select(
                    AgentSalesContact.state,
                    func.count(AgentSalesContact.id).label("count"),
                )
                .where(AgentSalesContact.agent_id == agent_id)
                .group_by(AgentSalesContact.state)
            )
            contact_counts = {row[0]: row[1] for row in contact_states}

            # Messages sent in last 24 hours
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            cutoff_24h = now - timedelta(hours=24)
            messages_24h = await session.scalar(
                select(func.count(AgentAnalyticsMessage.id)).where(
                    AgentAnalyticsMessage.agent_id == agent_id,
                    AgentAnalyticsMessage.channel == "telegram_userbot",
                    AgentAnalyticsMessage.role == "agent",
                    AgentAnalyticsMessage.created_at >= cutoff_24h,
                )
            )

            # Qualified leads last 7 days
            cutoff_7d = now - timedelta(days=7)
            qualified_leads = await session.scalar(
                select(func.count(AgentSalesContact.id)).where(
                    AgentSalesContact.agent_id == agent_id,
                    AgentSalesContact.state.in_(
                        {"QUALIFIED", "QUEUED", "SENT", "REPLIED_POSITIVE", "HANDOFF_CRM"}
                    ),
                    AgentSalesContact.updated_at >= cutoff_7d,
                )
            )

            # Positive replies
            positive_replies = contact_counts.get("REPLIED_POSITIVE", 0)

            # Sent to DM (sent items in last 7 days)
            sent_dms = await session.scalar(
                select(func.count(AgentSalesDmQueue.id)).where(
                    AgentSalesDmQueue.agent_id == agent_id,
                    AgentSalesDmQueue.status == "sent",
                    AgentSalesDmQueue.sent_at >= cutoff_7d,
                )
            )

            return {
                "ok": True,
                "agent_id": agent_id,
                "template_type": agent.template_type,
                "queue": {
                    "pending": queue_counts.get("pending", 0),
                    "sending": queue_counts.get("sending", 0),
                    "sent": queue_counts.get("sent", 0),
                    "failed": queue_counts.get("failed", 0),
                    "skipped": queue_counts.get("skipped", 0),
                    "total": sum(queue_counts.values()),
                },
                "contacts": {
                    "discovered": contact_counts.get("DISCOVERED", 0),
                    "qualified": contact_counts.get("QUALIFIED", 0),
                    "queued": contact_counts.get("QUEUED", 0),
                    "sent": contact_counts.get("SENT", 0),
                    "replied_positive": positive_replies,
                    "replied_negative": contact_counts.get("REPLIED_NEGATIVE", 0),
                    "no_reply": contact_counts.get("NO_REPLY", 0),
                    "handoff_crm": contact_counts.get("HANDOFF_CRM", 0),
                    "skipped": contact_counts.get("SKIPPED", 0),
                    "total": sum(contact_counts.values()),
                },
                "metrics": {
                    "qualified_leads_7d": qualified_leads or 0,
                    "positive_replies_total": positive_replies,
                    "sent_dms_7d": sent_dms or 0,
                    "messages_last_24h": messages_24h or 0,
                },
            }


async def get_sales_manager_dm_queue(
    *,
    agent_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Get DM queue items with optional filtering."""
    async with async_session_maker() as session:
        async with session.begin():
            query = select(AgentSalesDmQueue).where(AgentSalesDmQueue.agent_id == agent_id)
            if status:
                query = query.where(AgentSalesDmQueue.status == status)

            total = await session.scalar(
                select(func.count(AgentSalesDmQueue.id)).where(
                    AgentSalesDmQueue.agent_id == agent_id,
                    (AgentSalesDmQueue.status == status) if status else True,
                )
            )

            items = (
                await session.execute(
                    query.order_by(AgentSalesDmQueue.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).scalars().all()

            return {
                "ok": True,
                "agent_id": agent_id,
                "total": total or 0,
                "limit": limit,
                "offset": offset,
                "items": [
                    {
                        "id": item.id,
                        "target_user_id": item.target_user_external_id,
                        "source_chat_id": item.source_chat_id,
                        "status": item.status,
                        "retry_count": item.retry_count,
                        "max_retries": item.max_retries,
                        "scheduled_for": item.scheduled_for.isoformat() if item.scheduled_for else None,
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                        "sent_at": item.sent_at.isoformat() if item.sent_at else None,
                        "last_error": item.last_error,
                    }
                    for item in items
                ],
            }
