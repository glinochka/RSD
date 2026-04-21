"""WhatsApp userbot manager backed by wa_bridge runtime sessions."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from fastapi import status

from core.backendAPI import APIcreate, APIread, get_response_status
from core.config import settings
from core.crypto import decrypt_token
from services.ai_service import get_answer

logger = logging.getLogger(__name__)


def _bridge_headers() -> dict[str, str]:
    api_key = (settings.WHATSAPP_USERBOT_BRIDGE_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("WHATSAPP_USERBOT_BRIDGE_API_KEY is not configured")
    return {"X-API-Key": api_key}


def _bridge_base_url() -> str:
    base = (settings.WHATSAPP_USERBOT_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("WHATSAPP_USERBOT_BRIDGE_URL is not configured")
    return base


async def _bridge_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_bridge_base_url()}/{path.lstrip('/')}"
    timeout = httpx.Timeout(
        float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS),
        connect=min(20.0, float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS)),
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=_bridge_headers())
    if not response.is_success:
        raise RuntimeError(f"wa_bridge {path} failed: HTTP {response.status_code} {response.text[:300]}")
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"wa_bridge {path} returned unexpected payload")
    return data


async def _fetch_whatsapp_configs() -> list[dict[str, Any]]:
    url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/agents/internal/whatsapp_userbot_clients"
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY}
    timeout = httpx.Timeout(60.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        if not response.is_success:
            logger.warning(
                "whatsapp_userbot_clients: HTTP %s %s",
                response.status_code,
                response.text[:500],
            )
            return []
        data = response.json()
        return data if isinstance(data, list) else []


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


def _external_user_id_from_jid(remote_jid: str) -> str:
    jid = str(remote_jid or "").strip()
    if "@" in jid:
        return jid.split("@", 1)[0]
    return jid


async def _process_incoming(
    cfg: dict[str, Any],
    incoming: dict[str, Any],
) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return
    if str(incoming.get("from_me") or "").lower() == "true":
        return

    text = _extract_text(incoming)
    if not text:
        return

    bot_id = int(cfg["bot_id"])
    system_prompt = cfg.get("system_prompt") or ""
    welcome = cfg.get("welcome_message")
    push_name = str(incoming.get("push_name") or "").strip() or None
    user_external_id = _external_user_id_from_jid(remote_jid)
    user_display_name = push_name or user_external_id

    frozen_check = await APIread.agentFrozenCheck(bot_id, user_external_id)
    if get_response_status(frozen_check) == status.HTTP_200_OK and frozen_check.get("frozen"):
        await _bridge_post(
            "session/send",
            {
                "connection_id": cfg["connection_id"],
                "to_jid": remote_jid,
                "text": (
                    "Доступ к этому агенту для вас временно ограничен владельцем. "
                    "Если это ошибка, обратитесь в поддержку."
                ),
            },
        )
        return

    if text == "/start":
        await _bridge_post(
            "session/send",
            {
                "connection_id": cfg["connection_id"],
                "to_jid": remote_jid,
                "text": welcome or "Здравствуйте! Чем я могу вам помочь?",
            },
        )
        return

    try:
        await APIcreate.logAgentAnalyticsMessage(
            bot_id=bot_id,
            role="user",
            message_text=text,
            user_external_id=user_external_id,
            user_display_name=user_display_name,
            channel="whatsapp_userbot",
        )
    except Exception:
        pass

    context = await APIread.contextBy_botID(bot_id, text)
    get_response_status(context)
    if isinstance(context, dict) and context.get("error_code"):
        context_list: list = []
    else:
        context_list = context if isinstance(context, list) else []

    answer = await get_answer(text, context_list, system_prompt)
    await _bridge_post(
        "session/send",
        {
            "connection_id": cfg["connection_id"],
            "to_jid": remote_jid,
            "text": answer,
        },
    )
    try:
        await APIcreate.logAgentAnalyticsMessage(
            bot_id=bot_id,
            role="agent",
            message_text=answer,
            user_external_id=user_external_id,
            user_display_name=user_display_name,
            channel="whatsapp_userbot",
        )
    except Exception:
        pass


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
