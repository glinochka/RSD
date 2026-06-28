"""WhatsApp userbot manager backed by wa_bridge runtime sessions."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from ..config import settings
from ..router_agents.dao import AgentChannelConnectionDAO
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from ..services.human_delay import (
    get_online_delay,
    get_read_delay,
    get_typing_delay,
    mark_activity,
    is_human_delay_enabled,
)
from ..utils.crypto import decrypt_token
from ..utils.whatsapp_jid import bridge_post, is_private_whatsapp_jid, jid_for_whatsapp_analytics
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor
from .polling_manager import PollingChannelManager

logger = logging.getLogger(__name__)


async def _bridge_post_best_effort(path: str, payload: dict[str, Any]) -> None:
    try:
        await bridge_post(path, payload)
    except Exception:
        logger.debug("whatsapp_userbot: bridge call failed path=%s payload=%s", path, payload, exc_info=True)


def _extract_text(message: dict[str, Any]) -> str:
    msg = message.get("message") or {}
    text = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")
        or (msg.get("videoMessage") or {}).get("caption")
        or (msg.get("documentMessage") or {}).get("caption")
        or ""
    )
    return str(text).strip()


def _whatsapp_media_kind(inner: dict[str, Any]) -> str | None:
    """Baileys message content kind: audio for STT, or unsupported visual media."""
    if not isinstance(inner, dict):
        return None
    if inner.get("imageMessage") is not None:
        return "unsupported"
    if inner.get("stickerMessage") is not None:
        return "unsupported"
    if inner.get("audioMessage") is not None:
        return "audio"
    if inner.get("videoMessage") is not None:
        return "unsupported"
    dm = inner.get("documentMessage")
    if isinstance(dm, dict):
        mt = str(dm.get("mimetype") or "").lower()
        if mt.startswith("image/"):
            return "unsupported"
        if mt.startswith("audio/"):
            return "audio"
    return None


async def _bridge_download_media(connection_id: int, wa_message: dict[str, Any]) -> tuple[bytes, str] | None:
    try:
        data = await bridge_post(
            "session/download_media",
            {
                "connection_id": str(connection_id),
                "wa_message": wa_message,
            },
        )
    except Exception:
        logger.exception(
            "whatsapp_userbot: session/download_media failed connection_id=%s",
            connection_id,
        )
        return None
    b64 = data.get("base64")
    mime = str(data.get("mime_type") or "application/octet-stream").strip() or "application/octet-stream"
    if not b64 or not isinstance(b64, str):
        return None
    try:
        raw = base64.standard_b64decode(b64, validate=True)
    except Exception:
        return None
    if not raw:
        return None
    return raw, mime


async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return

    # Reply only in direct messages, never in groups/channels/broadcast chats.
    if not is_private_whatsapp_jid(remote_jid):
        return

    if bool(incoming.get("from_me")):
        return

    connection_id = int(cfg["connection_id"])
    inner = incoming.get("message") or {}
    if not isinstance(inner, dict):
        inner = {}
    text = _extract_text(incoming)
    kind = _whatsapp_media_kind(inner)
    wa_full = incoming.get("wa_message") if isinstance(incoming.get("wa_message"), dict) else None

    template_type = str(cfg.get("template_type") or "qa").strip().lower()
    runtime_ctx: dict[str, Any] = {}
    if template_type == "sales_manager":
        runtime_ctx = {
            "lead_initiated_private_dialog": True,
            "is_private_chat": True,
        }
    query = text
    _unsupported_media_reply = (
        "Спасибо, что написали! Пока я лучше всего понимаю текст и голосовые — "
        "с картинками и файлами, к сожалению, ещё не справляюсь. "
        "Напишите, пожалуйста, словами или отправьте голосовое — с радостью помогу."
    )

    if kind == "unsupported":
        if text:
            query = text
        else:
            await _bridge_post_best_effort(
                "session/read",
                {
                    "connection_id": str(connection_id),
                    "remote_jid": remote_jid,
                    "message_id": incoming.get("id"),
                },
            )
            try:
                await bridge_post(
                    "session/send",
                    {
                        "connection_id": str(connection_id),
                        "to_jid": remote_jid,
                        "text": _unsupported_media_reply,
                    },
                )
            except Exception:
                logger.exception(
                    "whatsapp_userbot: failed to send unsupported-media notice connection_id=%s",
                    connection_id,
                )
            return
    elif kind == "audio":
        if wa_full is None:
            if not text:
                return
        else:
            downloaded = await _bridge_download_media(connection_id, wa_full)
            if not downloaded:
                if not text:
                    return
            else:
                raw, mime = downloaded
                if len(raw) > int(settings.VOICE_MAX_BYTES):
                    query = (
                        f"{text}\n\n(Голосовое вложение слишком большое.)".strip()
                        if text
                        else "Голосовое сообщение слишком большое."
                    )
                elif not is_voice_stt_configured():
                    await _bridge_post_best_effort(
                        "session/read",
                        {
                            "connection_id": str(connection_id),
                            "remote_jid": remote_jid,
                            "message_id": incoming.get("id"),
                        },
                    )
                    try:
                        await bridge_post(
                            "session/send",
                            {
                                "connection_id": str(connection_id),
                                "to_jid": remote_jid,
                                "text": (
                                    "Голосовые сообщения недоступны: не настроено распознавание речи "
                                    "(установите faster-whisper или задайте OPENAI_API_KEY). Напишите, пожалуйста, текстом."
                                ),
                            },
                        )
                    except Exception:
                        logger.exception(
                            "whatsapp_userbot: failed to send STT-unavailable notice connection_id=%s",
                            connection_id,
                        )
                    return
                else:
                    transcript = await transcribe_voice_bytes(raw, mime_type=mime or "audio/ogg")
                    if transcript:
                        query = (
                            f"{text}\n\nТекст голосового сообщения: {transcript}".strip()
                            if text
                            else f"Текст голосового сообщения: {transcript}"
                        )
                    else:
                        query = text or (
                            "Пользователь прислал голосовое сообщение, но текст распознать не удалось."
                        )
    elif not kind and not text:
        return

    query = str(query or "").strip()
    if not query:
        return

    template_config: dict[str, Any] = cfg.get("template_config") or {}
    bot_id = int(cfg["bot_id"])
    agent_id = int(cfg.get("agent_id") or bot_id)
    user_ext_id = jid_for_whatsapp_analytics(remote_jid)
    human_delay = is_human_delay_enabled(template_config, Channel.WHATSAPP_USERBOT.value)

    # Phase 1: "come online" delay — skip for first-ever message in this conversation.
    if human_delay:
        online_wait = await get_online_delay(agent_id, user_ext_id, Channel.WHATSAPP_USERBOT.value)
        if online_wait > 0:
            await asyncio.sleep(online_wait)

    # Mark message as read (agent is now "online").
    await _bridge_post_best_effort(
        "session/read",
        {
            "connection_id": str(connection_id),
            "remote_jid": remote_jid,
            "message_id": incoming.get("id"),
        },
    )

    # Phase 2: reading pause proportional to incoming message length.
    if human_delay:
        await asyncio.sleep(get_read_delay(len(query)))

    # Phase 3: start typing indicator.
    await _bridge_post_best_effort(
        "session/typing",
        {
            "connection_id": str(connection_id),
            "to_jid": remote_jid,
            "is_typing": True,
        },
    )

    request = MessageRequest(
        bot_id=bot_id,
        query=query,
        user_external_id=user_ext_id,
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
        runtime_context=runtime_ctx or None,
    )
    try:
        response = await get_message_processor().process(request)
        # Phase 4: extra typing delay proportional to response length.
        if human_delay and response.delivers_reply():
            await asyncio.sleep(get_typing_delay(len(response.text or "")))
        if not response.delivers_reply():
            return
        await bridge_post(
            "session/send",
            {
                "connection_id": str(connection_id),
                "to_jid": remote_jid,
                "text": response.text,
            },
        )
        if human_delay:
            mark_activity(agent_id, user_ext_id, Channel.WHATSAPP_USERBOT.value)
    finally:
        await _bridge_post_best_effort(
            "session/typing",
            {
                "connection_id": str(connection_id),
                "to_jid": remote_jid,
                "is_typing": False,
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
    reconnect_delay = max(2, int(settings.WHATSAPP_USERBOT_RECONNECT_DELAY_SECONDS))
    poll_interval = max(1, int(settings.WHATSAPP_USERBOT_POLL_INTERVAL_SECONDS))
    closed_streak = 0

    while not stop.is_set():
        try:
            await bridge_post(
                "session/connect",
                {
                    "connection_id": str(connection_id),
                    "session_string": session_string,
                },
            )
            logger.info("whatsapp_userbot: connected connection_id=%s bot_id=%s", connection_id, cfg.get("bot_id"))
            closed_streak = 0

            while not stop.is_set():
                payload = await bridge_post(
                    "session/pull",
                    {
                        "connection_id": str(connection_id),
                        "limit": 20,
                    },
                )
                runtime_status = str(payload.get("status") or "").strip().lower()
                if runtime_status == "closed":
                    closed_streak += 1
                    last_error = payload.get("last_error")
                    if closed_streak == 1:
                        logger.warning(
                            "whatsapp_userbot: runtime closed connection_id=%s last_error=%s",
                            connection_id,
                            last_error,
                        )
                    if closed_streak >= 3:
                        logger.warning(
                            "whatsapp_userbot: reconnecting after closed runtime connection_id=%s",
                            connection_id,
                        )
                        break
                else:
                    closed_streak = 0

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
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("whatsapp_userbot: worker failed connection_id=%s", connection_id)
        finally:
            await _bridge_post_best_effort(
                "session/disconnect",
                {"connection_id": str(connection_id)},
            )

        if stop.is_set():
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=reconnect_delay)
        except asyncio.TimeoutError:
            continue


class WhatsAppUserbotManager(PollingChannelManager):
    def __init__(self) -> None:
        super().__init__(
            lock_key=20_002,
            lock_name="whatsapp_userbot_manager",
            poll_interval_seconds=max(10, int(settings.USERBOT_POLL_INTERVAL_SECONDS)),
            channel_name="WhatsAppUserbotManager",
            log_prefix="whatsapp_userbot",
            restart_on_fingerprint_change=False,
        )

    async def fetch_configs(self) -> list[dict[str, Any]]:
        return await AgentChannelConnectionDAO.fetch_active_channel_configs("whatsapp_userbot")

    async def run_worker(self, cfg: dict[str, Any], stop: asyncio.Event) -> None:
        await _run_one_client(cfg, stop)
