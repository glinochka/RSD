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
    AgentSalesContact,
    AgentSalesDmQueue,
    AgentSalesImportedContact,
    AiMopLead,
)
from .agent_outreach_service import mark_import_contact_sent
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID
from .dm_queue_service import get_dm_queue_service
from .outreach_send import (
    send_max_userbot_message,
    send_telegram_userbot_message,
    send_whatsapp_userbot_message,
)
from .agent_excel_import import EXCEL_IMPORT_SOURCE_CHAT_ID
from .fsm import SalesFSMService
from .sales_followup_service import (
    COMPOSE_AT_SEND_PLACEHOLDER,
    compose_follow_up_message,
    mark_follow_up_sent,
    should_send_follow_up,
)

logger = logging.getLogger(__name__)

_USERBOT_CHANNELS = frozenset({"telegram_userbot", "whatsapp_userbot", "max_userbot"})


def _provider_for_channel(channel: str) -> str:
    normalized = str(channel or "").strip().lower()
    if normalized in _USERBOT_CHANNELS:
        return normalized
    return "telegram_userbot"


async def _rekey_max_excel_contact(
    *,
    agent_id: int,
    old_external_id: str,
    chat_external_id: str,
    imported_contact_id: int | None,
) -> None:
    """После cold DM по телефону MAX привязываем FSM/импорт к chat_id диалога."""
    old_id = str(old_external_id or "").strip()
    new_id = str(chat_external_id or "").strip()
    if not old_id or not new_id or old_id == new_id or not old_id.startswith("+"):
        return
    async with async_session_maker() as session:
        async with session.begin():
            fsm_row = await session.scalar(
                select(AgentSalesContact).where(
                    AgentSalesContact.agent_id == agent_id,
                    AgentSalesContact.user_external_id == old_id,
                    AgentSalesContact.source_chat_id == EXCEL_IMPORT_SOURCE_CHAT_ID,
                )
            )
            if fsm_row is not None:
                fsm_row.user_external_id = new_id
                fsm_row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if imported_contact_id is not None:
                await session.execute(
                    update(AgentSalesImportedContact)
                    .where(AgentSalesImportedContact.id == int(imported_contact_id))
                    .values(
                        target_external_id=new_id[:256],
                        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )


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


def _is_ai_mop_queue_item(meta: dict[str, Any]) -> bool:
    if meta.get("ai_mop_lead_id") is not None:
        return True
    source = str(meta.get("source") or "")
    return source == "ai_mop" or source == "ai_mop_follow_up"


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

    @staticmethod
    def _dm_fallback_targets(*, primary_target: str, meta: dict[str, Any]) -> list[str]:
        targets = [str(primary_target or "").strip()]
        raw_fallbacks = meta.get("fallback_targets")
        if not isinstance(raw_fallbacks, list):
            hint = meta.get("target_resolve_hint")
            if isinstance(hint, dict):
                raw_fallbacks = hint.get("fallback_targets")
        if isinstance(raw_fallbacks, list):
            for value in raw_fallbacks:
                candidate = str(value or "").strip()
                if candidate and candidate not in targets:
                    targets.append(candidate)
        return [target for target in targets if target]

    @staticmethod
    def _should_try_next_dm_target(*, channel: str, exc: Exception, attempt_index: int, total: int) -> bool:
        if attempt_index >= total - 1:
            return False
        low = str(exc).casefold()
        if channel == "telegram_userbot":
            markers = (
                "you can't write in this chat",
                "could not find the input entity",
                "peeridinvalid",
                "chat_write_forbidden",
                "user is deactivated",
                "username not occupied",
                "nobody is using this username",
                "cannot find any entity",
            )
            return any(marker in low for marker in markers)
        if channel == "whatsapp_userbot":
            markers = (
                "could not find",
                "invalid",
                "not registered",
                "некорректный номер",
                "not on whatsapp",
            )
            return any(marker in low for marker in markers)
        if channel == "max_userbot":
            markers = (
                "некорректный chat_id",
                "не удалось отправить сообщение в max",
                "не удалось найти пользователя max",
                "пользователь max не найден",
                "chat not found",
                "forbidden",
                "not found",
            )
            return any(marker in low for marker in markers)
        return False

    @staticmethod
    def _cross_channel_fallbacks(meta: dict[str, Any]) -> list[dict[str, str]]:
        raw = meta.get("cross_channel_fallbacks")
        if not isinstance(raw, list):
            hint = meta.get("target_resolve_hint")
            if isinstance(hint, dict):
                raw = hint.get("cross_channel_fallbacks")
        if not isinstance(raw, list):
            return []
        cleaned: list[dict[str, str]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            channel = str(entry.get("channel") or "").strip().lower()
            target = str(entry.get("target") or "").strip()
            if channel in _USERBOT_CHANNELS and target:
                cleaned.append({"channel": channel, "target": target})
        return cleaned

    async def _try_cross_channel_fallbacks(
        self,
        *,
        item: AgentSalesDmQueue,
        meta: dict[str, Any],
        message_text: str,
        peer_access_hash: int | None,
    ) -> tuple[str, str, int] | None:
        for alt in self._cross_channel_fallbacks(meta):
            alt_channel = alt["channel"]
            alt_target = alt["target"]
            encrypted_credentials: str | None = None
            connection_id: int | None = None
            alt_peer_hash = peer_access_hash if alt_channel == "telegram_userbot" else None

            async with async_session_maker() as session:
                async with session.begin():
                    agent = await session.scalar(select(Agent).where(Agent.id == item.agent_id))
                    if agent is None:
                        continue
                    provider = _provider_for_channel(alt_channel)
                    channels = (
                        await session.execute(
                            select(AgentChannelConnection).where(
                                AgentChannelConnection.agent_id == agent.id,
                                AgentChannelConnection.provider == provider,
                                AgentChannelConnection.is_active.is_(True),
                            )
                        )
                    ).scalars().all()
                    available_ids = [int(ch.id) for ch in channels if ch.encrypted_credentials]
                    if not available_ids:
                        continue
                    chosen_id = self._pick_deterministic_connection(
                        provider=provider,
                        target_external=alt_target,
                        available_ids=sorted(available_ids),
                    )
                    if chosen_id is None:
                        continue
                    ch = await session.scalar(
                        select(AgentChannelConnection).where(
                            AgentChannelConnection.id == int(chosen_id),
                            AgentChannelConnection.is_active.is_(True),
                        )
                    )
                    if ch is None or not ch.encrypted_credentials:
                        continue
                    encrypted_credentials = str(ch.encrypted_credentials)
                    connection_id = int(ch.id)
                    if alt_channel == "telegram_userbot" and alt_peer_hash is None:
                        analytics_ns = int(agent.bot_id or agent.id)
                        alt_peer_hash = await _latest_telegram_userbot_peer_access_hash(
                            session,
                            analytics_namespace_id=analytics_ns,
                            user_external_id=alt_target,
                        )

            try:
                used_target = await self._send_dm_with_target_fallbacks(
                    channel=alt_channel,
                    primary_target=alt_target,
                    meta=meta,
                    message_text=message_text,
                    connection_id=int(connection_id or 0),
                    encrypted_credentials=encrypted_credentials or "",
                    peer_access_hash=alt_peer_hash,
                )
                logger.info(
                    "DM sent via cross-channel fallback queue_id=%d channel=%s target=%s",
                    item.id,
                    alt_channel,
                    used_target,
                )
                meta["channel"] = alt_channel
                return alt_channel, used_target, int(connection_id or 0)
            except Exception as exc:
                logger.warning(
                    "Cross-channel DM failed queue_id=%d channel=%s target=%s error=%s",
                    item.id,
                    alt_channel,
                    alt_target,
                    str(exc)[:200],
                )
        return None

    async def _send_dm_with_target_fallbacks(
        self,
        *,
        channel: str,
        primary_target: str,
        meta: dict[str, Any],
        message_text: str,
        connection_id: int,
        encrypted_credentials: str,
        peer_access_hash: int | None,
    ) -> str:
        targets = self._dm_fallback_targets(primary_target=primary_target, meta=meta)
        if not targets:
            raise ValueError("invalid target_user_external_id")

        last_exc: Exception | None = None
        for idx, target in enumerate(targets):
            try:
                if channel == "whatsapp_userbot":
                    await send_whatsapp_userbot_message(
                        connection_id=connection_id,
                        encrypted_credentials=encrypted_credentials,
                        user_external_id=target,
                        text=message_text,
                    )
                elif channel == "max_userbot":
                    resolved_chat_id = await send_max_userbot_message(
                        encrypted_credentials=encrypted_credentials,
                        user_external_id=target,
                        text=message_text,
                    )
                    if resolved_chat_id and resolved_chat_id != target:
                        target = resolved_chat_id
                else:
                    await send_telegram_userbot_message(
                        encrypted_credentials=encrypted_credentials,
                        target_external_id=target,
                        text=message_text,
                        peer_access_hash=peer_access_hash,
                    )
                if idx > 0:
                    logger.info(
                        "DM sent via fallback target channel=%s target=%s",
                        channel,
                        target,
                    )
                return target
            except Exception as exc:
                last_exc = exc
                if not self._should_try_next_dm_target(
                    channel=channel,
                    exc=exc,
                    attempt_index=idx,
                    total=len(targets),
                ):
                    raise
                logger.warning(
                    "DM target failed channel=%s target=%s error=%s — trying fallback",
                    channel,
                    target,
                    str(exc)[:200],
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("DM send failed")

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
        if not _is_ai_mop_queue_item(meta):
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
            "Deferred AI MOP message until Moscow business hours: queue_id=%d until=%s",
            item.id,
            scheduled_for.isoformat(),
        )
        return True

    async def _defer_if_ai_mop_pipeline_paused(
        self,
        *,
        item: AgentSalesDmQueue,
        meta: dict[str, Any],
    ) -> bool:
        if not _is_ai_mop_queue_item(meta):
            return False

        from ..ai_mop.pipeline_state import is_ai_mop_pipeline_paused

        if not await is_ai_mop_pipeline_paused():
            return False

        scheduled_for = self._now_utc_naive() + timedelta(minutes=1)
        await self._defer_queue_item(
            queue_id=int(item.id),
            scheduled_for=scheduled_for,
            meta=meta,
        )
        logger.info(
            "Deferred AI MOP message while pipeline paused: queue_id=%d until=%s",
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

    async def _send_ai_mop_queued_email(
        self,
        *,
        item: AgentSalesDmQueue,
        meta: dict[str, Any],
        message_text: str,
    ) -> None:
        from ..ai_mop.dm_hooks import on_dm_queue_sent
        from ..ai_mop.email_outreach import send_ai_mop_outreach_email

        to_email = str(item.target_user_external_id or "").strip()
        subject = str(meta.get("email_subject") or "").strip()
        html_body = str(meta.get("email_html") or "").strip()
        if not to_email or not subject or not message_text:
            await get_dm_queue_service().mark_failed(
                queue_id=item.id,
                error="Missing email fields in AI MOP queue item",
                retry=False,
            )
            return

        account_key = (int(item.agent_id), "email", 0)
        timeout_seconds = self._resolve_account_timeout_seconds(meta)
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
                    "Deferred AI MOP email by cooldown: queue_id=%d until=%s",
                    item.id,
                    next_allowed_at.isoformat(),
                )
                return

        await send_ai_mop_outreach_email(
            to_email=to_email,
            subject=subject,
            text=message_text,
            html_body=html_body,
        )
        logger.info(
            "Sent AI MOP email: queue_id=%d agent_id=%d to=%s",
            item.id,
            item.agent_id,
            to_email,
        )
        await get_dm_queue_service().mark_sent(queue_id=item.id)
        self._last_send_by_account[account_key] = self._now_utc_naive()
        await on_dm_queue_sent(item)

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
        if await self._defer_if_ai_mop_pipeline_paused(item=item, meta=meta):
            return
        if await self._defer_if_outside_ai_mop_send_window(item=item, meta=meta):
            return
        channel = str(meta.get("channel") or "telegram_userbot").strip().lower()
        message_text = (item.message_text or "").strip()
        imported_id = meta.get("imported_contact_id")
        follow_up_tier = str(meta.get("follow_up_tier") or "").strip().lower()

        if channel == "email":
            await self._send_ai_mop_queued_email(item=item, meta=meta, message_text=message_text)
            return

        if meta.get("compose_at_send") or message_text == COMPOSE_AT_SEND_PLACEHOLDER:
            ai_mop_lead_id = meta.get("ai_mop_lead_id")
            if ai_mop_lead_id is not None and meta.get("source") == "ai_mop_follow_up":
                from ..ai_mop.followup_service import (
                    compose_ai_mop_follow_up_message,
                    should_send_ai_mop_follow_up,
                )

                if not await should_send_ai_mop_follow_up(
                    agent_id=item.agent_id,
                    lead_id=int(ai_mop_lead_id),
                ):
                    await get_dm_queue_service().mark_skipped(
                        queue_id=item.id,
                        reason="client_replied_or_not_eligible",
                    )
                    return
                async with async_session_maker() as session:
                    async with session.begin():
                        agent = await session.scalar(select(Agent).where(Agent.id == item.agent_id))
                        lead = await session.scalar(
                            select(AiMopLead).where(AiMopLead.id == int(ai_mop_lead_id))
                        )
                if agent is None or lead is None:
                    await get_dm_queue_service().mark_failed(
                        queue_id=item.id,
                        error="Agent or AI MOP lead not found",
                        retry=False,
                    )
                    return
                message_text = (
                    await compose_ai_mop_follow_up_message(
                        agent=agent,
                        lead=lead,
                        tier=follow_up_tier or "day",
                    )
                ).strip()
            elif imported_id is not None:
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
            else:
                await get_dm_queue_service().mark_skipped(
                    queue_id=item.id,
                    reason="follow_up_missing_contact_reference",
                )
                return
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
        original_target_external = target_external
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

                provider = _provider_for_channel(channel)
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
            try:
                used_target = await self._send_dm_with_target_fallbacks(
                    channel=channel,
                    primary_target=target_external,
                    meta=meta,
                    message_text=message_text,
                    connection_id=int(connection_id or 0),
                    encrypted_credentials=encrypted_credentials or "",
                    peer_access_hash=peer_access_hash,
                )
            except Exception:
                cross = await self._try_cross_channel_fallbacks(
                    item=item,
                    meta=meta,
                    message_text=message_text,
                    peer_access_hash=peer_access_hash,
                )
                if cross is None:
                    raise
                channel, used_target, connection_id = cross
                target_external = used_target
                meta["channel"] = channel
                account_key = (int(item.agent_id), channel, int(connection_id))
                async with async_session_maker() as session:
                    async with session.begin():
                        await session.execute(
                            update(AgentSalesDmQueue)
                            .where(AgentSalesDmQueue.id == item.id)
                            .values(
                                target_user_external_id=used_target,
                                metadata_json=json.dumps(meta, ensure_ascii=False),
                                updated_at=self._now_utc_naive(),
                            )
                        )
                item.target_user_external_id = used_target
                item.metadata_json = json.dumps(meta, ensure_ascii=False)
            else:
                if used_target != target_external:
                    target_external = used_target
                    async with async_session_maker() as session:
                        async with session.begin():
                            await session.execute(
                                update(AgentSalesDmQueue)
                                .where(AgentSalesDmQueue.id == item.id)
                                .values(
                                    target_user_external_id=used_target,
                                    updated_at=self._now_utc_naive(),
                                )
                            )
                    meta["channel"] = channel

            logger.info(
                "Sent DM: queue_id=%d agent_id=%d channel=%s user_id=%s",
                item.id,
                item.agent_id,
                channel,
                target_external,
            )
            if (
                channel == "max_userbot"
                and original_target_external.startswith("+")
                and target_external != original_target_external
            ):
                await _rekey_max_excel_contact(
                    agent_id=int(item.agent_id),
                    old_external_id=original_target_external,
                    chat_external_id=target_external,
                    imported_contact_id=(
                        int(meta["imported_contact_id"])
                        if meta.get("imported_contact_id") is not None
                        else None
                    ),
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

            ai_mop_lead_id = meta.get("ai_mop_lead_id")
            if (
                ai_mop_lead_id is not None
                and meta.get("message_kind") == "follow_up"
                and follow_up_tier
            ):
                try:
                    from ..ai_mop.followup_service import mark_ai_mop_follow_up_sent

                    await mark_ai_mop_follow_up_sent(
                        lead_id=int(ai_mop_lead_id),
                        tier=follow_up_tier,
                    )
                except Exception:
                    logger.warning(
                        "Failed to mark AI MOP follow-up sent lead_id=%s",
                        ai_mop_lead_id,
                        exc_info=True,
                    )

        except Exception as exc:
            error_msg = str(exc)[:500]
            low = error_msg.casefold()
            non_retry_markers = (
                "could not find the input entity",
                "не удалось отправить dm",
                "invalid target_user_external_id",
                "некорректный номер",
                "пустой идентификатор",
                "peeridinvalid",
                "username not occupied",
                "you can't write in this chat",
                "chat_write_forbidden",
                "user is deactivated",
            )
            if channel == "whatsapp_userbot":
                non_retry_markers += (
                    "not on whatsapp",
                    "not registered on whatsapp",
                )
            if channel == "max_userbot":
                non_retry_markers += (
                    "некорректный chat_id",
                    "не удалось отправить сообщение в max",
                    "пользователь max не найден",
                    "не удалось найти пользователя max",
                )
            should_retry = "auth" not in low and not any(marker in low for marker in non_retry_markers)

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
