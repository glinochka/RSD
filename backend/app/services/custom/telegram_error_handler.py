"""Telegram error classification, retry with backoff, and account state updates."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog, SocialAccount

logger = logging.getLogger(__name__)

_SPAMBOT_OK = (
    "good news, no limits",
    "no limits are currently applied",
    "свободен от каких-либо ограничений",
    "нет ограничений",
    "не ограничен",
)
_SPAMBOT_BLOCK = (
    "your account is now limited",
    "your account was blocked for spam",
    "limited until",
    "reported them as spam",
    "reported as spam",
    "наложены некоторые ограничения",
    "наложены ограничения",
    "аккаунт ограничен",
    "временно ограничен",
    "получили жалобы",
    "как спам",
    "too many reports",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SessionInvalidError(RuntimeError):
    """Local session file is no longer authorized in Telegram."""


FLOOD_ERRORS = set()
DEACTIVATED_ERRORS = set()
SESSION_ERRORS = set()
SPAMBLOCK_ERRORS = set()
CHAT_RESTRICTED_ERRORS = set()


try:
    from telethon.errors import FloodWaitError

    FLOOD_ERRORS.add(FloodWaitError)
except Exception:
    pass


for cls_name in (
    "UserDeactivatedError",
    "UserDeactivatedBanError",
    "PhoneNumberBannedError",
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
    "AuthKeyDuplicatedError",
    "SessionExpiredError",
    "SessionRevokedError",
    "UnauthorizedError",
):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            SESSION_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in ("PeerFloodError",):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            SPAMBLOCK_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in (
    "UserBannedInChannelError",
    "ChatWriteForbiddenError",
    "ChatAdminRequiredError",
    "UserNotParticipantError",
    "ChannelPrivateError",
    "ChatForbiddenError",
):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            CHAT_RESTRICTED_ERRORS.add(cls)
    except Exception:
        pass


def parse_spambot_reply(text: str | None) -> bool | None:
    """True = spamblock, False = clean, None = unknown. Ignores a single-chat ban."""
    blob = (text or "").strip().lower()
    if not blob:
        return None
    if any(marker in blob for marker in _SPAMBOT_OK):
        return False
    if any(marker in blob for marker in _SPAMBOT_BLOCK):
        return True
    return None


def _looks_like_session_error(exc: Exception) -> bool:
    lowered = f"{type(exc).__name__} {exc}".lower()
    needles = (
        "authkeyunregistered",
        "auth_key_unregistered",
        "auth key unregistered",
        "sessionrevoked",
        "session revoked",
        "session expired",
        "not authorized",
        "authorization has been invalidated",
        "terminated all sessions",
        "key is not registered",
        "unregistered",
        "authkeyinvalid",
        "auth_key_invalid",
        "authkeyduplicated",
    )
    return any(needle in lowered for needle in needles)


def _classify_telegram_error(exc: Exception) -> dict[str, Any]:
    """Return dict with keys: kind, seconds (for flood)."""
    if isinstance(exc, SessionInvalidError) or _looks_like_session_error(exc):
        return {"kind": "session"}
    if FLOOD_ERRORS and isinstance(exc, tuple(FLOOD_ERRORS)):
        seconds = getattr(exc, "seconds", 60)
        return {"kind": "flood", "seconds": seconds}
    if SPAMBLOCK_ERRORS and isinstance(exc, tuple(SPAMBLOCK_ERRORS)):
        return {"kind": "spamblock"}
    if DEACTIVATED_ERRORS and isinstance(exc, tuple(DEACTIVATED_ERRORS)):
        return {"kind": "deactivated"}
    if SESSION_ERRORS and isinstance(exc, tuple(SESSION_ERRORS)):
        return {"kind": "session"}
    if CHAT_RESTRICTED_ERRORS and isinstance(exc, tuple(CHAT_RESTRICTED_ERRORS)):
        return {"kind": "chat_restricted"}
    name = type(exc).__name__
    lowered = str(exc).lower()
    compact = f"{name} {lowered}".lower().replace("_", "").replace(" ", "")
    if "flood" in lowered or "wait of" in lowered:
        return {"kind": "flood", "seconds": getattr(exc, "seconds", 60) or 60}
    if "peerflood" in compact or "too many requests" in lowered:
        return {"kind": "spamblock"}
    if "deactivated" in lowered or "phonenumberbanned" in compact:
        return {"kind": "deactivated"}
    if "bannedinchannel" in compact or "chatwriteforbidden" in compact:
        return {"kind": "chat_restricted"}
    if "auth" in lowered or "unregistered" in lowered or "revoked" in lowered:
        return {"kind": "session"}
    return {"kind": "other", "name": name}


def mark_session_invalid(account: SocialAccount) -> None:
    account.is_active = False
    account.updated_at = _utc_now()


def mark_account_deactivated(account: SocialAccount, exc: Exception) -> None:
    account.is_banned = True
    account.is_active = False
    account.banned_at = _utc_now()
    account.ban_reason = str(exc)[:255]
    account.updated_at = _utc_now()


def mark_spamblocked(account: SocialAccount, *, blocked: bool) -> None:
    account.is_spamblocked = blocked
    account.spamblocked_at = _utc_now() if blocked else None
    account.spamblock_checked_at = _utc_now()
    account.updated_at = _utc_now()


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
            if kind == "deactivated":
                mark_account_deactivated(account, exc)
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
            if kind == "spamblock":
                mark_spamblocked(account, blocked=True)
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
                mark_session_invalid(account)
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
            if kind == "chat_restricted":
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
    if kind == "deactivated":
        mark_account_deactivated(account, exc)
        await session.commit()
        return "banned"
    if kind == "spamblock":
        mark_spamblocked(account, blocked=True)
        await session.commit()
        return "spamblock"
    if kind == "session":
        mark_session_invalid(account)
        await session.commit()
        return "session_invalid"
    if kind == "chat_restricted":
        return "chat_restricted"
    if kind == "flood":
        return "flood"
    return "other"
