"""Shilling: two distinct userbots talk like real people and natively recommend the client."""
from __future__ import annotations

import json
import logging
import random
import re
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import commit_chat_scan, count_target_actions_today, is_paused, is_group_chat, is_lab_chat
from .chat_membership_service import (
    ensure_watcher_membership,
    is_chat_watchable,
    list_watchable_chats,
)
from .account_pacing import account_active_window, in_account_active_hours
from .pending_action_service import ensure_accounts_ready
from .post_engagement import SHILLING as POST_SHILLING, get_post_engagement_claim, post_target_id
from .rotation_service import accounts_are_distinct, record_successful_send, select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_invite import chat_entity_key
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import (
    AutomationActionLog,
    ChatMessage,
    ChatTarget,
    CustomAutomation,
    CustomPrompt,
    PromptType,
    SocialAccount,
)
from ...config import settings
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

CHAT_WINDOW_START_HOUR = 8
CHAT_WINDOW_END_HOUR = 20
CHAT_SHILL_ACTION = "shilling_chat"
POST_SHILL_ACTION = "shilling_post"
REPLY_DELAY_MIN_SECONDS = 8.0
REPLY_DELAY_MAX_SECONDS = 25.0
COMMENT_REPLY_DELAY_MIN_SECONDS = 5.0
CHAT_SHILL_MIN_MESSAGES = 100
CHAT_SHILL_MAX_IDLE = timedelta(days=7)

DEFAULT_SHILLING_SETUP = "Кто-нибудь уже пробовал сервис, о котором тут пишут? Не хочу влететь."
DEFAULT_SHILLING_REPLY = "Пользуюсь сам уже какое-то время, по работе зашёл. Если надо — могу в личке набросать, как подключался."

LIGHT_VARY_PROMPT = """Слегка измени формулировку двух реплик. Сохрани смысл, тон, длину и все названия/факты.
Это не сильный пересказ: те же мысли чуть другими словами, как будто человек написал заново.
Не усиливай рекламу, не добавляй ссылки, хештеги и новые обещания.

Вопрос:
{setup}

Ответ:
{reply}

Верни ТОЛЬКО JSON:
{{"setup": "...", "reply": "..."}}
"""


def _moscow_tz():
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _moscow_now(now: datetime | None = None) -> datetime:
    tz = _moscow_tz()
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc).astimezone(tz)
    return now.astimezone(tz)


def _moscow_day_utc_range(day=None, now: datetime | None = None) -> tuple[datetime, datetime]:
    moscow = _moscow_now(now)
    day = day or moscow.date()
    start = datetime.combine(day, time.min, tzinfo=_moscow_tz())
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _in_chat_window(
    now: datetime | None = None,
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
) -> bool:
    return in_account_active_hours(now, account, account_id=account_id)


def _random_time_today(
    now_moscow: datetime,
    account: SocialAccount | None = None,
    *,
    account_id: int | None = None,
) -> datetime:
    start_h, end_h = account_active_window(account, account_id=account_id)
    midnight = now_moscow.replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight + timedelta(seconds=int(start_h * 3600))
    end = midnight + timedelta(seconds=int(end_h * 3600))
    span = max(int((end - start).total_seconds()) - 1, 0)
    return start + timedelta(seconds=random.randint(0, span))


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _session_path(account: SocialAccount) -> Path | None:
    if not account.session_file_path:
        return None
    path = _media_root() / account.session_file_path
    return path if path.exists() else None


def parse_shilling_lines(content: str | None) -> tuple[str, str]:
    raw = (content or "").strip()
    if not raw:
        return "", ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        setup = str(data.get("setup") or data.get("question") or "").strip()
        reply = str(data.get("reply") or data.get("answer") or "").strip()
        return setup[:500], reply[:500]
    return "", ""


def encode_shilling_lines(setup: str, reply: str) -> str:
    return json.dumps(
        {"setup": (setup or "").strip(), "reply": (reply or "").strip()},
        ensure_ascii=False,
    )


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def light_vary_shilling_lines(setup: str, reply: str) -> tuple[str, str]:
    """Tiny wording drift so canned shill lines are not byte-identical."""
    source_setup = (setup or "").strip()
    source_reply = (reply or "").strip()
    if not source_setup or not source_reply:
        return source_setup, source_reply
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{
                "role": "user",
                "content": LIGHT_VARY_PROMPT.format(setup=source_setup, reply=source_reply),
            }],
            max_tokens=250,
            temperature=0.45,
        )
        data = _extract_json(response.choices[0].message.content or "")
        varied_setup = str(data.get("setup") or "").strip()[:500]
        varied_reply = str(data.get("reply") or "").strip()[:500]
        if varied_setup and varied_reply:
            return varied_setup, varied_reply
    except Exception as exc:
        logger.warning("Shilling light-vary failed: %s", exc)
    return source_setup, source_reply


async def generate_shilling_dialogue(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    chat_title: str,
    post_text: str = "",
    vary: bool = True,
) -> tuple[str, str]:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation.id,
            CustomPrompt.prompt_type == PromptType.SHILLING.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    setup, reply = parse_shilling_lines(prompt.content if prompt else "")
    if not setup or not reply:
        setup, reply = DEFAULT_SHILLING_SETUP, DEFAULT_SHILLING_REPLY
    if vary:
        setup, reply = await light_vary_shilling_lines(setup, reply)
    return setup, reply


async def _pick_speaker_pair(
    session: AsyncSession,
    automation: CustomAutomation,
    exclude_account_ids: set[int] | None = None,
) -> tuple[SocialAccount, SocialAccount] | None:
    excluded = set(exclude_account_ids or set())
    account_a = await select_account_for_action(
        session,
        automation,
        "shilling_question",
        exclude_account_ids=excluded,
    )
    if account_a is None:
        return None
    excluded.add(account_a.id)
    account_b = await select_account_for_action(
        session,
        automation,
        "shilling_answer",
        exclude_account_ids=excluded,
    )
    if account_b is None or not accounts_are_distinct(account_a, account_b):
        return None
    return account_a, account_b


async def _telegram_ids_distinct(account_a: SocialAccount, account_b: SocialAccount) -> bool:
    path_a = _session_path(account_a)
    path_b = _session_path(account_b)
    if not path_a or not path_b:
        return True
    try:
        async with TelegramAccountClient.for_account(account_a) as client_a:
            me_a = await client_a.client.get_me()
        async with TelegramAccountClient.for_account(account_b) as client_b:
            me_b = await client_b.client.get_me()
        return bool(me_a and me_b and me_a.id != me_b.id)
    except Exception as exc:
        logger.warning("Could not verify shilling telegram identities: %s", exc)
        return True


async def _discussion_entity_for_post(client: TelegramAccountClient, channel_entity: Any, post_id: int) -> Any:
    from telethon import functions

    result = await client(functions.messages.GetDiscussionMessageRequest(peer=channel_entity, msg_id=post_id))
    root = min(result.messages, key=lambda msg: msg.id)
    discussion = next(
        chat
        for chat in result.chats
        if getattr(getattr(root, "peer_id", None), "channel_id", None) == chat.id
    )
    return await client.client.get_input_entity(discussion)


async def _send_message(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    account: SocialAccount,
    text: str,
    *,
    action_type: str,
    target_id: str,
    reply_to: int | None = None,
    comment_to: int | None = None,
    discussion_post_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> int | None:
    path = _session_path(account)
    if not path:
        return None
    try:
        async with TelegramAccountClient.for_account(account) as client:
            channel_entity = await client.get_entity(
                chat_entity_key(chat_target)
            )
            if comment_to is not None or discussion_post_id is not None:
                from .chat_join_service import join_linked_discussion

                await join_linked_discussion(client, channel_entity)

            async def _send():
                from .human_dm import human_send_public

                if discussion_post_id is not None and reply_to is not None:
                    discussion_entity = await _discussion_entity_for_post(
                        client,
                        channel_entity,
                        discussion_post_id,
                    )
                    return await human_send_public(
                        client,
                        discussion_entity,
                        text,
                        reply_to=reply_to,
                        discussion_entity=discussion_entity,
                    )
                return await human_send_public(
                    client,
                    channel_entity,
                    text,
                    comment_to=comment_to,
                    reply_to=reply_to,
                )

            message = await execute_with_telegram_retry(
                session,
                account,
                _send,
                action_type=action_type,
                target_id=target_id,
                target_type="chat_post" if (comment_to is not None or discussion_post_id is not None) else "chat",
                payload=payload or {},
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("Shilling send failed for chat %s account %s: %s", chat_target.id, account.id, exc)
        return None
    message_id = getattr(message, "id", None)
    if message_id:
        record_successful_send(account)
        await session.commit()
    return message_id


async def _log(
    session: AsyncSession,
    *,
    automation_id: int,
    account_id: int,
    action_type: str,
    target_id: str,
    target_type: str,
    result: str,
    payload: dict[str, Any] | None = None,
    error_message: str | None = None,
    created_at: datetime | None = None,
) -> AutomationActionLog:
    log = AutomationActionLog(
        custom_automation_id=automation_id,
        social_account_id=account_id,
        action_type=action_type,
        target_id=target_id,
        target_type=target_type,
        result=result,
        error_message=error_message,
        payload=payload or {},
        created_at=created_at or _utc_now(),
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def _already_succeeded(
    session: AsyncSession,
    automation_id: int,
    action_type: str,
    target_id: str,
) -> bool:
    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == action_type,
            AutomationActionLog.target_id == target_id,
            AutomationActionLog.result == "success",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def perform_shilling_dialogue(
    session: AsyncSession,
    automation: CustomAutomation,
    chat_target: ChatTarget,
    *,
    action_type: str,
    target_id: str,
    target_type: str,
    post_text: str = "",
    comment_to: int | None = None,
    delay_seconds: float | None = None,
    sleep: Callable[[float], Any] | None = None,
) -> dict[str, Any]:
    """Send setup from account A and a reply from account B. Never one userbot to itself."""
    pair = await _pick_speaker_pair(session, automation)
    if not pair:
        return {"status": "skipped", "reason": "need_two_accounts"}
    account_a, account_b = pair
    if not accounts_are_distinct(account_a, account_b):
        return {"status": "skipped", "reason": "same_account"}
    if not await _telegram_ids_distinct(account_a, account_b):
        return {"status": "skipped", "reason": "same_telegram_user"}

    if comment_to is not None:
        from .chat_inspect_service import ensure_comment_access

        if chat_target.comments_open is False:
            return {"status": "skipped", "reason": "comments_closed"}
        for speaker in (account_a, account_b):
            probe = await ensure_comment_access(session, chat_target, speaker)
            if probe.account_blocked:
                return {"status": "skipped", "reason": "account_blocked"}
            if getattr(probe, "chat_read_lost", False):
                from .chat_membership_service import retire_reader_and_replace

                await retire_reader_and_replace(session, chat_target, speaker.id, error=probe.error)
                return {"status": "skipped", "reason": "reader_lost"}
            if probe.comments_open is False:
                return {"status": "skipped", "reason": "comments_closed"}

    ready = await ensure_accounts_ready(
        session,
        automation.id,
        chat_target,
        [account_a, account_b],
        action_type=action_type,
        target_id=target_id,
        payload={"post_text": post_text, "comment_to": comment_to},
    )
    if not ready:
        return {"status": "skipped", "reason": "waiting_join"}

    setup, reply = await generate_shilling_dialogue(
        session,
        automation,
        chat_title=chat_target.title or "",
        post_text=post_text,
    )
    if not setup or not reply:
        return {"status": "skipped", "reason": "empty_dialogue"}

    first_id = await _send_message(
        session,
        automation.id,
        chat_target,
        account_a,
        setup,
        action_type=action_type,
        target_id=target_id,
        comment_to=comment_to,
        payload={
            "role": "setup",
            "text": setup,
            "peer_account_id": account_b.id,
            "chat_target_id": chat_target.id,
            "_mod_probed": False,
        },
    )
    if not first_id:
        return {"status": "error", "reason": "setup_failed"}

    wait_for = delay_seconds
    if wait_for is None:
        wait_for = random.uniform(REPLY_DELAY_MIN_SECONDS, REPLY_DELAY_MAX_SECONDS)
    elif comment_to is not None and wait_for < COMMENT_REPLY_DELAY_MIN_SECONDS:
        wait_for = COMMENT_REPLY_DELAY_MIN_SECONDS
    sleeper = sleep or __import__("asyncio").sleep
    await sleeper(wait_for)

    second_id = await _send_message(
        session,
        automation.id,
        chat_target,
        account_b,
        reply,
        action_type=action_type,
        target_id=target_id,
        reply_to=first_id,
        discussion_post_id=comment_to,
        payload={
            "role": "reply",
            "text": reply,
            "peer_account_id": account_a.id,
            "reply_to": first_id,
            "chat_target_id": chat_target.id,
            "_mod_probed": False,
        },
    )
    if not second_id:
        return {"status": "error", "reason": "reply_failed", "setup_message_id": first_id}

    await _log(
        session,
        automation_id=automation.id,
        account_id=account_a.id,
        action_type=action_type,
        target_id=target_id,
        target_type=target_type,
        result="success",
        payload={
            "setup_account_id": account_a.id,
            "reply_account_id": account_b.id,
            "setup": setup,
            "reply": reply,
            "setup_message_id": first_id,
            "reply_message_id": second_id,
            "comment_to": comment_to,
            "chat_target_id": chat_target.id,
            "_mod_probed": False,
        },
    )
    return {
        "status": "ok",
        "setup_account_id": account_a.id,
        "reply_account_id": account_b.id,
        "setup_message_id": first_id,
        "reply_message_id": second_id,
    }


async def perform_post_shilling(
    session: AsyncSession,
    automation: CustomAutomation,
    chat_target: ChatTarget,
    post_id: int,
    post_text: str = "",
    *,
    lab_mode: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    target_id = post_target_id(chat_target.id, post_id)
    if await _already_succeeded(session, automation.id, POST_SHILL_ACTION, target_id):
        return {"status": "skipped", "reason": "already_sent"}
    target_actions_today = await count_target_actions_today(session, automation.id, chat_target.id)
    if target_actions_today >= chat_target.max_daily_target_actions:
        return {"status": "skipped", "reason": "chat_daily_target_limit"}
    claim = await get_post_engagement_claim(session, automation.id, chat_target.id, post_id)
    if claim and claim.result != POST_SHILLING and not lab_mode:
        return {"status": "skipped", "reason": "other_action", "claimed": claim.result}
    return await perform_shilling_dialogue(
        session,
        automation,
        chat_target,
        action_type=POST_SHILL_ACTION,
        target_id=target_id,
        target_type="chat_post",
        post_text=post_text,
        comment_to=post_id,
        **kwargs,
    )


def _moscow_period_utc_range(days: int, now: datetime | None = None) -> tuple[datetime, datetime]:
    moscow = _moscow_now(now)
    end_date = moscow.date()
    start_date = end_date - timedelta(days=max(days, 1) - 1)
    start = datetime.combine(start_date, time.min, tzinfo=_moscow_tz())
    end = datetime.combine(end_date, time.min, tzinfo=_moscow_tz()) + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


async def get_today_chat_logs(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    now: datetime | None = None,
) -> list[AutomationActionLog]:
    start, end = _moscow_day_utc_range(now=now)
    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == CHAT_SHILL_ACTION,
            AutomationActionLog.target_id == str(chat_target_id),
            AutomationActionLog.created_at >= start,
            AutomationActionLog.created_at < end,
        )
        .order_by(AutomationActionLog.id.asc())
    )
    return list(result.scalars().all())


async def last_successful_chat_shill(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    now: datetime | None = None,
) -> AutomationActionLog | None:
    """Successful chat shill today (Moscow day)."""
    start, end = _moscow_day_utc_range(now=now)
    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == CHAT_SHILL_ACTION,
            AutomationActionLog.target_id == str(chat_target_id),
            AutomationActionLog.result == "success",
            AutomationActionLog.created_at >= start,
            AutomationActionLog.created_at < end,
        )
        .order_by(AutomationActionLog.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def last_successful_chat_shill_ever(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
) -> AutomationActionLog | None:
    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == CHAT_SHILL_ACTION,
            AutomationActionLog.target_id == str(chat_target_id),
            AutomationActionLog.result == "success",
        )
        .order_by(AutomationActionLog.created_at.desc(), AutomationActionLog.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _message_id_from_shill_log(log: AutomationActionLog | None) -> int | None:
    if not log:
        return None
    payload = log.payload or {}
    for key in ("reply_message_id", "setup_message_id"):
        raw = payload.get(key)
        try:
            message_id = int(raw)
        except (TypeError, ValueError):
            continue
        if message_id > 0:
            return message_id
    return None


def chat_shill_activity_allows(
    *,
    last_at: datetime | None,
    messages_since: int | None,
    now: datetime,
    min_messages: int = CHAT_SHILL_MIN_MESSAGES,
    max_idle: timedelta = CHAT_SHILL_MAX_IDLE,
) -> bool:
    """Allow the next chat shill after 100 messages, or after 7 quiet days."""
    if last_at is None:
        return True
    elapsed = _naive_utc(now) - _naive_utc(last_at)
    if elapsed >= max_idle:
        return True
    if messages_since is None:
        return False
    return messages_since >= min_messages


async def _stored_messages_since(
    session: AsyncSession,
    chat_target_id: int,
    since: datetime,
) -> int:
    count = await session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.chat_target_id == chat_target_id,
            ChatMessage.sent_at > since,
        )
    )
    return int(count or 0)


async def _telegram_messages_since(
    account: SocialAccount | None,
    chat_target: ChatTarget,
    after_message_id: int,
    limit: int = CHAT_SHILL_MIN_MESSAGES,
) -> int | None:
    if not account or not after_message_id:
        return None
    path = _session_path(account)
    if not path:
        return None
    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(chat_entity_key(chat_target))
            history = await client.get_messages(entity, min_id=after_message_id, limit=limit)
    except Exception as exc:
        logger.warning("Chat shill activity fetch failed for chat %s: %s", chat_target.id, exc)
        return None
    return sum(1 for msg in (history or []) if msg and getattr(msg, "id", 0) > after_message_id)


async def resolve_chat_shill_messages_since(
    session: AsyncSession,
    chat_target: ChatTarget,
    last_log: AutomationActionLog,
    reader: SocialAccount | None,
    *,
    messages_since: int | None = None,
) -> int | None:
    if messages_since is not None:
        return messages_since
    last_id = _message_id_from_shill_log(last_log)
    if last_id:
        fetched = await _telegram_messages_since(reader, chat_target, last_id)
        if fetched is not None:
            return fetched
    return await _stored_messages_since(session, chat_target.id, last_log.created_at)


async def get_today_chat_decision(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    now: datetime | None = None,
) -> AutomationActionLog | None:
    logs = await get_today_chat_logs(session, automation_id, chat_target_id, now=now)
    if not logs:
        return None
    for log in logs:
        if log.result in {"skip", "success"}:
            return log
    return logs[0]


async def decide_chat_shilling_today(
    session: AsyncSession,
    automation: CustomAutomation,
    chat_target: ChatTarget,
    account_id: int,
    *,
    roll: Callable[[], float] | None = None,
    now: datetime | None = None,
    scheduled_at: datetime | None = None,
) -> str:
    """At most once per Moscow day per chat; random time 08:00–20:00 MSK.

    Returns skip | wait | due | done.
    """
    del roll
    if await last_successful_chat_shill(session, automation.id, chat_target.id, now=now):
        return "done"
    existing = await get_today_chat_decision(session, automation.id, chat_target.id, now=now)
    moscow = _moscow_now(now)
    if existing:
        if existing.result == "success":
            return "done"
        if existing.result == "skip":
            return "skip"
        if existing.result in {"scheduled", "pending"}:
            raw = (existing.payload or {}).get("scheduled_at")
            when = None
            if raw:
                try:
                    when = datetime.fromisoformat(str(raw))
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=_moscow_tz())
                except ValueError:
                    when = None
            if when is None or _moscow_now(when) <= moscow:
                return "due"
            return "wait"
        return existing.result

    if not _in_chat_window(now, account_id=account_id):
        return "wait"

    when = scheduled_at or _random_time_today(moscow, account_id=account_id)
    if when.tzinfo is None:
        when = when.replace(tzinfo=_moscow_tz())
    if when <= moscow:
        await _log(
            session,
            automation_id=automation.id,
            account_id=account_id,
            action_type=CHAT_SHILL_ACTION,
            target_id=str(chat_target.id),
            target_type="chat",
            result="pending",
            payload={"scheduled_at": moscow.isoformat()},
            created_at=moscow.astimezone(timezone.utc).replace(tzinfo=None),
        )
        return "due"

    await _log(
        session,
        automation_id=automation.id,
        account_id=account_id,
        action_type=CHAT_SHILL_ACTION,
        target_id=str(chat_target.id),
        target_type="chat",
        result="scheduled",
        payload={"scheduled_at": when.isoformat()},
        created_at=moscow.astimezone(timezone.utc).replace(tzinfo=None),
    )
    return "wait"


async def process_shilling_chat(
    session: AsyncSession,
    automation: CustomAutomation,
    chat_target: ChatTarget,
    **kwargs: Any,
) -> dict[str, Any]:
    include_lab = bool(kwargs.pop("include_lab", False))
    skip_schedule = bool(kwargs.pop("skip_schedule", False))
    if is_lab_chat(chat_target) and not include_lab:
        await commit_chat_scan(session, chat_target)
        return {"status": "skipped", "reason": "lab"}
    if is_paused(chat_target):
        await commit_chat_scan(session, chat_target)
        return {"status": "skipped", "reason": "paused"}
    if not is_group_chat(chat_target):
        await commit_chat_scan(session, chat_target)
        return {"status": "skipped", "reason": "channel"}
    if not await is_chat_watchable(session, chat_target):
        await ensure_watcher_membership(session, automation.id, chat_target, include_lab=include_lab)
        await commit_chat_scan(session, chat_target)
        return {"status": "skipped", "reason": "not_watchable"}

    target_actions_today = await count_target_actions_today(session, automation.id, chat_target.id)
    if target_actions_today >= chat_target.max_daily_target_actions:
        await commit_chat_scan(session, chat_target)
        return {"status": "skipped", "reason": "chat_daily_target_limit"}

    pair = await _pick_speaker_pair(session, automation)
    if not pair:
        await commit_chat_scan(session, chat_target)
        return {"status": "skipped", "reason": "need_two_accounts"}
    placeholder_account_id = pair[0].id

    if not skip_schedule:
        now = kwargs.pop("now", None)
        decision = await decide_chat_shilling_today(
            session,
            automation,
            chat_target,
            placeholder_account_id,
            now=now,
            roll=kwargs.pop("roll", None),
            scheduled_at=kwargs.pop("scheduled_at", None),
        )
        if decision != "due":
            await commit_chat_scan(session, chat_target)
            return {"status": "skipped", "reason": decision}
        last_shill = await last_successful_chat_shill_ever(
            session, automation.id, chat_target.id,
        )
        if last_shill:
            messages_since = await resolve_chat_shill_messages_since(
                session,
                chat_target,
                last_shill,
                pair[0],
                messages_since=kwargs.pop("messages_since", None),
            )
            if not chat_shill_activity_allows(
                last_at=last_shill.created_at,
                messages_since=messages_since,
                now=now or _utc_now(),
            ):
                await commit_chat_scan(session, chat_target)
                return {
                    "status": "skipped",
                    "reason": "wait_messages",
                    "messages_since": messages_since,
                }
        else:
            kwargs.pop("messages_since", None)
    else:
        kwargs.pop("messages_since", None)
        kwargs.setdefault("delay_seconds", 0)

    result = await perform_shilling_dialogue(
        session,
        automation,
        chat_target,
        action_type=CHAT_SHILL_ACTION,
        target_id=str(chat_target.id),
        target_type="chat",
        **kwargs,
    )
    await commit_chat_scan(session, chat_target)
    return result


async def run_shilling_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    chats_processed = 0
    dialogues_sent = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not automation.is_shilling_enabled:
            logger.info("Shilling disabled or automation not found for %s", automation_id)
            return {"status": "skipped", "reason": "feature_disabled", "chats_processed": 0, "dialogues_sent": 0}

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
                res = await process_shilling_chat(session, automation, chat_target)
                chats_processed += 1
                if res.get("status") == "ok":
                    dialogues_sent += 1
            except Exception as exc:
                logger.exception("Shilling failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chats_processed, "dialogues_sent": dialogues_sent}
