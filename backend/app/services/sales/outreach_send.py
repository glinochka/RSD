"""Отправка outreach-сообщений через userbot-каналы (вне HTTP router)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.request import Request as UrlRequest, urlopen

from ...config import settings
from ...utils.crypto import decrypt_token

logger = logging.getLogger(__name__)


def whatsapp_user_external_to_jid(user_external_id: str) -> str:
    raw = (user_external_id or "").strip()
    if not raw:
        raise RuntimeError("Пустой идентификатор получателя WhatsApp")
    if "@" in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 5:
        raise RuntimeError("Некорректный номер WhatsApp")
    return f"{digits}@s.whatsapp.net"


async def wa_userbot_bridge_post(path: str, payload: dict) -> dict:
    base = (settings.WHATSAPP_USERBOT_BRIDGE_URL or "").strip().rstrip("/")
    if not base:
        raise RuntimeError("WhatsApp userbot bridge не настроен")
    bridge_api_key = (settings.WHATSAPP_USERBOT_BRIDGE_API_KEY or "").strip()
    if not bridge_api_key:
        raise RuntimeError("WhatsApp userbot bridge API key не настроен")

    url = f"{base}/{path.lstrip('/')}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "X-API-Key": bridge_api_key,
    }
    request = UrlRequest(url, data=body, headers=headers, method="POST")

    def _post():
        with urlopen(request, timeout=float(settings.WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS)) as resp:
            return json.loads(resp.read().decode("utf-8"))

    result = await asyncio.get_running_loop().run_in_executor(None, _post)
    if not isinstance(result, dict):
        raise RuntimeError("WhatsApp bridge вернул неожиданный ответ")
    return result


async def ensure_whatsapp_session(connection_id: int, encrypted_credentials: str) -> None:
    bundle = json.loads(decrypt_token(encrypted_credentials))
    session_string = str(bundle.get("session_string") or "").strip()
    if not session_string:
        raise RuntimeError("Отсутствует session_string WhatsApp")
    await wa_userbot_bridge_post(
        "session/connect",
        {"connection_id": str(connection_id), "session_string": session_string},
    )


async def send_whatsapp_userbot_message(
    *,
    connection_id: int,
    encrypted_credentials: str,
    user_external_id: str,
    text: str,
) -> None:
    await ensure_whatsapp_session(connection_id, encrypted_credentials)
    to_jid = whatsapp_user_external_to_jid(user_external_id)
    await wa_userbot_bridge_post(
        "session/send",
        {"connection_id": str(connection_id), "to_jid": to_jid, "text": text},
    )


async def send_max_userbot_message(
    *,
    encrypted_credentials: str,
    user_external_id: str,
    text: str,
) -> str:
    """Отправить DM через MAX userbot. Возвращает chat_id диалога."""
    from ..max_userbot_session import bundle_from_credentials, send_outreach_message_once

    bundle = bundle_from_credentials(encrypted_credentials)
    return await send_outreach_message_once(
        bundle,
        target_external_id=user_external_id,
        text=text,
    )


async def send_telegram_userbot_message(
    *,
    encrypted_credentials: str,
    target_external_id: str,
    text: str,
    peer_access_hash: int | None = None,
) -> None:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from telethon.tl.types import InputPeerUser

    bundle = json.loads(decrypt_token(encrypted_credentials))
    api_id = int(bundle["api_id"])
    api_hash = str(bundle["api_hash"])
    session_str = str(bundle["session_string"])

    client = TelegramClient(StringSession(session_str), api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Userbot session not authorized")

        target = (target_external_id or "").strip()
        recipient: Any = None

        if peer_access_hash is not None and target.isdigit():
            recipient = InputPeerUser(user_id=int(target), access_hash=int(peer_access_hash))
        elif target.isdigit():
            recipient = await client.get_entity(int(target))
        else:
            entity_key = target
            if entity_key.startswith("+"):
                entity_key = entity_key
            elif re.fullmatch(r"\d{10,15}", entity_key):
                entity_key = f"+{entity_key}"
            recipient = await client.get_entity(entity_key)

        if recipient is None:
            raise RuntimeError("Не удалось разрешить получателя Telegram")
        await client.send_message(recipient, text)
    finally:
        if client.is_connected():
            await client.disconnect()
