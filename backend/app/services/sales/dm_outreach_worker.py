"""Worker for sending queued DM messages with rate limiting and retry logic."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update

from ...alembic.database import async_session_maker
from ...alembic.models import (
    Agent,
    AgentAnalyticsMessage,
    AgentChannelConnection,
    AgentSalesDmQueue,
    AgentSalesImportedContact,
)
from .agent_outreach_service import mark_import_contact_sent
from .dm_queue_service import get_dm_queue_service
from .outreach_send import send_telegram_userbot_message, send_whatsapp_userbot_message
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID
from .fsm import SalesFSMService
from .sales_followup_service import (
    COMPOSE_AT_SEND_PLACEHOLDER,
    compose_follow_up_message,
    mark_follow_up_sent,
    should_send_follow_up,
)

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


def _parse_queue_metadata(item: AgentSalesDmQueue) -> dict[str, Any]:
    if not item.metadata_json:
        return {}
    try:
        meta = json.loads(item.metadata_json)
        return meta if isinstance(meta, dict) else {}
    except json.JSONDecodeError:
        return {}


def _is_ai_mop_first_outreach(meta: dict[str, Any]) -> bool:
    if meta.get("message_kind") == "follow_up" or meta.get("compose_at_send"):
        return False
    return meta.get("source") == "ai_mop" or meta.get("ai_mop_lead_id") is not None


class DmOutreachWorker:
    """Background worker for sending queued DM messages."""

    def __init__(self, batch_size: int = 10, min_interval_seconds: float = 0.3) -> None:
        self.batch_size = batch_size
        self.min_interval_seconds = min_interval_seconds
        self._stop = asyncio.Event()
        self._last_send_by_account: dict[tuple[int, str, int], datetime] = {}

    @staticmethod
    def _now_utc_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _resolve_account_timeout_seconds(meta: dict[str, Any]) -> int:
        raw = meta.get("account_timeout_seconds")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 0
        if 180 <= value <= 420:
            return value
        timeout = random.randint(180, 420)
        meta["account_timeout_seconds"] = timeout
        return timeout

    @staticmethod
    def _pick_deterministic_connection(
        *,
        provider: str,
        target_external: str,
        available_ids: list[int],
    ) -> int | None:
        if not available_ids:
            return None
        if len(available_ids) == 1:
            return available_ids[0]
        digest = hashlib.sha256(f"{provider}:{target_external}".encode("utf-8")).hexdigest()
        slot = int(digest[:16], 16) % len(available_ids)
        return available_ids[slot]

    async def _defer_queue_item(self, *, queue_id: int, scheduled_for: datetime, meta: dict[str, Any]) -> None:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(
                    update(AgentSalesDmQueue)
                    .where(AgentSalesDmQueue.id == queue_id)
                    .values(
                        status="pending",
                        scheduled_for=scheduled_for,
                        metadata_json=json.dumps(meta, ensure_ascii=False),
                    )
                )

    async def _defer_if_outside_ai_mop_send_window(
        self,
        *,
        item: AgentSalesDmQueue,
        meta: dict[str, Any],
    ) -> bool:
        if not _is_ai_mop_first_outreach(meta):
            return False

        from ..ai_mop.send_window import ai_mop_first_message_allowed_now, next_ai_mop_first_message_at

        if ai_mop_first_message_allowed_now():
            return False

        scheduled_for = next_ai_mop_first_message_at()
        await self._defer_queue_item(
            queue_id=int(item.id),
            scheduled_for=scheduled_for,
            meta=meta,
        )
        logger.info(
            "Deferred AI MOP first message until Moscow business hours: queue_id=%d until=%s",
            item.id,
            scheduled_for.isoformat(),
        )
        return True

    async def shutdown(self) -> None:
        """Stop the worker."""
        self._stop.set()

    async def run_forever(self) -> None:
        """Main worker loop."""
        logger.info("DmOutreachWorker starting")
        interval_seconds = 2

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
                await asyncio.sleep(self.min_interval_seconds)
            except Exception as exc:
                logger.exception("Error sending DM queue_id=%d: %s", item.id, exc)
                await service.mark_failed(queue_id=item.id, error=str(exc)[:500], retry=True)

    async def _send_message(self, item: AgentSalesDmQueue) -> None:
        """Send a single queued message via userbot (Telegram or WhatsApp)."""
        meta = _parse_queue_metadata(item)
        if await self._defer_if_outside_ai_mop_send_window(item=item, meta=meta):
            return
        channel = str(meta.get("channel") or "telegram_userbot").strip().lower()
        message_text = (item.message_text or "").strip()
        imported_id = meta.get("imported_contact_id")
        follow_up_tier = str(meta.get("follow_up_tier") or "").strip().lower()

        if meta.get("compose_at_send") or message_text == COMPOSE_AT_SEND_PLACEHOLDER:
            if imported_id is None:
                await get_dm_queue_service().mark_skipped(
                    queue_id=item.id,
                    reason="follow_up_missing_imported_contact_id",
                )
                return
            if not await should_send_follow_up(
                agent_id=item.agent_id,
                imported_contact_id=int(imported_id),
            ):
                await get_dm_queue_service().mark_skipped(
                    queue_id=item.id,
                    reason="client_replied_or_not_eligible",
                )
                return
            async with async_session_maker() as session:
                async with session.begin():
                    agent = await session.scalar(select(Agent).where(Agent.id == item.agent_id))
                    row = await session.scalar(
                        select(AgentSalesImportedContact).where(
                            AgentSalesImportedContact.id == int(imported_id)
                        )
                    )
            if agent is None or row is None:
                await get_dm_queue_service().mark_failed(
                    queue_id=item.id,
                    error="Agent or imported contact not found",
                    retry=False,
                )
                return
            message_text = (
                await compose_follow_up_message(
                    agent=agent,
                    row=row,
                    tier=follow_up_tier or "day",
                )
            ).strip()
            if not message_text:
                await get_dm_queue_service().mark_failed(
                    queue_id=item.id,
                    error="Empty follow-up message",
                    retry=True,
                )
                return
        peer_access_hash: int | None = None
        if meta.get("telegram_peer_access_hash") is not None:
            try:
                mh = int(meta["telegram_peer_access_hash"])
                if mh > 0:
                    peer_access_hash = mh
            except (TypeError, ValueError):
                pass

        encrypted_credentials: str | None = None
        connection_id: int | None = None
        target_external = str(item.target_user_external_id or "").strip()
        metadata_changed = False

        async with async_session_maker() as session:
            async with session.begin():
                agent = await session.scalar(select(Agent).where(Agent.id == item.agent_id))
                if agent is None:
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error="Agent not found",
                        retry=False,
                    )
                    return

                provider = (
                    "whatsapp_userbot"
                    if channel == "whatsapp_userbot"
                    else "telegram_userbot"
                )
                channels = (
                    await session.execute(
                        select(AgentChannelConnection).where(
                            AgentChannelConnection.agent_id == agent.id,
                            AgentChannelConnection.provider == provider,
                            AgentChannelConnection.is_active.is_(True),
                        )
                    )
                ).scalars().all()

                if not channels:
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error=f"No active {provider} channel",
                        retry=False,
                    )
                    return

                available_ids = [int(ch.id) for ch in channels if ch.encrypted_credentials]
                if not available_ids:
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error=f"No active {provider} channel with credentials",
                        retry=False,
                    )
                    return

                assigned_raw = meta.get("assigned_connection_id")
                assigned_connection_id: int | None = None
                try:
                    assigned_connection_id = int(assigned_raw) if assigned_raw is not None else None
                except (TypeError, ValueError):
                    assigned_connection_id = None

                if assigned_connection_id not in available_ids:
                    # Для sales_manager закрепляем лида за конкретным аккаунтом (по хешу),
                    # чтобы два аккаунта не вели одного и того же лида.
                    if str(agent.template_type or "").strip().lower() == "sales_manager":
                        assigned_connection_id = self._pick_deterministic_connection(
                            provider=provider,
                            target_external=target_external,
                            available_ids=sorted(available_ids),
                        )
                    else:
                        assigned_connection_id = available_ids[0]
                    meta["assigned_connection_id"] = assigned_connection_id
                    metadata_changed = True

                ch = await session.scalar(
                    select(AgentChannelConnection).where(
                        AgentChannelConnection.agent_id == agent.id,
                        AgentChannelConnection.provider == provider,
                        AgentChannelConnection.id == int(assigned_connection_id),
                        AgentChannelConnection.is_active.is_(True),
                    )
                )

                if ch is None or not ch.encrypted_credentials:
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error=f"No active {provider} channel",
                        retry=False,
                    )
                    return

                encrypted_credentials = str(ch.encrypted_credentials)
                connection_id = int(ch.id)
                analytics_ns = int(agent.bot_id or agent.id)
                if provider == "telegram_userbot" and peer_access_hash is None:
                    peer_access_hash = await _latest_telegram_userbot_peer_access_hash(
                        session,
                        analytics_namespace_id=analytics_ns,
                        user_external_id=target_external,
                    )
        if metadata_changed:
            await self._defer_queue_item(
                queue_id=int(item.id),
                scheduled_for=item.scheduled_for or self._now_utc_naive(),
                meta=meta,
            )

        timeout_seconds = self._resolve_account_timeout_seconds(meta)
        account_key = (int(item.agent_id), channel, int(connection_id or 0))
        now = self._now_utc_naive()
        last_sent_at = self._last_send_by_account.get(account_key)
        if last_sent_at is not None:
            next_allowed_at = last_sent_at + timedelta(seconds=timeout_seconds)
            if next_allowed_at > now:
                await self._defer_queue_item(
                    queue_id=int(item.id),
                    scheduled_for=next_allowed_at,
                    meta=meta,
                )
                logger.info(
                    "Deferred DM by account cooldown: queue_id=%d connection_id=%d until=%s",
                    item.id,
                    int(connection_id or 0),
                    next_allowed_at.isoformat(),
                )
                return

        try:
            if channel == "whatsapp_userbot":
                await send_whatsapp_userbot_message(
                    connection_id=int(connection_id or 0),
                    encrypted_credentials=encrypted_credentials or "",
                    user_external_id=target_external,
                    text=message_text,
                )
            else:
                await send_telegram_userbot_message(
                    encrypted_credentials=encrypted_credentials or "",
                    target_external_id=target_external,
                    text=message_text,
                    peer_access_hash=peer_access_hash,
                )

            logger.info(
                "Sent DM: queue_id=%d agent_id=%d channel=%s user_id=%s",
                item.id,
                item.agent_id,
                channel,
                target_external,
            )
            await get_dm_queue_service().mark_sent(queue_id=item.id)
            self._last_send_by_account[account_key] = self._now_utc_naive()

            from ..ai_mop.dm_hooks import on_dm_queue_sent

            await on_dm_queue_sent(item)

            if imported_id is not None:
                try:
                    if meta.get("message_kind") == "follow_up" and follow_up_tier:
                        await mark_follow_up_sent(
                            imported_contact_id=int(imported_id),
                            tier=follow_up_tier,
                        )
                    else:
                        await mark_import_contact_sent(imported_contact_id=int(imported_id))
                        fsm = SalesFSMService()
                        try:
                            await fsm.transition_contact(
                                agent_id=item.agent_id,
                                user_external_id=target_external,
                                source_chat_id=EXCEL_IMPORT_SOURCE_CHAT_ID,
                                to_state="SENT",
                                reason="excel_import_first_message_sent",
                            )
                        except Exception:
                            logger.debug("FSM SENT transition skipped queue_id=%s", item.id, exc_info=True)
                except Exception:
                    logger.warning("Failed to mark imported contact sent id=%s", imported_id, exc_info=True)

        except Exception as exc:
            error_msg = str(exc)[:500]
            low = error_msg.lower()
            non_retry_substrings = (
                "could not find the input entity",
                "не удалось отправить dm",
                "invalid target_user_external_id",
                "некорректный номер",
                "пустой идентификатор",
            )
            is_peer_resolution = any(s in low for s in non_retry_substrings)
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
