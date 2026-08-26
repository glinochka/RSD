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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .chat_scope import is_group_chat, is_paused
from .post_engagement import SHILLING as POST_SHILLING, get_post_engagement_claim, post_target_id
from .rotation_service import accounts_are_distinct, select_distinct_accounts_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_invite import chat_entity_key
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import (
    AutomationActionLog,
    ChatJoinStatus,
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
CHAT_SHILL_PROBABILITY = 0.40
CHAT_SHILL_COOLDOWN_DAYS = 2
CHAT_SHILL_ACTION = "shilling_chat"
POST_SHILL_ACTION = "shilling_post"
REPLY_DELAY_MIN_SECONDS = 8.0
REPLY_DELAY_MAX_SECONDS = 25.0

DEFAULT_SHILLING_PROMPT = """Ты пишешь нативный диалог двух незнакомцев в Telegram (партизанский маркетинг).
Первый жалуется или спрашивает совет по теме оффера. Второй отвечает как живой человек из своего опыта и мягко рекомендует сервис заказчика.
Без ссылок, без хештегов, без рекламного тона, без «всем советую». 1-2 предложения на реплику.
Если уместно, второй может предложить скинуть контакт в личку.

Индустрия/оффер: {industry}
Клиент: {client_name}
Чат: {chat_title}
Контекст поста (может быть пусто): {post_text}

Верни ТОЛЬКО JSON:
{
  "setup": "реплика первого",
  "reply": "реплика второго"
}"""


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


def _in_chat_window(now: datetime | None = None) -> bool:
    moscow = _moscow_now(now)
    return CHAT_WINDOW_START_HOUR <= moscow.hour < CHAT_WINDOW_END_HOUR


def _random_time_today(now_moscow: datetime) -> datetime:
    start = now_moscow.replace(hour=CHAT_WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    end = now_moscow.replace(hour=CHAT_WINDOW_END_HOUR, minute=0, second=0, microsecond=0)
    span = max(int((end - start).total_seconds()) - 1, 0)
    return start + timedelta(seconds=random.randint(0, span))


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _session_path(account: SocialAccount) -> Path | None:
    if not account.session_file_path:
        return None
    path = _media_root() / account.session_file_path
    return path if path.exists() else None


async def _load_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.SHILLING.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_SHILLING_PROMPT


def _format_prompt(template: str, **kwargs: str) -> str:
    rendered = template
    for key, value in kwargs.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


async def generate_shilling_dialogue(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    chat_title: str,
    post_text: str = "",
) -> tuple[str, str]:
    prompt = _format_prompt(
        await _load_prompt(session, automation.id),
        industry=automation.industry or "",
        client_name=automation.client_name or "",
        chat_title=chat_title or "",
        post_text=post_text or "",
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.85,
        )
        data = _extract_json(response.choices[0].message.content or "")
        setup = str(data.get("setup") or "").strip()[:500]
        reply = str(data.get("reply") or "").strip()[:500]
        return setup, reply
    except Exception as exc:
        logger.warning("Shilling dialogue generation failed: %s", exc)
        return "", ""


async def _pick_speaker_pair(
    session: AsyncSession,
    automation: CustomAutomation,
    exclude_account_ids: set[int] | None = None,
) -> tuple[SocialAccount, SocialAccount] | None:
    pair = await select_distinct_accounts_for_action(
        session,
        automation,
        "shilling",
        count=2,
        exclude_account_ids=exclude_account_ids,
    )
    if len(pair) != 2 or not accounts_are_distinct(*pair):
        return None
    return pair[0], pair[1]


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
    payload: dict[str, Any] | None = None,
) -> int | None:
    path = _session_path(account)
    if not path:
        return None
    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(
                chat_entity_key(chat_target)
            )

            async def _send():
                kwargs: dict[str, Any] = {}
                if comment_to is not None:
                    kwargs["comment_to"] = comment_to
                if reply_to is not None:
                    kwargs["reply_to"] = reply_to
                return await client.client.send_message(entity, text, **kwargs)

            message = await execute_with_telegram_retry(
                session,
                account,
                _send,
                action_type=action_type,
                target_id=target_id,
                target_type="chat_post" if comment_to is not None else "chat",
                payload=payload or {},
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("Shilling send failed for chat %s account %s: %s", chat_target.id, account.id, exc)
        return None
    return getattr(message, "id", None)


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
        payload={"role": "setup", "text": setup, "peer_account_id": account_b.id},
    )
    if not first_id:
        return {"status": "error", "reason": "setup_failed"}

    wait_for = delay_seconds
    if wait_for is None:
        wait_for = random.uniform(REPLY_DELAY_MIN_SECONDS, REPLY_DELAY_MAX_SECONDS)
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
        comment_to=comment_to,
        payload={"role": "reply", "text": reply, "peer_account_id": account_a.id, "reply_to": first_id},
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
    **kwargs: Any,
) -> dict[str, Any]:
    target_id = post_target_id(chat_target.id, post_id)
    if await _already_succeeded(session, automation.id, POST_SHILL_ACTION, target_id):
        return {"status": "skipped", "reason": "already_sent"}
    claim = await get_post_engagement_claim(session, automation.id, chat_target.id, post_id)
    if claim and claim.result != POST_SHILLING:
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
    *,
    days: int = CHAT_SHILL_COOLDOWN_DAYS,
) -> AutomationActionLog | None:
    start, end = _moscow_period_utc_range(days, now=now)
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
    """At most once per 2 Moscow days after a success; 40% chance once per day, 08:00–20:00.

    Returns skip | wait | due | done.
    """
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

    if not _in_chat_window(now):
        return "wait"

    rand = roll or random.random
    if rand() >= CHAT_SHILL_PROBABILITY:
        await _log(
            session,
            automation_id=automation.id,
            account_id=account_id,
            action_type=CHAT_SHILL_ACTION,
            target_id=str(chat_target.id),
            target_type="chat",
            result="skip",
            payload={"reason": "daily_probability"},
            created_at=_moscow_now(now).astimezone(timezone.utc).replace(tzinfo=None),
        )
        return "skip"

    when = scheduled_at or _random_time_today(moscow)
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
    if is_paused(chat_target):
        return {"status": "skipped", "reason": "paused"}
    if not is_group_chat(chat_target):
        return {"status": "skipped", "reason": "channel"}
    if chat_target.join_status != ChatJoinStatus.JOINED.value:
        return {"status": "skipped", "reason": "not_joined"}

    available = await select_distinct_accounts_for_action(
        session, automation, "shilling", count=2, consume_quota=False
    )
    if len(available) < 2:
        return {"status": "skipped", "reason": "need_two_accounts"}
    placeholder_account_id = available[0].id

    decision = await decide_chat_shilling_today(
        session,
        automation,
        chat_target,
        placeholder_account_id,
        now=kwargs.pop("now", None),
        roll=kwargs.pop("roll", None),
        scheduled_at=kwargs.pop("scheduled_at", None),
    )
    if decision != "due":
        return {"status": "skipped", "reason": decision}

    result = await perform_shilling_dialogue(
        session,
        automation,
        chat_target,
        action_type=CHAT_SHILL_ACTION,
        target_id=str(chat_target.id),
        target_type="chat",
        **kwargs,
    )
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

        result = await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.is_active.is_(True),
                ChatTarget.join_status == ChatJoinStatus.JOINED.value,
                ChatTarget.mode != "inactive",
            )
        )
        chats = result.scalars().all()
        for chat_target in chats:
            try:
                res = await process_shilling_chat(session, automation, chat_target)
                chats_processed += 1
                if res.get("status") == "ok":
                    dialogues_sent += 1
            except Exception as exc:
                logger.exception("Shilling failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chats_processed, "dialogues_sent": dialogues_sent}
