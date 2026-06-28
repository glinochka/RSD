"""MAX userbot manager based on PyMax (maxapi-python)."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import tempfile
from typing import Any

from pymax import Message
from pymax.types.domain.enums import ChatType

from ..config import settings
from ..router_agents.dao import AgentChannelConnectionDAO
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
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor
from .polling_manager import PollingChannelManager

logger = logging.getLogger(__name__)


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
    template_type = str(cfg.get("template_type") or "qa").strip().lower()
    template_config: dict[str, Any] = cfg.get("template_config") or {}
    human_delay = is_human_delay_enabled(template_config, Channel.MAX_USERBOT.value)
    chat_key = str(chat_id)

    runtime_ctx: dict[str, Any] = {}
    if template_type == "sales_manager":
        runtime_ctx = {
            "lead_initiated_private_dialog": True,
            "is_private_chat": True,
        }
    if sender_name:
        runtime_ctx["user_display_name"] = sender_name
    sender_id = message.sender
    if sender_id is not None:
        runtime_ctx["sender_user_id"] = str(sender_id)

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
        runtime_context=runtime_ctx or None,
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


class MaxUserbotManager(PollingChannelManager):
    def __init__(self) -> None:
        super().__init__(
            lock_key=20_003,
            lock_name="max_userbot_manager",
            poll_interval_seconds=max(10, int(settings.MAX_USERBOT_POLL_INTERVAL_SECONDS)),
            channel_name="MaxUserbotManager",
            log_prefix="max_userbot",
            restart_on_fingerprint_change=True,
        )

    async def fetch_configs(self) -> list[dict[str, Any]]:
        return await AgentChannelConnectionDAO.fetch_active_channel_configs("max_userbot")

    async def run_worker(self, cfg: dict[str, Any], stop: asyncio.Event) -> None:
        await _run_one_client(cfg, stop)
