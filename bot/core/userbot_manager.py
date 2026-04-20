"""Telethon userbot clients manager for active agents."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from fastapi import status
from telethon import TelegramClient, connection, events
from telethon.sessions import StringSession

from core.backendAPI import APIcreate, APIread, get_response_status
from core.config import settings
from core.crypto import decrypt_token
from services.ai_service import get_answer

logger = logging.getLogger(__name__)


def _make_client(session_string: str, api_id: int, api_hash: str) -> TelegramClient:
    if settings.TELEGRAM_MTPROXY_HOST:
        proxy = (
            settings.TELEGRAM_MTPROXY_HOST,
            int(settings.TELEGRAM_MTPROXY_PORT),
            settings.TELEGRAM_MTPROXY_SECRET,
        )
        return TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash,
            connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy,
        )
    return TelegramClient(StringSession(session_string), api_id, api_hash)


async def _fetch_userbot_configs() -> list[dict[str, Any]]:
    url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/agents/internal/userbot_clients"
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY}
    timeout = httpx.Timeout(60.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        if not response.is_success:
            logger.warning(
                "userbot_clients: HTTP %s %s",
                response.status_code,
                response.text[:500],
            )
            return []
        data = response.json()
        return data if isinstance(data, list) else []


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
    user_display_name = (
        (getattr(sender, "first_name", "") or "").strip()
        + " "
        + (getattr(sender, "last_name", "") or "").strip()
    ).strip() or getattr(sender, "username", None)

    frozen_check = await APIread.agentFrozenCheck(bot_id, user_external_id)
    if get_response_status(frozen_check) == status.HTTP_200_OK and frozen_check.get("frozen"):
        await event.respond(
            "Доступ к этому агенту для вас временно ограничен владельцем. "
            "Если это ошибка, обратитесь в поддержку."
        )
        return

    if query == "/start":
        text = welcome_message or "Здравствуйте! Чем я могу вам помочь?"
        await event.respond(text)
        return

    try:
        await APIcreate.logAgentAnalyticsMessage(
            bot_id=bot_id,
            role="user",
            message_text=query,
            user_external_id=user_external_id,
            user_display_name=user_display_name,
            channel="telegram_userbot",
        )
    except Exception:
        pass

    context = await APIread.contextBy_botID(bot_id, query)
    get_response_status(context)
    if isinstance(context, dict) and context.get("error_code"):
        context_list: list = []
    else:
        context_list = context if isinstance(context, list) else []

    answer = await get_answer(query, context_list, system_prompt)
    try:
        await APIcreate.logAgentAnalyticsMessage(
            bot_id=bot_id,
            role="agent",
            message_text=answer,
            user_external_id=user_external_id,
            user_display_name=user_display_name,
            channel="telegram_userbot",
        )
    except Exception:
        pass
    await event.respond(answer)


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

    async def shutdown(self) -> None:
        self._stop.set()
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def run_forever(self) -> None:
        interval = max(10, int(settings.USERBOT_POLL_INTERVAL_SECONDS))
        logger.info("UserbotManager polling every %s sec", interval)
        while not self._stop.is_set():
            try:
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
