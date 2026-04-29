"""Worker for sending queued DM messages with rate limiting and retry logic."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from datetime import timedelta

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentChannelConnection, AgentSalesDmQueue
from ...utils.crypto import decrypt_token
from .dm_queue_service import DmQueueService, get_dm_queue_service

logger = logging.getLogger(__name__)


class DmOutreachWorker:
    """Background worker for sending queued DM messages."""

    def __init__(self, batch_size: int = 10, min_interval_seconds: float = 0.3) -> None:
        self.batch_size = batch_size
        self.min_interval_seconds = min_interval_seconds
        self._stop = asyncio.Event()

    async def shutdown(self) -> None:
        """Stop the worker."""
        self._stop.set()

    async def run_forever(self) -> None:
        """Main worker loop."""
        logger.info("DmOutreachWorker starting")
        interval_seconds = 2  # Poll every 2 seconds for more responsive processing
        
        try:
            while not self._stop.is_set():
                try:
                    await self._process_batch()
                except Exception as exc:
                    logger.exception("DmOutreachWorker batch error: %s", exc)
                
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval_seconds)
                    break
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            logger.info("DmOutreachWorker cancelled")
            raise
        finally:
            logger.info("DmOutreachWorker stopped")

    async def _process_batch(self) -> None:
        """Process one batch of pending messages."""
        service = get_dm_queue_service()
        pending = await service.get_pending_messages(limit=self.batch_size)
        
        if not pending:
            return

        logger.info("Processing %d queued DM messages", len(pending))

        for item in pending:
            try:
                logger.info(
                    "Sending DM: queue_id=%d agent_id=%d user_id=%s text_preview=%s",
                    item.id,
                    item.agent_id,
                    item.target_user_external_id,
                    item.message_text[:50] if len(item.message_text) > 50 else item.message_text,
                )
                await self._send_message(item)
                # Throttle between sends to avoid rate limiting
                await asyncio.sleep(self.min_interval_seconds)
            except Exception as exc:
                logger.exception("Error sending DM queue_id=%d: %s", item.id, exc)
                await service.mark_failed(queue_id=item.id, error=str(exc)[:500], retry=True)

    async def _send_message(self, item: AgentSalesDmQueue) -> None:
        """Send a single queued message via userbot."""
        async with async_session_maker() as session:
            async with session.begin():
                # Get agent and channel info
                agent = await session.scalar(select(Agent).where(Agent.id == item.agent_id))
                if agent is None:
                    logger.warning("Agent not found for queue_id=%d agent_id=%d", item.id, item.agent_id)
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error="Agent not found",
                        retry=False,
                    )
                    return

                channel = await session.scalar(
                    select(AgentChannelConnection).where(
                        AgentChannelConnection.agent_id == agent.id,
                        AgentChannelConnection.provider == "telegram_userbot",
                        AgentChannelConnection.is_active.is_(True),
                    )
                )
                
                if channel is None or not channel.encrypted_credentials:
                    logger.warning("No active userbot channel for agent_id=%d", agent.id)
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error="No userbot channel available",
                        retry=False,
                    )
                    return

        # Send via Telethon userbot
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            from telethon.tl.types import InputPeerUser

            bundle = json.loads(decrypt_token(channel.encrypted_credentials))
            api_id = int(bundle["api_id"])
            api_hash = str(bundle["api_hash"])
            session_str = str(bundle["session_string"])

            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            
            try:
                await client.connect()
                if not await client.is_user_authorized():
                    raise RuntimeError("Userbot session not authorized")

                target_id = int(item.target_user_external_id)
                await client.send_message(target_id, item.message_text)
                
                logger.info(
                    "Sent DM via userbot: queue_id=%d agent_id=%d user_id=%s",
                    item.id,
                    item.agent_id,
                    item.target_user_external_id,
                )
                await get_dm_queue_service().mark_sent(queue_id=item.id)
                
            finally:
                if client.is_connected():
                    await client.disconnect()

        except Exception as exc:
            error_msg = str(exc)[:500]
            # Retry on connection errors, not on auth/user errors
            should_retry = "auth" not in error_msg.lower() and "not found" not in error_msg.lower()
            
            logger.warning(
                "Failed to send DM queue_id=%d: %s (retry=%s)",
                item.id,
                error_msg,
                should_retry,
            )
            await get_dm_queue_service().mark_failed(
                queue_id=item.id,
                error=error_msg,
                retry=should_retry,
            )
            raise


_dm_worker: DmOutreachWorker | None = None


def get_dm_outreach_worker() -> DmOutreachWorker:
    global _dm_worker
    if _dm_worker is None:
        _dm_worker = DmOutreachWorker(batch_size=10, min_interval_seconds=0.3)
    return _dm_worker
