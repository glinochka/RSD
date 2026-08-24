"""Telegram error classification, retry with backoff, and account state updates."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog, SocialAccount

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Base classes we always have.
FLOOD_ERRORS = set()
BANNED_ERRORS = set()
DEACTIVATED_ERRORS = set()
SESSION_ERRORS = set()


try:
    from telethon.errors import FloodWaitError

    FLOOD_ERRORS.add(FloodWaitError)
except Exception:
    pass


for cls_name in (
    "UserBannedInChannelError",
    "UserBannedError",
    "ChatAdminRequiredError",
):
    try:
        from telethon.errors import RPCError

        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            BANNED_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in (
    "UserDeactivatedError",
    "UserDeactivatedBanError",
    "PhoneNumberBannedError",
    "UserIsBlockedError",
):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            DEACTIVATED_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in (
    "AuthKeyUnregisteredError",
    "AuthKeyInvalidError",
    "AuthKeyPermEmptyError",
    "SessionExpiredError",
    "SessionPasswordNeededError",
):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            SESSION_ERRORS.add(cls)
    except Exception:
        pass


def _classify_telegram_error(exc: Exception) -> dict[str, Any]:
    """Return dict with keys: kind, seconds (for flood)."""
    if FLOOD_ERRORS and isinstance(exc, tuple(FLOOD_ERRORS)):
        seconds = getattr(exc, "seconds", 60)
        return {"kind": "flood", "seconds": seconds}
    if DEACTIVATED_ERRORS and isinstance(exc, tuple(DEACTIVATED_ERRORS)):
        return {"kind": "deactivated"}
    if BANNED_ERRORS and isinstance(exc, tuple(BANNED_ERRORS)):
        return {"kind": "banned"}
    if SESSION_ERRORS and isinstance(exc, tuple(SESSION_ERRORS)):
        return {"kind": "session"}
    name = type(exc).__name__
    lowered = str(exc).lower()
    if "flood" in lowered or "wait" in lowered:
        return {"kind": "flood", "seconds": 60}
    if "banned" in lowered or "deactivated" in lowered or "blocked" in lowered:
        return {"kind": "deactivated"}
    if "auth" in lowered or "session" in lowered or "unregistered" in lowered:
        return {"kind": "session"}
    return {"kind": "other", "name": name}


async def log_action_error(
    session: AsyncSession,
    account: SocialAccount,
    *,
    action_type: str,
    target_id: str | None,
    target_type: str = "account",
    payload: dict[str, Any] | None,
    error_message: str,
    automation_id: int | None = None,
) -> None:
    try:
        log = AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account.id,
            action_type=action_type,
            target_id=target_id or f"account:{account.id}",
            target_type=target_type,
            result="error",
            error_message=error_message[:2000],
            payload=payload or {},
            created_at=_utc_now(),
        )
        session.add(log)
        await session.commit()
    except Exception as exc:
        logger.warning("Failed to write action error log: %s", exc)


async def execute_with_telegram_retry(
    session: AsyncSession,
    account: SocialAccount,
    coro_fn: Callable[[], Awaitable[Any]],
    *,
    action_type: str,
    target_id: str | None = None,
    target_type: str = "account",
    payload: dict[str, Any] | None = None,
    automation_id: int | None = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Any:
    """Run a Telegram coroutine, handle flood/ban/session errors, log failures."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            classification = _classify_telegram_error(exc)
            kind = classification["kind"]
            if kind in {"deactivated", "banned"}:
                account.is_banned = True
                account.banned_at = _utc_now()
                account.ban_reason = str(exc)[:255]
                account.updated_at = _utc_now()
                await session.commit()
                await log_action_error(
                    session, account,
                    action_type=action_type,
                    target_id=target_id,
                    target_type=target_type,
                    payload=payload,
                    error_message=str(exc),
                    automation_id=automation_id,
                )
                raise
            if kind == "session":
                account.is_active = False
                account.updated_at = _utc_now()
                await session.commit()
                await log_action_error(
                    session, account,
                    action_type=action_type,
                    target_id=target_id,
                    target_type=target_type,
                    payload=payload,
                    error_message=str(exc),
                    automation_id=automation_id,
                )
                raise
            if kind == "flood":
                wait_seconds = int(classification.get("seconds") or 60)
                if attempt >= max_retries - 1:
                    break
                logger.info("FloodWait for account %s: sleeping %s seconds", account.id, wait_seconds)
                await asyncio.sleep(wait_seconds)
                continue
            if attempt >= max_retries - 1:
                break
            await asyncio.sleep(base_delay * (2 ** attempt))
            continue

    await log_action_error(
        session, account,
        action_type=action_type,
        target_id=target_id,
        target_type=target_type,
        payload=payload,
        error_message=str(last_exc) if last_exc else "unknown error",
        automation_id=automation_id,
    )
    if last_exc:
        raise last_exc
    raise RuntimeError("execute_with_telegram_retry exhausted")


async def update_account_after_telegram_error(
    session: AsyncSession,
    account: SocialAccount,
    exc: Exception,
) -> str:
    """Classify a Telegram error and update account state accordingly."""
    classification = _classify_telegram_error(exc)
    kind = classification["kind"]
    if kind in {"deactivated", "banned"}:
        account.is_banned = True
        account.banned_at = _utc_now()
        account.ban_reason = str(exc)[:255]
        account.updated_at = _utc_now()
        await session.commit()
        return "banned"
    if kind == "session":
        account.is_active = False
        account.updated_at = _utc_now()
        await session.commit()
        return "session_invalid"
    if kind == "flood":
        return "flood"
    return "other"
