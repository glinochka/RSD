"""Worker for sending queued DM messages with rate limiting and retry logic."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentAnalyticsMessage, AgentChannelConnection, AgentSalesDmQueue
from ...utils.crypto import decrypt_token
from .dm_queue_service import get_dm_queue_service

logger = logging.getLogger(__name__)


async def _latest_telegram_userbot_peer_access_hash(
    session,
    *,
    analytics_namespace_id: int,
    user_external_id: str,
) -> int | None:
    """Latest known access_hash for Telethon InputPeerUser (matches router outreach/send helpers)."""
    uid = (user_external_id or "").strip()
    if not uid:
        return None
    row = await session.scalar(
        select(AgentAnalyticsMessage.telegram_peer_access_hash)
        .where(
            AgentAnalyticsMessage.bot_id == analytics_namespace_id,
            AgentAnalyticsMessage.channel == "telegram_userbot",
            AgentAnalyticsMessage.user_external_id == uid,
            AgentAnalyticsMessage.telegram_peer_access_hash.is_not(None),
            AgentAnalyticsMessage.telegram_peer_access_hash > 0,
        )
        .order_by(AgentAnalyticsMessage.created_at.desc())
        .limit(1)
    )
    return int(row) if row is not None else None


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
        encrypted_credentials: str | None = None
        peer_access_hash: int | None = None
        target_external = str(item.target_user_external_id or "").strip()

        if item.metadata_json:
            try:
                meta = json.loads(item.metadata_json)
                if isinstance(meta, dict) and meta.get("telegram_peer_access_hash") is not None:
                    mh = int(meta["telegram_peer_access_hash"])
                    if mh > 0:
                        peer_access_hash = mh
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        async with async_session_maker() as session:
            async with session.begin():
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

                encrypted_credentials = str(channel.encrypted_credentials)
                analytics_ns = int(agent.bot_id or agent.id)
                if peer_access_hash is None:
                    peer_access_hash = await _latest_telegram_userbot_peer_access_hash(
                        session,
                        analytics_namespace_id=analytics_ns,
                        user_external_id=target_external,
                    )

        # Send via Telethon userbot (needs InputPeerUser when entity is not in session cache)
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            from telethon.tl.types import InputPeerUser

            bundle = json.loads(decrypt_token(encrypted_credentials or ""))
            api_id = int(bundle["api_id"])
            api_hash = str(bundle["api_hash"])
            session_str = str(bundle["session_string"])

            client = TelegramClient(StringSession(session_str), api_id, api_hash)

            try:
                await client.connect()
                if not await client.is_user_authorized():
                    raise RuntimeError("Userbot session not authorized")

                try:
                    target_id = int(target_external)
                except ValueError as exc:
                    raise RuntimeError(f"Invalid target_user_external_id (expected numeric Telegram id): {target_external}") from exc

                recipient: Any
                if peer_access_hash is not None:
                    recipient = InputPeerUser(user_id=target_id, access_hash=int(peer_access_hash))
                    logger.debug(
                        "DM outreach using InputPeerUser user_id=%s access_hash present queue_id=%s",
                        target_id,
                        item.id,
                    )
                else:
                    try:
                        recipient = await client.get_entity(target_id)
                    except Exception:
                        recipient = None
                    if recipient is None:
                        raise RuntimeError(
                            "Не удалось отправить DM: нет telegram_peer_access_hash для этого пользователя "
                            "и не удалось найти peer в кэше Telethon. Нужен хотя бы один контакт с этим "
                            "аккаунтом userbot: сообщение в ЛС, пост в отслеживаемой группе/канале с этим "
                            "userbot, или другой способ, чтобы Telegram выдал access_hash."
                        )

                await client.send_message(recipient, item.message_text)

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
            low = error_msg.lower()
            non_retry_substrings = (
                "could not find the input entity",
                "не удалось отправить dm",
                "invalid target_user_external_id",
            )
            is_peer_resolution = any(s in low for s in non_retry_substrings)
            if isinstance(exc, ValueError) and "input entity" in low:
                is_peer_resolution = True
            should_retry = (
                "auth" not in low
                and "not found" not in low
                and not is_peer_resolution
            )
            
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


_dm_worker: DmOutreachWorker | None = None


def get_dm_outreach_worker() -> DmOutreachWorker:
    global _dm_worker
    if _dm_worker is None:
        _dm_worker = DmOutreachWorker(batch_size=10, min_interval_seconds=0.3)
    return _dm_worker
