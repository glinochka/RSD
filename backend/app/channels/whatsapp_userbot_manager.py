"""WhatsApp userbot manager backed by wa_bridge runtime sessions."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..utils.crypto import decrypt_token
from ..utils.wa_bridge_client import wa_bridge_post
from .message_processor import Channel, MessageRequest, get_message_processor

logger = logging.getLogger(__name__)


async def _bridge_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return await wa_bridge_post(path, payload)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


async def _fetch_whatsapp_configs() -> list[dict[str, Any]]:
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
                            AgentChannelConnection.id.label("connection_id"),
                            AgentChannelConnection.external_id.label("phone_number"),
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "whatsapp_userbot",
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
            "connection_id": int(row["connection_id"]),
            "phone_number": row["phone_number"] or "",
            "system_prompt": row["system_prompt"] or "",
            "welcome_message": row["welcome_message"],
            "encrypted_credentials": row["encrypted_credentials"],
        }
        for row in rows
    ]


def _extract_text(message: dict[str, Any]) -> str:
    msg = message.get("message") or {}
    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")
        or (msg.get("videoMessage") or {}).get("caption")
        or ""
    )
    return str(text).strip()


def _user_external_id_for_whatsapp_analytics(jid: str) -> str:
    """JID для аналитики: предпочтительно тот же, что уходит в session/send (полная строка, ≤128)."""
    out = str(jid or "").strip()
    if len(out) > 128:
        return out[:128]
    return out


async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    remote_jid_alt = str(incoming.get("remote_jid_alt") or "").strip()
    if not remote_jid and not remote_jid_alt:
        return

    if str(incoming.get("from_me") or "").lower() == "true":
        return

    text = _extract_text(incoming)
    if not text:
        return

    # PN в remoteJidAlt при входящем @lid — иначе ответ уходит не в тот «тред» в клиенте WhatsApp.
    canonical_jid = (remote_jid_alt or remote_jid).strip()
    if not canonical_jid:
        return

    bot_id = int(cfg["bot_id"])
    request = MessageRequest(
        bot_id=bot_id,
        query=text,
        user_external_id=_user_external_id_for_whatsapp_analytics(canonical_jid),
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
    )
    response = await get_message_processor().process(request)

    await _bridge_post(
        "session/send",
        {
            "connection_id": cfg["connection_id"],
            "to_jid": canonical_jid,
            "text": response.text,
        },
    )


async def _run_one_client(cfg: dict[str, Any], stop: asyncio.Event) -> None:
    encrypted_bundle = cfg.get("encrypted_credentials")
    if not encrypted_bundle:
        logger.warning("whatsapp_userbot: missing encrypted_credentials for connection_id=%s", cfg["connection_id"])
        return
    bundle = json.loads(decrypt_token(encrypted_bundle))
    session_string = str(bundle.get("session_string") or "").strip()
    if not session_string:
        logger.warning("whatsapp_userbot: empty session_string for connection_id=%s", cfg["connection_id"])
        return

    connection_id = int(cfg["connection_id"])
    await _bridge_post(
        "session/connect",
        {
            "connection_id": connection_id,
            "session_string": session_string,
        },
    )
    logger.info("whatsapp_userbot: connected connection_id=%s bot_id=%s", connection_id, cfg.get("bot_id"))

    poll_interval = max(1, int(settings.WHATSAPP_USERBOT_POLL_INTERVAL_SECONDS))
    while not stop.is_set():
        payload = await _bridge_post(
            "session/pull",
            {
                "connection_id": connection_id,
                "limit": 20,
            },
        )
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if isinstance(messages, list):
            for item in messages:
                if not isinstance(item, dict):
                    continue
                try:
                    await _process_incoming(cfg, item)
                except Exception:
                    logger.exception(
                        "whatsapp_userbot: failed processing message connection_id=%s",
                        connection_id,
                    )
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            continue


class WhatsAppUserbotManager:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}

    async def shutdown(self) -> None:
        self._stop.set()
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def run_forever(self) -> None:
        interval = max(10, int(settings.USERBOT_POLL_INTERVAL_SECONDS))
        logger.info("WhatsAppUserbotManager polling every %s sec", interval)
        while not self._stop.is_set():
            try:
                configs = await _fetch_whatsapp_configs()
                wanted = {int(c["connection_id"]) for c in configs if c.get("connection_id") is not None}

                for connection_id in list(self._tasks):
                    if connection_id not in wanted:
                        task = self._tasks.pop(connection_id)
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        logger.info("whatsapp_userbot: removed connection_id=%s", connection_id)

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
                                "whatsapp_userbot: previous worker crashed connection_id=%s",
                                connection_id,
                            )
                        existing = None
                    if existing is None:
                        self._tasks[connection_id] = asyncio.create_task(_run_one_client(cfg, self._stop))
                        logger.info("whatsapp_userbot: started worker connection_id=%s", connection_id)
            except Exception:
                logger.exception("WhatsAppUserbotManager cycle failed")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
