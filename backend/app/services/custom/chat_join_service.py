"""Join Telegram chats from pool accounts with rate-limit handling."""
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.errors import FloodWaitError, InviteHashExpiredError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from .rotation_service import select_account_for_action
from .telegram_account_client import TelegramAccountClient
from ...alembic.models import ChatJoinStatus, ChatTarget, SocialAccount
from ...config import settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def is_private_invite_link(link: str | None) -> bool:
    if not link:
        return False
    lower = link.strip().lower()
    return "/+" in lower or "joinchat" in lower or lower.startswith("+")


def _extract_invite_hash(link: str) -> str | None:
    if not link:
        return None
    parsed = urlparse(link.strip())
    path = parsed.path.strip("/")
    if path.lower().startswith("joinchat/"):
        path = path.split("/", 1)[-1]
    if path.startswith("+"):
        return path[1:]
    parts = path.split("/")
    if parts:
        last = parts[-1]
        if last.startswith("+"):
            return last[1:]
        if len(last) > 5 and is_private_invite_link(link):
            return last
    return None


async def _try_join_chat(
    session: AsyncSession,
    chat_target: ChatTarget,
    account: SocialAccount,
) -> dict[str, Any]:
    if not account.session_file_path:
        return {"status": "failed", "error": "no session file"}

    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return {"status": "failed", "error": "session file missing"}

    try:
        async with TelegramAccountClient(str(session_path)) as client:
            invite_link = chat_target.invite_link
            entity = None
            if invite_link and is_private_invite_link(invite_link):
                invite_hash = _extract_invite_hash(invite_link)
                if not invite_hash:
                    return {"status": "failed", "error": "invalid invite link"}
                try:
                    entity = await client(ImportChatInviteRequest(invite_hash))
                except UserAlreadyParticipantError:
                    entity = await client.resolve_peer(invite_link)
            else:
                identifier = invite_link or chat_target.external_chat_id or chat_target.title
                if not identifier:
                    return {"status": "failed", "error": "no chat identifier"}
                entity = await client.resolve_peer(identifier)
                try:
                    await client(JoinChannelRequest(entity))
                except UserAlreadyParticipantError:
                    pass

            if entity is not None:
                chat_id = getattr(getattr(entity, "chats", [None])[0] if hasattr(entity, "chats") else entity, "id", None)
                if chat_id:
                    chat_target.external_chat_id = str(chat_id)

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
        return {"status": "failed", "error": "invite link expired"}
    except UserAlreadyParticipantError:
        return {"status": "joined", "joined_at": _utc_now(), "joined_by_account_id": account.id}
    except Exception as exc:
        logger.warning("Join chat %s failed for account %s: %s", chat_target.id, account.id, exc)
        return {"status": "failed", "error": str(exc)[:255]}


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
        account = await select_account_for_action(session, automation_id, "commenting")
        if not account:
            results.append({"chat_target_id": chat_target.id, "status": "skipped", "error": "no eligible account"})
            continue

        chat_target.join_status = ChatJoinStatus.JOINING.value
        chat_target.join_attempts += 1
        chat_target.last_join_attempt_at = now
        await session.commit()

        join_result = await _try_join_chat(session, chat_target, account)
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
        else:
            chat_target.join_status = ChatJoinStatus.ERROR.value
            chat_target.last_join_error = join_result.get("error")
            chat_target.next_join_attempt_at = now + timedelta(minutes=random.randint(2, 5))

        await session.commit()
        results.append({"chat_target_id": chat_target.id, "status": join_result["status"]})

    return results


async def run_join_pending_for_automation(automation_id: int) -> list[dict[str, Any]]:
    """Scheduler entrypoint: open a session and join pending chats."""
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        return await join_pending_chats(session, automation_id)
