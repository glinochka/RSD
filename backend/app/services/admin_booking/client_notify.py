"""Исходящие уведомления клиенту после подтверждения платной брони."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import quote

from sqlalchemy import select

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentAnalyticsMessage, AgentChannelConnection
from ...utils.crypto import decrypt_token
from ..sales.outreach_send import send_telegram_userbot_message, send_whatsapp_userbot_message
from .payment_fulfillment import BookingFulfillmentResult

logger = logging.getLogger(__name__)


async def _telegram_bot_send(bot_token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{quote(bot_token, safe='')}/sendMessage"
    payload_bytes = json.dumps({"chat_id": chat_id, "text": text}, ensure_ascii=False).encode("utf-8")

    def _post():
        from urllib.request import Request, urlopen

        req = Request(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                raise RuntimeError(data.get("description") or str(data))

    await asyncio.get_running_loop().run_in_executor(None, _post)


async def _log_agent_message(
    *,
    agent_id: int,
    bot_id: int,
    channel: str,
    user_external_id: str,
    message_text: str,
) -> None:
    text = (message_text or "").strip()
    if not text:
        return
    async with async_session_maker() as session:
        async with session.begin():
            session.add(
                AgentAnalyticsMessage(
                    agent_id=agent_id,
                    bot_id=bot_id,
                    role="agent",
                    channel=channel,
                    user_external_id=user_external_id,
                    message_text=text,
                )
            )


async def notify_booking_payment_confirmed(result: BookingFulfillmentResult) -> None:
    if not result.client_message or not result.agent_id or not result.client_external_id:
        return

    agent_id = int(result.agent_id)
    uid = str(result.client_external_id).strip()
    text = result.client_message.strip()
    channel = (result.source_channel or "telegram").strip().lower()

    async with async_session_maker() as session:
        agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
        if agent is None:
            return
        bot_id = int(agent.bot_id if agent.bot_id is not None else agent.id)

        tg_bot = await session.scalar(
            select(AgentChannelConnection).where(
                AgentChannelConnection.agent_id == agent_id,
                AgentChannelConnection.provider == "telegram_bot",
                AgentChannelConnection.connection_type == "bot",
                AgentChannelConnection.is_active.is_(True),
                AgentChannelConnection.encrypted_credentials.is_not(None),
            )
        )
        tg_userbot = await session.scalar(
            select(AgentChannelConnection).where(
                AgentChannelConnection.agent_id == agent_id,
                AgentChannelConnection.provider == "telegram_userbot",
                AgentChannelConnection.connection_type == "userbot",
                AgentChannelConnection.is_active.is_(True),
                AgentChannelConnection.encrypted_credentials.is_not(None),
            )
        )
        wa_userbot = await session.scalar(
            select(AgentChannelConnection).where(
                AgentChannelConnection.agent_id == agent_id,
                AgentChannelConnection.provider == "whatsapp_userbot",
                AgentChannelConnection.is_active.is_(True),
                AgentChannelConnection.encrypted_credentials.is_not(None),
            )
        )

    delivered_channel: str | None = None

    try:
        if channel in {"telegram", "telegram_userbot", "telegram_bot"}:
            if tg_bot and tg_bot.encrypted_credentials and uid.isdigit():
                token = decrypt_token(tg_bot.encrypted_credentials)
                await _telegram_bot_send(token, int(uid), text)
                delivered_channel = "telegram"
            elif tg_userbot and tg_userbot.encrypted_credentials:
                await send_telegram_userbot_message(
                    encrypted_credentials=tg_userbot.encrypted_credentials,
                    target_external_id=uid,
                    text=text,
                )
                delivered_channel = "telegram_userbot"
        elif channel == "whatsapp_userbot" and wa_userbot and wa_userbot.encrypted_credentials:
            await send_whatsapp_userbot_message(
                connection_id=int(wa_userbot.id),
                encrypted_credentials=wa_userbot.encrypted_credentials,
                user_external_id=uid,
                text=text,
            )
            delivered_channel = "whatsapp_userbot"
        else:
            if tg_bot and tg_bot.encrypted_credentials and uid.isdigit():
                token = decrypt_token(tg_bot.encrypted_credentials)
                await _telegram_bot_send(token, int(uid), text)
                delivered_channel = "telegram"
            elif tg_userbot and tg_userbot.encrypted_credentials:
                await send_telegram_userbot_message(
                    encrypted_credentials=tg_userbot.encrypted_credentials,
                    target_external_id=uid,
                    text=text,
                )
                delivered_channel = "telegram_userbot"
    except Exception:
        logger.exception(
            "notify_booking_payment_confirmed: send failed agent_id=%s channel=%s",
            agent_id,
            channel,
        )
        return

    if delivered_channel:
        await _log_agent_message(
            agent_id=agent_id,
            bot_id=bot_id,
            channel=delivered_channel,
            user_external_id=uid,
            message_text=text,
        )


async def notify_client_booking_message(
    *,
    agent_id: int,
    client_external_id: str,
    source_channel: str | None,
    text: str,
) -> bool:
    """Отправить произвольное текстовое сообщение клиенту в канал бронирования."""
    if not (text or "").strip() or not client_external_id:
        return False

    result = BookingFulfillmentResult(
        fulfilled=False,
        already_booked=False,
        agent_id=agent_id,
        client_external_id=client_external_id.strip(),
        source_channel=source_channel,
        client_message=text.strip(),
    )
    await notify_booking_payment_confirmed(result)
    return True


def _format_refund_amount(amount_rub: float | int | None) -> str:
    if amount_rub is None:
        return ""
    try:
        value = float(amount_rub)
    except (TypeError, ValueError):
        return ""
    if value == int(value):
        return f"{int(value)} ₽"
    return f"{value:.2f} ₽".replace(".", ",")


async def notify_refund_auto_completed(
    *,
    agent_id: int,
    client_external_id: str,
    source_channel: str | None,
    amount_rub: float | int | None,
) -> None:
    amount_label = _format_refund_amount(amount_rub)
    text = (
        "Ваша запись отменена. "
        f"Полный возврат {amount_label} оформлен автоматически — "
        "деньги вернутся на карту в срок вашего банка (обычно 3–10 рабочих дней)."
    ).replace("  ", " ").strip()
    await notify_client_booking_message(
        agent_id=agent_id,
        client_external_id=client_external_id,
        source_channel=source_channel,
        text=text,
    )


async def notify_refund_request_approved(
    *,
    agent_id: int,
    client_external_id: str,
    source_channel: str | None,
    amount_rub: float | int | None,
) -> None:
    amount_label = _format_refund_amount(amount_rub)
    text = (
        "Заявка на возврат одобрена. "
        f"Полный возврат {amount_label} отправлен — "
        "ожидайте зачисления на карту в срок банка."
    ).replace("  ", " ").strip()
    await notify_client_booking_message(
        agent_id=agent_id,
        client_external_id=client_external_id,
        source_channel=source_channel,
        text=text,
    )


async def notify_refund_request_rejected(
    *,
    agent_id: int,
    client_external_id: str,
    source_channel: str | None,
    reason: str | None = None,
) -> None:
    base = "Заявка на возврат отклонена."
    if (reason or "").strip():
        text = f"{base} Причина: {reason.strip()}"
    else:
        text = f"{base} По вопросам обратитесь к администратору салона."
    await notify_client_booking_message(
        agent_id=agent_id,
        client_external_id=client_external_id,
        source_channel=source_channel,
        text=text,
    )
