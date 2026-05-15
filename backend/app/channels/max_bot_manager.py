"""Official MAX bot manager based on platform-api.max.ru long polling."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..utils.crypto import decrypt_token
from .leader_lock import PgLeaderLock
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

logger = logging.getLogger(__name__)

MAX_API_BASE = "https://platform-api.max.ru"


def _build_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": access_token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def _max_api_get(
    *,
    access_token: str,
    path: str,
    params: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    timeout = httpx.Timeout(timeout_seconds or 30.0, connect=15.0)
    async with httpx.AsyncClient(base_url=MAX_API_BASE, timeout=timeout) as client:
        response = await client.get(path, params=params, headers=_build_headers(access_token))
    if not response.is_success:
        raise RuntimeError(f"MAX API GET {path} failed: HTTP {response.status_code} {response.text[:300]}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"MAX API GET {path} returned non-object payload")
    return payload


async def _max_api_post(
    *,
    access_token: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timeout = httpx.Timeout(30.0, connect=15.0)
    async with httpx.AsyncClient(base_url=MAX_API_BASE, timeout=timeout) as client:
        response = await client.post(
            path,
            params=params,
            json=body or {},
            headers=_build_headers(access_token),
        )
    if not response.is_success:
        raise RuntimeError(f"MAX API POST {path} failed: HTTP {response.status_code} {response.text[:300]}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"MAX API POST {path} returned non-object payload")
    return payload


async def _fetch_max_bot_configs() -> list[dict[str, Any]]:
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
                            AgentChannelConnection.external_id.label("max_bot_id"),
                            AgentChannelConnection.encrypted_credentials,
                        )
                        .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
                        .where(
                            Agent.is_active.is_(True),
                            AgentChannelConnection.provider == "max_bot",
                            AgentChannelConnection.connection_type == "bot",
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
            "max_bot_id": str(row["max_bot_id"] or "").strip(),
            "system_prompt": row["system_prompt"] or "",
            "welcome_message": row["welcome_message"],
            "encrypted_credentials": row["encrypted_credentials"],
        }
        for row in rows
    ]


def _extract_message_text(update: dict[str, Any]) -> str:
    message = update.get("message")
    if isinstance(message, dict):
        body = message.get("body")
        if isinstance(body, dict):
            text = str(body.get("text") or "").strip()
            if text:
                return text
        legacy_text = str(message.get("text") or "").strip()
        if legacy_text:
            return legacy_text
    legacy_payload = str(update.get("payload") or "").strip()
    if legacy_payload:
        return legacy_payload
    return ""


def _extract_chat_id(update: dict[str, Any]) -> str:
    message = update.get("message")
    if isinstance(message, dict):
        recipient = message.get("recipient")
        if isinstance(recipient, dict):
            for key in ("chat_id", "chatId"):
                value = recipient.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
        for key in ("chat_id", "chatId"):
            value = message.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    for key in ("chat_id", "chatId"):
        value = update.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _extract_sender_info(update: dict[str, Any]) -> tuple[str, str | None]:
    message = update.get("message")
    if isinstance(message, dict):
        sender = message.get("sender")
        if isinstance(sender, dict):
            user_id = sender.get("user_id")
            if user_id is not None and str(user_id).strip():
                first_name = str(sender.get("first_name") or "").strip()
                last_name = str(sender.get("last_name") or "").strip()
                username = str(sender.get("username") or "").strip()
                display_name = " ".join(part for part in [first_name, last_name] if part).strip() or username or None
                return str(user_id).strip(), display_name
    user = update.get("user")
    if isinstance(user, dict):
        user_id = user.get("user_id")
        if user_id is not None and str(user_id).strip():
            first_name = str(user.get("first_name") or "").strip()
            last_name = str(user.get("last_name") or "").strip()
            username = str(user.get("username") or "").strip()
            display_name = " ".join(part for part in [first_name, last_name] if part).strip() or username or None
            return str(user_id).strip(), display_name
    legacy_user_id = update.get("user_id")
    if legacy_user_id is not None and str(legacy_user_id).strip():
        return str(legacy_user_id).strip(), None
    return "", None


def _is_bot_sender(update: dict[str, Any]) -> bool:
    message = update.get("message")
    if not isinstance(message, dict):
        return False
    sender = message.get("sender")
    if not isinstance(sender, dict):
        return False
    return bool(sender.get("is_bot"))


async def _send_max_message(*, access_token: str, chat_id: str, text: str) -> None:
    await _max_api_post(
        access_token=access_token,
        path="/messages",
        params={"chat_id": chat_id},
        body={"text": text},
    )


async def _process_update(cfg: dict[str, Any], access_token: str, update: dict[str, Any]) -> None:
    update_type = str(update.get("update_type") or "").strip().lower()
    if update_type not in {"message_created", "bot_started"}:
        return
    if _is_bot_sender(update):
        return

    chat_id = _extract_chat_id(update)
    if not chat_id:
        return
    user_external_id, user_display_name = _extract_sender_info(update)
    if not user_external_id:
        return

    text = _extract_message_text(update)
    if update_type == "bot_started" and not text:
        text = "/start"
    if not text:
        return

    request = MessageRequest(
        bot_id=int(cfg["bot_id"]),
        query=text,
        user_external_id=user_external_id,
        channel=Channel.MAX_BOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=user_display_name,
    )
    response = await get_message_processor().process(request)
    if response.status == ProcessingStatus.DISCARDED or not response.text.strip():
        return
    await _send_max_message(access_token=access_token, chat_id=chat_id, text=response.text)


async def _run_one_client(cfg: dict[str, Any], stop: asyncio.Event) -> None:
    encrypted_bundle = cfg.get("encrypted_credentials")
    if not encrypted_bundle:
        logger.warning("max_bot: missing encrypted credentials connection_id=%s", cfg.get("connection_id"))
        return
    bundle = json.loads(decrypt_token(str(encrypted_bundle)))
    access_token = str(bundle.get("max_bot_token") or "").strip()
    if not access_token:
        logger.warning("max_bot: empty token connection_id=%s", cfg.get("connection_id"))
        return

    connection_id = int(cfg["connection_id"])
    reconnect_delay = max(2, int(settings.MAX_BOT_RECONNECT_DELAY_SECONDS))
    updates_timeout = max(1, min(90, int(settings.MAX_BOT_UPDATES_TIMEOUT_SECONDS)))
    marker: int | None = None

    while not stop.is_set():
        try:
            params: dict[str, Any] = {
                "limit": 100,
                "timeout": updates_timeout,
            }
            if marker is not None:
                params["marker"] = marker
            payload = await _max_api_get(
                access_token=access_token,
                path="/updates",
                params=params,
                timeout_seconds=float(updates_timeout + 15),
            )
            marker_value = payload.get("marker")
            if marker_value is not None:
                try:
                    marker = int(marker_value)
                except (TypeError, ValueError):
                    pass
            updates = payload.get("updates")
            if isinstance(updates, list):
                for item in updates:
                    if not isinstance(item, dict):
                        continue
                    try:
                        await _process_update(cfg, access_token, item)
                    except Exception:
                        logger.exception("max_bot: failed processing update connection_id=%s", connection_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("max_bot: worker failed connection_id=%s", connection_id)
            if stop.is_set():
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=reconnect_delay)
            except asyncio.TimeoutError:
                pass


class MaxBotManager:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._leader_lock = PgLeaderLock(20_004, "max_bot_manager")

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
        interval = max(10, int(settings.MAX_BOT_POLL_INTERVAL_SECONDS))
        logger.info("MaxBotManager polling every %s sec", interval)
        try:
            while not self._stop.is_set():
                try:
                    is_leader = await self._leader_lock.ensure_acquired()
                    if not is_leader:
                        if self._tasks:
                            await self._cancel_all_tasks()
                        logger.info("max_bot: another replica holds leader lock, waiting")
                    else:
                        configs = await _fetch_max_bot_configs()
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
                                logger.info("max_bot: removed connection_id=%s", connection_id)

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
                                        "max_bot: previous worker crashed connection_id=%s",
                                        connection_id,
                                    )
                                existing = None
                            if existing is None:
                                self._tasks[connection_id] = asyncio.create_task(_run_one_client(cfg, self._stop))
                                logger.info("max_bot: started worker connection_id=%s", connection_id)
                except Exception:
                    logger.exception("MaxBotManager cycle failed")

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            await self._cancel_all_tasks()
            await self._leader_lock.release()
