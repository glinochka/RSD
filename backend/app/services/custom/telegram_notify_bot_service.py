"""Telegram bot for DMP lead alerts: login then password, then push notifications."""
from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import CustomAutomation, CustomAutomationCredential, CustomBotSubscriber, CustomLead, LeadStatus
from ...config import settings
from ...utils import crypto as crypto_utils
from ...utils.security import get_password_hash, verify_password
from .google_sheets_service import decrypt_service_account, ensure_header_and_append, parse_spreadsheet_id

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15
PASSWORD_WAIT_SECONDS = 300
SEND_ATTEMPTS = 3
RETRY_BATCH = 50
TELEGRAM_API = "https://api.telegram.org/bot"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_bot_webhook_secret(automation: CustomAutomation) -> str:
    if automation.telegram_bot_webhook_secret:
        return automation.telegram_bot_webhook_secret
    automation.telegram_bot_webhook_secret = secrets.token_urlsafe(24)
    return automation.telegram_bot_webhook_secret


def public_bot_webhook_url(automation_id: int, secret: str | None) -> str:
    base = (settings.BASE_URL or "").rstrip("/")
    if not base or not secret:
        return ""
    return f"{base}/api/custom/webhooks/telegram/{automation_id}/{secret}"


def set_bot_password(automation: CustomAutomation, password: str) -> None:
    value = (password or "").strip()
    if not value:
        raise ValueError("Укажите пароль бота")
    automation.telegram_bot_password_hash = get_password_hash(value)
    automation.updated_at = _utc_now()


def uses_password_gate(automation: CustomAutomation) -> bool:
    """Lead-handoff bots ask only for the settings password. DMP-bot still uses login+password."""
    from .solution_templates import is_dmp_notify_pipeline

    if is_dmp_notify_pipeline(automation):
        return False
    return bool((getattr(automation, "telegram_bot_password_hash", None) or "").strip())


def lead_telegram_username(lead: CustomLead) -> str | None:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    if (lead.contact_type or "") == "telegram":
        value = str(lead.contact_value or "").strip().lstrip("@")
        if value and value != "unknown" and not value.lstrip("-").isdigit():
            return value
    for key in (
        "sender_username",
        "resolved_telegram_username",
        "resolved_telegram",
        "telegram",
        "username",
        "tg",
    ):
        value = str(raw.get(key) or "").strip().lstrip("@")
        if value and value != "unknown" and not value.lstrip("-").isdigit():
            return value
    return None


def _profile_link(lead: CustomLead, username: str | None) -> str | None:
    if username:
        return f"https://t.me/{username}"
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    for key in ("sender_id", "resolved_telegram_id", "telegram_id", "tg_id"):
        value = str(raw.get(key) or "").strip()
        if value.lstrip("-").isdigit():
            return f"tg://user?id={value}"
    if (lead.contact_type or "") == "telegram":
        value = str(lead.contact_value or "").strip()
        if value.lstrip("-").isdigit():
            return f"tg://user?id={value}"
    return None


def _format_lead_when(lead: CustomLead) -> str:
    from .work_mode import moscow_now

    stamp = getattr(lead, "created_at", None) or _utc_now()
    return moscow_now(stamp).strftime("%d.%m.%Y %H:%M")


def _source_lines(lead: CustomLead) -> list[str]:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    source = str(lead.source or "").strip()
    if source == "chat_monitoring":
        title = str(raw.get("chat_title") or "").strip()
        lines = [f"Источник: чат «{title}»" if title else "Источник: перехват в чате"]
        link = str(raw.get("chat_link") or "").strip()
        if link:
            lines.append(f"Чат: {link}")
        return lines
    if source == "dmp_one":
        return ["Источник: DMP.one"]
    if source == "sasha_ai":
        return ["Источник: звонок Sasha AI"]
    if source:
        return [f"Источник: {source}"]
    return []


def _sasha_blob(lead: CustomLead, override: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(override, dict):
        return override
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    blob = raw.get("sasha")
    return blob if isinstance(blob, dict) else {}


def _warmth_label(quality: int | None) -> str:
    if quality is None:
        return ""
    if quality >= 7:
        return "горячий"
    if quality >= 4:
        return "тёплый"
    return "холодный"


def _sasha_card_lines(lead: CustomLead, blob: dict[str, Any]) -> list[str]:
    """Phone-call block on the same card as chat and DMP leads."""
    quality = blob.get("lead_quality")
    if quality is None:
        quality = getattr(lead, "sasha_lead_quality", None)
    try:
        quality = int(quality) if quality is not None and quality != "" else None
    except (TypeError, ValueError):
        quality = None
    facts = str(blob.get("client_facts") or "").strip()
    agreements = str(blob.get("agreements") or "").strip()
    destination = str(blob.get("lead_destination") or "").strip()
    transcript = str(blob.get("transcript") or "").strip()
    record = str(blob.get("record_url") or "").strip()
    committed = bool(blob.get("is_commit") or getattr(lead, "sasha_is_commit", False))
    if not any((quality is not None, facts, agreements, destination, transcript, record, committed)):
        return []
    lines = ["Квалификация: звонок Sasha AI"]
    if quality is not None:
        warmth = _warmth_label(quality)
        lines.append(f"Прогрев: {quality}/10 ({warmth})" if warmth else f"Прогрев: {quality}/10")
    if agreements:
        lines.append(f"Договорённость: {agreements}")
    if destination:
        lines.append(f"Следующий шаг: {destination}")
    if transcript:
        lines.append("Звонок:")
        lines.append(transcript[:2500])
    if record:
        lines.append(f"Запись: {record}")
    return lines


def _need_text(lead: CustomLead) -> str:
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    for key in ("source_text", "need", "topic", "reason"):
        value = str(raw.get(key) or "").strip()
        if value and value not in {"queued", "llm_error"}:
            return value[:1000]
    return ""


def format_lead_bot_message(
    lead: CustomLead,
    *,
    conversation: str = "",
    handoff_reason: str | None = None,
    sasha: dict[str, Any] | None = None,
) -> str:
    """One card for chat intercept, DMP and a finished Sasha AI call."""
    from .dmp_one_service import lead_phone
    from .lead_delivery_service import HANDOFF_DMP_NO_REPLY, HANDOFF_DMP_WARMED

    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    blob = _sasha_blob(lead, sasha)
    lines = [_format_lead_when(lead)]
    lines.extend(_source_lines(lead))
    username = lead_telegram_username(lead)
    if username:
        lines.append(f"Username: @{username}")
    profile = _profile_link(lead, username)
    if profile:
        lines.append(f"Профиль: {profile}")
    phone = lead_phone(lead)
    if not phone and (getattr(lead, "contact_type", None) or "") == "phone":
        phone = str(getattr(lead, "contact_value", None) or "").strip() or None
    if phone:
        lines.append(f"Телефон: {phone}")
    name = str(
        getattr(lead, "full_name", None)
        or blob.get("client_name")
        or raw.get("sender_name")
        or raw.get("name")
        or raw.get("fio")
        or ""
    ).strip()
    if name:
        lines.append(f"Имя: {name}")
    company = str(getattr(lead, "company", None) or raw.get("company") or "").strip()
    if company:
        lines.append(f"Компания: {company}")
    website = str(raw.get("website") or blob.get("website") or "").strip()
    if website and website != company:
        lines.append(f"Сайт: {website}")
    page = str(raw.get("page") or getattr(lead, "position", None) or "").strip()
    if page:
        lines.append(f"Страница: {page}")
    need = _need_text(lead) or str(blob.get("client_facts") or "").strip()
    if need:
        lines.append(f"Что нужно: {need}")
    if handoff_reason == HANDOFF_DMP_NO_REPLY:
        lines.append("Статус: не ответил, нужен дозвон")
    elif handoff_reason == HANDOFF_DMP_WARMED:
        lines.append("Статус: был контакт, лид прогрет")
    lines.extend(_sasha_card_lines(lead, blob))
    context = (conversation or "").strip()
    if context:
        lines.append("Разговор:")
        lines.append(context[:2500])
    if len(lines) <= 1:
        fallback = str(lead.contact_value or "").strip() or "Новый лид"
        lines.append(fallback)
    return "\n".join(lines)


def format_handoff_lead_message(
    lead: CustomLead,
    *,
    agreed: bool = True,
    conversation: str = "",
    handoff_reason: str | None = None,
) -> str:
    del agreed
    return format_lead_bot_message(lead, conversation=conversation, handoff_reason=handoff_reason)


def format_dmp_lead_message(lead: CustomLead) -> str:
    return format_lead_bot_message(lead)


def decrypt_bot_token(automation: CustomAutomation) -> str | None:
    blob = (automation.telegram_bot_token_enc or "").strip()
    if not blob:
        return None
    try:
        token = crypto_utils.decrypt_token(blob).strip()
    except Exception:
        return None
    return token or None


def bot_webhook_secret_ok(automation: CustomAutomation | None, incoming: str, header_token: str = "") -> bool:
    expected = ((automation.telegram_bot_webhook_secret if automation else None) or "").strip()
    if not expected:
        return False
    path_ok = secrets.compare_digest(incoming or "", expected)
    if not header_token:
        return path_ok
    return path_ok and secrets.compare_digest(header_token, expected)


async def _telegram_api(token: str, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{TELEGRAM_API}{quote(token, safe='')}/{method}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload or {})
            data = response.json() if response.content else {}
    except Exception as exc:
        return {"ok": False, "description": str(exc)[:200]}
    if not isinstance(data, dict):
        return {"ok": False, "description": "invalid telegram response"}
    return data


async def connect_telegram_bot(automation: CustomAutomation, token: str) -> dict[str, Any]:
    token = (token or "").strip()
    if not token:
        raise ValueError("Укажите API-ключ бота")
    me = await _telegram_api(token, "getMe")
    if not me.get("ok"):
        raise ValueError(me.get("description") or "Не удалось проверить бота")
    username = str((me.get("result") or {}).get("username") or "")
    secret = ensure_bot_webhook_secret(automation)
    webhook_url = public_bot_webhook_url(automation.id, secret)
    if not webhook_url:
        raise ValueError("BASE_URL не задан — нельзя поставить webhook бота")
    hooked = await _telegram_api(
        token,
        "setWebhook",
        {"url": webhook_url, "secret_token": secret, "drop_pending_updates": False},
    )
    if not hooked.get("ok"):
        raise ValueError(hooked.get("description") or "Не удалось установить webhook")
    automation.telegram_bot_token_enc = crypto_utils.encrypt_token(token)
    automation.telegram_bot_username = username or None
    automation.updated_at = _utc_now()
    return {"username": username, "webhook_url": webhook_url}


async def disconnect_telegram_bot(automation: CustomAutomation) -> None:
    token = decrypt_bot_token(automation)
    if token:
        try:
            await _telegram_api(token, "deleteWebhook")
        except Exception as exc:
            logger.warning("deleteWebhook failed for automation %s: %s", automation.id, exc)
    automation.telegram_bot_token_enc = None
    automation.telegram_bot_username = None
    automation.updated_at = _utc_now()


async def send_bot_message(token: str, chat_id: int, text: str) -> dict[str, Any]:
    last: dict[str, Any] = {"ok": False}
    for attempt in range(SEND_ATTEMPTS):
        result = await _telegram_api(token, "sendMessage", {"chat_id": chat_id, "text": text})
        last = result if isinstance(result, dict) else {"ok": False}
        if last.get("ok"):
            return last
        description = str(last.get("description") or "")
        if _is_permanent_telegram_error(description):
            logger.warning("Telegram sendMessage permanent fail chat %s: %s", chat_id, description)
            return last
        if attempt + 1 < SEND_ATTEMPTS:
            await asyncio.sleep(0.4 * (attempt + 1))
    logger.warning("Telegram sendMessage failed chat %s: %s", chat_id, last.get("description"))
    return last


def _is_permanent_telegram_error(description: str) -> bool:
    text = (description or "").lower()
    return any(
        needle in text
        for needle in (
            "bot was blocked",
            "forbidden",
            "chat not found",
            "user is deactivated",
            "bot can't initiate",
        )
    )


def _notified_chat_ids(lead: CustomLead) -> list[int]:
    raw = lead.bot_notified_chat_ids or []
    ids: list[int] = []
    for item in raw:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _sheets_configured(automation: CustomAutomation) -> bool:
    if not parse_spreadsheet_id(automation.google_sheets_spreadsheet_id):
        return False
    try:
        return decrypt_service_account(automation) is not None
    except Exception:
        return False


async def restore_telegram_webhook(automation: CustomAutomation) -> dict[str, Any]:
    """Re-bind webhook after container restart. Never drops pending updates or subscribers."""
    token = decrypt_bot_token(automation)
    if not token:
        return {"ok": False, "reason": "no_token"}
    secret = ensure_bot_webhook_secret(automation)
    webhook_url = public_bot_webhook_url(automation.id, secret)
    if not webhook_url:
        return {"ok": False, "reason": "no_base_url"}
    info = await _telegram_api(token, "getWebhookInfo")
    current = str(((info.get("result") or {}) if isinstance(info, dict) else {}).get("url") or "")
    if current == webhook_url:
        return {"ok": True, "unchanged": True, "webhook_url": webhook_url}
    hooked = await _telegram_api(
        token,
        "setWebhook",
        {"url": webhook_url, "secret_token": secret, "drop_pending_updates": False},
    )
    if not hooked.get("ok"):
        logger.warning(
            "Failed to restore Telegram webhook for automation %s: %s",
            automation.id,
            hooked.get("description"),
        )
        return {"ok": False, "reason": hooked.get("description") or "setWebhook failed"}
    logger.info("Restored Telegram webhook for automation %s", automation.id)
    return {"ok": True, "restored": True, "webhook_url": webhook_url}


async def restore_all_telegram_webhooks() -> dict[str, Any]:
    restored = 0
    skipped = 0
    async with async_session_maker() as session:
        result = await session.execute(
            select(CustomAutomation).where(CustomAutomation.telegram_bot_token_enc.is_not(None))
        )
        automations = list(result.scalars().all())
        for automation in automations:
            try:
                info = await restore_telegram_webhook(automation)
                if info.get("ok"):
                    restored += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
                logger.exception("Webhook restore failed for automation %s", automation.id)
        await session.commit()
    return {"restored": restored, "skipped": skipped, "total": len(automations)}


async def _deliver_bot(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
    *,
    text: str | None = None,
) -> dict[str, Any]:
    token = decrypt_bot_token(automation)
    if not token:
        return {"sent": 0, "pending": True, "reason": "no_token"}
    already = set(_notified_chat_ids(lead))
    result = await session.execute(
        select(CustomBotSubscriber).where(
            CustomBotSubscriber.custom_automation_id == automation.id,
            CustomBotSubscriber.status == "subscribed",
        )
    )
    subscribers = list(result.scalars().all())
    if not subscribers:
        return {"sent": 0, "pending": True, "reason": "no_subscribers"}

    body = text or format_dmp_lead_message(lead)
    sent = 0
    now = _utc_now()
    for subscriber in subscribers:
        chat_id = int(subscriber.telegram_chat_id)
        if chat_id in already:
            continue
        response = await send_bot_message(token, chat_id, body)
        if response.get("ok"):
            already.add(chat_id)
            sent += 1
            continue
        if _is_permanent_telegram_error(str(response.get("description") or "")):
            subscriber.status = "idle"
            subscriber.updated_at = now
            logger.warning("Unsubscribed chat %s after permanent Telegram error", chat_id)

    lead.bot_notified_chat_ids = sorted(already)
    remaining = [row for row in subscribers if int(row.telegram_chat_id) not in already and row.status == "subscribed"]
    if not remaining and already:
        lead.bot_notified_at = now
    return {"sent": sent, "pending": bool(remaining) or not already}


async def _deliver_sheets(session: AsyncSession, automation: CustomAutomation, lead: CustomLead) -> dict[str, Any]:
    if lead.sheets_synced_at:
        return {"ok": True, "skipped": True}
    if not _sheets_configured(automation):
        return {"ok": False, "reason": "sheets_not_configured"}
    try:
        sheets = await ensure_header_and_append(session, automation, lead)
    except Exception as exc:
        logger.warning("Google Sheets append failed for lead %s: %s", lead.id, exc)
        return {"ok": False, "reason": str(exc)[:200]}
    if sheets.get("ok"):
        lead.sheets_synced_at = _utc_now()
    return sheets


def _is_locked(subscriber: CustomBotSubscriber) -> bool:
    if not subscriber.locked_until:
        return False
    return subscriber.locked_until > _utc_now()


async def _get_or_create_subscriber(
    session: AsyncSession,
    automation_id: int,
    chat_id: int,
    username: str | None,
) -> CustomBotSubscriber:
    row = await session.scalar(
        select(CustomBotSubscriber).where(
            CustomBotSubscriber.custom_automation_id == automation_id,
            CustomBotSubscriber.telegram_chat_id == chat_id,
        )
    )
    now = _utc_now()
    if row:
        if username:
            row.telegram_username = username
        row.last_message_at = now
        row.updated_at = now
        return row
    row = CustomBotSubscriber(
        custom_automation_id=automation_id,
        telegram_chat_id=chat_id,
        telegram_username=username,
        status="idle",
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def _mark_failure(subscriber: CustomBotSubscriber, *, password_only: bool = False) -> str:
    subscriber.failed_attempts = (subscriber.failed_attempts or 0) + 1
    subscriber.pending_username = None
    subscriber.pending_started_at = None
    subscriber.status = "idle"
    subscriber.updated_at = _utc_now()
    if subscriber.failed_attempts >= MAX_FAILED_ATTEMPTS:
        subscriber.locked_until = _utc_now() + timedelta(minutes=LOCK_MINUTES)
        subscriber.status = "locked"
        return f"Слишком много попыток. Подождите {LOCK_MINUTES} минут."
    left = MAX_FAILED_ATTEMPTS - subscriber.failed_attempts
    if password_only:
        return f"Неверный пароль. Осталось попыток: {left}."
    return f"Неверный логин или пароль. Осталось попыток: {left}."


async def _verify_credentials(
    session: AsyncSession,
    automation_id: int,
    username: str,
    password: str,
) -> bool:
    credential = await session.scalar(
        select(CustomAutomationCredential).where(
            CustomAutomationCredential.custom_automation_id == automation_id,
            CustomAutomationCredential.username == username,
            CustomAutomationCredential.is_active.is_(True),
        )
    )
    if not credential:
        return False
    try:
        return bool(verify_password(password, credential.password_hash))
    except Exception:
        return False


async def handle_bot_update(
    session: AsyncSession,
    automation: CustomAutomation,
    payload: dict[str, Any],
) -> dict[str, Any]:
    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return {"ok": True, "ignored": True}
    chat_id = int(chat_id)
    username = ((message.get("from") or {}).get("username") or "").strip() or None
    text = str(message.get("text") or "").strip()
    token = decrypt_bot_token(automation)
    if not token:
        return {"ok": False, "reason": "bot_not_configured"}

    subscriber = await _get_or_create_subscriber(session, automation.id, chat_id, username)
    reply = await _next_auth_reply(session, automation, subscriber, text)
    status = subscriber.status
    await session.commit()
    if reply:
        await send_bot_message(token, chat_id, reply)
    return {"ok": True, "status": status}


async def _next_auth_reply(
    session: AsyncSession,
    automation: CustomAutomation,
    subscriber: CustomBotSubscriber,
    text: str,
) -> str:
    lowered = text.lower()
    if _is_locked(subscriber):
        return f"Слишком много попыток. Подождите {LOCK_MINUTES} минут."
    if subscriber.locked_until and subscriber.locked_until <= _utc_now():
        subscriber.locked_until = None
        subscriber.failed_attempts = 0
        subscriber.status = "idle"

    if uses_password_gate(automation):
        return await _next_password_reply(automation, subscriber, text)

    if lowered in {"/stop", "стоп"}:
        subscriber.status = "idle"
        subscriber.pending_username = None
        subscriber.pending_started_at = None
        subscriber.authenticated_at = None
        subscriber.updated_at = _utc_now()
        return "Уведомления выключены. Чтобы включить снова — логин, затем пароль."

    if subscriber.status == "subscribed":
        if lowered in {"/start", "старт"}:
            return "Уведомления уже включены."
        return ""

    if lowered in {"/start", "старт"} or not text:
        subscriber.status = "idle"
        subscriber.pending_username = None
        subscriber.pending_started_at = None
        subscriber.updated_at = _utc_now()
        return "Введите логин"

    if subscriber.status != "awaiting_password":
        subscriber.status = "awaiting_password"
        subscriber.pending_username = text[:64]
        subscriber.pending_started_at = _utc_now()
        subscriber.updated_at = _utc_now()
        return "Введите пароль"

    started = subscriber.pending_started_at
    if started and (_utc_now() - started).total_seconds() > PASSWORD_WAIT_SECONDS:
        subscriber.status = "idle"
        subscriber.pending_username = None
        subscriber.pending_started_at = None
        subscriber.updated_at = _utc_now()
        return "Время вышло. Введите логин ещё раз."

    login = (subscriber.pending_username or "").strip()
    ok = await _verify_credentials(session, automation.id, login, text)
    if not ok:
        return await _mark_failure(subscriber)

    subscriber.status = "subscribed"
    subscriber.pending_username = None
    subscriber.pending_started_at = None
    subscriber.failed_attempts = 0
    subscriber.locked_until = None
    subscriber.authenticated_at = _utc_now()
    subscriber.updated_at = _utc_now()
    return "Готово. Буду присылать новых лидов."


async def _next_password_reply(
    automation: CustomAutomation,
    subscriber: CustomBotSubscriber,
    text: str,
) -> str:
    lowered = text.lower()
    if lowered in {"/stop", "стоп"}:
        subscriber.status = "idle"
        subscriber.pending_username = None
        subscriber.pending_started_at = None
        subscriber.authenticated_at = None
        subscriber.updated_at = _utc_now()
        return "Уведомления выключены. Чтобы включить снова — отправьте пароль."

    if subscriber.status == "subscribed":
        if lowered in {"/start", "старт"}:
            return "Уведомления уже включены."
        return ""

    if lowered in {"/start", "старт"} or not text:
        subscriber.status = "awaiting_password"
        subscriber.pending_started_at = _utc_now()
        subscriber.updated_at = _utc_now()
        return "Введите пароль"

    if subscriber.status != "awaiting_password":
        subscriber.status = "awaiting_password"
        subscriber.pending_started_at = _utc_now()
        subscriber.updated_at = _utc_now()

    started = subscriber.pending_started_at
    if started and (_utc_now() - started).total_seconds() > PASSWORD_WAIT_SECONDS:
        subscriber.status = "awaiting_password"
        subscriber.pending_started_at = _utc_now()
        subscriber.updated_at = _utc_now()
        return "Время вышло. Введите пароль ещё раз."

    hashed = (getattr(automation, "telegram_bot_password_hash", None) or "").strip()
    try:
        ok = bool(hashed) and verify_password(text, hashed)
    except Exception:
        ok = False
    if not ok:
        return await _mark_failure(subscriber, password_only=True)

    subscriber.status = "subscribed"
    subscriber.pending_username = None
    subscriber.pending_started_at = None
    subscriber.failed_attempts = 0
    subscriber.locked_until = None
    subscriber.authenticated_at = _utc_now()
    subscriber.updated_at = _utc_now()
    return "Готово. Буду присылать новых лидов."


async def count_subscribers(session: AsyncSession, automation_id: int) -> int:
    return await session.scalar(
        select(func.count(CustomBotSubscriber.id)).where(
            CustomBotSubscriber.custom_automation_id == automation_id,
            CustomBotSubscriber.status == "subscribed",
        )
    ) or 0


async def dispatch_dmp_notifications(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
) -> dict[str, Any]:
    from .lead_delivery_service import lead_conversation_text

    conversation = await lead_conversation_text(session, lead.id)
    bot = await _deliver_bot(
        session,
        automation,
        lead,
        text=format_lead_bot_message(lead, conversation=conversation),
    )
    sheets = await _deliver_sheets(session, automation, lead)
    now = _utc_now()
    lead.status = LeadStatus.TRANSFERRED.value
    lead.transferred_at = lead.transferred_at or now
    lead.status_history = (lead.status_history or []) + [
        {
            "status": LeadStatus.TRANSFERRED.value,
            "changed_at": now.isoformat(),
            "bot_sent": bot.get("sent") or 0,
            "bot_pending": bool(bot.get("pending")),
            "sheets": sheets.get("ok"),
        }
    ]
    lead.updated_at = now
    await session.commit()
    return {"transferred": True, "bot_sent": bot.get("sent") or 0, "bot_pending": bool(bot.get("pending")), "sheets": sheets}


async def dispatch_sales_bot_notification(
    session: AsyncSession,
    automation: CustomAutomation,
    lead: CustomLead,
    *,
    handoff_reason: str | None = None,
) -> dict[str, Any]:
    from .lead_delivery_service import lead_conversation_text

    conversation = await lead_conversation_text(session, lead.id)
    text = format_lead_bot_message(
        lead,
        conversation=conversation,
        handoff_reason=handoff_reason,
    )
    bot = await _deliver_bot(session, automation, lead, text=text)
    now = _utc_now()
    if bot.get("sent") and not lead.transferred_at:
        lead.status = LeadStatus.TRANSFERRED.value
        lead.transferred_at = now
        lead.status_history = (lead.status_history or []) + [
            {
                "status": LeadStatus.TRANSFERRED.value,
                "changed_at": now.isoformat(),
                "channel": "telegram_bot",
                "handoff_reason": handoff_reason,
                "bot_sent": bot.get("sent") or 0,
            }
        ]
        lead.updated_at = now
    await session.commit()
    return {"transferred": bool(lead.transferred_at), "bot_sent": bot.get("sent") or 0, "bot_pending": bool(bot.get("pending"))}


def _lead_needs_notify(automation: CustomAutomation, lead: CustomLead) -> bool:
    if not lead.bot_notified_at:
        return True
    if not lead.sheets_synced_at and _sheets_configured(automation):
        return True
    return False


async def retry_pending_dmp_notifications(automation_id: int) -> dict[str, Any]:
    """Push missed bot/sheet deliveries after downtime. Does not require /start."""
    from .solution_templates import is_dmp_notify_pipeline

    retried = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"retried": 0, "reason": "automation_not_found"}
        try:
            await restore_telegram_webhook(automation)
        except Exception:
            logger.exception("Webhook restore failed for automation %s", automation_id)
        await session.commit()

        dmp_bot = is_dmp_notify_pipeline(automation)
        if dmp_bot:
            filters = [
                CustomLead.custom_automation_id == automation_id,
                CustomLead.source == "dmp_one",
                or_(
                    CustomLead.bot_notified_at.is_(None),
                    CustomLead.sheets_synced_at.is_(None),
                ),
            ]
        else:
            filters = [
                CustomLead.custom_automation_id == automation_id,
                CustomLead.bot_notified_at.is_(None),
                CustomLead.status.in_(
                    (
                        LeadStatus.QUALIFIED.value,
                        LeadStatus.TRANSFERRED.value,
                        LeadStatus.PROCESSING.value,
                    )
                ),
            ]
        result = await session.execute(
            select(CustomLead.id)
            .where(*filters)
            .order_by(CustomLead.created_at.asc())
            .limit(RETRY_BATCH)
        )
        lead_ids = [row[0] for row in result.all()]
        for lead_id in lead_ids:
            automation = await session.get(CustomAutomation, automation_id)
            lead = await session.get(CustomLead, lead_id)
            if not automation or not lead:
                continue
            if dmp_bot:
                if not _lead_needs_notify(automation, lead):
                    continue
                await dispatch_dmp_notifications(session, automation, lead)
            else:
                if lead.bot_notified_at:
                    continue
                reason = None
                for item in reversed(lead.status_history or []):
                    if isinstance(item, dict) and item.get("handoff_reason"):
                        reason = item.get("handoff_reason")
                        break
                await dispatch_sales_bot_notification(session, automation, lead, handoff_reason=reason)
            retried += 1
    return {"retried": retried}
