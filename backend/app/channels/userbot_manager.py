"""Telethon userbot clients manager for active agents."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..utils.crypto import decrypt_token
from .leader_lock import PgLeaderLock
from .message_processor import Channel, MessageRequest, get_message_processor

logger = logging.getLogger(__name__)


def _make_client(session_string: str, api_id: int, api_hash: str) -> TelegramClient:
    return TelegramClient(StringSession(session_string), api_id, api_hash)


async def _fetch_userbot_configs() -> list[dict[str, Any]]:
    """Fetch active userbot configurations including sales_manager template info."""
    async with async_session_maker() as session:
        async with session.begin():
            rows = (
                (
                    await session.execute(
                        select(
                            Agent.id.label("agent_id"),
                            Agent.bot_id,
                            Agent.system_prompt,
                            Agent.welcome_message,
                            Agent.template_type,
                            Agent.template_config,
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "telegram_userbot",
                            AgentChannelConnection.connection_type == "userbot",
                            AgentChannelConnection.is_active.is_(True),
                            AgentChannelConnection.encrypted_credentials.is_not(None),
                        )
                    )
                )
                .mappings()
                .all()
            )
    return [
        {
            "agent_id": int(row["agent_id"]),
            "bot_id": int(row["bot_id"] if row["bot_id"] is not None else row["agent_id"]),
            "system_prompt": row["system_prompt"] or "",
            "welcome_message": row["welcome_message"],
            "template_type": str(row["template_type"] or "qa").strip().lower(),
            "template_config": json.loads(row["template_config"]) if row["template_config"] else {},
            "encrypted_userbot_bundle": row["encrypted_credentials"],
        }
        for row in rows
    ]


async def _handle_private_message(
    event: events.NewMessage.Event,
    *,
    bot_id: int,
    system_prompt: str,
    welcome_message: str | None,
) -> None:
    if not event.is_private:
        return

    raw = event.message.message
    if raw is None or not str(raw).strip():
        await event.respond("Напишите, пожалуйста, текстовое сообщение.")
        return

    query = str(raw).strip()
    sender = await event.get_sender()
    user_external_id = str(getattr(sender, "id", None) or "")
    if not user_external_id:
        return

    peer_access_hash: int | None = None
    if isinstance(sender, User):
        ah = getattr(sender, "access_hash", None)
        if ah is not None:
            peer_access_hash = int(ah)

    user_display_name = (
        (getattr(sender, "first_name", "") or "").strip()
        + " "
        + (getattr(sender, "last_name", "") or "").strip()
    ).strip() or getattr(sender, "username", None)

    request = MessageRequest(
        bot_id=bot_id,
        query=query,
        user_external_id=user_external_id,
        channel=Channel.TELEGRAM_USERBOT,
        system_prompt=system_prompt,
        welcome_message=welcome_message,
        user_display_name=user_display_name,
        telegram_peer_access_hash=peer_access_hash,
    )
    response = await get_message_processor().process(request)
    await event.respond(response.text)


async def _run_one_client(cfg: dict[str, Any]) -> None:
    bundle = json.loads(decrypt_token(cfg["encrypted_userbot_bundle"]))
    api_id = int(bundle["api_id"])
    api_hash = str(bundle["api_hash"])
    session_str = str(bundle["session_string"])
    bot_id = int(cfg["bot_id"])
    system_prompt = cfg.get("system_prompt") or ""
    welcome = cfg.get("welcome_message")

    client = _make_client(session_str, api_id, api_hash)

    async def handler(event: events.NewMessage.Event) -> None:
        await _handle_private_message(
            event,
            bot_id=bot_id,
            system_prompt=system_prompt,
            welcome_message=welcome,
        )

    client.add_event_handler(handler, events.NewMessage(incoming=True))
    try:
        logger.info("userbot: connecting bot_id=%s", bot_id)
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("userbot: session unauthorized bot_id=%s", bot_id)
            return
        me = await client.get_me()
        logger.info(
            "userbot: online bot_id=%s telegram_user=%s",
            bot_id,
            getattr(me, "username", None) or me.id,
        )
        await client.run_until_disconnected()
    except asyncio.CancelledError:
        logger.info("userbot: stopping bot_id=%s", bot_id)
        raise
    except Exception:
        logger.exception("userbot: worker failed bot_id=%s", bot_id)
    finally:
        if client.is_connected():
            await client.disconnect()


class UserbotManager:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._leader_lock = PgLeaderLock(20_001, "telegram_userbot_manager")

    async def _cancel_all_tasks(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def shutdown(self) -> None:
        self._stop.set()
        await self._cancel_all_tasks()
        await self._leader_lock.release()

    async def run_forever(self) -> None:
        interval = max(10, int(settings.USERBOT_POLL_INTERVAL_SECONDS))
        logger.info("UserbotManager polling every %s sec", interval)
        try:
            while not self._stop.is_set():
                try:
                    is_leader = await self._leader_lock.ensure_acquired()
                    if not is_leader:
                        if self._tasks:
                            await self._cancel_all_tasks()
                        logger.info("userbot: another replica holds leader lock, waiting")
                    else:
                        configs = await _fetch_userbot_configs()
                        wanted = {int(c["bot_id"]) for c in configs if c.get("bot_id") is not None}

                        for bot_id in list(self._tasks):
                            if bot_id not in wanted:
                                task = self._tasks.pop(bot_id)
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass
                                logger.info("userbot: removed bot_id=%s", bot_id)

                        by_id = {int(c["bot_id"]): c for c in configs if c.get("bot_id") is not None}
                        for bot_id, cfg in by_id.items():
                            existing = self._tasks.get(bot_id)
                            if existing and existing.done():
                                self._tasks.pop(bot_id, None)
                                try:
                                    existing.result()
                                except Exception:
                                    logger.exception("userbot: previous worker crashed bot_id=%s", bot_id)
                                existing = None
                            if existing is None:
                                self._tasks[bot_id] = asyncio.create_task(_run_one_client(cfg))
                                logger.info("userbot: started worker bot_id=%s", bot_id)
                except Exception:
                    logger.exception("UserbotManager cycle failed")

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            await self._cancel_all_tasks()
            await self._leader_lock.release()
