"""Telegram error classification, retry with backoff, and account state updates."""
import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog, SocialAccount
from .account_pacing import (
    action_uses_target_rest,
    action_uses_humanization_rest,
    schedule_account_target_rest,
    schedule_account_humanization_rest,
    schedule_account_retry,
    schedule_flood_quarantine,
    looks_like_flood_quarantine,
    # Legacy alias kept for external callers
    action_uses_write_rest,
)


def _schedule_rest_for_action(account: "SocialAccount", action_type: str) -> None:
    """Humanization keeps a short gap; target writes no longer flash-rest 40–70 min."""
    if action_uses_humanization_rest(action_type) or action_type == "account_warmup":
        schedule_account_humanization_rest(account, seconds=random.uniform(120, 300))
        return
    # Target actions continue through the work window; idle gaps are planned globally.

logger = logging.getLogger(__name__)

_SPAMBOT_OK = (
    "good news, no limits",
    "no limits are currently applied",
    "свободен от каких-либо ограничений",
    "нет ограничений",
    "не ограничен",
    "limits have been lifted",
    "restrictions have been lifted",
    "we have lifted",
    "ограничения сняты",
    "сняли ограничения",
    "больше нет ограничений",
)
_SPAMBOT_APPEAL = (
    "this is a mistake",
    "that's a mistake",
    "that is a mistake",
    "это ошибка",
    "submit a complaint",
    "отправить жалобу",
    "обжаловать",
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


class ProxyDeadError(RuntimeError):
    """Assigned SOCKS/HTTP proxy is unreachable. Session file is still valid."""


def looks_like_proxy_dead(exc: Exception) -> bool:
    if isinstance(exc, ProxyDeadError):
        return True
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    blob = f"{name} {text}"
    compact = blob.replace("_", "").replace(" ", "")
    needles = (
        "proxyconnectionerror",
        "proxyerror",
        "could not connect to proxy",
        "connect to proxy",
        "connect call failed",
        "socks5",
        "socks4",
    )
    if any(token.replace(" ", "") in compact or token in blob for token in needles):
        return True
    return "connection to telegram failed" in text and "proxy" in blob


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

try:
    from telethon.errors import FloodError

    FLOOD_ERRORS.add(FloodError)
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
    from .account_restriction import classify_spambot_reply

    info = classify_spambot_reply(text)
    if info is None:
        blob = (text or "").strip().lower()
        if not blob:
            return None
        if any(marker in blob for marker in _SPAMBOT_OK):
            return False
        if any(marker in blob for marker in _SPAMBOT_BLOCK):
            return True
        return None
    return bool(info.get("blocked"))


def spambot_verdict_from_messages(texts: list[str] | None) -> bool | None:
    """Newest message first: first decisive SpamBot reply wins."""
    for text in texts or []:
        parsed = parse_spambot_reply(text)
        if parsed is not None:
            return parsed
    return None


def is_spambot_appeal_button(label: str | None) -> bool:
    blob = (label or "").strip().lower()
    if not blob:
        return False
    return any(marker in blob for marker in _SPAMBOT_APPEAL)


def _looks_like_invite_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    compact = f"{name} {text}".replace("_", "").replace(" ", "")
    needles = (
        "invitehashexpired",
        "invitehashinvalid",
        "invitehashempty",
        "invitehashexpirederror",
        "invite hash expired",
        "invite hash invalid",
        "invite hash empty",
    )
    return any(needle.replace(" ", "") in compact or needle in text for needle in needles)


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
    if looks_like_proxy_dead(exc):
        return {"kind": "proxy"}
    if isinstance(exc, SessionInvalidError) or _looks_like_session_error(exc):
        return {"kind": "session"}
    if FROZEN_ERRORS and isinstance(exc, tuple(FROZEN_ERRORS)):
        return {"kind": "frozen"}
    if _looks_like_frozen_error(exc):
        return {"kind": "frozen"}
    if _looks_like_invite_error(exc):
        return {"kind": "invite_invalid"}
    if looks_like_flood_quarantine(exc) and "too many attempts" in str(exc).lower():
        seconds = getattr(exc, "seconds", None) or (12 * 60 * 60)
        return {"kind": "flood", "seconds": seconds}
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
    if looks_like_flood_quarantine(exc) or "flood" in lowered or "wait of" in lowered:
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


def is_comments_unusable(exc: Exception) -> bool:
    """True when this channel/chat cannot take comments from anyone, so it should be black-boxed."""
    if is_chat_write_forbidden(exc):
        return True
    name = type(exc).__name__
    blob = f"{name} {exc}".lower()
    compact = blob.replace("_", "").replace(" ", "")
    needles = (
        "channelprivate",
        "chatforbidden",
        "the channel specified is private",
        "invitehashexpired",
        "invite hash expired",
    )
    return any(token.replace(" ", "") in compact or token in blob for token in needles)


def is_chat_write_forbidden(exc: Exception) -> bool:
    """True when comments/posts are closed for this chat, not a global account ban."""
    name = type(exc).__name__
    blob = f"{name} {exc}".lower()
    compact = blob.replace("_", "").replace(" ", "")
    return (
        name == "ChatWriteForbiddenError"
        or "chatwriteforbidden" in compact
        or "can't write in this chat" in blob
        or "cannot write in this chat" in blob
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
    from .account_pacing import account_is_flood_quarantined

    if account_is_flood_quarantined(account):
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


def mark_spamblocked(account: SocialAccount, *, blocked: bool, kind: str | None = None) -> None:
    from .account_restriction import KIND_LIMITED, apply_limited_flag

    apply_limited_flag(account, blocked=blocked, kind=kind or KIND_LIMITED)


def mark_channel_banned(account: SocialAccount) -> None:
    """Cannot write to any group/channel. Session and DMs may still work."""
    account.is_channel_banned = True
    account.updated_at = _utc_now()


def mark_frozen(account: SocialAccount) -> None:
    """Session stays valid; Telegram rejects writes until the freeze is lifted."""
    from .account_restriction import KIND_FROZEN

    account.is_frozen = True
    account.frozen_at = account.frozen_at or _utc_now()
    account.restriction_kind = KIND_FROZEN
    account.updated_at = _utc_now()


_OPERATIONAL_SKIP_MARKERS = (
    "comments_closed",
    "can't write in this chat",
    "cannot write in this chat",
    "chatwriteforbidden",
    "settypingrequest",
    "invite hash expired",
    "invite hash invalid",
    "ссылка-приглашение истекла",
    "некорректная ссылка-приглашение",
    "такого чата или канала нет",
    "the channel specified is private",
    "channelprivate",
)


def is_operational_skip_error(message: str | None, payload: dict[str, Any] | None = None) -> bool:
    """Closed comments / write-forbidden: expected blackbox, not an error-feed event."""
    payload = payload if isinstance(payload, dict) else {}
    blob = f"{message or ''} {payload.get('error') or ''}".lower()
    if any(marker in blob for marker in _OPERATIONAL_SKIP_MARKERS):
        return True
    return False


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
    if is_operational_skip_error(error_message, payload):
        return
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
    log_errors: bool = True,
) -> Any:
    """Run a Telegram coroutine. Failed requests park 3–5 minutes before the next attempt.

    FloodWait under 20 seconds is the only in-process wait; longer floods are deferred.
    Successful writes rest the account; joins keep their own cooldown.
    """
    del base_delay
    last_exc: Exception | None = None
    attempts = max(1, int(max_retries))
    apply_write_rest = pace and action_uses_write_rest(action_type)

    async def _log_error(error_message: str) -> None:
        if not log_errors:
            return
        await log_action_error(
            session, account,
            action_type=action_type,
            target_id=target_id,
            target_type=target_type,
            payload=payload,
            error_message=error_message,
            automation_id=automation_id,
        )

    for attempt in range(attempts):
        try:
            result = await coro_fn()
            if apply_write_rest:
                _schedule_rest_for_action(account, action_type)
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
            if kind == "proxy":
                from .proxy_service import recover_dead_proxy

                rotated = await recover_dead_proxy(session, account)
                if rotated is not None:
                    await session.commit()
                    await session.refresh(account)
                schedule_account_retry(account)
                await _log_error(str(exc))
                raise
            if kind == "session_busy":
                schedule_account_retry(account)
                await _log_error(str(exc))
                raise
            if kind == "invite_invalid":
                raise
            if kind == "chat_restricted":
                if is_chat_write_forbidden(exc):
                    raise
                schedule_account_retry(account)
                await _log_error(str(exc))
                raise
            if kind == "flood":
                wait_seconds = int(classification.get("seconds") or 60)
                if wait_seconds <= 20 and attempt < attempts - 1 and not looks_like_flood_quarantine(exc):
                    logger.info("FloodWait for account %s: sleeping %s seconds", account.id, wait_seconds)
                    await asyncio.sleep(wait_seconds)
                    continue
                until = schedule_flood_quarantine(account)
                logger.warning(
                    "Flood quarantine for account %s until %s",
                    account.id,
                    until.isoformat(),
                )
                if automation_id:
                    try:
                        from .job_service import STREAM_JOB_TYPES, actor_label, list_active_job_types, log_active

                        hours = max(1, int((until - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() // 3600))
                        message = (
                            f"{actor_label(account)} карантин {hours} ч "
                            "(FloodWait / too many attempts)"
                        )
                        active = await list_active_job_types(automation_id)
                        for job_type in active or set(STREAM_JOB_TYPES.values()):
                            await log_active(automation_id, job_type, message, level="warning")
                    except Exception:
                        logger.debug("Flood quarantine log skipped", exc_info=True)
                await session.commit()
                break
            schedule_account_retry(account)
            break

    await _log_error(str(last_exc) if last_exc else "unknown error")
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
    if kind == "flood":
        schedule_flood_quarantine(account)
        await session.commit()
        return "flood"
    if kind == "session_busy":
        return "session_busy"
    if kind == "proxy":
        return "proxy"
    if kind == "chat_restricted":
        return "chat_restricted"
    if kind == "flood":
        return "flood"
    return "other"
