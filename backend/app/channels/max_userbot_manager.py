"""MAX userbot manager based on web.max.ru websocket protocol."""
from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from typing import Any

from sqlalchemy import select
from websockets.sync.client import connect

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..utils.crypto import decrypt_token
from .leader_lock import PgLeaderLock
from ..services.human_delay import (
    get_online_delay,
    get_read_delay,
    get_typing_delay,
    mark_activity,
    is_human_delay_enabled,
)
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

logger = logging.getLogger(__name__)


class MaxWsClient:
    ws_url = "wss://ws-api.oneme.ru/websocket"

    def __init__(self, token: str) -> None:
        self.token = token
        self.websocket = None
        self.seq = 0
        self.me: dict[str, Any] = {}

    def connect(self) -> None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://web.max.ru",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Accept-Language": "ru,en;q=0.9",
        }
        self.websocket = connect(
            self.ws_url,
            additional_headers=headers,
            origin="https://web.max.ru",
            ping_interval=20,
            ping_timeout=20,
        )

    def auth(self) -> None:
        connect_message = {
            "ver": 11,
            "cmd": 0,
            "seq": self.seq,
            "opcode": 6,
            "payload": {
                "userAgent": {
                    "deviceType": "WEB",
                    "locale": "ru",
                    "deviceLocale": "ru",
                    "osVersion": "Windows",
                    "deviceName": "RSD Agent",
                    "headerUserAgent": "Mozilla/5.0",
                    "appVersion": "25.7.4",
                    "screen": "1080x1920 1.0x",
                    "timezone": "Europe/Moscow",
                },
                "deviceId": str(uuid.uuid4()),
            },
        }
        self.send(connect_message)
        _ = self.recv()

        session_message = {
            "ver": 11,
            "cmd": 0,
            "seq": self.seq,
            "opcode": 19,
            "payload": {
                "interactive": True,
                "token": self.token,
                "chatsSync": 0,
                "contactsSync": 0,
                "presenceSync": 0,
                "draftsSync": 0,
                "chatsCount": 40,
            },
        }
        self.send(session_message)
        response_raw = self.recv()
        if not response_raw:
            raise RuntimeError("MAX auth failed: empty session response")
        response = json.loads(response_raw)
        self.me = response.get("payload") or {}

    def send(self, payload: dict[str, Any]) -> None:
        if self.websocket is None:
            raise RuntimeError("MAX websocket is not connected")
        self.websocket.send(json.dumps(payload, ensure_ascii=False))
        self.seq += 1

    def recv(self) -> str | None:
        if self.websocket is None:
            return None
        try:
            return self.websocket.recv(timeout=5)
        except Exception:
            return None

    def heartbeat(self) -> None:
        self.send(
            {
                "ver": 11,
                "cmd": 0,
                "seq": self.seq,
                "opcode": 1,
                "payload": {"interactive": False},
            }
        )

    def send_message(self, chat_id: str, text: str) -> None:
        self.send(
            {
                "ver": 11,
                "cmd": 0,
                "seq": self.seq,
                "opcode": 64,
                "payload": {
                    "chatId": chat_id,
                    "message": {
                        "text": text,
                        "cid": random.randint(423232424, 3242533566365),
                        "elements": [],
                        "attaches": [],
                    },
                    "notify": True,
                },
            }
        )
        _ = self.recv()

    def get_user(self, contact_id: str | int) -> dict[str, Any]:
        self.send(
            {
                "ver": 11,
                "cmd": 0,
                "seq": self.seq,
                "opcode": 32,
                "payload": {"contactIds": [contact_id]},
            }
        )
        raw = self.recv()
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
            return decoded if isinstance(decoded, dict) else {}
        except Exception:
            return {}

    def close(self) -> None:
        if self.websocket is not None:
            try:
                self.websocket.close()
            except Exception:
                pass


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


def _extract_sender_name(user_payload: dict[str, Any]) -> str | None:
    contacts = (user_payload.get("payload") or {}).get("contacts") or []
    if not contacts:
        return None
    names = (contacts[0] or {}).get("names") or []
    if not names:
        return None
    first = str((names[0] or {}).get("firstName") or "").strip()
    last = str((names[0] or {}).get("lastName") or "").strip()
    display = f"{first} {last}".strip()
    return display or None


async def _process_event(client: MaxWsClient, cfg: dict[str, Any], raw_event: str) -> None:
    event = json.loads(raw_event)
    if not isinstance(event, dict):
        return
    if int(event.get("opcode") or 0) != 128:
        return
    payload = event.get("payload") or {}
    message = payload.get("message") or {}
    sender = str(message.get("sender") or "").strip()
    chat_id = str(payload.get("chatId") or "").strip()
    if not sender or not chat_id:
        return
    chat_type = str(payload.get("chatType") or "").strip().lower()
    if chat_type and chat_type not in {"private", "direct", "dialog"}:
        return
    my_id = str((((client.me or {}).get("profile") or {}).get("contact") or {}).get("id") or "").strip()
    if my_id and sender == my_id:
        return
    status = str(message.get("status") or "").strip().upper()
    if status == "REMOVED":
        return
    text = str(message.get("text") or "").strip()
    if not text:
        return

    sender_profile = await asyncio.to_thread(client.get_user, sender)
    sender_name = _extract_sender_name(sender_profile)

    bot_id = int(cfg["bot_id"])
    agent_id = int(cfg.get("agent_id") or bot_id)
    template_config: dict[str, Any] = cfg.get("template_config") or {}
    human_delay = is_human_delay_enabled(template_config, Channel.MAX_USERBOT.value)

    # Phase 1: "come online" delay — skip for first-ever message in this conversation.
    if human_delay:
        online_wait = await get_online_delay(agent_id, chat_id, Channel.MAX_USERBOT.value)
        if online_wait > 0:
            await asyncio.sleep(online_wait)

    # Phase 2: reading pause proportional to incoming message length.
    if human_delay:
        await asyncio.sleep(get_read_delay(len(text)))

    request = MessageRequest(
        bot_id=bot_id,
        query=text,
        user_external_id=chat_id,
        channel=Channel.MAX_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=sender_name,
    )
    response = await get_message_processor().process(request)

    # Phase 3: extra typing delay proportional to response length.
    if human_delay and response.delivers_reply():
        await asyncio.sleep(get_typing_delay(len(response.text or "")))

    if not response.delivers_reply():
        return
    if human_delay:
        mark_activity(agent_id, chat_id, Channel.MAX_USERBOT.value)
    await asyncio.to_thread(client.send_message, chat_id, response.text)


async def _run_one_client(cfg: dict[str, Any], stop: asyncio.Event) -> None:
    encrypted_bundle = cfg.get("encrypted_credentials")
    if not encrypted_bundle:
        logger.warning("max_userbot: missing encrypted credentials connection_id=%s", cfg.get("connection_id"))
        return
    bundle = json.loads(decrypt_token(str(encrypted_bundle)))
    max_token = str(bundle.get("max_token") or "").strip()
    if not max_token:
        logger.warning("max_userbot: empty token connection_id=%s", cfg.get("connection_id"))
        return

    connection_id = int(cfg["connection_id"])
    reconnect_delay = max(2, int(settings.MAX_USERBOT_RECONNECT_DELAY_SECONDS))
    while not stop.is_set():
        client = MaxWsClient(max_token)
        try:
            await asyncio.to_thread(client.connect)
            await asyncio.to_thread(client.auth)
            logger.info(
                "max_userbot: connected connection_id=%s bot_id=%s",
                connection_id,
                cfg.get("bot_id"),
            )
            while not stop.is_set():
                raw = await asyncio.to_thread(client.recv)
                if raw:
                    await _process_event(client, cfg, raw)
                else:
                    await asyncio.to_thread(client.heartbeat)
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
            await asyncio.to_thread(client.close)


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
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass
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
                                try:
                                    existing.result()
                                except Exception:
                                    logger.exception(
                                        "max_userbot: previous worker crashed connection_id=%s",
                                        connection_id,
                                    )
                                existing = None
                            if existing is None:
                                self._tasks[connection_id] = asyncio.create_task(_run_one_client(cfg, self._stop))
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
