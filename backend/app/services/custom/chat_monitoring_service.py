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

from .chat_membership_service import get_reader_account, live_joined_chat_ids, recover_reader_after_error
from .chat_scope import (
    apply_entity_metadata,
    is_group_chat,
    is_paused,
    load_own_sender_keys,
    load_shilling_message_ids,
    message_is_own_activity,
)
from .lead_keywords import normalize_lead_keywords, should_classify_lead_text
from .prompt_service import render_prompt
from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_invite import chat_entity_key
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import (
    ChatMessage,
    ChatTarget,
    CustomAutomation,
    CustomLead,
    CustomLeadMessage,
    CustomPrompt,
    LeadStatus,
    PromptType,
    SocialAccount,
)
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


DEFAULT_TRIGGER_PROMPT = """Ты анализируешь сообщение в Telegram-чате.
Нужно понять, ищет ли человек услугу или решение — прямо («мне нужна N») или косвенно
(«кто знает где сделать», «у меня такая проблема, кто сталкивался?»).

Оффер, относительно которого оцениваем заявку (слов оффера в сообщении может не быть):
{offer}

Считай заявкой (is_lead=true), если человек ищет подрядчика, сервис, совет «где сделать» или описывает боль, которую закрывает оффер.
НЕ заявка: флуд, мемы, вакансии в штат, чужая реклама, оффтоп без отношения к офферу.

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


def _naive_utc(value: datetime | None) -> datetime | None:
    """Strip tzinfo for TIMESTAMP WITHOUT TIME ZONE + asyncpg."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


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


def _offer_context(automation: CustomAutomation | None, keywords: list[str] | None = None) -> str:
    parts = [
        getattr(automation, "name", None) or "",
        getattr(automation, "industry", None) or "",
        getattr(automation, "description", None) or "",
    ]
    words = [item for item in (keywords or []) if item]
    if words:
        parts.append("Ключевые темы: " + ", ".join(words[:20]))
    text = "\n".join(part.strip() for part in parts if part and str(part).strip())
    return text or "услуги компании"


async def _classify_message(
    session: AsyncSession,
    automation_id: int,
    text: str,
    *,
    offer: str = "",
) -> dict[str, Any]:
    try:
        template = await _load_prompt(session, automation_id, PromptType.CHAT_MONITORING_TRIGGER.value)
        if "{offer}" not in template:
            template = template.rstrip() + "\n\nОффер (слов оффера в сообщении может не быть):\n{offer}"
        prompt = render_prompt(
            template,
            {"text": text or "", "offer": offer or "услуги компании"},
        )
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


def _response_text_from_llm(raw: str) -> str:
    text = (raw or "").strip()
    try:
        data = _extract_json(text)
        message = str(data.get("message") or "").strip()
        if message:
            return message[:1000]
    except Exception:
        pass
    return text[:1000]


async def _generate_response(
    session: AsyncSession,
    automation_id: int,
    text: str,
) -> str:
    try:
        prompt = render_prompt(
            await _load_prompt(session, automation_id, PromptType.CHAT_MONITORING_RESPONSE.value),
            {"text": text or ""},
        )
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        return _response_text_from_llm(response.choices[0].message.content or "")
    except Exception as exc:
        logger.warning("Response generation failed: %s", exc)
        return "Здравствуйте! Увидел ваш вопрос в чате. Готов помочь — напишите, что именно интересует."


def _account_can_open_session(account: SocialAccount | None) -> bool:
    if account is None or not account.is_active or account.is_banned or getattr(account, "is_frozen", False):
        return False
    if getattr(account, "encrypted_session", None):
        return True
    path = (account.session_file_path or "").strip()
    if not path:
        return False
    return (_media_root() / path).exists()


async def _get_account_for_chat(session: AsyncSession, chat_target: ChatTarget) -> SocialAccount | None:
    """Prefer an account that actually joined this chat, then any reader."""
    account = await get_reader_account(session, chat_target)
    if _account_can_open_session(account):
        return account
    return None


async def list_monitor_chats(session: AsyncSession, automation_id: int) -> list[ChatTarget]:
    """Target groups that already have a live JOINED member."""
    from .chat_monitoring_module_service import runtime_monitor_cfg
    from .task_targets import load_work_pool

    automation = await session.get(CustomAutomation, automation_id)
    cfg = runtime_monitor_cfg(automation)
    joined_ids = live_joined_chat_ids(automation_id)
    work_pool = await load_work_pool(session, automation_id, cfg, task_key="chat_monitoring")
    pool_ids = work_pool.chat_ids if work_pool.active else set()
    filters = [
        ChatTarget.custom_automation_id == automation_id,
        ChatTarget.is_active.is_(True),
        ChatTarget.mode != "inactive",
        ChatTarget.id.in_(joined_ids),
    ]
    if pool_ids:
        filters.append(ChatTarget.id.in_(pool_ids))
    result = await session.execute(select(ChatTarget).where(*filters))
    chats = []
    for chat in result.scalars().all():
        if is_paused(chat) or not is_group_chat(chat):
            continue
        chats.append(chat)
    return chats


async def fetch_messages_for_chat(
    session: AsyncSession,
    chat_target: ChatTarget,
    limit: int = 50,
) -> list[dict[str, Any]]:
    tried: set[int] = set()
    while True:
        account = await get_reader_account(session, chat_target, exclude_account_ids=tried)
        if not account or not _account_can_open_session(account):
            logger.warning("No account to fetch messages for chat %s", chat_target.id)
            return []
        tried.add(account.id)
        messages = []
        try:
            async with TelegramAccountClient.for_account(account) as client:
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
                        "sent_at": _naive_utc(msg.date) or _utc_now(),
                    })
            return messages
        except Exception as exc:
            logger.warning("Fetch messages for chat %s failed: %s", chat_target.id, exc)
            if await recover_reader_after_error(session, chat_target, account, exc):
                continue
            return []


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
        sent_at=_naive_utc(data.get("sent_at")) or _utc_now(),
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


async def _pick_writer_account(session: AsyncSession, automation_id: int) -> SocialAccount | None:
    from .chat_monitoring_module_service import leadgen_restrict_ids

    automation = await session.get(CustomAutomation, automation_id)
    return await select_account_for_action(
        session,
        automation_id,
        "dm",
        restrict_account_ids=leadgen_restrict_ids(automation),
    )


def _dm_recipient(chat_message: ChatMessage) -> str | int | None:
    username = (chat_message.sender_username or "").strip().lstrip("@")
    if username:
        return username
    raw = chat_message.sender_id
    if raw is None or str(raw).strip() == "":
        return None
    text = str(raw).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return text


async def _send_dm_and_create_lead(
    session: AsyncSession,
    automation_id: int,
    chat_message: ChatMessage,
    classification: dict[str, Any],
) -> bool:
    account = await _pick_writer_account(session, automation_id)
    if not account:
        logger.warning("No trusted account to send DM for message %s", chat_message.id)
        return False
    from .chat_monitoring_module_service import runtime_monitor_cfg
    from .daily_quota import account_blocked_for_task

    automation = await session.get(CustomAutomation, automation_id)
    if await account_blocked_for_task(
        session, automation_id, account, "chat_monitoring", runtime_monitor_cfg(automation), default_max=15
    ):
        logger.info("Lead DM skipped, account %s reached today's quota", account.id)
        return False

    response_text = await _generate_response(session, automation_id, chat_message.text)

    if not _account_can_open_session(account):
        logger.warning("DM account session missing for account %s", account.id)
        return False

    profile_phone = None
    try:
        async with TelegramAccountClient.for_account(account) as client:
            recipient = _dm_recipient(chat_message)
            if not recipient:
                logger.warning("No recipient for message %s", chat_message.id)
                return False

            async def _send():
                nonlocal profile_phone
                entity = await client.resolve_peer(recipient)
                phone_raw = getattr(entity, "phone", None)
                if isinstance(phone_raw, str) and phone_raw.strip():
                    profile_phone = phone_raw.strip()
                await client.human_reply(entity, response_text)

            await execute_with_telegram_retry(
                session,
                account,
                _send,
                action_type="dm",
                target_id=f"chat_message:{chat_message.id}",
                target_type="chat_message",
                payload={"recipient": recipient, "text": response_text},
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("Send DM failed for message %s: %s", chat_message.id, exc)
        return False

    chat = await session.get(ChatTarget, chat_message.chat_target_id)
    username = (chat_message.sender_username or "").strip().lstrip("@")
    contact = classification.get("contact_value") or (f"@{username}" if username else None) or str(chat_message.sender_id) or "unknown"
    lead = CustomLead(
        custom_automation_id=automation_id,
        source="chat_monitoring",
        contact_type=classification.get("contact_type") or "telegram",
        contact_value=contact,
        full_name=chat_message.sender_name,
        chat_message_id=chat_message.id,
        assigned_account_id=account.id,
        status=LeadStatus.WARMING.value,
        dmp_raw_data={
            "chat_id": chat_message.chat_target_id,
            "chat_title": getattr(chat, "title", None),
            "chat_link": getattr(chat, "invite_link", None),
            "sender_id": chat_message.sender_id,
            "sender_username": chat_message.sender_username,
            "sender_name": chat_message.sender_name,
            "source_text": (chat_message.text or "")[:1000],
            "reason": classification.get("reason") or "",
            "writer_account_id": account.id,
            "phone": profile_phone,
        },
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
        sent_at=_naive_utc(chat_message.sent_at) or _utc_now(),
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
    from .job_service import actor_label, chat_label, clip_text, log_active

    who = f"@{username}" if username else (chat_message.sender_name or chat_message.sender_id or "лид")
    where = chat_label(chat) if chat is not None else "чат"
    try:
        await log_active(
            automation_id,
            "chat_monitoring",
            f"{actor_label(account)} пишет в ЛС {who} из {where}: «{clip_text(chat_message.text)}»",
        )
    except Exception:
        logger.debug("chat monitoring DM log skipped", exc_info=True)

    automation = await session.get(CustomAutomation, automation_id)
    if automation:
        from .integration_webhook_service import dispatch_event

        await dispatch_event(session, automation, "lead.created", lead)
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
    from .chat_monitoring_module_service import runtime_monitor_cfg
    from .task_targets import load_work_pool

    automation = await session.get(CustomAutomation, automation_id)
    cfg = runtime_monitor_cfg(automation)
    keywords = cfg.get("keywords") or normalize_lead_keywords(
        getattr(automation, "lead_keywords", None) if automation else None
    )
    offer = _offer_context(automation, keywords)
    work_pool = await load_work_pool(session, automation_id, cfg, task_key="chat_monitoring")
    pool_ids = work_pool.chat_ids if work_pool.active else set()

    leads_created = 0
    errors = 0
    for chat_message in messages:
        message_id = chat_message.id
        try:
            chat_id = chat_message.chat_target_id
            if chat_id not in shill_ids_by_chat:
                shill_ids_by_chat[chat_id] = await load_shilling_message_ids(session, automation_id, chat_id)
            if pool_ids and chat_id not in pool_ids:
                chat_message.is_processed = True
                chat_message.matched_intent = "out_of_scope"
                await session.commit()
                continue
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
            if chat_message.matched_intent == "lead_pending":
                classification = {
                    "is_lead": True,
                    "confidence": float(chat_message.trigger_confidence or 0.9),
                    "reason": "queued",
                    "contact_type": "telegram",
                    "contact_value": (chat_message.sender_username or "").strip()
                    or str(chat_message.sender_id or ""),
                }
            else:
                if not should_classify_lead_text(chat_message.text, keywords):
                    chat_message.is_processed = True
                    chat_message.matched_intent = "not_request"
                    await session.commit()
                    continue
                classification = await _classify_message(
                    session, automation_id, chat_message.text, offer=offer
                )
                if not (
                    classification["is_lead"]
                    and classification["confidence"] >= confidence_threshold
                ):
                    chat_message.is_processed = True
                    chat_message.matched_intent = "not_lead"
                    chat_message.trigger_confidence = classification["confidence"]
                    await session.commit()
                    continue
                chat_message.matched_intent = "lead_pending"
                chat_message.trigger_confidence = classification["confidence"]
                await session.commit()
                from .job_service import chat_label, clip_text, log_active

                chat = await session.get(ChatTarget, chat_message.chat_target_id)
                username = (chat_message.sender_username or "").strip().lstrip("@")
                who = f"@{username}" if username else (chat_message.sender_name or chat_message.sender_id or "лид")
                where = chat_label(chat) if chat is not None else "чат"
                try:
                    await log_active(
                        automation_id,
                        "chat_monitoring",
                        f"заявка в {where} от {who}: «{clip_text(chat_message.text)}» — передаём ответственному, ЛС после паузы",
                    )
                except Exception:
                    logger.debug("chat monitoring sighting log skipped", exc_info=True)
            from .account_pacing import farm_overlap_active_hours

            if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
                continue
            from .human_dm import stable_reply_delay_seconds

            sent_at = chat_message.sent_at
            if sent_at is not None:
                if sent_at.tzinfo is not None:
                    import datetime as _dt
                    sent_at = sent_at.astimezone(_dt.timezone.utc).replace(tzinfo=None)
                age_secs = (_utc_now() - sent_at).total_seconds()
                required_delay = stable_reply_delay_seconds(str(chat_message.id))
                if age_secs < required_delay:
                    logger.debug(
                        "Chat monitoring DM for message %s not ready yet (age %.0fs < required %.0fs)",
                        chat_message.id, age_secs, required_delay,
                    )
                    continue
            dm_account = await _pick_writer_account(session, automation_id)
            if not dm_account:
                logger.warning("No trusted account to send DM for message %s", chat_message.id)
                errors += 1
                continue
            success = await _send_dm_and_create_lead(session, automation_id, chat_message, classification)
            if success:
                leads_created += 1
            else:
                errors += 1
        except Exception as exc:
            await session.rollback()
            logger.exception("Processing chat message %s failed: %s", message_id, exc)
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

        chats = await list_monitor_chats(session, automation_id)
        chats.sort(key=lambda item: (item.last_scanned_at is not None, item.last_scanned_at or _utc_now(), item.id))
        chats = chats[: settings.CUSTOM_MONITOR_SCAN_BATCH]
        own_keys = await load_own_sender_keys(session, automation_id)

        fetched = 0
        scanned = 0
        for chat_target in chats:
            scanned += 1
            chat_id = chat_target.id
            try:
                shill_ids = await load_shilling_message_ids(session, automation_id, chat_id)
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
                await session.rollback()
                logger.warning("Scan chat %s failed: %s", chat_id, exc)

        processing = await process_unprocessed_messages(session, automation_id, confidence_threshold=confidence_threshold)
        return {"chats_scanned": scanned, "messages_fetched": fetched, **processing}
