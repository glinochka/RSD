"""Discussion / artificial activity: pool accounts join chats and reply naturally."""
import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import (
    apply_entity_metadata,
    commit_chat_scan,
    is_group_chat,
    is_paused,
    is_public_readable,
    load_own_sender_keys,
    load_shilling_message_ids,
    message_is_own_activity,
)
from .chat_membership_service import (
    account_is_joined,
    ensure_watcher_membership,
    get_reader_account,
    is_chat_watchable,
    list_watchable_chats,
    recover_reader_after_error,
)
from .conversation_guard import sanitize_public_text
from .lead_keywords import matched_lead_keyword, normalize_lead_keywords
from .prompt_service import render_prompt
from .account_pacing import account_should_idle, farm_overlap_active_hours
from .rotation_service import record_successful_send
from .shilling_service import _moscow_day_utc_range
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from .telegram_invite import chat_entity_key
from ...alembic.models import AutomationActionLog, ChatTarget, CustomPrompt, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)


DEFAULT_DISCUSSION_PROMPT = """Ты — обычный участник Telegram-чата. К тебе обратились или задали вопрос в сообщении.
Напиши короткий, естественный, дружелюбный ответ (1-3 предложения). Мягко поделись мнением или опытом, если уместно, но не навязывай продукт и не используй ссылки, промокоды и названия сервисов.

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


async def _skip_chat(session: AsyncSession, chat_target: ChatTarget, reason: str) -> dict[str, Any]:
    await commit_chat_scan(session, chat_target)
    return {"status": "skipped", "reason": reason}


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def _load_prompt(session: AsyncSession, automation_id: int, prompt_id: int | None = None) -> str:
    if prompt_id:
        prompt = await session.get(CustomPrompt, prompt_id)
        if (
            prompt
            and prompt.custom_automation_id == automation_id
            and prompt.prompt_type == PromptType.DISCUSSION_REPLY.value
            and prompt.content
        ):
            return str(prompt.content).strip()
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


def _as_int_list(raw: Any) -> list[int]:
    items: list[int] = []
    seen: set[int] = set()
    for value in raw or []:
        try:
            ident = int(value)
        except (TypeError, ValueError):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ident)
    return items


def _delay_bounds(run_config: dict[str, Any] | None) -> tuple[float, float]:
    cfg = run_config or {}
    try:
        low = int(cfg.get("delay_before_min") if cfg.get("delay_before_min") is not None else 20)
    except (TypeError, ValueError):
        low = 20
    try:
        high = int(cfg.get("delay_before_max") if cfg.get("delay_before_max") is not None else 60)
    except (TypeError, ValueError):
        high = 60
    low = max(0, min(low, 3600))
    high = max(low, min(high, 3600))
    return float(low), float(high)


def _message_age_seconds(message, *, now: datetime | None = None) -> float | None:
    raw = getattr(message, "date", None)
    if not isinstance(raw, datetime):
        return None
    posted = raw.astimezone(timezone.utc).replace(tzinfo=None) if raw.tzinfo is not None else raw
    current = now or _utc_now()
    return max(0.0, (current - posted).total_seconds())


async def _generate_reply(
    session: AsyncSession,
    automation_id: int,
    *,
    message_text: str,
    chat_title: str,
    prompt_id: int | None = None,
    reply_condition: str = "",
    context: str = "",
) -> str:
    prompt = render_prompt(
        await _load_prompt(session, automation_id, prompt_id),
        {
            "message_text": message_text or "",
            "chat_title": chat_title or "",
        },
    )
    extras: list[str] = []
    condition = (reply_condition or "").strip()
    if condition:
        extras.append(
            f"Отвечай только если сообщение подходит под условие: {condition}. "
            'Если не подходит — верни {"reply": ""}.'
        )
    if (context or "").strip():
        extras.append(f"Недавние сообщения чата:\n{context.strip()}")
    if extras:
        prompt = f"{prompt}\n\n" + "\n\n".join(extras)
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.8,
        )
        data = _extract_json(response.choices[0].message.content or "")
        reply = sanitize_public_text(str(data.get("reply") or "").strip())
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


def _is_active_hour(
    config: dict,
    *,
    respect_night: bool = True,
    work_always: bool = False,
) -> bool:
    if respect_night and not farm_overlap_active_hours():
        return False
    if work_always:
        return True
    activity_hours = config.get("activity_hours") or []
    if not activity_hours:
        return True
    from .account_pacing import moscow_now
    hour = moscow_now().hour
    for window in activity_hours:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            continue
        start, end = int(window[0]), int(window[1])
        if start <= hour <= end:
            return True
    return False


async def _count_replies_today(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    now: datetime | None = None,
) -> int:
    start, end = _moscow_day_utc_range(now=now)
    count = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "discussion",
            AutomationActionLog.result == "success",
            AutomationActionLog.target_id.like(f"{chat_target_id}:%"),
            AutomationActionLog.created_at >= start,
            AutomationActionLog.created_at < end,
        )
    )
    return int(count or 0)


async def _already_replied_today(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    now: datetime | None = None,
) -> bool:
    return await _count_replies_today(session, automation_id, chat_target_id, now=now) > 0


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
    if not account or not account.is_active or account.is_banned or getattr(account, "is_frozen", False):
        return None
    if account_should_idle(account):
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
            from .human_dm import human_send_public

            sent = await execute_with_telegram_retry(
                session,
                account,
                lambda: human_send_public(
                    client,
                    entity,
                    text,
                    reply_to=message.id,
                    lab_mode=False,
                ),
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

    record_successful_send(account)

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
    run_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = run_config if isinstance(run_config, dict) else {}
    only_joined = bool(cfg.get("only_joined"))
    if is_paused(chat_target):
        return await _skip_chat(session, chat_target, "paused")
    if not is_group_chat(chat_target):
        return await _skip_chat(session, chat_target, "channel")
    if not await is_chat_watchable(session, chat_target):
        if not only_joined:
            await ensure_watcher_membership(session, automation_id, chat_target)
        return await _skip_chat(session, chat_target, "not_watchable")

    try:
        chat_limit = max(1, min(20, int(cfg.get("max_per_chat") or 1)))
    except (TypeError, ValueError):
        chat_limit = 1
    if await _count_replies_today(session, automation_id, chat_target.id) >= chat_limit:
        return await _skip_chat(session, chat_target, "daily_limit")

    config = dict(chat_target.discussion_config or {})
    respect_night = bool(cfg.get("respect_night_hours", True))
    work_always = bool(cfg.get("work_always"))
    if not _is_active_hour(config, respect_night=respect_night, work_always=work_always):
        return await _skip_chat(session, chat_target, "activity_hours")

    try:
        probability_pct = int(cfg.get("probability") if cfg.get("probability") is not None else round(float(config.get("reply_probability") or 0.3) * 100))
    except (TypeError, ValueError):
        probability_pct = 30
    probability_pct = max(0, min(100, probability_pct))
    probability = probability_pct / 100.0
    if probability <= 0:
        return await _skip_chat(session, chat_target, "probability_zero")

    try:
        replies_this_run = max(1, min(chat_limit, int(cfg.get("max_replies_per_run") or max_replies_per_run or 1)))
    except (TypeError, ValueError):
        replies_this_run = max_replies_per_run or 1
    reply_mode = str(cfg.get("reply_mode") or "interval").strip().lower()
    keywords = normalize_lead_keywords(cfg.get("keywords"))
    if reply_mode == "triggers" and not keywords:
        return await _skip_chat(session, chat_target, "no_triggers")
    try:
        prompt_id = int(cfg.get("prompt_id")) if cfg.get("prompt_id") else None
    except (TypeError, ValueError):
        prompt_id = None
    try:
        context_depth = max(0, min(20, int(cfg.get("context_depth") if cfg.get("context_depth") is not None else 0)))
    except (TypeError, ValueError):
        context_depth = 0
    reply_condition = str(cfg.get("reply_condition") or "").strip()[:500]
    delay_min, delay_max = _delay_bounds(cfg)
    allowed_accounts = set(_as_int_list(cfg.get("account_ids")))
    blocked_accounts = set(_as_int_list(cfg.get("blacklisted_account_ids")))
    require_proxy = bool(cfg.get("require_proxy"))

    tried: set[int] = set()
    messages = []
    reader = None
    while True:
        reader = await get_reader_account(session, chat_target, exclude_account_ids=tried)
        if not reader or not reader.session_file_path:
            if not only_joined:
                await ensure_watcher_membership(session, automation_id, chat_target)
            return await _skip_chat(session, chat_target, "no_reader")
        tried.add(reader.id)
        if allowed_accounts and reader.id not in allowed_accounts:
            continue
        if reader.id in blocked_accounts:
            continue
        if require_proxy and not getattr(reader, "telegram_proxy", None):
            continue
        session_path = _media_root() / reader.session_file_path
        if not session_path.exists():
            continue
        messages = []
        try:
            async with TelegramAccountClient.for_account(reader) as client:
                entity = await client.get_entity(
                    chat_entity_key(chat_target)
                )
                apply_entity_metadata(chat_target, entity)
                if not is_group_chat(chat_target):
                    return await _skip_chat(session, chat_target, "channel")
                history = await client.client.get_messages(entity, limit=50)
                for msg in history:
                    if not msg or not msg.text or msg.id is None:
                        continue
                    if getattr(msg, "out", False):
                        continue
                    age = _message_age_seconds(msg)
                    if age is None or age > 24 * 3600:
                        continue
                    messages.append(msg)
            break
        except Exception as exc:
            logger.warning("Fetch discussion messages for chat %s failed: %s", chat_target.id, exc)
            if await recover_reader_after_error(session, chat_target, reader, exc):
                continue
            await commit_chat_scan(session, chat_target)
            return {"status": "error", "error": str(exc)}

    account = reader
    if not account or not account.session_file_path:
        return await _skip_chat(session, chat_target, "no_account")
    joined = await account_is_joined(session, chat_target.id, account.id)
    if not joined:
        if only_joined or not is_public_readable(chat_target):
            return await _skip_chat(session, chat_target, "waiting_join")

    messages.sort(key=lambda m: m.id)
    own_keys = await load_own_sender_keys(session, automation_id)
    shill_ids = await load_shilling_message_ids(session, automation_id, chat_target.id)
    sent_today = await _count_replies_today(session, automation_id, chat_target.id)

    sent = 0
    for index, msg in enumerate(messages):
        if sent >= replies_this_run or sent_today + sent >= chat_limit:
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
        age = _message_age_seconds(msg)
        if age is not None and age < random.uniform(delay_min, delay_max):
            continue
        if reply_mode == "triggers" and not matched_lead_keyword(msg.text or "", keywords):
            continue
        if random.random() > probability:
            continue

        chosen = account
        if not chosen or chosen.daily_messages_sent >= max_daily or not chosen.session_file_path:
            continue
        if not await account_is_joined(session, chat_target.id, chosen.id) and (only_joined or not is_public_readable(chat_target)):
            continue

        context = ""
        if context_depth:
            prior = messages[max(0, index - context_depth):index]
            context = "\n".join((item.text or "")[:220] for item in prior if getattr(item, "text", None))

        reply = await _generate_reply(
            session,
            automation_id,
            message_text=msg.text,
            chat_title=chat_target.title or "",
            prompt_id=prompt_id,
            reply_condition=reply_condition,
            context=context,
        )
        if not reply:
            continue

        success = await _send_reply(session, automation_id, chat_target, chosen, msg, reply)
        if success:
            sent += 1
            if chosen is not account:
                await session.commit()

    chat_target.last_scanned_at = _utc_now()
    chat_target.updated_at = _utc_now()
    await session.commit()
    return {"status": "ok", "sent": sent}


async def run_discussion_pass(automation_id: int, run_config: dict[str, Any] | None = None) -> dict[str, Any]:
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
        cfg = run_config if isinstance(run_config, dict) else ((automation.module_settings or {}).get("neurochatting") or {})
        chat_ids = set(_as_int_list(cfg.get("chat_ids")))
        if chat_ids:
            chats = [
                chat
                for chat in (
                    await session.execute(
                        select(ChatTarget).where(
                            ChatTarget.custom_automation_id == automation_id,
                            ChatTarget.id.in_(chat_ids),
                            ChatTarget.black_boxed_at.is_(None),
                        )
                    )
                ).scalars().all()
                if is_group_chat(chat)
            ]
        else:
            chats = [
                chat
                for chat in await list_watchable_chats(
                    session,
                    automation_id,
                    limit=settings.CUSTOM_ACTION_SCAN_BATCH,
                )
                if is_group_chat(chat)
            ]
        for chat_target in chats:
            try:
                res = await process_chat_target(session, automation_id, chat_target, max_daily, run_config=cfg)
                chat_count += 1
                if res.get("sent"):
                    total_sent += int(res["sent"])
            except Exception as exc:
                logger.exception("Discussion failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chat_count, "replies_sent": total_sent}
