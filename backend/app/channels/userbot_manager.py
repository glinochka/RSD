"""Telethon userbot clients manager for active agents."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from io import BytesIO
from typing import Any

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerUser, User

from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..utils.crypto import decrypt_token
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from .leader_lock import PgLeaderLock
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

logger = logging.getLogger(__name__)


def _make_client(session_string: str, api_id: int, api_hash: str) -> TelegramClient:
    return TelegramClient(StringSession(session_string), api_id, api_hash)


async def _resolve_peer_access_hash_for_private_dm(
    event: events.NewMessage.Event,
    *,
    sender: Any,
    user_external_id: str,
) -> int | None:
    """Full User from get_sender() sometimes has no access_hash (e.g. some media updates)."""
    if isinstance(sender, User):
        ah = getattr(sender, "access_hash", None)
        if ah is not None:
            h = int(ah)
            return h if h != 0 else None
    try:
        inp = await event.get_input_sender()
        if isinstance(inp, InputPeerUser) and getattr(inp, "access_hash", None) is not None:
            h = int(inp.access_hash)
            return h if h != 0 else None
    except Exception:
        logger.debug("userbot: get_input_sender failed for access_hash", exc_info=True)
    try:
        uid = int(str(user_external_id).strip())
        full = await event.client.get_entity(uid)
        if isinstance(full, User):
            ah = getattr(full, "access_hash", None)
            if ah is not None:
                h = int(ah)
                return h if h != 0 else None
    except Exception:
        logger.debug("userbot: get_entity failed for access_hash", exc_info=True)
    return None


def _should_process_sales_manager_public_event(
    *,
    is_group_message: bool,
    is_channel_message: bool,
    lead_generation_enabled: bool,
    neuro_commenting_enabled: bool,
    live_chat_simulation_enabled: bool,
) -> tuple[bool, bool]:
    """Return (should_process_group, should_process_channel) for public messages."""
    should_process_group = is_group_message and (lead_generation_enabled or live_chat_simulation_enabled)
    should_process_channel = is_channel_message and neuro_commenting_enabled
    return should_process_group, should_process_channel


def _normalize_trigger_token(value: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", (value or "").strip().lower(), flags=re.IGNORECASE)


def _extract_message_tokens(value: str) -> list[str]:
    parts = re.split(r"[^a-zа-яё0-9]+", (value or "").strip().lower(), flags=re.IGNORECASE)
    normalized: list[str] = []
    for item in parts:
        token = _normalize_trigger_token(item)
        if token:
            normalized.append(token)
    return normalized


def _is_message_matching_triggers(message_text: str, trigger_words: list[str]) -> bool:
    tokens = _extract_message_tokens(message_text)
    normalized_triggers = [_normalize_trigger_token(item) for item in (trigger_words or [])]
    normalized_triggers = [item for item in normalized_triggers if item]
    if not normalized_triggers:
        normalized_triggers = ["купить"]
    if not tokens:
        return False
    for token in tokens:
        for trigger in normalized_triggers:
            # Non-strict matching in both directions ("купи" <-> "купить")
            if token in trigger or trigger in token:
                return True
    return False


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
    agent_id: int,
    system_prompt: str,
    welcome_message: str | None,
    template_type: str,
    template_config: dict[str, Any],
) -> None:
    """Handle incoming private messages (DM)."""
    if not event.is_private:
        return

    sender = await event.get_sender()
    user_external_id = str(getattr(sender, "id", None) or "")
    if not user_external_id:
        return

    peer_access_hash = await _resolve_peer_access_hash_for_private_dm(
        event, sender=sender, user_external_id=user_external_id
    )

    sender_is_bot = bool(getattr(sender, "bot", False))
    if sender_is_bot:
        return

    user_display_name = (
        (getattr(sender, "first_name", "") or "").strip()
        + " "
        + (getattr(sender, "last_name", "") or "").strip()
    ).strip() or getattr(sender, "username", None)

    caption_or_text = (event.message.message or "").strip()
    runtime_ctx: dict[str, Any] = {
        "lead_initiated_private_dialog": template_type == "sales_manager",
        "is_private_chat": True,
    }
    query = caption_or_text
    voice_bytes: bytes | None = None
    voice_mime = "audio/ogg"

    try:
        if event.message.photo:
            buf = BytesIO()
            await event.message.download_media(buf)
            raw = buf.getvalue()
            if len(raw) > int(settings.IMAGE_MAX_BYTES):
                await event.respond("Изображение слишком большое. Отправьте файл поменьше.")
                return
            mime = "image/jpeg"
            runtime_ctx["vision_image_data_url"] = (
                f"data:{mime};base64,{base64.standard_b64encode(raw).decode('ascii')}"
            )
            query = caption_or_text or "[Фото без подписи]"
        elif event.message.document:
            doc = event.message.document
            doc_mime = (getattr(doc, "mime_type", None) or "").strip().lower()
            if doc_mime.startswith("image/"):
                buf = BytesIO()
                await event.message.download_media(buf)
                raw = buf.getvalue()
                if len(raw) > int(settings.IMAGE_MAX_BYTES):
                    await event.respond("Изображение слишком большое. Отправьте файл поменьше.")
                    return
                mime = getattr(doc, "mime_type", None) or "image/jpeg"
                runtime_ctx["vision_image_data_url"] = (
                    f"data:{mime};base64,{base64.standard_b64encode(raw).decode('ascii')}"
                )
                query = caption_or_text or "[Изображение без подписи]"
            elif doc_mime.startswith("audio/"):
                buf = BytesIO()
                await event.message.download_media(buf)
                voice_bytes = buf.getvalue()
                voice_mime = getattr(doc, "mime_type", None) or "audio/mpeg"
                if len(voice_bytes) > int(settings.VOICE_MAX_BYTES):
                    await event.respond("Аудиофайл слишком большой.")
                    return
                if not caption_or_text:
                    query = ""
            elif caption_or_text:
                query = caption_or_text
            else:
                await event.respond(
                    "Пока поддерживаются текст, фото, изображения-файлы, голос и аудио. Отправьте что-то из этого."
                )
                return
        elif getattr(event.message, "voice", None):
            buf = BytesIO()
            await event.message.download_media(buf)
            voice_bytes = buf.getvalue()
            voice_mime = getattr(event.message.voice, "mime_type", None) or "audio/ogg"
            if len(voice_bytes) > int(settings.VOICE_MAX_BYTES):
                await event.respond("Голосовое сообщение слишком большое.")
                return
            if not caption_or_text:
                query = ""
        elif getattr(event.message, "audio", None):
            buf = BytesIO()
            await event.message.download_media(buf)
            voice_bytes = buf.getvalue()
            voice_mime = getattr(event.message.audio, "mime_type", None) or "audio/mpeg"
            if len(voice_bytes) > int(settings.VOICE_MAX_BYTES):
                await event.respond("Аудиосообщение слишком большое.")
                return
            if not caption_or_text:
                query = ""
        elif caption_or_text:
            query = caption_or_text
        else:
            await event.respond(
                "Пока поддерживаются текст, фото, изображения-файлы, голос и аудио. Отправьте что-то из этого."
            )
            return
    except Exception:
        logger.exception(
            "userbot: failed to download/process media bot_id=%s agent_id=%s",
            bot_id,
            agent_id,
        )
        await event.respond("Не удалось обработать вложение. Попробуйте ещё раз.")
        return

    if voice_bytes is not None:
        if is_voice_stt_configured():
            transcript = await transcribe_voice_bytes(voice_bytes, mime_type=voice_mime)
            if transcript:
                query = (
                    f"{caption_or_text}\n\nТекст голосового сообщения: {transcript}".strip()
                    if caption_or_text
                    else f"Текст голосового сообщения: {transcript}"
                )
            else:
                query = caption_or_text or (
                    "Пользователь прислал голосовое сообщение, но текст распознать не удалось."
                )
        else:
            await event.respond(
                "Голосовые сообщения недоступны: не настроено распознавание речи "
                "(установите faster-whisper или задайте OPENAI_API_KEY). Напишите, пожалуйста, текстом."
            )
            return

    query = str(query or "").strip()
    if not query:
        await event.respond("Не удалось получить текст сообщения.")
        return

    # Mark incoming message as read for better DM UX.
    try:
        await event.client.send_read_acknowledge(event.chat_id, max_id=event.message.id)
    except Exception:
        logger.debug("userbot: failed to mark message as read bot_id=%s", bot_id, exc_info=True)

    request = MessageRequest(
        bot_id=bot_id,
        query=query,
        user_external_id=user_external_id,
        channel=Channel.TELEGRAM_USERBOT,
        system_prompt=system_prompt,
        welcome_message=welcome_message,
        user_display_name=user_display_name,
        telegram_peer_access_hash=peer_access_hash,
        runtime_context=runtime_ctx,
    )
    try:
        try:
            async with event.client.action(event.chat_id, "typing"):
                response = await get_message_processor().process(request)
        except Exception:
            logger.debug(
                "userbot: typing action unavailable bot_id=%s agent_id=%s, fallback without typing",
                bot_id,
                agent_id,
                exc_info=True,
            )
            response = await get_message_processor().process(request)
    except Exception:
        logger.exception("userbot: failed to process private message bot_id=%s agent_id=%s", bot_id, agent_id)
        raise
    if response.status != ProcessingStatus.DISCARDED:
        await event.respond(response.text)


async def _handle_chat_message(
    event: events.NewMessage.Event,
    *,
    bot_id: int,
    agent_id: int,
    system_prompt: str,
    template_type: str,
    template_config: dict[str, Any],
) -> None:
    """Handle incoming group/channel messages for sales_manager scanning."""
    if event.is_private:
        return
    if template_type != "sales_manager":
        return

    cfg = template_config or {}
    lead_generation_enabled = bool(cfg.get("lead_generation_enabled", True))
    neuro_commenting_enabled = bool(cfg.get("neuro_commenting_enabled", False))
    live_chat_simulation_enabled = bool(cfg.get("live_chat_simulation_enabled", False))

    # Routing rules for sales_manager:
    # - DMs are always handled separately in _handle_private_message
    # - groups are scanned by lead-generation and live-chat-simulation flows
    # - channels are scanned only by neuro-commenting flow
    is_group_message = bool(getattr(event, "is_group", False))
    is_channel_message = bool(getattr(event, "is_channel", False) and not is_group_message)
    should_process_group, should_process_channel = _should_process_sales_manager_public_event(
        is_group_message=is_group_message,
        is_channel_message=is_channel_message,
        lead_generation_enabled=lead_generation_enabled,
        neuro_commenting_enabled=neuro_commenting_enabled,
        live_chat_simulation_enabled=live_chat_simulation_enabled,
    )
    if not should_process_group and not should_process_channel:
        return

    # Skip system messages
    if event.message.action is not None:
        return

    # Skip if message from bot itself
    sender = await event.get_sender()
    if sender is None:
        return
    
    sender_is_bot = getattr(sender, "bot", False)
    if sender_is_bot:
        return
    
    # Skip messages from self (userbot)
    try:
        me = await event.client.get_me()
        if sender.id == me.id:
            return
    except Exception:
        pass

    raw = event.message.message
    if raw is None or not str(raw).strip():
        return

    query = str(raw).strip()
    trigger_words = cfg.get("trigger_words")
    normalized_trigger_words = trigger_words if isinstance(trigger_words, list) else []
    if should_process_group and not _is_message_matching_triggers(query, normalized_trigger_words):
        return
    user_external_id = str(getattr(sender, "id", None) or "")
    if not user_external_id:
        return

    peer_access_hash: int | None = None
    if isinstance(sender, User):
        ah = getattr(sender, "access_hash", None)
        if ah is not None:
            peer_access_hash = int(ah)

    source_chat_id = str(event.chat_id) if hasattr(event, "chat_id") else "0"
    
    user_display_name = (
        (getattr(sender, "first_name", "") or "").strip()
        + " "
        + (getattr(sender, "last_name", "") or "").strip()
    ).strip() or getattr(sender, "username", None)

    # Process through message processor (will route to sales_manager template runtime)
    request = MessageRequest(
        bot_id=bot_id,
        query=query,
        user_external_id=user_external_id,
        channel=Channel.TELEGRAM_USERBOT,
        system_prompt=system_prompt,
        welcome_message=None,
        user_display_name=user_display_name,
        telegram_peer_access_hash=peer_access_hash,
        skip_chat_portrait_update=True,
        runtime_context={
            "is_group_chat": should_process_group,
            "is_channel_chat": should_process_channel,
            "lead_initiated_private_dialog": False,
            "lead_generation_enabled": lead_generation_enabled,
            "neuro_commenting_enabled": neuro_commenting_enabled,
            "live_chat_simulation_enabled": live_chat_simulation_enabled,
        },
    )
    
    # Note: Response is not sent to group, only processed/queued in backend
    try:
        logger.info(
            "Processing group message: bot_id=%s chat_id=%s user_id=%s text_preview=%s",
            bot_id,
            source_chat_id,
            user_external_id,
            query[:50] if len(query) > 50 else query,
        )
        response = await get_message_processor().process(request)
        logger.info(
            "Group message processed: bot_id=%s user_id=%s status=%s",
            bot_id,
            user_external_id,
            response.status.value,
        )
        # Neuro-commenting mode should publish comment under the same channel post.
        if should_process_channel and response.text.strip():
            try:
                await event.client.send_message(
                    entity=event.chat_id,
                    message=response.text.strip(),
                    comment_to=event.message.id,
                )
            except Exception:
                logger.exception(
                    "Failed to post channel comment: bot_id=%s chat_id=%s msg_id=%s",
                    bot_id,
                    source_chat_id,
                    getattr(event.message, "id", None),
                )
    except Exception as exc:
        logger.exception(
            "sales_manager chat scanning error: bot_id=%s chat_id=%s user_id=%s error=%s",
            bot_id,
            source_chat_id,
            user_external_id,
            exc,
        )



async def _run_one_client(cfg: dict[str, Any]) -> None:
    """Run Telethon client for userbot: handle DMs and scan chats for sales_manager."""
    bundle = json.loads(decrypt_token(cfg["encrypted_userbot_bundle"]))
    api_id = int(bundle["api_id"])
    api_hash = str(bundle["api_hash"])
    session_str = str(bundle["session_string"])
    bot_id = int(cfg["bot_id"])
    agent_id = int(cfg["agent_id"])
    system_prompt = cfg.get("system_prompt") or ""
    welcome = cfg.get("welcome_message")
    template_type = cfg.get("template_type") or "qa"
    template_config = cfg.get("template_config") or {}

    client = _make_client(session_str, api_id, api_hash)

    async def private_msg_handler(event: events.NewMessage.Event) -> None:
        await _handle_private_message(
            event,
            bot_id=bot_id,
            agent_id=agent_id,
            system_prompt=system_prompt,
            welcome_message=welcome,
            template_type=template_type,
            template_config=template_config,
        )

    async def chat_msg_handler(event: events.NewMessage.Event) -> None:
        await _handle_chat_message(
            event,
            bot_id=bot_id,
            agent_id=agent_id,
            system_prompt=system_prompt,
            template_type=template_type,
            template_config=template_config,
        )

    # Register handlers: private messages and group/chat messages
    client.add_event_handler(private_msg_handler, events.NewMessage(incoming=True, func=lambda e: e.is_private))
    client.add_event_handler(chat_msg_handler, events.NewMessage(incoming=True, func=lambda e: not e.is_private))
    
    try:
        logger.info("userbot: connecting bot_id=%s agent_id=%s", bot_id, agent_id)
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("userbot: session unauthorized bot_id=%s agent_id=%s", bot_id, agent_id)
            return
        me = await client.get_me()
        logger.info(
            "userbot: online bot_id=%s agent_id=%s telegram_user=%s template_type=%s",
            bot_id,
            agent_id,
            getattr(me, "username", None) or me.id,
            template_type,
        )
        await client.run_until_disconnected()
    except asyncio.CancelledError:
        logger.info("userbot: stopping bot_id=%s agent_id=%s", bot_id, agent_id)
        raise
    except Exception:
        logger.exception("userbot: worker failed bot_id=%s agent_id=%s", bot_id, agent_id)
    finally:
        if client.is_connected():
            await client.disconnect()


class UserbotManager:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._config_fingerprints: dict[int, str] = {}
        self._leader_lock = PgLeaderLock(20_001, "telegram_userbot_manager")

    async def _cancel_all_tasks(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._config_fingerprints.clear()

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
                                self._config_fingerprints.pop(bot_id, None)
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass
                                logger.info("userbot: removed bot_id=%s", bot_id)

                        by_id = {int(c["bot_id"]): c for c in configs if c.get("bot_id") is not None}
                        for bot_id, cfg in by_id.items():
                            fingerprint = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
                            existing = self._tasks.get(bot_id)
                            if existing and existing.done():
                                self._tasks.pop(bot_id, None)
                                self._config_fingerprints.pop(bot_id, None)
                                try:
                                    existing.result()
                                except Exception:
                                    logger.exception("userbot: previous worker crashed bot_id=%s", bot_id)
                                existing = None
                            previous_fingerprint = self._config_fingerprints.get(bot_id)
                            if existing and previous_fingerprint != fingerprint:
                                logger.info("userbot: config changed, restarting worker bot_id=%s", bot_id)
                                existing.cancel()
                                try:
                                    await existing
                                except asyncio.CancelledError:
                                    pass
                                except Exception:
                                    logger.exception("userbot: worker failed during restart bot_id=%s", bot_id)
                                self._tasks.pop(bot_id, None)
                                existing = None
                            if existing is None:
                                self._tasks[bot_id] = asyncio.create_task(_run_one_client(cfg))
                                self._config_fingerprints[bot_id] = fingerprint
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
