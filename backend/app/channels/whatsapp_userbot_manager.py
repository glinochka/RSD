"""WhatsApp userbot manager backed by wa_bridge runtime sessions."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection
from ..config import settings
from ..services.voice_transcription import is_voice_stt_configured, transcribe_voice_bytes
from ..utils.crypto import decrypt_token
from .leader_lock import PgLeaderLock
from .message_processor import Channel, MessageRequest, ProcessingStatus, get_message_processor

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


async def _bridge_post_best_effort(path: str, payload: dict[str, Any]) -> None:
    try:
        await _bridge_post(path, payload)
    except Exception:
        logger.debug("whatsapp_userbot: bridge call failed path=%s payload=%s", path, payload, exc_info=True)


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
                            Agent.template_type,
                            Agent.template_config,
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
                "phone_number": row["phone_number"] or "",
                "system_prompt": row["system_prompt"] or "",
                "welcome_message": row["welcome_message"],
                "template_type": str(row.get("template_type") or "qa").strip().lower(),
                "template_config": template_config,
                "encrypted_credentials": row["encrypted_credentials"],
            }
        )
    return configs


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
        data = await _bridge_post(
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


def _user_external_id_for_whatsapp_analytics(remote_jid: str) -> str:
    """Полный JID как во входящем сообщении Baileys (…@s.whatsapp.net или …@lid и т.д.).

    Раньше сохранялась только локальная часть до «@» — при @lid или смене PN/LID
    ответы с дашборда уходили на неверный JID (в мессенджере не появлялись).
    """
    jid = str(remote_jid or "").strip()
    if len(jid) > 128:
        return jid[:128]
    return jid


def _is_private_whatsapp_jid(jid: str) -> bool:
    value = str(jid or "").strip().lower()
    if not value:
        return False
    if value.endswith("@g.us") or value.endswith("@broadcast") or value == "status@broadcast":
        return False
    return ("@" in value) and (value.endswith("@s.whatsapp.net") or value.endswith("@lid"))


async def _process_incoming(cfg: dict[str, Any], incoming: dict[str, Any]) -> None:
    remote_jid = str(incoming.get("remote_jid") or "").strip()
    if not remote_jid:
        return

    # Reply only in direct messages, never in groups/channels/broadcast chats.
    if not _is_private_whatsapp_jid(remote_jid):
        return

    if str(incoming.get("from_me") or "").lower() == "true":
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
                    "connection_id": connection_id,
                    "remote_jid": remote_jid,
                    "message_id": incoming.get("id"),
                },
            )
            try:
                await _bridge_post(
                    "session/send",
                    {
                        "connection_id": connection_id,
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
                            "connection_id": connection_id,
                            "remote_jid": remote_jid,
                            "message_id": incoming.get("id"),
                        },
                    )
                    try:
                        await _bridge_post(
                            "session/send",
                            {
                                "connection_id": connection_id,
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

    await _bridge_post_best_effort(
        "session/read",
        {
            "connection_id": connection_id,
            "remote_jid": remote_jid,
            "message_id": incoming.get("id"),
        },
    )
    await _bridge_post_best_effort(
        "session/typing",
        {
            "connection_id": connection_id,
            "to_jid": remote_jid,
            "is_typing": True,
        },
    )

    bot_id = int(cfg["bot_id"])
    request = MessageRequest(
        bot_id=bot_id,
        query=query,
        user_external_id=_user_external_id_for_whatsapp_analytics(remote_jid),
        channel=Channel.WHATSAPP_USERBOT,
        system_prompt=cfg.get("system_prompt") or "",
        welcome_message=cfg.get("welcome_message"),
        user_display_name=str(incoming.get("push_name") or "").strip() or None,
        runtime_context=runtime_ctx or None,
    )
    try:
        response = await get_message_processor().process(request)
        if response.status == ProcessingStatus.DISCARDED:
            return
        await _bridge_post(
            "session/send",
            {
                "connection_id": connection_id,
                "to_jid": remote_jid,
                "text": response.text,
            },
        )
    finally:
        await _bridge_post_best_effort(
            "session/typing",
            {
                "connection_id": connection_id,
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
    try:
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
    finally:
        await _bridge_post_best_effort("session/disconnect", {"connection_id": connection_id})


class WhatsAppUserbotManager:
    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._leader_lock = PgLeaderLock(20_002, "whatsapp_userbot_manager")

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
        logger.info("WhatsAppUserbotManager polling every %s sec", interval)
        try:
            while not self._stop.is_set():
                try:
                    is_leader = await self._leader_lock.ensure_acquired()
                    if not is_leader:
                        if self._tasks:
                            await self._cancel_all_tasks()
                        logger.info("whatsapp_userbot: another replica holds leader lock, waiting")
                    else:
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
        finally:
            await self._cancel_all_tasks()
            await self._leader_lock.release()
