"""Warm up newly uploaded Telegram accounts against trusted usernames."""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from ...alembic.models import CustomAutomation, PoolAccount, SocialAccount

logger = logging.getLogger(__name__)

DEFAULT_WARMUP_MESSAGES = ["Привет", "Как дела?", "Что нового?"]
WARMUP_STATUSES = {"idle", "rest", "warming", "complete"}


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
    return True


def _due_for_dialog(pool_account: PoolAccount) -> bool:
    status = (pool_account.warmup_status or "idle").strip().lower()
    if status not in {"rest", "warming"}:
        return False
    today = _moscow_date()
    if status == "rest":
        started = pool_account.warmup_started_at
        if not started:
            return True
        return _moscow_date(started) < today
    last = pool_account.warmup_last_dialog_at
    if not last:
        return True
    return _moscow_date(last) < today


async def _send_dialog(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    usernames: list[str],
    messages: list[str],
    *,
    sleeper=None,
    delay: bool = True,
) -> dict[str, Any]:
    if not usernames:
        return {"status": "skipped", "reason": "no_usernames"}
    peer = random.choice(usernames)
    sent = 0
    try:
        async with TelegramAccountClient.for_account(account) as client:
            for index, text in enumerate(messages):
                await execute_with_telegram_retry(
                    session,
                    account,
                    lambda t=text: client.send_message(peer, t),
                    action_type="account_warmup",
                    target_id=peer,
                    target_type="warmup",
                    payload={"text": text, "username": peer},
                    automation_id=automation.id,
                )
                sent += 1
                account.daily_messages_sent = (account.daily_messages_sent or 0) + 1
                account.last_used_at = _utc_now()
                if delay and index < len(messages) - 1:
                    fn = sleeper or __import__("asyncio").sleep
                    await fn(random.uniform(3, 8))
    except Exception as exc:
        logger.warning("Account warmup dialog failed for %s: %s", account.id, exc)
        return {"status": "error", "reason": str(exc)[:200], "sent": sent, "peer": peer}
    return {"status": "ok", "sent": sent, "peer": peer}


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
            if not social.is_active or social.is_banned or not social.session_file_path:
                continue
            if not _due_for_dialog(pool_account):
                continue
            processed += 1
            outcome = await _send_dialog(session, automation, social, usernames, messages)
            if outcome.get("status") != "ok":
                continue
            dialogs += 1
            pool_account.warmup_dialog_count = (pool_account.warmup_dialog_count or 0) + 1
            pool_account.warmup_last_dialog_at = _utc_now()
            if pool_account.warmup_dialog_count >= 2:
                pool_account.warmup_status = "complete"
                completed += 1
                from .chat_membership_service import ensure_memberships_for_account

                await ensure_memberships_for_account(session, automation.id, social.id)
            else:
                pool_account.warmup_status = "warming"
            await session.commit()
    return {"processed": processed, "dialogs": dialogs, "completed": completed}
