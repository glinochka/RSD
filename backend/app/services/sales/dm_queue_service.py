"""DM (Direct Message) queue manager for sales_manager outreach."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any

from sqlalchemy import select, update

from ...alembic.database import async_session_maker
from ...alembic.models import AgentSalesDmQueue

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DmQueueService:
    """Manage outbound DM queue with rate limiting and retry logic."""

    @staticmethod
    async def enqueue_dm(
        *,
        agent_id: int,
        target_user_external_id: str,
        source_chat_id: str,
        message_text: str,
        scheduled_for: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSalesDmQueue:
        """Add message to outbound queue."""
        async with async_session_maker() as session:
            async with session.begin():
                metadata_str = json.dumps(metadata or {}, ensure_ascii=False) if metadata else None
                queue_item = AgentSalesDmQueue(
                    agent_id=agent_id,
                    target_user_external_id=target_user_external_id,
                    source_chat_id=source_chat_id,
                    message_text=message_text,
                    status="pending",
                    retry_count=0,
                    max_retries=3,
                    scheduled_for=scheduled_for,
                    metadata_json=metadata_str,
                    created_at=_now_utc(),
                    updated_at=_now_utc(),
                )
                session.add(queue_item)
                await session.flush()
                return queue_item

    @staticmethod
    async def get_pending_messages(
        *,
        agent_id: int | None = None,
        limit: int = 100,
    ) -> list[AgentSalesDmQueue]:
        """Get pending messages ready to send (respecting rate limits)."""
        async with async_session_maker() as session:
            async with session.begin():
                now = _now_utc()
                query = select(AgentSalesDmQueue).where(
                    AgentSalesDmQueue.status == "pending",
                    (AgentSalesDmQueue.scheduled_for.is_(None)) | (AgentSalesDmQueue.scheduled_for <= now),
                )
                if agent_id is not None:
                    query = query.where(AgentSalesDmQueue.agent_id == agent_id)
                query = query.order_by(AgentSalesDmQueue.created_at).limit(limit)
                rows = (await session.execute(query)).scalars().all()
                return rows

    @staticmethod
    async def mark_skipped(
        *,
        queue_id: int,
        reason: str | None = None,
    ) -> None:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(
                    update(AgentSalesDmQueue)
                    .where(AgentSalesDmQueue.id == queue_id)
                    .values(
                        status="skipped",
                        last_error=reason,
                        updated_at=_now_utc(),
                    )
                )

    @staticmethod
    async def mark_sent(
        *,
        queue_id: int,
    ) -> None:
        """Mark message as successfully sent."""
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(
                    update(AgentSalesDmQueue)
                    .where(AgentSalesDmQueue.id == queue_id)
                    .values(
                        status="sent",
                        sent_at=_now_utc(),
                        updated_at=_now_utc(),
                    )
                )

    @staticmethod
    async def mark_failed(
        *,
        queue_id: int,
        error: str | None = None,
        retry: bool = True,
    ) -> None:
        """Mark message as failed with optional retry."""
        async with async_session_maker() as session:
            async with session.begin():
                row = await session.scalar(select(AgentSalesDmQueue).where(AgentSalesDmQueue.id == queue_id))
                if row is None:
                    return

                new_retry_count = row.retry_count + 1
                new_status = "pending" if (retry and new_retry_count < row.max_retries) else "failed"

                await session.execute(
                    update(AgentSalesDmQueue)
                    .where(AgentSalesDmQueue.id == queue_id)
                    .values(
                        status=new_status,
                        retry_count=new_retry_count,
                        last_error=error,
                        updated_at=_now_utc(),
                    )
                )

    @staticmethod
    async def get_queue_stats(
        *,
        agent_id: int,
    ) -> dict[str, Any]:
        """Get queue statistics for agent."""
        async with async_session_maker() as session:
            async with session.begin():
                rows = (
                    await session.execute(
                        select(
                            AgentSalesDmQueue.status,
                            select(1).correlate(None).scalar_subquery().label("count"),
                        )
                        .where(AgentSalesDmQueue.agent_id == agent_id)
                        .group_by(AgentSalesDmQueue.status)
                    )
                ).all()
                
                stats: dict[str, int] = {}
                for row in rows:
                    status = row.status
                    count = (
                        await session.scalar(
                            select(select(1).scalar_subquery())
                            .select_from(AgentSalesDmQueue)
                            .where(
                                AgentSalesDmQueue.agent_id == agent_id,
                                AgentSalesDmQueue.status == status,
                            )
                        )
                    ) or 0
                    stats[status] = count

                return {
                    "pending": stats.get("pending", 0),
                    "sending": stats.get("sending", 0),
                    "sent": stats.get("sent", 0),
                    "failed": stats.get("failed", 0),
                    "skipped": stats.get("skipped", 0),
                    "total": sum(stats.values()),
                }

    @staticmethod
    async def get_sent_count_in_window(
        *,
        agent_id: int,
        window_seconds: int = 3600,
    ) -> int:
        """Get count of messages sent in the last N seconds."""
        async with async_session_maker() as session:
            async with session.begin():
                cutoff = _now_utc() - timedelta(seconds=window_seconds)
                count = await session.scalar(
                    select(select(1).scalar_subquery()).select_from(
                        select(1).select_from(AgentSalesDmQueue)
                        .where(
                            AgentSalesDmQueue.agent_id == agent_id,
                            AgentSalesDmQueue.status == "sent",
                            AgentSalesDmQueue.sent_at >= cutoff,
                        )
                        .correlate(None)
                        .scalar_subquery()
                    )
                )
                return count or 0

    @staticmethod
    async def cleanup_old_records(
        *,
        older_than_days: int = 30,
    ) -> int:
        """Remove old completed/failed records."""
        async with async_session_maker() as session:
            async with session.begin():
                cutoff = _now_utc() - timedelta(days=older_than_days)
                result = await session.execute(
                    update(AgentSalesDmQueue)
                    .where(
                        AgentSalesDmQueue.status.in_({"sent", "skipped"}),
                        AgentSalesDmQueue.updated_at < cutoff,
                    )
                    .values(status="archived")
                )
                return result.rowcount or 0


_dm_queue_service: DmQueueService | None = None


def get_dm_queue_service() -> DmQueueService:
    global _dm_queue_service
    if _dm_queue_service is None:
        _dm_queue_service = DmQueueService()
    return _dm_queue_service
