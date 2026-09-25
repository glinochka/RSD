"""Warm up newly uploaded Telegram accounts against trusted usernames.

Uses the HUMANIZATION rest queue (next_humanization_at, 8-15 min) so warmup DMs
never block target actions (neurocommenting, shilling, dm).

Warmup messages are AI-varied via LLM so each send slightly differs from the
template — avoids identical fingerprints across the account pool.
"""
from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_humanization_should_idle, schedule_account_humanization_rest
from .rotation_service import record_successful_humanization
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import CustomAutomation, PoolAccount, SocialAccount
from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

DEFAULT_WARMUP_MESSAGES = ["Привет", "Как дела?", "Что нового?"]
WARMUP_STATUSES = {"idle", "rest", "warming", "complete"}
WARMUP_GAP_MIN_SECONDS = 60 * 60      # 1 h
WARMUP_GAP_MAX_SECONDS = 2 * 60 * 60  # 2 h

# AI variation prompt – keeps meaning but changes wording slightly
_VARY_PROMPT = """Перефразируй следующее сообщение чата. Сохрани смысл, но измени формулировку немного.
Используй разговорный стиль, без эмодзи, без лишних слов. Ответь ТОЛЬКО перефразированным текстом.

Сообщение: {text}"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _moscow_tz():
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def _moscow_date(value: datetime | None = None):
    tz = _moscow_tz()
    if value is None:
        return datetime.now(tz).date()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz).date()


def normalize_warmup_usernames(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    seen: list[str] = []
    for item in raw:
        value = str(item or "").strip().lstrip("@")
        if not value or value in seen:
            continue
        seen.append(value[:64])
        if len(seen) >= 3:
            break
    return seen


def normalize_warmup_messages(raw) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raw = []
    messages = [str(item or "").strip()[:400] for item in raw if str(item or "").strip()]
    if len(messages) < 2:
        return list(DEFAULT_WARMUP_MESSAGES)
    return messages[:3]


async def _vary_message(text: str) -> str:
    """Ask the LLM to rephrase the warmup message slightly.

    Falls back to the original if the call fails so warmup is never blocked.
    """
    try:
        prompt = _VARY_PROMPT.replace("{text}", text)
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.85,
        )
        varied = (response.choices[0].message.content or "").strip()
        # Safety: if LLM returned JSON or empty, fall back
        if not varied or len(varied) > 500 or varied.startswith("{"):
            return text
        return varied[:400]
    except Exception as exc:
        logger.debug("Warmup message variation failed: %s", exc)
        return text


def enroll_pool_account(automation: CustomAutomation | None, pool_account: PoolAccount) -> bool:
    if not automation or not automation.account_warmup_enabled:
        return False
    status = (pool_account.warmup_status or "idle").strip().lower()
    if status not in {"idle", ""}:
        return False
    pool_account.warmup_status = "rest"
    pool_account.warmup_started_at = _utc_now()
    pool_account.warmup_dialog_count = 0
    pool_account.warmup_last_dialog_at = None
    pool_account.warmup_message_index = 0
    pool_account.warmup_next_at = None
    return True


def warmup_gap_seconds() -> int:
    return random.randint(WARMUP_GAP_MIN_SECONDS, WARMUP_GAP_MAX_SECONDS)


def _due_for_dialog(pool_account: PoolAccount) -> bool:
    """Backward-compatible alias used by tests."""
    return _due_for_next_message(pool_account)


def _due_for_next_message(pool_account: PoolAccount, *, now: datetime | None = None) -> bool:
    status = (pool_account.warmup_status or "idle").strip().lower()
    if status not in {"rest", "warming"}:
        return False
    current = now or _utc_now()
    next_at = getattr(pool_account, "warmup_next_at", None)
    if next_at and next_at > current:
        return False
    today = _moscow_date(current)
    index = int(getattr(pool_account, "warmup_message_index", 0) or 0)
    if index > 0:
        return True
    if status == "rest":
        started = pool_account.warmup_started_at
        if not started:
            return True
        return _moscow_date(started) < today
    last = pool_account.warmup_last_dialog_at
    if not last:
        return True
    return _moscow_date(last) < today


async def _send_one_message(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    usernames: list[str],
    text: str,
    *,
    first: bool,
) -> dict[str, Any]:
    if not usernames:
        return {"status": "skipped", "reason": "no_usernames"}
    peer = random.choice(usernames)

    # AI-vary the warmup text so each send looks slightly different
    varied_text = await _vary_message(text)

    try:
        async with TelegramAccountClient.for_account(account) as client:
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.human_reply(peer, varied_text, skip_read=first),
                action_type="account_warmup",  # → humanization rest queue
                target_id=peer,
                target_type="warmup",
                payload={"text": varied_text, "original_text": text, "username": peer},
                automation_id=automation.id,
            )
        record_successful_humanization(account)
        # Warmup uses the humanization rest (15-30 min), independent of target actions
        schedule_account_humanization_rest(account)
        await session.commit()
    except Exception as exc:
        logger.warning("Account warmup message failed for %s: %s", account.id, exc)
        return {"status": "error", "reason": str(exc)[:200], "sent": 0, "peer": peer}
    return {"status": "ok", "sent": 1, "peer": peer}


async def _send_dialog(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    usernames: list[str],
    messages: list[str],
    *,
    sleeper=None,
    delay: bool = True,
    message_index: int = 0,
) -> dict[str, Any]:
    """Send the next warmup line only."""
    if not messages:
        return {"status": "skipped", "reason": "no_messages"}
    index = max(0, min(int(message_index), len(messages) - 1))
    return await _send_one_message(
        session,
        automation,
        account,
        usernames,
        messages[index],
        first=index == 0,
    )


async def run_account_warmup_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    processed = 0
    dialogs = 0
    completed = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "not_found"}
        usernames = normalize_warmup_usernames(automation.account_warmup_usernames)
        messages = normalize_warmup_messages(automation.account_warmup_messages)
        result = await session.execute(
            select(PoolAccount, SocialAccount)
            .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.custom_automation_id == automation_id,
                PoolAccount.warmup_status.in_(["rest", "warming"]),
            )
        )
        rows = list(result.all())
        for pool_account, social in rows:
            if not social.is_active or social.is_banned or getattr(social, "is_frozen", False) or not social.session_file_path:
                continue
            # Use HUMANIZATION idle check – target-action cooldown must NOT block warmup
            if account_humanization_should_idle(social):
                continue
            if not _due_for_next_message(pool_account):
                continue
            processed += 1
            index = int(getattr(pool_account, "warmup_message_index", 0) or 0)
            outcome = await _send_dialog(
                session,
                automation,
                social,
                usernames,
                messages,
                message_index=index,
            )
            if outcome.get("status") != "ok":
                continue
            dialogs += 1
            index += 1
            pool_account.warmup_status = "warming"
            if index < len(messages):
                pool_account.warmup_message_index = index
                pool_account.warmup_next_at = _utc_now() + timedelta(seconds=warmup_gap_seconds())
            else:
                pool_account.warmup_message_index = 0
                pool_account.warmup_next_at = None
                pool_account.warmup_dialog_count = (pool_account.warmup_dialog_count or 0) + 1
                pool_account.warmup_last_dialog_at = _utc_now()
                if pool_account.warmup_dialog_count >= 2:
                    pool_account.warmup_status = "complete"
                    completed += 1
                    from .chat_membership_service import ensure_memberships_for_account

                    await ensure_memberships_for_account(session, automation.id, social.id)
            await session.commit()
    return {"processed": processed, "dialogs": dialogs, "completed": completed}
