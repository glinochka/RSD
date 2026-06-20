"""MAX userbot manager based on PyMax (maxapi-python)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import shutil
import tempfile
from typing import Any

from pymax import Message
from pymax.types.domain.enums import ChatType
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..services.human_delay import (
    get_online_delay,
    get_read_delay,
    get_typing_delay,
    is_human_delay_enabled,
    mark_activity,
)
from ..services.max_userbot_session import (
    build_runtime_client,
    bundle_from_credentials,
    profile_display_name,
    write_session_store,
)
from ..utils.crypto import decrypt_token
from .leader_lock import PgLeaderLock
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

logger = logging.getLogger(__name__)


async def _fetch_max_configs() -> list[dict[str, Any]]:
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
                            Agent.template_config,
                            AgentChannelConnection.id.label("connection_id"),
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "max_userbot",
                            AgentChannelConnection.connection_type == "userbot",
                            AgentChannelConnection.is_active.is_(True),
                            AgentChannelConnection.encrypted_credentials.is_not(None),
                        )
                    )
                )
                .mappings()
                .all()
            )
    configs: list[dict[str, Any]] = []
    for row in rows:
        template_config: dict[str, Any] = {}
        raw_cfg = row.get("template_config")
        if raw_cfg:
            try:
                loaded = json.loads(raw_cfg) if isinstance(raw_cfg, str) else raw_cfg
                if isinstance(loaded, dict):
                    template_config = loaded
            except Exception:
                template_config = {}
        configs.append(
            {
                "agent_id": int(row["agent_id"]),
                "bot_id": int(row["bot_id"] if row["bot_id"] is not None else row["agent_id"]),
                "connection_id": int(row["connection_id"]),
                "system_prompt": row["system_prompt"] or "",
                "welcome_message": row["welcome_message"],
                "template_config": template_config,
                "encrypted_credentials": row["encrypted_credentials"],
            }
        )
    return configs


def _resolve_sender_name(message: Message, client) -> str | None:
    sender_id = message.sender
    if sender_id is None:
        return None
    users = getattr(client, "users", None) or {}
    user = users.get(sender_id)
    if user is not None:
        names = getattr(user, "names", None) or []
        if names:
            first = str(getattr(names[0], "first_name", "") or "").strip()
            last = str(getattr(names[0], "last_name", "") or "").strip()
            display = f"{first} {last}".strip()
            if display:
                return display
    contacts = getattr(client, "contacts", None) or []
    for contact in contacts:
        if contact is None:
            continue
        if getattr(contact, "id", None) == sender_id:
            names = getattr(contact, "names", None) or []
            if names:
                first = str(getattr(names[0], "first_name", "") or "").strip()
                last = str(getattr(names[0], "last_name", "") or "").strip()
                display = f"{first} {last}".strip()
                if display:
                    return display
    return None


def _is_private_dialog(message: Message, client) -> bool:
    chat_id = message.chat_id
    if chat_id is None:
        return False
    chats = getattr(client, "chats", None) or []
    for chat in chats:
        if getattr(chat, "id", None) == chat_id:
            chat_type = getattr(chat, "type", None)
            if chat_type == ChatType.DIALOG:
                return True
            if isinstance(chat_type, str) and chat_type.upper() == "DIALOG":
                return True
            return bool(getattr(chat, "is_dialog", False))
    # If chat list is incomplete, allow processing (PyMax may lazy-load chats).
    return True


async def _handle_message(message: Message, client, cfg: dict[str, Any]) -> None:
    text = str(message.text or "").strip()
    if not text:
        return
    if not _is_private_dialog(message, client):
        return

    my_id = None
    if client.me and client.me.contact is not None:
        my_id = client.me.contact.id
    if my_id is not None and message.sender == my_id:
        return

    chat_id = message.chat_id
    if chat_id is None:
        return

    sender_name = _resolve_sender_name(message, client)
    bot_id = int(cfg["bot_id"])
    agent_id = int(cfg.get("agent_id") or bot_id)
    template_config: dict[str, Any] = cfg.get("template_config") or {}
    human_delay = is_human_delay_enabled(template_config, Channel.MAX_USERBOT.value)
    chat_key = str(chat_id)

    if human_delay:
        online_wait = await get_online_delay(agent_id, chat_key, Channel.MAX_USERBOT.value)
        if online_wait > 0:
            await asyncio.sleep(online_wait)
    if human_delay:
        await asyncio.sleep(get_read_delay(len(text)))

    request = MessageRequest(
        bot_id=bot_id,
        query=text,
        user_external_id=chat_key,
        channel=Channel.MAX_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=sender_name,
    )
    response = await get_message_processor().process(request)

    if human_delay and response.delivers_reply():
        await asyncio.sleep(get_typing_delay(len(response.text or "")))

    if not response.delivers_reply():
        return
    if human_delay:
        mark_activity(agent_id, chat_key, Channel.MAX_USERBOT.value)
    await message.answer(response.text)


async def _run_one_client(cfg: dict[str, Any], stop: asyncio.Event) -> None:
    encrypted_bundle = cfg.get("encrypted_credentials")
    if not encrypted_bundle:
        logger.warning("max_userbot: missing encrypted credentials connection_id=%s", cfg.get("connection_id"))
        return

    connection_id = int(cfg["connection_id"])
    reconnect_delay = max(2, int(settings.MAX_USERBOT_RECONNECT_DELAY_SECONDS))
    work_dir = tempfile.mkdtemp(prefix=f"rsd_max_conn_{connection_id}_")

    while not stop.is_set():
        client = None
        client_task: asyncio.Task[None] | None = None
        try:
            bundle = bundle_from_credentials(str(encrypted_bundle))
            await write_session_store(work_dir, bundle)
            client = build_runtime_client(work_dir, bundle)
            ready = asyncio.Event()
            startup_error: dict[str, Exception] = {}

            @client.on_start()
            async def on_start(active_client) -> None:
                me = active_client.me
                if me is not None:
                    logger.info(
                        "max_userbot: connected connection_id=%s bot_id=%s account=%s",
                        connection_id,
                        cfg.get("bot_id"),
                        profile_display_name(me) or getattr(me.contact, "id", "?"),
                    )
                ready.set()

            @client.on_message()
            async def on_message(message: Message, active_client) -> None:
                try:
                    await _handle_message(message, active_client, cfg)
                except Exception:
                    logger.exception("max_userbot: failed to process message connection_id=%s", connection_id)

            client_task = asyncio.create_task(client.start())
            try:
                await asyncio.wait_for(ready.wait(), timeout=120)
            except asyncio.TimeoutError as exc:
                startup_error["error"] = exc
                raise RuntimeError("MAX userbot startup timeout") from exc

            stop_task = asyncio.create_task(stop.wait())
            done, _pending = await asyncio.wait(
                {client_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done:
                stop_task.result()
            elif client_task in done:
                client_task.result()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("max_userbot: worker failed connection_id=%s", connection_id)
            if stop.is_set():
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=reconnect_delay)
            except asyncio.TimeoutError:
                pass
        finally:
            if client is not None:
                with contextlib.suppress(Exception):
                    await client.close()
            if client_task is not None:
                client_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await client_task

    shutil.rmtree(work_dir, ignore_errors=True)


class MaxUserbotManager:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._leader_lock = PgLeaderLock(20_003, "max_userbot_manager")

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
        interval = max(10, int(settings.MAX_USERBOT_POLL_INTERVAL_SECONDS))
        logger.info("MaxUserbotManager polling every %s sec", interval)
        try:
            while not self._stop.is_set():
                try:
                    is_leader = await self._leader_lock.ensure_acquired()
                    if not is_leader:
                        if self._tasks:
                            await self._cancel_all_tasks()
                        logger.info("max_userbot: another replica holds leader lock, waiting")
                    else:
                        configs = await _fetch_max_configs()
                        wanted = {
                            int(c["connection_id"])
                            for c in configs
                            if c.get("connection_id") is not None
                        }

                        for connection_id in list(self._tasks):
                            if connection_id not in wanted:
                                task = self._tasks.pop(connection_id)
                                task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await task
                                logger.info("max_userbot: removed connection_id=%s", connection_id)

                        by_id = {
                            int(c["connection_id"]): c
                            for c in configs
                            if c.get("connection_id") is not None
                        }
                        for connection_id, cfg in by_id.items():
                            existing = self._tasks.get(connection_id)
                            if existing and existing.done():
                                self._tasks.pop(connection_id, None)
                                with contextlib.suppress(Exception):
                                    existing.result()
                                existing = None
                            if existing is None:
                                self._tasks[connection_id] = asyncio.create_task(
                                    _run_one_client(cfg, self._stop)
                                )
                                logger.info("max_userbot: started worker connection_id=%s", connection_id)
                except Exception:
                    logger.exception("MaxUserbotManager cycle failed")

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            await self._cancel_all_tasks()
            await self._leader_lock.release()
