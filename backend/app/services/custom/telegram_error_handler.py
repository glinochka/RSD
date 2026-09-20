"""Telegram error classification, retry with backoff, and account state updates."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog, SocialAccount
from .account_pacing import action_uses_write_rest, schedule_account_rest, schedule_account_retry

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
SESSION_BUSY_ERRORS = set()
SPAMBLOCK_ERRORS = set()
FROZEN_ERRORS = set()
CHAT_RESTRICTED_ERRORS = set()
CHANNEL_BAN_ERRORS = set()


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


for cls_name in ("AuthKeyDuplicatedError", "AuthRestartError"):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            SESSION_BUSY_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in ("PeerFloodError",):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            SPAMBLOCK_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in ("FrozenMethodInvalidError", "FrozenParticipantMissingError"):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            FROZEN_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in ("UserBannedInChannelError",):
    try:
        cls = getattr(__import__("telethon.errors", fromlist=[cls_name]), cls_name, None)
        if cls:
            CHANNEL_BAN_ERRORS.add(cls)
    except Exception:
        pass


for cls_name in (
    "ChatWriteForbiddenError",
    "ChatAdminRequiredError",
    "UserNotParticipantError",
    "ChannelPrivateError",
    "ChatForbiddenError",
    "UserKickedError",
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


def _looks_like_frozen_error(exc: Exception) -> bool:
    lowered = f"{type(exc).__name__} {exc}".lower().replace("_", " ")
    compact = lowered.replace(" ", "")
    needles = (
        "frozenmethodinvalid",
        "frozenparticipantmissing",
        "frozenaccounts",
        "frozen account",
        "account is frozen",
        "not available for frozen",
        "method that is not available for frozen",
    )
    return any(needle in compact or needle in lowered for needle in needles)


def _error_blob(exc: Exception) -> tuple[str, str]:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    compact = f"{name} {text}".replace("_", "").replace(" ", "")
    return text, compact


def _looks_like_session_busy_error(exc: Exception) -> bool:
    """Same auth key used twice, or Telegram asked to restart the handshake.

    The .session file is still valid. Marking the account revoked here is how
    a live purchased account disappears right after upload.
    """
    if SESSION_BUSY_ERRORS and isinstance(exc, tuple(SESSION_BUSY_ERRORS)):
        return True
    _text, compact = _error_blob(exc)
    needles = (
        "authkeyduplicated",
        "auth key duplicated",
        "authorization key is already in use",
        "used under two different ip",
        "authrestart",
        "auth restart",
        "restart the authorization",
    )
    return any(needle.replace(" ", "") in compact for needle in needles)


def _looks_like_session_error(exc: Exception) -> bool:
    if _looks_like_session_busy_error(exc):
        return False
    lowered, compact = _error_blob(exc)
    needles = (
        "authkeyunregistered",
        "auth_key_unregistered",
        "auth key unregistered",
        "sessionrevoked",
        "session revoked",
        "session expired",
        "session is not authorized",
        "the user has not authorized",
        "authorization has been invalidated",
        "terminated all sessions",
        "key is not registered",
        "authkeyinvalid",
        "auth_key_invalid",
        "authkeypermempty",
    )
    return any(needle.replace("_", "").replace(" ", "") in compact or needle in lowered for needle in needles)


def _classify_telegram_error(exc: Exception) -> dict[str, Any]:
    """Return dict with keys: kind, seconds (for flood)."""
    if _looks_like_session_busy_error(exc):
        return {"kind": "session_busy"}
    if isinstance(exc, SessionInvalidError) or _looks_like_session_error(exc):
        return {"kind": "session"}
    if FROZEN_ERRORS and isinstance(exc, tuple(FROZEN_ERRORS)):
        return {"kind": "frozen"}
    if _looks_like_frozen_error(exc):
        return {"kind": "frozen"}
    if FLOOD_ERRORS and isinstance(exc, tuple(FLOOD_ERRORS)):
        seconds = getattr(exc, "seconds", 60)
        return {"kind": "flood", "seconds": seconds}
    if SPAMBLOCK_ERRORS and isinstance(exc, tuple(SPAMBLOCK_ERRORS)):
        return {"kind": "spamblock"}
    if DEACTIVATED_ERRORS and isinstance(exc, tuple(DEACTIVATED_ERRORS)):
        return {"kind": "deactivated"}
    if SESSION_BUSY_ERRORS and isinstance(exc, tuple(SESSION_BUSY_ERRORS)):
        return {"kind": "session_busy"}
    if SESSION_ERRORS and isinstance(exc, tuple(SESSION_ERRORS)):
        return {"kind": "session"}
    if CHANNEL_BAN_ERRORS and isinstance(exc, tuple(CHANNEL_BAN_ERRORS)):
        return {"kind": "channel_banned"}
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
    if "bannedinchannel" in compact or "banned from sending messages in supergroups" in lowered:
        return {"kind": "channel_banned"}
    if "chatwriteforbidden" in compact:
        return {"kind": "chat_restricted"}
    if any(
        token in compact
        for token in (
            "usernotparticipant",
            "channelprivate",
            "chatforbidden",
            "userkicked",
            "youwerekicked",
        )
    ):
        return {"kind": "chat_restricted"}
    if any(
        token in compact
        for token in (
            "authkeyunregistered",
            "sessionrevoked",
            "sessionexpired",
            "authkeyinvalid",
        )
    ):
        return {"kind": "session"}
    return {"kind": "other", "name": name}


_READ_LOST_NAMES = {
    "UserNotParticipantError",
    "ChannelPrivateError",
    "ChatForbiddenError",
    "UserKickedError",
}
_READ_LOST_TOKENS = (
    "usernotparticipant",
    "channelprivate",
    "chatforbidden",
    "userkicked",
    "youwerekicked",
)
_WRITE_ONLY_TOKENS = (
    "chatwriteforbidden",
    "chatadminrequired",
    "bannedinchannel",
    "bannedfromsendingmessagesinsupergroups",
)


def is_chat_read_lost(exc: Exception) -> bool:
    """True when this account can no longer see this chat (kick/ban/private), not a global account ban."""
    name = type(exc).__name__
    if name in _READ_LOST_NAMES:
        return True
    compact = f"{name} {exc}".lower().replace("_", "").replace(" ", "")
    if any(token in compact for token in _WRITE_ONLY_TOKENS):
        return False
    return any(token in compact for token in _READ_LOST_TOKENS)


def is_account_dead(exc: Exception) -> bool:
    kind = _classify_telegram_error(exc).get("kind")
    return kind in {"session", "deactivated", "frozen"}


def account_is_usable(account: SocialAccount | None) -> bool:
    """Session is authorized and the account can still perform Telegram actions."""
    if not account or not account.is_active or account.is_banned:
        return False
    if getattr(account, "is_frozen", False):
        return False
    return True


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


def mark_channel_banned(account: SocialAccount) -> None:
    """Cannot write to any group/channel. Session and DMs may still work."""
    account.is_channel_banned = True
    account.updated_at = _utc_now()


def mark_frozen(account: SocialAccount) -> None:
    """Session stays valid; Telegram rejects writes until the freeze is lifted."""
    account.is_frozen = True
    account.frozen_at = account.frozen_at or _utc_now()
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
    max_retries: int = 1,
    base_delay: float = 1.0,
    pace: bool = True,
) -> Any:
    """Run a Telegram coroutine once. Failed writes wait 3–5 minutes before the next job tick.

    FloodWait under 20 seconds is the only in-process wait; longer floods are deferred.
    Successful/failed writes rest the account; joins keep their own 3–5 minute cooldown.
    """
    del base_delay
    last_exc: Exception | None = None
    attempts = max(1, int(max_retries))
    apply_write_rest = pace and action_uses_write_rest(action_type)
    for attempt in range(attempts):
        try:
            result = await coro_fn()
            if apply_write_rest:
                schedule_account_rest(account)
            return result
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
            if kind == "frozen":
                mark_frozen(account)
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
                try:
                    from .chat_membership_service import replace_watchers_for_dead_account

                    await replace_watchers_for_dead_account(session, account.id)
                    await session.commit()
                except Exception as replace_exc:
                    logger.warning("Could not replace watchers for frozen account %s: %s", account.id, replace_exc)
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
            if kind == "channel_banned":
                mark_channel_banned(account)
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
                from .session_hygiene_service import promote_spare_session

                if promote_spare_session(account):
                    logger.warning("Promoted spare Telegram session for account %s", account.id)
                    await session.commit()
                else:
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
            if kind == "session_busy":
                if apply_write_rest:
                    schedule_account_retry(account)
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
                if apply_write_rest:
                    schedule_account_retry(account)
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
                if wait_seconds <= 20 and attempt < attempts - 1:
                    logger.info("FloodWait for account %s: sleeping %s seconds", account.id, wait_seconds)
                    await asyncio.sleep(wait_seconds)
                    continue
                if apply_write_rest:
                    extra = max(0, wait_seconds - 20)
                    schedule_account_retry(account, extra_seconds=extra)
                break
            if apply_write_rest:
                schedule_account_retry(account)
            break

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
    if kind == "frozen":
        mark_frozen(account)
        await session.commit()
        return "frozen"
    if kind == "spamblock":
        mark_spamblocked(account, blocked=True)
        await session.commit()
        return "spamblock"
    if kind == "channel_banned":
        mark_channel_banned(account)
        await session.commit()
        return "channel_banned"
    if kind == "session":
        from .session_hygiene_service import promote_spare_session

        if promote_spare_session(account):
            await session.commit()
            return "session_retry"
        mark_session_invalid(account)
        await session.commit()
        return "session_invalid"
    if kind == "session_busy":
        return "session_busy"
    if kind == "chat_restricted":
        return "chat_restricted"
    if kind == "flood":
        return "flood"
    return "other"
