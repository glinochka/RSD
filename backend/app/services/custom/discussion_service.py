"""Discussion / artificial activity: pool accounts join chats and reply naturally."""
import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import apply_entity_metadata, is_group_chat, is_lab_chat, is_paused, load_own_sender_keys, load_shilling_message_ids, message_is_own_activity
from .prompt_service import render_prompt
from .rotation_service import select_account_for_action
from .shilling_service import _moscow_day_utc_range
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from .telegram_invite import chat_entity_key
from ...alembic.models import AutomationActionLog, ChatJoinStatus, ChatTarget, CustomPrompt, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


DEFAULT_DISCUSSION_PROMPT = """Ты — обычный участник Telegram-чата. К тебе обратились или задали вопрос в сообщении.
Напиши короткий, естественный, дружелюбный ответ (1-3 предложения). Мягко поделись мнением или опытом, если уместно, но не навязывай продукт и не используй ссылки.

Сообщение:
{message_text}

Контекст чата:
{chat_title}

Верни ТОЛЬКО JSON:
{
  "reply": "текст ответа"
}"""


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


async def _load_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.DISCUSSION_REPLY.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_DISCUSSION_PROMPT


async def _generate_reply(
    session: AsyncSession,
    automation_id: int,
    *,
    message_text: str,
    chat_title: str,
) -> str:
    prompt = render_prompt(
        await _load_prompt(session, automation_id),
        {
            "message_text": message_text or "",
            "chat_title": chat_title or "",
        },
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.8,
        )
        data = _extract_json(response.choices[0].message.content or "")
        reply = str(data.get("reply") or "").strip()
        return reply[:500]
    except Exception as exc:
        logger.warning("Discussion reply generation failed: %s", exc)
        return ""


def _thread_id(message) -> int:
    reply_id = (
        getattr(message, "reply_to_msg_id", None)
        or getattr(getattr(message, "reply_to", None), "reply_to_msg_id", None)
    )
    return int(reply_id or message.id)


def _is_active_hour(config: dict) -> bool:
    activity_hours = config.get("activity_hours") or []
    if not activity_hours:
        return True
    hour = datetime.now(timezone.utc).hour
    for window in activity_hours:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            continue
        start, end = int(window[0]), int(window[1])
        if start <= hour <= end:
            return True
    return False


async def _already_replied_today(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    now: datetime | None = None,
) -> bool:
    start, end = _moscow_day_utc_range(now=now)
    row = await session.scalar(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "discussion",
            AutomationActionLog.result == "success",
            AutomationActionLog.target_id.like(f"{chat_target_id}:%"),
            AutomationActionLog.created_at >= start,
            AutomationActionLog.created_at < end,
        )
    )
    return row is not None


async def _already_replied_to_message(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    external_message_id: int,
) -> bool:
    row = await session.scalar(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "discussion",
            AutomationActionLog.target_type == "chat_message",
            AutomationActionLog.payload.contains({"chat_target_id": chat_target_id, "external_message_id": str(external_message_id)}),
            AutomationActionLog.result == "success",
        )
    )
    return row is not None


async def _assigned_account_for_thread(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    thread_id: int,
    max_daily: int,
) -> SocialAccount | None:
    log = await session.scalar(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "discussion",
            AutomationActionLog.target_type == "chat_thread",
            AutomationActionLog.target_id == f"{chat_target_id}:{thread_id}",
            AutomationActionLog.result == "success",
        ).order_by(AutomationActionLog.created_at.desc())
    )
    if not log or not log.social_account_id:
        return None
    account = await session.get(SocialAccount, log.social_account_id)
    if not account or not account.is_active or account.is_banned:
        return None
    if account.daily_messages_sent >= max_daily:
        return None
    if not account.session_file_path:
        return None
    return account


async def _send_reply(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    account: SocialAccount,
    message,
    text: str,
) -> bool:
    if not account.session_file_path:
        return False
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False

    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(
                chat_entity_key(chat_target)
            )
            sent = await execute_with_telegram_retry(
                session,
                account,
                lambda: client.client.send_message(entity, text, reply_to=message.id),
                action_type="discussion",
                target_id=f"{chat_target.id}:{_thread_id(message)}",
                target_type="chat_message",
                payload={"chat_target_id": chat_target.id, "message_id": message.id, "text": text},
                automation_id=automation_id,
            )
            reply_message_id = getattr(sent, "id", None)
    except Exception as exc:
        logger.warning("Send discussion reply failed for chat %s message %s: %s", chat_target.id, message.id, exc)
        return False

    sender = getattr(message, "sender", None)
    source_author = " ".join(
        filter(None, [getattr(sender, "first_name", None), getattr(sender, "last_name", None)])
    ).strip() or getattr(sender, "username", None)

    log = AutomationActionLog(
        custom_automation_id=automation_id,
        social_account_id=account.id,
        action_type="discussion",
        target_id=f"{chat_target.id}:{_thread_id(message)}",
        target_type="chat_thread",
        result="success",
        payload={
            "chat_target_id": chat_target.id,
            "chat_title": chat_target.title,
            "external_message_id": str(message.id),
            "reply_message_id": str(reply_message_id) if reply_message_id else None,
            "source_text": (getattr(message, "text", None) or "")[:500],
            "source_author": source_author,
            "text": text,
        },
        created_at=_utc_now(),
    )
    session.add(log)
    await session.commit()
    return True


async def process_chat_target(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    max_daily: int,
    *,
    max_replies_per_run: int = 1,
) -> dict[str, Any]:
    if is_paused(chat_target):
        return {"status": "skipped", "reason": "paused"}
    if not is_group_chat(chat_target):
        return {"status": "skipped", "reason": "channel"}
    if chat_target.join_status != ChatJoinStatus.JOINED.value:
        return {"status": "skipped", "reason": "not_joined"}

    if await _already_replied_today(session, automation_id, chat_target.id):
        return {"status": "skipped", "reason": "daily_limit"}

    config = chat_target.discussion_config or {}
    if not _is_active_hour(config):
        return {"status": "skipped", "reason": "activity_hours"}

    probability = float(config.get("reply_probability") or 0.3)
    if probability <= 0:
        return {"status": "skipped", "reason": "probability_zero"}

    account = await select_account_for_action(session, automation_id, "discussion")
    if not account or not account.session_file_path:
        return {"status": "skipped", "reason": "no_account"}

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return {"status": "skipped", "reason": "session_missing"}

    messages = []
    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(
                chat_entity_key(chat_target)
            )
            apply_entity_metadata(chat_target, entity)
            if not is_group_chat(chat_target):
                await session.commit()
                return {"status": "skipped", "reason": "channel"}
            history = await client.client.get_messages(entity, limit=50)
            for msg in history:
                if not msg or not msg.text or msg.id is None:
                    continue
                if getattr(msg, "out", False):
                    continue
                msg_age_hours = (datetime.now(timezone.utc) - msg.date).total_seconds() / 3600
                if msg_age_hours > 24:
                    continue
                messages.append(msg)
    except Exception as exc:
        logger.warning("Fetch discussion messages for chat %s failed: %s", chat_target.id, exc)
        return {"status": "error", "error": str(exc)}

    messages.sort(key=lambda m: m.id)
    own_keys = await load_own_sender_keys(session, automation_id)
    shill_ids = await load_shilling_message_ids(session, automation_id, chat_target.id)

    sent = 0
    for msg in messages:
        if sent >= max_replies_per_run:
            break
        if account.daily_messages_sent >= max_daily:
            break
        sender = getattr(msg, "sender", None)
        sender_username = getattr(sender, "username", None)
        sender_name = " ".join(
            filter(None, [getattr(sender, "first_name", None), getattr(sender, "last_name", None)])
        ).strip()
        if message_is_own_activity(
            {
                "external_message_id": str(msg.id),
                "sender_username": sender_username,
                "sender_name": sender_name or sender_username,
                "sender_id": str(getattr(sender, "id", "") or ""),
            },
            own_keys,
            shill_ids,
        ):
            continue
        if await _already_replied_to_message(session, automation_id, chat_target.id, msg.id):
            continue

        if random.random() > probability:
            continue

        thread_id = _thread_id(msg)
        assigned = await _assigned_account_for_thread(session, automation_id, chat_target.id, thread_id, max_daily)
        chosen = assigned or account
        if not chosen or chosen.daily_messages_sent >= max_daily or not chosen.session_file_path:
            continue

        reply = await _generate_reply(session, automation_id, message_text=msg.text, chat_title=chat_target.title or "")
        if not reply:
            continue

        success = await _send_reply(session, automation_id, chat_target, chosen, msg, reply)
        if success:
            sent += 1
            chosen.daily_messages_sent += 1
            chosen.last_used_at = _utc_now()
            if chosen is not account:
                await session.commit()

    chat_target.last_scanned_at = _utc_now()
    chat_target.updated_at = _utc_now()
    await session.commit()
    return {"status": "ok", "sent": sent}


async def run_discussion_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker
    from ...alembic.models import CustomAutomation

    total_sent = 0
    chat_count = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not automation.is_digital_footprint_enabled:
            logger.info("Digital footprint / discussion disabled or automation not found for %s", automation_id)
            return {"status": "skipped", "reason": "feature_disabled", "chats_processed": 0, "replies_sent": 0}
        max_daily = automation.max_daily_messages_per_account
        result = await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.is_active.is_(True),
                ChatTarget.join_status == ChatJoinStatus.JOINED.value,
                ChatTarget.mode != "inactive",
            )
        )
        chats = [chat for chat in result.scalars().all() if not is_lab_chat(chat)]
        for chat_target in chats:
            try:
                res = await process_chat_target(session, automation_id, chat_target, max_daily)
                chat_count += 1
                if res.get("sent"):
                    total_sent += int(res["sent"])
            except Exception as exc:
                logger.exception("Discussion failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chat_count, "replies_sent": total_sent}
