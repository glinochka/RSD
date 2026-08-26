"""Chat monitoring: fetch messages, deduplicate, classify leads, send DMs."""
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import (
    apply_entity_metadata,
    is_group_chat,
    is_paused,
    load_own_sender_keys,
    load_shilling_message_ids,
    message_is_own_activity,
)
from .lead_keywords import matched_lead_keyword, normalize_lead_keywords
from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_invite import chat_entity_key
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import ChatJoinStatus, ChatMessage, ChatTarget, CustomAutomation, CustomLead, CustomLeadMessage, CustomPrompt, LeadStatus, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


DEFAULT_TRIGGER_PROMPT = """Ты анализируешь сообщение в Telegram-чате.
Определи, является ли это сообщение заявкой или запросом на услуги (SEO, маркетинг, сайт, автоматизация, CRM, чат-боты и т.п.).

Верни ТОЛЬКО валидный JSON без markdown:
{
  "is_lead": true/false,
  "confidence": 0.0-1.0,
  "reason": "краткое объяснение",
  "contact_type": "telegram",
  "contact_value": "username или id отправителя, если видно"
}

Сообщение:
{text}"""


DEFAULT_RESPONSE_PROMPT = """Напиши короткое дружелюбное сообщение в Telegram ЛС от имени представителя компании.
Ответь на вопрос или предложи помощь по услугам (SEO, маркетинг, сайт, автоматизация, CRM).

Контекст сообщения из чата:
{text}

Максимум 2 предложения, без ссылок и телефонов."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def _load_prompt(session: AsyncSession, automation_id: int, prompt_type: str) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == prompt_type,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    if prompt_type == PromptType.CHAT_MONITORING_TRIGGER.value:
        return DEFAULT_TRIGGER_PROMPT
    if prompt_type == PromptType.CHAT_MONITORING_RESPONSE.value:
        return DEFAULT_RESPONSE_PROMPT
    return ""


async def _classify_message(
    session: AsyncSession,
    automation_id: int,
    text: str,
) -> dict[str, Any]:
    prompt = (await _load_prompt(session, automation_id, PromptType.CHAT_MONITORING_TRIGGER.value)).format(text=text or "")
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        data = _extract_json(response.choices[0].message.content or "")
        return {
            "is_lead": bool(data.get("is_lead", False)),
            "confidence": float(data.get("confidence") or 0.0),
            "reason": str(data.get("reason") or ""),
            "contact_type": str(data.get("contact_type") or "telegram"),
            "contact_value": str(data.get("contact_value") or ""),
        }
    except Exception as exc:
        logger.warning("Message classification failed: %s", exc)
        return {"is_lead": False, "confidence": 0.0, "reason": "llm_error", "contact_type": "telegram", "contact_value": ""}


async def _generate_response(
    session: AsyncSession,
    automation_id: int,
    text: str,
) -> str:
    prompt = (await _load_prompt(session, automation_id, PromptType.CHAT_MONITORING_RESPONSE.value)).format(text=text or "")
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        return (response.choices[0].message.content or "").strip()[:1000]
    except Exception as exc:
        logger.warning("Response generation failed: %s", exc)
        return "Здравствуйте! Увидел ваш вопрос в чате. Готов помочь — напишите, что именно интересует."


async def _get_account_for_chat(session: AsyncSession, chat_target: ChatTarget) -> SocialAccount | None:
    if chat_target.joined_by_account_id:
        account = await session.get(SocialAccount, chat_target.joined_by_account_id)
        if account and account.is_active and not account.is_banned and account.session_file_path:
            return account
    # fallback to any eligible account
    return await select_account_for_action(session, chat_target.custom_automation_id, "commenting")


async def fetch_messages_for_chat(
    session: AsyncSession,
    chat_target: ChatTarget,
    limit: int = 50,
) -> list[dict[str, Any]]:
    account = await _get_account_for_chat(session, chat_target)
    if not account:
        logger.warning("No account to fetch messages for chat %s", chat_target.id)
        return []

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return []

    messages = []
    try:
        async with TelegramAccountClient(str(session_path)) as client:
            entity = await client.get_entity(chat_entity_key(chat_target))
            apply_entity_metadata(chat_target, entity)
            if not is_group_chat(chat_target):
                return []
            history = await client.get_messages(entity, limit=limit)
            for msg in history:
                if not msg or not msg.text:
                    continue
                if getattr(msg, "out", False):
                    continue
                sender = msg.sender
                sender_id = getattr(sender, "id", None)
                sender_username = getattr(sender, "username", None)
                sender_name = " ".join(filter(None, [getattr(sender, "first_name", None), getattr(sender, "last_name", None)])).strip()
                messages.append({
                    "external_message_id": str(msg.id),
                    "external_chat_id": str(getattr(entity, "id", chat_target.external_chat_id) or ""),
                    "sender_id": str(sender_id) if sender_id else None,
                    "sender_username": sender_username,
                    "sender_name": sender_name or sender_username,
                    "text": msg.text,
                    "sent_at": msg.date,
                })
    except Exception as exc:
        logger.warning("Fetch messages for chat %s failed: %s", chat_target.id, exc)

    return messages


async def save_chat_message(
    session: AsyncSession,
    chat_target: ChatTarget,
    data: dict[str, Any],
    *,
    ignore_as: str | None = None,
) -> ChatMessage | None:
    dedup_key = f"telegram:{data['external_chat_id']}:{data['external_message_id']}"

    existing = await session.scalar(
        select(ChatMessage).where(
            ChatMessage.custom_automation_id == chat_target.custom_automation_id,
            ChatMessage.dedup_key == dedup_key,
        )
    )
    if existing:
        return existing

    message = ChatMessage(
        custom_automation_id=chat_target.custom_automation_id,
        chat_target_id=chat_target.id,
        external_message_id=data["external_message_id"],
        external_chat_id=data["external_chat_id"],
        sender_id=data.get("sender_id"),
        sender_username=data.get("sender_username"),
        sender_name=data.get("sender_name"),
        text=data["text"],
        sent_at=data["sent_at"],
        dedup_key=dedup_key,
        is_processed=bool(ignore_as),
        is_duplicate=False,
        matched_intent=ignore_as,
        created_at=_utc_now(),
    )
    session.add(message)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(ChatMessage).where(
                ChatMessage.custom_automation_id == chat_target.custom_automation_id,
                ChatMessage.dedup_key == dedup_key,
            )
        )
        if existing:
            return existing
        return None
    await session.refresh(message)
    return message


async def _send_dm_and_create_lead(
    session: AsyncSession,
    automation_id: int,
    chat_message: ChatMessage,
    classification: dict[str, Any],
) -> bool:
    account = await select_account_for_action(session, automation_id, "dm")
    if not account:
        logger.warning("No trusted account to send DM for message %s", chat_message.id)
        return False

    response_text = await _generate_response(session, automation_id, chat_message.text)

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        logger.warning("DM account session file missing for account %s", account.id)
        return False

    try:
        async with TelegramAccountClient(str(session_path)) as client:
            recipient = chat_message.sender_username or chat_message.sender_id
            if not recipient:
                logger.warning("No recipient for message %s", chat_message.id)
                return False
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.send_message(recipient, response_text),
                action_type="dm",
                target_id=f"chat_message:{chat_message.id}",
                target_type="chat_message",
                payload={"recipient": recipient, "text": response_text},
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("Send DM failed for message %s: %s", chat_message.id, exc)
        return False

    lead = CustomLead(
        custom_automation_id=automation_id,
        source="chat_monitoring",
        contact_type=classification.get("contact_type") or "telegram",
        contact_value=classification.get("contact_value") or chat_message.sender_username or str(chat_message.sender_id) or "unknown",
        full_name=chat_message.sender_name,
        chat_message_id=chat_message.id,
        assigned_account_id=account.id,
        status=LeadStatus.WARMING.value,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(lead)
    await session.flush()

    incoming = CustomLeadMessage(
        custom_lead_id=lead.id,
        direction="incoming",
        text=chat_message.text,
        external_message_id=str(chat_message.external_message_id),
        sent_at=chat_message.sent_at,
        created_at=_utc_now(),
    )
    outgoing = CustomLeadMessage(
        custom_lead_id=lead.id,
        social_account_id=account.id,
        direction="outgoing",
        text=response_text,
        sent_at=_utc_now(),
        created_at=_utc_now(),
    )
    session.add(incoming)
    session.add(outgoing)

    lead.last_message_at = _utc_now()

    chat_message.is_processed = True
    chat_message.processed_by_account_id = account.id
    chat_message.matched_intent = "lead"
    chat_message.trigger_confidence = classification.get("confidence")
    await session.commit()

    automation = await session.get(CustomAutomation, automation_id)
    if automation and not automation.lead_warmup_enabled:
        from .lead_warmup_service import auto_transfer_lead
        await auto_transfer_lead(session, automation_id, lead)
    return True


async def process_unprocessed_messages(
    session: AsyncSession,
    automation_id: int,
    *,
    confidence_threshold: float = 0.6,
) -> dict[str, Any]:
    result = await session.execute(
        select(ChatMessage).where(
            ChatMessage.custom_automation_id == automation_id,
            ChatMessage.is_processed.is_(False),
            ChatMessage.is_duplicate.is_(False),
        ).order_by(ChatMessage.sent_at.asc())
    )
    messages = result.scalars().all()
    own_keys = await load_own_sender_keys(session, automation_id)
    shill_ids_by_chat: dict[int, set[str]] = {}
    automation = await session.get(CustomAutomation, automation_id)
    keywords = normalize_lead_keywords(getattr(automation, "lead_keywords", None) if automation else None)

    leads_created = 0
    errors = 0
    for chat_message in messages:
        try:
            chat_id = chat_message.chat_target_id
            if chat_id not in shill_ids_by_chat:
                shill_ids_by_chat[chat_id] = await load_shilling_message_ids(session, automation_id, chat_id)
            if message_is_own_activity(
                {
                    "external_message_id": chat_message.external_message_id,
                    "sender_username": chat_message.sender_username,
                    "sender_name": chat_message.sender_name,
                    "sender_id": chat_message.sender_id,
                },
                own_keys,
                shill_ids_by_chat[chat_id],
            ):
                chat_message.is_processed = True
                chat_message.matched_intent = "own_activity"
                await session.commit()
                continue
            if not matched_lead_keyword(chat_message.text, keywords):
                chat_message.is_processed = True
                chat_message.matched_intent = "no_keyword"
                await session.commit()
                continue
            classification = await _classify_message(session, automation_id, chat_message.text)
            if classification["is_lead"] and classification["confidence"] >= confidence_threshold:
                success = await _send_dm_and_create_lead(session, automation_id, chat_message, classification)
                if success:
                    leads_created += 1
                else:
                    errors += 1
            else:
                chat_message.is_processed = True
                chat_message.matched_intent = "not_lead"
                chat_message.trigger_confidence = classification["confidence"]
                await session.commit()
        except Exception as exc:
            logger.exception("Processing chat message %s failed: %s", chat_message.id, exc)
            errors += 1

    return {"processed": len(messages), "leads_created": leads_created, "errors": errors}


async def scan_chats_and_process(
    automation_id: int,
    *,
    message_limit: int = 50,
    confidence_threshold: float = 0.6,
) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not automation.is_chat_monitoring_enabled:
            logger.info("Chat monitoring disabled or automation not found for %s", automation_id)
            return {"status": "skipped", "reason": "feature_disabled"}

        result = await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.is_active.is_(True),
                ChatTarget.join_status == ChatJoinStatus.JOINED.value,
                ChatTarget.mode != "inactive",
            )
        )
        chats = result.scalars().all()
        own_keys = await load_own_sender_keys(session, automation_id)

        fetched = 0
        for chat_target in chats:
            if is_paused(chat_target) or not is_group_chat(chat_target):
                continue
            try:
                shill_ids = await load_shilling_message_ids(session, automation_id, chat_target.id)
                messages = await fetch_messages_for_chat(session, chat_target, limit=message_limit)
                if not is_group_chat(chat_target):
                    chat_target.last_scanned_at = _utc_now()
                    chat_target.updated_at = _utc_now()
                    await session.commit()
                    continue
                for data in messages:
                    ignore = "own_activity" if message_is_own_activity(data, own_keys, shill_ids) else None
                    await save_chat_message(session, chat_target, data, ignore_as=ignore)
                chat_target.last_scanned_at = _utc_now()
                chat_target.updated_at = _utc_now()
                await session.commit()
                fetched += len(messages)
            except Exception as exc:
                logger.warning("Scan chat %s failed: %s", chat_target.id, exc)

        processing = await process_unprocessed_messages(session, automation_id, confidence_threshold=confidence_threshold)
        return {"chats_scanned": len(chats), "messages_fetched": fetched, **processing}
