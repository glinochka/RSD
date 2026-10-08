"""Join Telegram chats/channels from pool accounts and resolve them on create."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
try:
    from telethon.errors import UsernameNotOccupiedError
except Exception:  # pragma: no cover
    class UsernameNotOccupiedError(Exception):
        pass
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantRequest, JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, DeleteChatUserRequest, ImportChatInviteRequest

from .chat_membership_service import (
    ACTOR_PURPOSE,
    JOIN_DELAY_MAX_SECONDS,
    JOIN_DELAY_MIN_SECONDS,
    MAX_JOINS_PER_TICK,
    apply_account_join_cooldown,
    blackbox_unusable_chat,
    bulk_membership_counts,
    ensure_memberships_for_automation,
    ensure_memberships_for_chat,
    membership_counts,
    pick_next_pending_membership,
    recover_stale_joining_memberships,
    retire_reader_and_replace,
    sync_chat_join_status,
)
from .account_pacing import (
    ACCOUNT_RETRY_MAX_SECONDS,
    ACCOUNT_RETRY_MIN_SECONDS,
    account_membership_should_idle,
    farm_overlap_active_hours,
    schedule_account_retry,
)
from .chat_scope import apply_entity_metadata, is_broadcast_channel, is_lab_chat, is_user_peer, unwrap_telegram_chat
from .chat_target_dedup import find_existing_chat_target
from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import SessionInvalidError, execute_with_telegram_retry, is_chat_read_lost, log_action_error
from .telegram_invite import TelegramChatRef, TelegramChatRefError, parse_telegram_chat_ref, _looks_like_invite_hash, _invite_ref
from ...alembic.models import (
    AccountChatMembership,
    AutomationActionLog,
    ChatFolder,
    ChatJoinStatus,
    ChatMode,
    ChatSource,
    ChatTarget,
    CustomAutomation,
    SocialAccount,
)

logger = logging.getLogger(__name__)

_PERMANENT_JOIN_ERRORS = (
    "no user has",
    "username is not in use",
    "username not occupied",
    "invite hash expired",
    "invite hash invalid",
    "comments_closed",
    "invalid invite link",
    "ссылка-приглашение истекла",
    "некорректная ссылка-приглашение",
    "такого чата или канала нет",
)

JOIN_FAIL_RETRY_MIN_SECONDS = ACCOUNT_RETRY_MIN_SECONDS
JOIN_FAIL_RETRY_MAX_SECONDS = ACCOUNT_RETRY_MAX_SECONDS
MAX_JOIN_ATTEMPTS = 2

try:
    from telethon.errors import InviteRequestSentError
except Exception:  # pragma: no cover - older Telethon
    class InviteRequestSentError(Exception):
        pass

try:
    from telethon.errors import UserNotParticipantError
except Exception:  # pragma: no cover - older Telethon
    class UserNotParticipantError(Exception):
        pass

try:
    from telethon.errors import ChannelsTooMuchError
except Exception:  # pragma: no cover - older Telethon
    class ChannelsTooMuchError(Exception):
        pass

try:
    from telethon.errors import FloodWaitError
except Exception:  # pragma: no cover - older Telethon
    class FloodWaitError(Exception):
        seconds = 60

try:
    from telethon.errors import UserAlreadyParticipantError
except Exception:  # pragma: no cover - older Telethon
    class UserAlreadyParticipantError(Exception):
        pass

try:
    from telethon.errors import InviteHashExpiredError
except Exception:  # pragma: no cover - older Telethon
    class InviteHashExpiredError(Exception):
        pass

try:
    from telethon.errors import InviteHashInvalidError
except Exception:  # pragma: no cover - older Telethon
    class InviteHashInvalidError(Exception):
        pass


_LOOKUP_ERRORS = {
    "UsernameNotOccupiedError": "Такого чата или канала нет",
    "UsernameInvalidError": "Некорректное имя канала или чата",
    "InviteHashExpiredError": "Ссылка-приглашение истекла",
    "InviteHashInvalidError": "Некорректная ссылка-приглашение",
    "InviteHashEmptyError": "Некорректная ссылка-приглашение",
    "ChannelPrivateError": "Чат или канал закрыт",
    "ChannelInvalidError": "Не удалось открыть чат или канал",
    "ChatIdInvalidError": "Не удалось открыть чат",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _sleep_between_joins(
    *,
    rate_limit: bool,
    sleeper=None,
) -> None:
    if not rate_limit:
        return
    fn = sleeper or asyncio.sleep
    await fn(random.uniform(JOIN_DELAY_MIN_SECONDS, JOIN_DELAY_MAX_SECONDS))


def is_private_invite_link(link: str | None) -> bool:
    if not link:
        return False
    try:
        return parse_telegram_chat_ref(link).kind == "invite"
    except TelegramChatRefError:
        lower = link.strip().lower()
        return "/+" in lower or "joinchat" in lower or lower.startswith("+")


def _extract_invite_hash(link: str) -> str | None:
    try:
        parsed = parse_telegram_chat_ref(link)
    except TelegramChatRefError:
        return None
    return parsed.value if parsed.kind == "invite" else None


def _friendly_telegram_error(exc: Exception, fallback: str) -> str:
    cause: BaseException | None = exc
    while cause is not None:
        mapped = _LOOKUP_ERRORS.get(type(cause).__name__)
        if mapped:
            return mapped
        cause = cause.__cause__
    text = str(exc) or type(exc).__name__
    lower = text.lower()
    if "no user has" in lower or "username is not in use" in lower:
        return "Такого чата или канала нет — проверьте @username или вставьте ссылку-приглашение"
    return f"{fallback}: {text[:180]}"


def _join_error_is_permanent(error: str | None) -> bool:
    text = (error or "").strip().lower()
    return any(token in text for token in _PERMANENT_JOIN_ERRORS)


def _join_retry_delay() -> timedelta:
    return timedelta(seconds=random.randint(JOIN_FAIL_RETRY_MIN_SECONDS, JOIN_FAIL_RETRY_MAX_SECONDS))


def _parse_chat_ref(chat_target: ChatTarget) -> TelegramChatRef:
    for raw in (chat_target.invite_link, chat_target.external_chat_id, chat_target.title):
        if not raw:
            continue
        try:
            return parse_telegram_chat_ref(str(raw))
        except TelegramChatRefError:
            continue
    raise TelegramChatRefError("no chat identifier")


def _can_join_as_channel(entity: Any) -> bool:
    target = unwrap_telegram_chat(entity)
    if target is None or is_user_peer(target):
        return False
    name = type(target).__name__
    if name == "Channel":
        return True
    return bool(
        getattr(target, "broadcast", False)
        or getattr(target, "megagroup", False)
        or getattr(target, "gigagroup", False)
    )


async def _resolve_entity(client: TelegramAccountClient, parsed: TelegramChatRef) -> Any:
    if parsed.kind == "invite":
        return await client(CheckChatInviteRequest(parsed.value))
    return await client.get_entity(parsed.lookup_value)


async def _is_participant(client: TelegramAccountClient, entity: Any) -> bool | None:
    """True/False when sure; None when Telegram RPC is inconclusive (do not demote)."""
    target = unwrap_telegram_chat(entity)
    if target is None or is_user_peer(target):
        return False
    try:
        me = await client.client.get_me()
    except Exception:
        return None

    try:
        perms = await client.client.get_permissions(target, me)
        if perms is not None and not bool(getattr(perms, "has_left", False)):
            return True
        return False
    except UserNotParticipantError:
        return False
    except Exception as exc:
        logger.debug("get_permissions participant check failed: %s", exc)

    name = type(target).__name__
    if name == "Channel" or getattr(target, "broadcast", False) or getattr(target, "megagroup", False):
        try:
            await client(GetParticipantRequest(target, me))
            return True
        except UserNotParticipantError:
            return False
        except Exception as exc:
            logger.debug("GetParticipant check failed: %s", exc)
            return None
    return None


async def _join_public(client: TelegramAccountClient, parsed: TelegramChatRef) -> Any:
    try:
        entity = await client.get_entity(parsed.lookup_value)
    except UsernameNotOccupiedError:
        if parsed.kind == "username" and _looks_like_invite_hash(str(parsed.value)):
            return await _join_private(client, _invite_ref(str(parsed.value)))
        raise
    if is_user_peer(entity):
        raise ValueError("Это пользователь, а не чат или канал")
    if not _can_join_as_channel(entity):
        if await _is_participant(client, entity):
            return entity
        raise ValueError(
            "Не удалось вступить: нужен супергрупповой чат/@username или ссылка-приглашение t.me/+"
        )

    channel = unwrap_telegram_chat(entity)
    join_accepted = False
    try:
        result = await client(JoinChannelRequest(channel))
        entity = unwrap_telegram_chat(result) or channel
        join_accepted = True
    except UserAlreadyParticipantError:
        entity = channel
        join_accepted = True
    except InviteRequestSentError:
        raise

    # Fresh resolve — Updates payload is a poor input for participant checks.
    try:
        entity = await client.get_entity(parsed.lookup_value)
    except Exception:
        pass

    if join_accepted:
        # JoinChannelRequest / AlreadyParticipant is authoritative for public chats.
        # Participant RPC can lag or fail on megagroups right after join.
        return entity

    if await _is_participant(client, entity):
        return entity
    raise ValueError("Telegram не подтвердил вступление в канал/чат")


async def join_linked_discussion(client: TelegramAccountClient, channel_entity: Any) -> Any | None:
    """Join the comments megagroup. Telegram rejects comment_to until the account is in it."""
    target = unwrap_telegram_chat(channel_entity)
    if target is None:
        return None
    try:
        full = await client(GetFullChannelRequest(target))
    except Exception as exc:
        logger.info("GetFullChannel for discussion join failed: %s", exc)
        return None
    linked_id = getattr(getattr(full, "full_chat", None), "linked_chat_id", None)
    if not linked_id:
        return None
    discussion = None
    for nested in getattr(full, "chats", None) or []:
        if getattr(nested, "id", None) == linked_id:
            discussion = nested
            break
    if discussion is None:
        try:
            discussion = await client.get_entity(linked_id)
        except Exception as exc:
            logger.info("Could not resolve discussion group %s: %s", linked_id, exc)
            return None
    try:
        if await _is_participant(client, discussion) is True:
            return discussion
        await asyncio.sleep(random.uniform(2.0, 12.0))
        await client(JoinChannelRequest(discussion))
    except UserAlreadyParticipantError:
        pass
    except InviteRequestSentError:
        raise
    return discussion


async def _join_private(client: TelegramAccountClient, parsed: TelegramChatRef) -> Any:
    join_accepted = False
    try:
        result = await client(ImportChatInviteRequest(parsed.value))
        join_accepted = True
    except UserAlreadyParticipantError:
        result = await client(CheckChatInviteRequest(parsed.value))
        join_accepted = True

    entity = unwrap_telegram_chat(result) or result
    try:
        # Private invites often need the chat id from the invite payload.
        if getattr(entity, "id", None) is not None:
            entity = await client.get_entity(entity)
    except Exception:
        pass

    if join_accepted:
        return entity
    if await _is_participant(client, entity):
        return entity
    raise ValueError("Telegram не подтвердил вступление по ссылке-приглашению")


async def _try_join_chat(
    session: AsyncSession,
    chat_target: ChatTarget,
    account: SocialAccount,
) -> dict[str, Any]:
    if not account.session_file_path and not getattr(account, "encrypted_session", None):
        return {"status": "failed", "error": "no session file"}
    if (getattr(chat_target, "mod_status", None) or "") == "moderated":
        return {"status": "blackbox", "error": "already_moderated", "reason": "already_moderated"}
    if chat_target.comments_open is False:
        return {"status": "blackbox", "error": "comments_closed", "reason": "comments_closed"}

    try:
        parsed = _parse_chat_ref(chat_target)
    except TelegramChatRefError:
        return {"status": "failed", "error": "invalid invite link"}

    try:
        async with TelegramAccountClient.for_account(account) as client:
            automation_id = int(chat_target.custom_automation_id)
            if parsed.kind == "username" and (
                is_broadcast_channel(chat_target) or not (chat_target.chat_type or "").strip()
            ):
                from .chat_inspect_service import probe_public_posts_for_comments

                probe = await probe_public_posts_for_comments(client, chat_target)
                if getattr(probe, "retry_account", False):
                    return {
                        "status": "failed",
                        "error": probe.error or "probe_failed",
                        "retry_account": True,
                    }
                if probe.comments_open is True:
                    chat_target.comments_open = True
                    chat_target.comments_checked_at = _utc_now()
                    chat_target.comments_check_error = None
                if probe.comments_open is False:
                    err = (probe.error or "").lower()
                    reason = (
                        "invalid_ref"
                        if any(token in err for token in ("no user has", "username", "invite hash"))
                        else "comments_closed"
                    )
                    return {
                        "status": "blackbox",
                        "error": probe.error or reason,
                        "reason": reason,
                    }

            async def _perform_join() -> Any:
                if parsed.kind == "invite":
                    return await _join_private(client, parsed)
                return await _join_public(client, parsed)

            try:
                entity = await execute_with_telegram_retry(
                    session,
                    account,
                    _perform_join,
                    action_type="join_chat",
                    target_id=str(chat_target.id),
                    target_type="chat",
                    automation_id=automation_id,
                    log_errors=False,
                )
            except InviteRequestSentError:
                try:
                    entity = await _resolve_entity(client, parsed)
                except Exception:
                    entity = None
                if entity is not None:
                    apply_entity_metadata(chat_target, entity)
                    chat_target.invite_link = parsed.canonical
                return {"status": "failed", "error": "Нужно одобрение заявки на вступление"}
            except SessionInvalidError as exc:
                logger.warning("Join chat %s skipped account %s: %s", chat_target.id, account.id, exc)
                return {"status": "failed", "error": "session_invalid", "retry_account": True}

            if entity is None:
                return {"status": "failed", "error": "Пустой ответ Telegram при вступлении"}
            apply_entity_metadata(chat_target, entity)
            chat_target.invite_link = parsed.canonical
            # JoinChannelRequest / ImportChatInvite success is enough.
            # Megagroup participant RPC often lags and caused false "0/N joined" for chats.
            try:
                from .humanization_session import settle_after_join

                await settle_after_join(client, entity, account)
            except Exception as settle_exc:
                logger.info(
                    "Post-join settle skipped for chat %s account %s: %s",
                    chat_target.id,
                    account.id,
                    settle_exc,
                )

        return {
            "status": "joined",
            "joined_at": _utc_now(),
            "joined_by_account_id": account.id,
        }
    except FloodWaitError as exc:
        from .account_pacing import schedule_flood_quarantine

        until = schedule_flood_quarantine(account)
        wait_seconds = max(int(exc.seconds or 0), int((until - _utc_now()).total_seconds()))
        return {
            "status": "rate_limited",
            "error": f"FloodWait: {wait_seconds}s",
            "next_join_attempt_at": until,
        }
    except ChannelsTooMuchError:
        return {"status": "failed", "error": "account_channels_full", "slots_full": True}
    except InviteHashExpiredError:
        return {"status": "blackbox", "error": "Ссылка-приглашение истекла", "reason": "invalid_ref"}
    except InviteHashInvalidError:
        return {"status": "blackbox", "error": "Некорректная ссылка-приглашение", "reason": "invalid_ref"}
    except UserAlreadyParticipantError:
        try:
            async with TelegramAccountClient.for_account(account) as client:
                entity = await _resolve_entity(client, parsed)
                if entity is not None:
                    apply_entity_metadata(chat_target, entity)
                    chat_target.invite_link = parsed.canonical
        except Exception as exc:
            logger.warning(
                "Join chat %s already participant but metadata refresh failed: %s",
                chat_target.id,
                exc,
            )
        return {"status": "joined", "joined_at": _utc_now(), "joined_by_account_id": account.id}
    except SessionInvalidError as exc:
        logger.warning("Join chat %s skipped account %s: %s", chat_target.id, account.id, exc)
        return {"status": "failed", "error": "session_invalid", "retry_account": True}
    except ValueError as exc:
        return {"status": "failed", "error": str(exc)[:255]}
    except Exception as exc:
        if is_chat_read_lost(exc):
            logger.warning("Join chat %s banned for account %s: %s", chat_target.id, account.id, exc)
            return {
                "status": "banned",
                "error": _friendly_telegram_error(exc, "Аккаунт заблокирован в чате")[:255],
            }
        logger.warning("Join chat %s failed for account %s: %s", chat_target.id, account.id, exc)
        friendly = _friendly_telegram_error(exc, "Не удалось вступить")[:255]
        if _join_error_is_permanent(str(exc)) or _join_error_is_permanent(friendly) or type(exc).__name__ in _LOOKUP_ERRORS:
            return {"status": "blackbox", "error": friendly, "reason": "invalid_ref"}
        return {"status": "failed", "error": friendly}


async def _apply_membership_result(
    session: AsyncSession,
    membership: AccountChatMembership,
    chat_target: ChatTarget,
    account: SocialAccount,
    join_result: dict[str, Any],
    *,
    automation_id: int,
    apply_cooldown: bool = True,
) -> None:
    now = _utc_now()
    membership.join_attempts += 1
    membership.last_join_attempt_at = now
    membership.updated_at = now

    if join_result.get("retry_account"):
        membership.join_status = ChatJoinStatus.PENDING.value
        membership.last_join_error = join_result.get("error")
        membership.join_attempts = max(0, membership.join_attempts - 1)
        membership.next_join_attempt_at = now + _join_retry_delay()
        schedule_account_retry(account)
        await sync_chat_join_status(session, chat_target)
        return

    if join_result["status"] == "blackbox":
        reason = str(join_result.get("reason") or join_result.get("error") or "unusable")[:64]
        error = str(join_result.get("error") or reason)
        if reason != "already_moderated":
            await blackbox_unusable_chat(session, chat_target, reason=reason)
            if reason != "comments_closed" and error != "comments_closed" and not _join_error_is_permanent(error):
                await log_action_error(
                    session,
                    account,
                    action_type="join_chat",
                    target_id=str(chat_target.id),
                    target_type="chat",
                    error_message=error[:2000],
                    payload={
                        "chat_target_id": chat_target.id,
                        "membership_id": membership.id,
                        "account_id": account.id,
                        "blackbox": True,
                    },
                    automation_id=automation_id,
                )
        membership.last_join_error = join_result.get("error")
        membership.next_join_attempt_at = None
        schedule_account_retry(account)
        await sync_chat_join_status(session, chat_target)
        return

    if join_result["status"] == "joined":
        membership.join_status = ChatJoinStatus.JOINED.value
        membership.joined_at = join_result.get("joined_at") or now
        membership.next_join_attempt_at = None
        membership.last_join_error = None
    elif join_result["status"] == "rate_limited":
        membership.join_status = ChatJoinStatus.RATE_LIMITED.value
        membership.next_join_attempt_at = join_result.get("next_join_attempt_at")
        membership.last_join_error = join_result.get("error")
    elif join_result["status"] == "banned":
        await retire_reader_and_replace(
            session,
            chat_target,
            account.id,
            error=join_result.get("error"),
        )
        await log_action_error(
            session,
            account,
            action_type="join_chat",
            target_id=str(chat_target.id),
            target_type="chat",
            error_message=str(join_result.get("error") or "chat_restricted")[:2000],
            payload={
                "chat_target_id": chat_target.id,
                "membership_id": membership.id,
                "account_id": account.id,
            },
            automation_id=automation_id,
        )
        if apply_cooldown:
            await apply_account_join_cooldown(session, automation_id, account.id)
        return
    elif join_result["status"] == "skipped":
        membership.last_join_error = join_result.get("error")
    else:
        error = join_result.get("error")
        if error == "session_invalid":
            error = "Не удалось войти в Telegram. Если вы не выходили из аккаунта — подождите и попробуйте снова."
        if error == "account_channels_full":
            error = "У аккаунта закончились слоты Telegram (около 500 чатов)."
        if _join_error_is_permanent(str(error or join_result.get("error") or "")):
            await blackbox_unusable_chat(
                session,
                chat_target,
                reason="invalid_ref" if "no user has" in str(error or "").lower() else "unusable",
            )
            membership.last_join_error = error
            membership.next_join_attempt_at = None
            membership.join_status = ChatJoinStatus.ERROR.value
            schedule_account_retry(account)
            await sync_chat_join_status(session, chat_target)
            return
        membership.join_status = ChatJoinStatus.ERROR.value
        membership.last_join_error = error
        membership.next_join_attempt_at = now + _join_retry_delay()
        if membership.join_attempts >= MAX_JOIN_ATTEMPTS:
            membership.next_join_attempt_at = None
        schedule_account_retry(account)
        await log_action_error(
            session,
            account,
            action_type="join_chat",
            target_id=str(chat_target.id),
            target_type="chat",
            error_message=str(error or "join_failed")[:2000],
            payload={
                "chat_target_id": chat_target.id,
                "membership_id": membership.id,
                "account_id": account.id,
            },
            automation_id=automation_id,
        )

    await sync_chat_join_status(session, chat_target)
    if apply_cooldown and join_result["status"] in {"joined", "rate_limited"}:
        wait = None
        if join_result["status"] == "rate_limited":
            nxt = join_result.get("next_join_attempt_at")
            if nxt:
                wait = max(0.0, (nxt - now).total_seconds())
        await apply_account_join_cooldown(
            session,
            automation_id,
            account.id,
            wait_seconds=wait,
        )
    if join_result["status"] == "joined":
        from .pending_action_service import process_pending_for_membership

        await process_pending_for_membership(session, membership)


async def preview_chat_entity(
    session: AsyncSession,
    automation_id: int,
    parsed: TelegramChatRef,
) -> Any:
    tried: set[int] = set()
    last_session_error: Exception | None = None
    entity = None
    while True:
        account = await select_account_for_action(
            session,
            automation_id,
            "prepare_join",
            consume_quota=False,
            exclude_account_ids=tried,
        )
        if not account:
            break
        tried.add(account.id)
        try:
            async with TelegramAccountClient.for_account(account) as client:
                entity = await _resolve_entity(client, parsed)
            break
        except FloodWaitError as exc:
            from .account_pacing import schedule_flood_quarantine

            schedule_flood_quarantine(account)
            continue
        except SessionInvalidError as exc:
            last_session_error = exc
            logger.warning("Preview chat %s skipped account %s: %s", parsed.canonical, account.id, exc)
            continue
        except TelegramChatRefError:
            raise
        except Exception as exc:
            logger.warning("Preview chat %s failed: %s", parsed.canonical, exc)
            raise ValueError(_friendly_telegram_error(exc, "Не удалось найти чат или канал")) from exc

    if entity is None:
        if last_session_error:
            raise ValueError(
                "Не удалось войти в Telegram, чтобы найти чат. "
                "Если вы не выходили из аккаунта — подождите и попробуйте снова."
            ) from last_session_error
        raise ValueError("Нет подключённого юзербота, чтобы найти чат")

    if is_user_peer(entity):
        raise ValueError("Это пользователь, а не чат или канал")
    if unwrap_telegram_chat(entity) is None and not getattr(entity, "title", None):
        raise ValueError("Не удалось найти чат или канал")
    return entity


async def create_chat_from_link(
    session: AsyncSession,
    automation_id: int,
    raw_link: str,
    *,
    mode: str | None = None,
    folder_id: int | None = None,
) -> ChatTarget:
    parsed = parse_telegram_chat_ref(raw_link)
    bound_folder_id = None
    if folder_id:
        folder = await session.get(ChatFolder, int(folder_id))
        if folder is not None and folder.custom_automation_id == automation_id:
            bound_folder_id = folder.id

    existing = await find_existing_chat_target(
        session,
        automation_id,
        invite_link=parsed.canonical,
        external_chat_id=parsed.value if parsed.kind == "channel_id" else None,
    )
    if existing:
        raise ValueError("Этот чат уже добавлен")

    entity = await preview_chat_entity(session, automation_id, parsed)

    now = _utc_now()
    chat = ChatTarget(
        custom_automation_id=automation_id,
        provider="telegram",
        invite_link=parsed.canonical,
        external_chat_id=parsed.value if parsed.kind == "channel_id" else None,
        title=None,
        description=None,
        chat_type=None,
        mode=(mode or "").strip() or ChatMode.MONITORING.value,
        source=ChatSource.MANUAL.value,
        folder_id=bound_folder_id,
        join_status=ChatJoinStatus.PENDING.value,
        join_attempts=0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    apply_entity_metadata(chat, entity)

    duplicate = await find_existing_chat_target(
        session,
        automation_id,
        invite_link=chat.invite_link,
        external_chat_id=chat.external_chat_id,
    )
    if duplicate and duplicate.id != chat.id:
        raise ValueError("Этот чат уже добавлен")

    session.add(chat)
    await session.flush()
    await ensure_memberships_for_chat(session, automation_id, chat)
    await session.commit()
    await session.refresh(chat)
    return chat


async def _seed_join_logs(session: AsyncSession, account_id: int) -> list[AutomationActionLog]:
    result = await session.execute(
        select(AutomationActionLog)
        .where(
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type == "seed_channel_join",
        )
        .order_by(AutomationActionLog.created_at.desc())
    )
    return list(result.scalars().all())


def _seed_log_query(row: AutomationActionLog) -> str:
    payload = row.payload if isinstance(row.payload, dict) else {}
    return str(payload.get("query") or row.target_id or "").strip()


def _seed_cooldown_active(logs: list[AutomationActionLog], *, now: datetime) -> bool:
    from .chat_membership_service import JOIN_DELAY_MIN_SECONDS

    for row in logs:
        payload = row.payload if isinstance(row.payload, dict) else {}
        raw = payload.get("cooldown_until")
        if raw:
            try:
                until = datetime.fromisoformat(str(raw))
                if until.tzinfo is not None:
                    until = until.replace(tzinfo=None)
                if until > now:
                    return True
            except ValueError:
                pass
        if row.result in {"ok", "success", "already"} and row.created_at:
            then = row.created_at.replace(tzinfo=None) if getattr(row.created_at, "tzinfo", None) else row.created_at
            if (now - then).total_seconds() < JOIN_DELAY_MIN_SECONDS:
                return True
        break
    return False


async def join_next_seed_channel(
    session: AsyncSession,
    automation_id: int,
    *,
    exclude_account_ids: set[int] | None = None,
    apply_cooldown: bool = True,
) -> dict[str, Any] | None:
    """Day-1 warmup: search a seed channel title and join it. 2–3 per day."""
    from .account_pacing import (
        account_membership_should_idle,
        account_uses_seed_channel_joins,
        join_daily_cap,
        moscow_day_start_utc,
    )
    from .humanization_session import SEED_CHANNEL_QUERIES, search_and_join_seed_channel
    from .rotation_service import list_alive_session_accounts

    automation = await session.get(CustomAutomation, automation_id)
    warmup = ((automation.module_settings or {}).get("warmup") or {}) if automation else {}
    if not automation or not getattr(automation, "account_warmup_enabled", False):
        return None
    if warmup.get("do_joins") is False:
        return None
    blocked = set(exclude_account_ids or set())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = moscow_day_start_utc(now)
    for account in await list_alive_session_accounts(session, automation_id):
        if account.id in blocked:
            continue
        if not account_uses_seed_channel_joins(account):
            continue
        if account_membership_should_idle(account):
            continue
        logs = await _seed_join_logs(session, account.id)
        if apply_cooldown and _seed_cooldown_active(logs, now=now):
            continue
        cap = join_daily_cap(account, now=now) or 0
        joined_today = sum(
            1
            for row in logs
            if row.result in {"ok", "success"}
            and row.created_at
            and (row.created_at.replace(tzinfo=None) if getattr(row.created_at, "tzinfo", None) else row.created_at) >= since
        )
        if joined_today >= cap:
            continue
        done = {_seed_log_query(row) for row in logs if row.result in {"ok", "success", "already"} and _seed_log_query(row)}
        remaining = [query for query in SEED_CHANNEL_QUERIES if query not in done]
        if not remaining:
            continue
        query = random.choice(remaining)
        try:
            async with TelegramAccountClient.for_account(account) as client:
                outcome = await execute_with_telegram_retry(
                    session,
                    account,
                    lambda: search_and_join_seed_channel(client, query, account=account),
                    action_type="join_chat",
                    target_id=query,
                    target_type="seed_channel",
                    payload={"query": query},
                    automation_id=automation_id,
                    pace=False,
                )
        except Exception as exc:
            logger.info("Seed channel join failed for %s (%s): %s", account.id, query, exc)
            return {
                "status": "error",
                "reason": str(exc)[:200],
                "account_id": account.id,
                "query": query,
            }
        status = str((outcome or {}).get("status") or "error")
        delay = random.uniform(JOIN_DELAY_MIN_SECONDS, JOIN_DELAY_MAX_SECONDS)
        cooldown_until = now + timedelta(seconds=delay)
        session.add(
            AutomationActionLog(
                custom_automation_id=automation_id,
                social_account_id=account.id,
                action_type="seed_channel_join",
                target_id=str((outcome or {}).get("username") or query)[:255],
                target_type="channel",
                result="success" if status in {"ok", "already"} else status[:32],
                payload={
                    "query": query,
                    "title": (outcome or {}).get("title"),
                    "username": (outcome or {}).get("username"),
                    "chat_id": (outcome or {}).get("chat_id"),
                    "cooldown_until": cooldown_until.isoformat(),
                },
                created_at=now,
            )
        )
        if apply_cooldown:
            await apply_account_join_cooldown(session, automation_id, account.id, wait_seconds=delay)
        await session.commit()
        return {
            "status": status,
            "account_id": account.id,
            "query": query,
            "title": (outcome or {}).get("title"),
            "reason": "seed_channel",
        }
    return None


async def join_next_membership(
    session: AsyncSession,
    automation_id: int,
    *,
    max_attempts: int = MAX_JOIN_ATTEMPTS,
    exclude_account_ids: set[int] | None = None,
    apply_cooldown: bool = True,
    skip_ensure: bool = False,
) -> dict[str, Any] | None:
    """Process one pending account×chat join (scheduler entry)."""
    if not skip_ensure:
        await ensure_memberships_for_automation(session, automation_id)
        await recover_stale_joining_memberships(session, automation_id)
    membership = await pick_next_pending_membership(
        session,
        automation_id,
        max_attempts=max_attempts,
        exclude_account_ids=exclude_account_ids,
        ignore_retry_delay=not apply_cooldown,
    )
    if not membership:
        return None

    chat_target = await session.get(ChatTarget, membership.chat_target_id)
    account = await session.get(SocialAccount, membership.social_account_id)
    if not chat_target or not account:
        return {"status": "skipped", "reason": "missing_entities"}
    if account_membership_should_idle(account):
        return {"status": "skipped", "reason": "account_idle"}
    from .account_pacing import (
        activity_ramp_factor,
        account_may_do_work,
        account_uses_seed_channel_joins,
        join_daily_cap,
        moscow_day_start_utc,
    )

    if account_uses_seed_channel_joins(account):
        return {"status": "skipped", "reason": "seed_channel_joins", "account_id": account.id}

    cap = join_daily_cap(account)
    if cap == 0:
        return {"status": "skipped", "reason": "settle_rest"}
    if cap is not None:
        from .chat_membership_service import count_joins_since

        joined_today = await count_joins_since(session, account.id, moscow_day_start_utc())
        if joined_today >= cap:
            return {"status": "skipped", "reason": "join_daily_cap"}
    elif account_may_do_work(account) and random.random() > activity_ramp_factor(account):
        return {"status": "skipped", "reason": "ramp"}
    from .chat_addlist_service import chat_addlist_slug

    if (membership.purpose or "") == ACTOR_PURPOSE or chat_addlist_slug(chat_target):
        return {
            "status": "skipped",
            "reason": "addlist",
            "account_id": account.id,
            "chat_target_id": chat_target.id,
        }

    membership.join_status = ChatJoinStatus.JOINING.value
    membership.updated_at = _utc_now()
    await session.commit()

    join_result = await _try_join_chat(session, chat_target, account)
    is_actor = (membership.purpose or "") == ACTOR_PURPOSE
    await _apply_membership_result(
        session,
        membership,
        chat_target,
        account,
        join_result,
        automation_id=automation_id,
        apply_cooldown=apply_cooldown and not is_actor,
    )
    await session.commit()
    return {
        "membership_id": membership.id,
        "chat_target_id": chat_target.id,
        "account_id": account.id,
        "status": join_result.get("status"),
    }


async def _reset_lab_join_queue(
    session: AsyncSession,
    automation_id: int,
    *,
    chat_target_ids: list[int],
    account_ids: list[int],
) -> int:
    """Lab: clear exhausted attempts/errors so «Вступить» can retry chats."""
    if not chat_target_ids or not account_ids:
        return 0
    result = await session.execute(
        select(AccountChatMembership).where(
            AccountChatMembership.custom_automation_id == automation_id,
            AccountChatMembership.chat_target_id.in_(chat_target_ids),
            AccountChatMembership.social_account_id.in_(account_ids),
            AccountChatMembership.join_status != ChatJoinStatus.JOINED.value,
        )
    )
    now = _utc_now()
    reset = 0
    for membership in result.scalars().all():
        membership.join_status = ChatJoinStatus.PENDING.value
        membership.join_attempts = 0
        membership.next_join_attempt_at = None
        membership.last_join_error = None
        membership.joined_at = None
        membership.updated_at = now
        reset += 1
    for chat_id in chat_target_ids:
        chat_target = await session.get(ChatTarget, chat_id)
        if chat_target:
            await sync_chat_join_status(session, chat_target)
    return reset


async def sync_memberships_with_telegram(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    account_ids: list[int] | None = None,
    demote: bool = True,
) -> tuple[int, int]:
    """Align membership rows with real Telegram participation. Returns (joined, total)."""
    filters = [
        AccountChatMembership.custom_automation_id == automation_id,
        AccountChatMembership.chat_target_id == chat_target.id,
    ]
    if account_ids:
        filters.append(AccountChatMembership.social_account_id.in_(account_ids))
    memberships = list(
        (await session.execute(select(AccountChatMembership).where(*filters))).scalars().all()
    )
    if not memberships:
        await ensure_memberships_for_chat(
            session,
            automation_id,
            chat_target,
            account_ids=account_ids,
            include_lab=is_lab_chat(chat_target=chat_target),
        )
        memberships = list(
            (await session.execute(select(AccountChatMembership).where(*filters))).scalars().all()
        )

    now = _utc_now()
    for membership in memberships:
        account = await session.get(SocialAccount, membership.social_account_id)
        if not account or account.is_banned or not account.is_active or getattr(account, "is_frozen", False):
            continue
        if not account.session_file_path and not getattr(account, "encrypted_session", None):
            continue
        ok: bool | None = None
        try:
            parsed = _parse_chat_ref(chat_target)
            async with TelegramAccountClient.for_account(account) as client:
                entity = await _resolve_entity(client, parsed)
                ok = await _is_participant(client, entity)
                if ok is True and entity is not None:
                    apply_entity_metadata(chat_target, entity)
        except UserNotParticipantError:
            ok = False
        except Exception as exc:
            logger.info(
                "Membership sync chat=%s account=%s failed: %s",
                chat_target.id,
                membership.social_account_id,
                exc,
            )
            continue
        if ok is None:
            continue
        if ok is True:
            if membership.join_status != ChatJoinStatus.JOINED.value:
                membership.join_status = ChatJoinStatus.JOINED.value
                membership.joined_at = membership.joined_at or now
                membership.last_join_error = None
                membership.next_join_attempt_at = None
                membership.updated_at = now
        elif demote and membership.join_status == ChatJoinStatus.JOINED.value:
            await retire_reader_and_replace(
                session,
                chat_target,
                membership.social_account_id,
                error="Не состоит в участниках Telegram",
            )

    await sync_chat_join_status(session, chat_target)
    await session.commit()
    return await membership_counts(session, chat_target.id)


async def join_loaded_chats_for_accounts(
    session: AsyncSession,
    automation_id: int,
    account_ids: list[int] | None = None,
    *,
    chat_ids: list[int] | None = None,
    include_lab: bool = False,
    rate_limit: bool = True,
    ignore_retry_delay: bool = False,
    sleeper=None,
) -> dict[str, Any]:
    """Every alive account joins loaded chats. One pair per step when rate_limit=True."""
    from .rotation_service import list_alive_session_accounts

    accounts = await list_alive_session_accounts(session, automation_id)
    if account_ids:
        wanted = set(account_ids)
        accounts = [account for account in accounts if account.id in wanted]
    chats = (
        await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.is_active.is_(True),
                ChatTarget.provider == "telegram",
            )
        )
    ).scalars().all()
    if chat_ids:
        wanted_chats = set(chat_ids)
        chats = [chat for chat in chats if chat.id in wanted_chats]
    if not include_lab:
        chats = [chat for chat in chats if not is_lab_chat(chat_target=chat)]
    target_ids = [chat.id for chat in chats]
    if include_lab:
        for chat in chats:
            await ensure_memberships_for_chat(
                session,
                automation_id,
                chat,
                account_ids=[account.id for account in accounts],
                include_lab=include_lab,
            )
    else:
        await ensure_memberships_for_automation(session, automation_id)
    if include_lab and target_ids:
        await _reset_lab_join_queue(
            session,
            automation_id,
            chat_target_ids=target_ids,
            account_ids=[account.id for account in accounts],
        )
    await session.commit()

    attempts = 0
    joined_pairs = 0
    failed_pairs = 0
    rate_limited_pairs = 0
    attempted_ids: set[int] = set()
    pick_max_attempts = 10_000 if include_lab else MAX_JOIN_ATTEMPTS
    while True:
        membership = await pick_next_pending_membership(
            session,
            automation_id,
            max_attempts=pick_max_attempts,
            include_lab=include_lab,
            chat_target_ids=target_ids if chat_ids else None,
            ignore_retry_delay=ignore_retry_delay or not rate_limit,
        )
        if not membership:
            break
        if membership.id in attempted_ids:
            # Avoid tight FloodWait retry loops in lab (ignore_retry_delay=True).
            break
        attempted_ids.add(membership.id)
        if account_ids and membership.social_account_id not in set(account_ids):
            membership.join_status = ChatJoinStatus.PENDING.value
            await session.commit()
            continue
        chat_target = await session.get(ChatTarget, membership.chat_target_id)
        account = await session.get(SocialAccount, membership.social_account_id)
        if not chat_target or not account:
            break
        attempts += 1
        join_result = await _try_join_chat(session, chat_target, account)
        status = join_result.get("status")
        if status == "joined":
            joined_pairs += 1
        elif status == "rate_limited":
            rate_limited_pairs += 1
        else:
            failed_pairs += 1
        await _apply_membership_result(
            session,
            membership,
            chat_target,
            account,
            join_result,
            automation_id=automation_id,
            apply_cooldown=rate_limit,
        )
        await session.commit()
        if rate_limit:
            break
        remaining = await pick_next_pending_membership(
            session,
            automation_id,
            max_attempts=pick_max_attempts,
            include_lab=include_lab,
            chat_target_ids=target_ids if chat_ids else None,
            ignore_retry_delay=ignore_retry_delay or not rate_limit,
        )
        if remaining and remaining.id not in attempted_ids:
            # Artificial pause only in field mode (rate_limit=True never reaches here).
            await _sleep_between_joins(rate_limit=False, sleeper=sleeper)

    joined_chats = 0
    full_targets = 0
    per_target: list[dict[str, Any]] = []
    for chat in chats:
        joined, total = await membership_counts(session, chat.id)
        error_rows = (
            await session.execute(
                select(AccountChatMembership.last_join_error)
                .where(
                    AccountChatMembership.chat_target_id == chat.id,
                    AccountChatMembership.join_status != ChatJoinStatus.JOINED.value,
                    AccountChatMembership.last_join_error.is_not(None),
                )
                .limit(3)
            )
        ).scalars().all()
        errors = [str(err) for err in error_rows if err]
        per_target.append(
            {
                "chat_target_id": chat.id,
                "title": chat.title,
                "invite_link": chat.invite_link,
                "joined": joined,
                "total": total,
                "join_status": chat.join_status,
                "errors": errors,
            }
        )
        if include_lab:
            if joined > 0:
                joined_chats += 1
            if total and joined >= total:
                full_targets += 1
        elif total and joined >= total:
            joined_chats += 1
            full_targets += 1
    return {
        "accounts": len(accounts),
        "chats": len(chats),
        "attempts": attempts,
        "joined_chats": joined_chats,
        "joined_pairs": joined_pairs,
        "failed_pairs": failed_pairs,
        "rate_limited_pairs": rate_limited_pairs,
        "full_targets": full_targets,
        "per_target": per_target,
    }


async def join_pending_chats(
    session: AsyncSession,
    automation_id: int,
    *,
    max_attempts: int = MAX_JOIN_ATTEMPTS,
    rate_limit: bool = True,
    sleeper=None,
    max_pairs: int | None = None,
) -> list[dict[str, Any]]:
    """Join pending account×chat pairs. Scheduler: one pair per account per tick."""
    del sleeper
    from .pending_action_service import process_due_pending_actions
    from .chat_addlist_service import ensure_task_joins_for_automation, join_pending_addlists

    from .job_service import JOIN_JOB_TYPES, list_active_job_types

    active = await list_active_job_types(automation_id)
    need_task_joins = bool(active & JOIN_JOB_TYPES)
    if need_task_joins:
        await ensure_task_joins_for_automation(session, automation_id)
        await join_pending_addlists(session, automation_id)
        if rate_limit and not farm_overlap_active_hours():
            return []
        seed = await join_next_seed_channel(session, automation_id, apply_cooldown=rate_limit)
        return [seed] if seed else []
    else:
        await recover_stale_joining_memberships(session, automation_id)
        await process_due_pending_actions(session, automation_id)
        automation = await session.get(CustomAutomation, automation_id)
        warmup = ((automation.module_settings or {}).get("warmup") or {}) if automation else {}
        if not (
            automation
            and getattr(automation, "account_warmup_enabled", False)
            and warmup.get("do_joins") is not False
        ):
            return []
        await ensure_memberships_for_automation(session, automation_id)
    await recover_stale_joining_memberships(session, automation_id)
    await process_due_pending_actions(session, automation_id)
    if rate_limit and not farm_overlap_active_hours():
        return []
    pairs = max_pairs if max_pairs is not None else (MAX_JOINS_PER_TICK if rate_limit else 10_000)
    from .rotation_service import list_alive_session_accounts
    from .account_pacing import account_uses_seed_channel_joins

    alive = await list_alive_session_accounts(session, automation_id)
    used_accounts: set[int] = {
        account.id
        for account in alive
        if account_membership_should_idle(account) or account_uses_seed_channel_joins(account)
    }
    results: list[dict[str, Any]] = []
    seed = await join_next_seed_channel(
        session,
        automation_id,
        exclude_account_ids={account.id for account in alive if account_membership_should_idle(account)},
        apply_cooldown=rate_limit,
    )
    if seed:
        results.append(seed)
        if seed.get("account_id"):
            used_accounts.add(int(seed["account_id"]))
    for _ in range(max(0, pairs - len(results))):
        outcome = await join_next_membership(
            session,
            automation_id,
            max_attempts=max_attempts,
            exclude_account_ids=used_accounts,
            apply_cooldown=rate_limit,
            skip_ensure=True,
        )
        if not outcome:
            break
        account_id = outcome.get("account_id")
        if account_id:
            used_accounts.add(int(account_id))
        results.append(outcome)
    return results


async def run_join_pending_for_automation(automation_id: int) -> list[dict[str, Any]]:
    """Scheduler entrypoint: join one chat per idle account, respecting per-account delays."""
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        return await join_pending_chats(session, automation_id, max_pairs=MAX_JOINS_PER_TICK)


async def leave_chat_for_account(
    session: AsyncSession,
    chat_target: ChatTarget,
    account: SocialAccount,
) -> dict[str, Any]:
    """Leave a channel/megagroup (or basic chat) with one account."""
    if getattr(account, "is_frozen", False) or account.is_banned or not account.is_active:
        return {"status": "skipped", "error": "account_unavailable"}
    if not account.session_file_path and not getattr(account, "encrypted_session", None):
        return {"status": "failed", "error": "no session file"}
    try:
        parsed = _parse_chat_ref(chat_target)
    except TelegramChatRefError:
        return {"status": "failed", "error": "invalid invite link"}
    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await _resolve_entity(client, parsed)
            target = unwrap_telegram_chat(entity) or entity
            name = type(target).__name__
            if name == "Channel" or getattr(target, "broadcast", False) or getattr(target, "megagroup", False):
                try:
                    await client(LeaveChannelRequest(target))
                except UserNotParticipantError:
                    pass
            elif name == "Chat" or getattr(target, "id", None):
                me = await client.client.get_me()
                try:
                    await client(DeleteChatUserRequest(int(target.id), me.id))
                except Exception:
                    # Already left / not a basic chat — ignore.
                    if await _is_participant(client, target) is True:
                        raise
            else:
                return {"status": "failed", "error": "unsupported chat type"}
        return {"status": "left"}
    except FloodWaitError as exc:
        from .account_pacing import schedule_flood_quarantine

        schedule_flood_quarantine(account)
        return {"status": "rate_limited", "error": f"FloodWait: {exc.seconds or 60}s"}
    except Exception as exc:
        from .telegram_error_handler import _classify_telegram_error, update_account_after_telegram_error

        kind = _classify_telegram_error(exc).get("kind")
        if kind in {"frozen", "deactivated", "session"}:
            await update_account_after_telegram_error(session, account, exc)
            return {"status": "skipped", "error": kind}
        logger.warning("Leave chat %s failed for account %s: %s", chat_target.id, account.id, exc)
        return {"status": "failed", "error": _friendly_telegram_error(exc, "Не удалось выйти")[:255]}


async def leave_loaded_chats_for_accounts(
    session: AsyncSession,
    automation_id: int,
    *,
    chat_ids: list[int],
) -> dict[str, Any]:
    """Lab reset helper: every pool account leaves the given chats and memberships go pending."""
    from .rotation_service import list_alive_session_accounts

    accounts = await list_alive_session_accounts(session, automation_id)
    if not chat_ids or not accounts:
        return {"accounts": len(accounts), "chats": 0, "left_pairs": 0, "failed_pairs": 0}
    chats = (
        await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.id.in_(chat_ids),
            )
        )
    ).scalars().all()
    left_pairs = 0
    failed_pairs = 0
    now = _utc_now()
    for chat in chats:
        await ensure_memberships_for_chat(
            session,
            automation_id,
            chat,
            account_ids=[account.id for account in accounts],
            include_lab=True,
        )
        memberships = (
            await session.execute(
                select(AccountChatMembership).where(
                    AccountChatMembership.chat_target_id == chat.id,
                    AccountChatMembership.social_account_id.in_([a.id for a in accounts]),
                )
            )
        ).scalars().all()
        by_account = {m.social_account_id: m for m in memberships}
        for account in accounts:
            outcome = await leave_chat_for_account(session, chat, account)
            membership = by_account.get(account.id)
            if outcome.get("status") == "left":
                left_pairs += 1
                if membership:
                    membership.join_status = ChatJoinStatus.PENDING.value
                    membership.joined_at = None
                    membership.join_attempts = 0
                    membership.next_join_attempt_at = None
                    membership.last_join_error = None
                    membership.updated_at = now
            else:
                failed_pairs += 1
                if membership and membership.join_status == ChatJoinStatus.JOINED.value:
                    # Still force lab reset so «Вступить» can be recorded again.
                    membership.join_status = ChatJoinStatus.PENDING.value
                    membership.joined_at = None
                    membership.join_attempts = 0
                    membership.next_join_attempt_at = None
                    membership.last_join_error = outcome.get("error")
                    membership.updated_at = now
        chat.join_status = ChatJoinStatus.PENDING.value
        chat.joined_at = None
        chat.joined_by_account_id = None
        chat.updated_at = now
        await sync_chat_join_status(session, chat)
    await session.commit()
    return {
        "accounts": len(accounts),
        "chats": len(chats),
        "left_pairs": left_pairs,
        "failed_pairs": failed_pairs,
    }


__all__ = [
    "create_chat_from_link",
    "join_loaded_chats_for_accounts",
    "join_pending_chats",
    "leave_loaded_chats_for_accounts",
    "preview_chat_entity",
    "run_join_pending_for_automation",
    "sync_memberships_with_telegram",
]
