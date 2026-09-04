"""Join Telegram chats/channels from pool accounts and resolve them on create."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FloodWaitError, InviteHashExpiredError, UserAlreadyParticipantError
from telethon.tl.functions.channels import GetParticipantRequest, JoinChannelRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

from .chat_membership_service import (
    bulk_membership_counts,
    ensure_memberships_for_automation,
    ensure_memberships_for_chat,
    membership_counts,
    pick_next_pending_membership,
    recover_stale_joining_memberships,
    sync_chat_join_status,
)
from .chat_scope import apply_entity_metadata, is_lab_chat, is_user_peer, unwrap_telegram_chat
from .chat_target_dedup import find_existing_chat_target
from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import SessionInvalidError, execute_with_telegram_retry, log_action_error
from .telegram_invite import TelegramChatRef, TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import AccountChatMembership, ChatJoinStatus, ChatMode, ChatSource, ChatTarget, SocialAccount

logger = logging.getLogger(__name__)

JOIN_DELAY_MIN_SECONDS = 120
JOIN_DELAY_MAX_SECONDS = 300

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
    entity = await client.get_entity(parsed.lookup_value)
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

    try:
        parsed = _parse_chat_ref(chat_target)
    except TelegramChatRefError:
        return {"status": "failed", "error": "invalid invite link"}

    try:
        async with TelegramAccountClient.for_account(account) as client:
            automation_id = int(chat_target.custom_automation_id)

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
                    max_retries=3,
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

        return {
            "status": "joined",
            "joined_at": _utc_now(),
            "joined_by_account_id": account.id,
        }
    except FloodWaitError as exc:
        wait_seconds = exc.seconds or random.randint(120, 300)
        return {
            "status": "rate_limited",
            "error": f"FloodWait: {wait_seconds}s",
            "next_join_attempt_at": _utc_now() + timedelta(seconds=wait_seconds),
        }
    except InviteHashExpiredError:
        return {"status": "failed", "error": "Ссылка-приглашение истекла"}
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
        logger.warning("Join chat %s failed for account %s: %s", chat_target.id, account.id, exc)
        return {"status": "failed", "error": _friendly_telegram_error(exc, "Не удалось вступить")[:255]}


async def _apply_membership_result(
    session: AsyncSession,
    membership: AccountChatMembership,
    chat_target: ChatTarget,
    account: SocialAccount,
    join_result: dict[str, Any],
    *,
    automation_id: int,
) -> None:
    now = _utc_now()
    membership.join_attempts += 1
    membership.last_join_attempt_at = now
    membership.updated_at = now

    if join_result.get("retry_account"):
        membership.join_status = ChatJoinStatus.PENDING.value
        membership.last_join_error = join_result.get("error")
        membership.join_attempts = max(0, membership.join_attempts - 1)
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
    elif join_result["status"] == "skipped":
        membership.last_join_error = join_result.get("error")
    else:
        error = join_result.get("error")
        if error == "session_invalid":
            error = "Не удалось войти в Telegram. Если вы не выходили из аккаунта — подождите и попробуйте снова."
        membership.join_status = ChatJoinStatus.ERROR.value
        membership.last_join_error = error
        membership.next_join_attempt_at = now + timedelta(minutes=random.randint(2, 5))
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
            wait_seconds = exc.seconds or 60
            raise ValueError(f"Telegram просит подождать {wait_seconds} сек.") from exc
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
) -> ChatTarget:
    parsed = parse_telegram_chat_ref(raw_link)

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


async def join_next_membership(
    session: AsyncSession,
    automation_id: int,
    *,
    max_attempts: int = 5,
) -> dict[str, Any] | None:
    """Process one pending account×chat join (scheduler entry)."""
    await ensure_memberships_for_automation(session, automation_id)
    await recover_stale_joining_memberships(session, automation_id)
    membership = await pick_next_pending_membership(session, automation_id, max_attempts=max_attempts)
    if not membership:
        return None

    chat_target = await session.get(ChatTarget, membership.chat_target_id)
    account = await session.get(SocialAccount, membership.social_account_id)
    if not chat_target or not account:
        return {"status": "skipped", "reason": "missing_entities"}

    membership.join_status = ChatJoinStatus.JOINING.value
    membership.updated_at = _utc_now()
    await session.commit()

    join_result = await _try_join_chat(session, chat_target, account)
    await _apply_membership_result(
        session,
        membership,
        chat_target,
        account,
        join_result,
        automation_id=automation_id,
    )
    await session.commit()
    return {
        "membership_id": membership.id,
        "chat_target_id": chat_target.id,
        "account_id": account.id,
        "status": join_result.get("status"),
    }


async def sync_memberships_with_telegram(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    account_ids: list[int] | None = None,
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
        if not account or account.is_banned or not account.is_active:
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
        elif membership.join_status == ChatJoinStatus.JOINED.value:
            membership.join_status = ChatJoinStatus.PENDING.value
            membership.joined_at = None
            membership.last_join_error = "Не состоит в участниках Telegram"
            membership.updated_at = now
        else:
            membership.last_join_error = membership.last_join_error or "Не состоит в участниках Telegram"
            membership.updated_at = now

    await sync_chat_join_status(session, chat_target)
    await session.commit()
    return await membership_counts(session, chat_target.id)


async def _requeue_unverified_joined_memberships(
    session: AsyncSession,
    automation_id: int,
    *,
    chat_target_ids: list[int],
    account_ids: list[int],
) -> int:
    """Lab only: if DB says joined but Telegram says not — put back to pending."""
    if not chat_target_ids or not account_ids:
        return 0
    reset = 0
    for chat_id in chat_target_ids:
        chat_target = await session.get(ChatTarget, chat_id)
        if not chat_target:
            continue
        before_joined, _ = await membership_counts(session, chat_id)
        await sync_memberships_with_telegram(
            session,
            automation_id,
            chat_target,
            account_ids=account_ids,
        )
        after_joined, _ = await membership_counts(session, chat_id)
        if after_joined < before_joined:
            reset += before_joined - after_joined
    return reset


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
    for chat in chats:
        await ensure_memberships_for_chat(
            session,
            automation_id,
            chat,
            account_ids=[account.id for account in accounts],
            include_lab=include_lab,
        )
    if include_lab and target_ids:
        await _requeue_unverified_joined_memberships(
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
    while True:
        membership = await pick_next_pending_membership(
            session,
            automation_id,
            include_lab=include_lab,
            chat_target_ids=target_ids if chat_ids else None,
            ignore_retry_delay=ignore_retry_delay,
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
        )
        await session.commit()
        if rate_limit:
            break
        remaining = await pick_next_pending_membership(
            session,
            automation_id,
            include_lab=include_lab,
            chat_target_ids=target_ids if chat_ids else None,
            ignore_retry_delay=ignore_retry_delay,
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
    max_attempts: int = 3,
    rate_limit: bool = True,
    sleeper=None,
    max_pairs: int | None = 1,
) -> list[dict[str, Any]]:
    """Join pending account×chat pairs. Default: one pair per call (scheduler)."""
    results: list[dict[str, Any]] = []
    pairs = max_pairs if max_pairs is not None else (1 if rate_limit else 10_000)
    for index in range(pairs):
        outcome = await join_next_membership(session, automation_id, max_attempts=max_attempts)
        if not outcome:
            break
        results.append(outcome)
        if index < pairs - 1 and rate_limit:
            await _sleep_between_joins(rate_limit=True, sleeper=sleeper)
    return results


async def run_join_pending_for_automation(automation_id: int) -> list[dict[str, Any]]:
    """Scheduler entrypoint: open a session and join one pending membership."""
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        return await join_pending_chats(session, automation_id, max_pairs=1)


__all__ = [
    "create_chat_from_link",
    "join_loaded_chats_for_accounts",
    "join_pending_chats",
    "preview_chat_entity",
    "run_join_pending_for_automation",
]
