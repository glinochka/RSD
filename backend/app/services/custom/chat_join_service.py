"""Join Telegram chats/channels from pool accounts and resolve them on create."""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FloodWaitError, InviteHashExpiredError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

from .chat_scope import apply_entity_metadata, is_user_peer, unwrap_telegram_chat
from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import SessionInvalidError
from .telegram_invite import TelegramChatRef, TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import ChatJoinStatus, ChatMode, ChatSource, ChatTarget, SocialAccount

logger = logging.getLogger(__name__)

try:
    from telethon.errors import InviteRequestSentError
except Exception:  # pragma: no cover - older Telethon
    class InviteRequestSentError(Exception):
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
    mapped = _LOOKUP_ERRORS.get(type(exc).__name__)
    if mapped:
        return mapped
    text = str(exc) or type(exc).__name__
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


async def _join_public(client: TelegramAccountClient, parsed: TelegramChatRef) -> Any:
    entity = await client.get_entity(parsed.lookup_value)
    if is_user_peer(entity):
        raise ValueError("Это пользователь, а не чат или канал")
    if _can_join_as_channel(entity):
        try:
            joined = await client(JoinChannelRequest(unwrap_telegram_chat(entity)))
            return joined or entity
        except UserAlreadyParticipantError:
            return entity
        except InviteRequestSentError:
            raise
    return entity


async def _join_private(client: TelegramAccountClient, parsed: TelegramChatRef) -> Any:
    try:
        return await client(ImportChatInviteRequest(parsed.value))
    except UserAlreadyParticipantError:
        return await client(CheckChatInviteRequest(parsed.value))


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
            try:
                if parsed.kind == "invite":
                    entity = await _join_private(client, parsed)
                else:
                    entity = await _join_public(client, parsed)
            except InviteRequestSentError:
                try:
                    entity = await _resolve_entity(client, parsed)
                except Exception:
                    entity = None
                if entity is not None:
                    apply_entity_metadata(chat_target, entity)
                    chat_target.invite_link = parsed.canonical
                return {"status": "failed", "error": "Нужно одобрение заявки на вступление"}

            if entity is not None:
                apply_entity_metadata(chat_target, entity)
                chat_target.invite_link = parsed.canonical

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
        return {"status": "joined", "joined_at": _utc_now(), "joined_by_account_id": account.id}
    except SessionInvalidError as exc:
        logger.warning("Join chat %s skipped account %s: %s", chat_target.id, account.id, exc)
        return {"status": "failed", "error": "session_invalid", "retry_account": True}
    except ValueError as exc:
        return {"status": "failed", "error": str(exc)[:255]}
    except Exception as exc:
        logger.warning("Join chat %s failed for account %s: %s", chat_target.id, account.id, exc)
        return {"status": "failed", "error": _friendly_telegram_error(exc, "Не удалось вступить")[:255]}


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
            "commenting",
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

    existing = await session.scalar(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.invite_link == parsed.canonical,
        )
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

    if chat.external_chat_id:
        duplicate = await session.scalar(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.external_chat_id == chat.external_chat_id,
            )
        )
        if duplicate:
            raise ValueError("Этот чат уже добавлен")

    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


async def join_pending_chats(
    session: AsyncSession,
    automation_id: int,
    *,
    max_attempts: int = 3,
) -> list[dict[str, Any]]:
    """Attempt to join all chats that are pending or ready for retry."""
    now = _utc_now()
    result = await session.execute(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.is_active.is_(True),
            ChatTarget.provider == "telegram",
            ChatTarget.join_status.in_(
                [ChatJoinStatus.PENDING.value, ChatJoinStatus.JOINING.value, ChatJoinStatus.RATE_LIMITED.value]
            ),
            ChatTarget.join_attempts < max_attempts,
            (ChatTarget.next_join_attempt_at.is_(None)) | (ChatTarget.next_join_attempt_at <= now),
        )
    )
    chats = result.scalars().all()

    results = []
    for chat_target in chats:
        excluded: set[int] = set()
        join_result: dict[str, Any] | None = None
        account = None
        chat_target.join_status = ChatJoinStatus.JOINING.value
        chat_target.join_attempts += 1
        chat_target.last_join_attempt_at = now
        await session.commit()

        for _ in range(3):
            account = await select_account_for_action(
                session,
                automation_id,
                "commenting",
                exclude_account_ids=excluded,
            )
            if not account:
                join_result = {"status": "skipped", "error": "no eligible account"}
                break
            excluded.add(account.id)
            join_result = await _try_join_chat(session, chat_target, account)
            if join_result["status"] == "joined" or not join_result.get("retry_account"):
                break

        if join_result is None:
            join_result = {"status": "skipped", "error": "no eligible account"}

        chat_target.updated_at = now

        if join_result["status"] == "joined":
            chat_target.join_status = ChatJoinStatus.JOINED.value
            chat_target.joined_at = join_result.get("joined_at")
            chat_target.joined_by_account_id = join_result.get("joined_by_account_id")
            chat_target.next_join_attempt_at = None
            chat_target.last_join_error = None
        elif join_result["status"] == "rate_limited":
            chat_target.join_status = ChatJoinStatus.RATE_LIMITED.value
            chat_target.next_join_attempt_at = join_result.get("next_join_attempt_at")
            chat_target.last_join_error = join_result.get("error")
        elif join_result["status"] == "skipped":
            chat_target.join_status = ChatJoinStatus.PENDING.value
            chat_target.last_join_error = join_result.get("error")
        else:
            error = join_result.get("error")
            if error == "session_invalid":
                error = "Не удалось войти в Telegram. Если вы не выходили из аккаунта — подождите и попробуйте снова."
            chat_target.join_status = ChatJoinStatus.ERROR.value
            chat_target.last_join_error = error
            chat_target.next_join_attempt_at = now + timedelta(minutes=random.randint(2, 5))

        await session.commit()
        results.append({"chat_target_id": chat_target.id, "status": join_result["status"]})

    return results


async def run_join_pending_for_automation(automation_id: int) -> list[dict[str, Any]]:
    """Scheduler entrypoint: open a session and join pending chats."""
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        return await join_pending_chats(session, automation_id)
