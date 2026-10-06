"""Parser: collect users from uploaded chat folders and live Telegram history."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_humanization_should_idle, farm_overlap_active_hours, schedule_account_humanization_rest
from .module_account_filters import no_accounts_picked, skip_account_for_module
from .rotation_service import record_successful_humanization
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import (
    AutomationActionLog,
    ChatTarget,
    CustomAutomation,
    ParserUser,
    PoolAccount,
    SocialAccount,
)
from ...config import settings

logger = logging.getLogger(__name__)

ACTION_TYPE = "parser"
MODES = ("messages", "participants", "comments")
SINCE_HOURS = (1, 6, 24, 72, 168, 720)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_int_list(raw: Any) -> list[int]:
    items: list[int] = []
    seen: set[int] = set()
    for value in raw or []:
        try:
            ident = int(value)
        except (TypeError, ValueError):
            continue
        if ident in seen:
            continue
        seen.add(ident)
        items.append(ident)
    return items


def normalize_parser_targets(raw: Any) -> list[str]:
    if isinstance(raw, str):
        values = raw.replace(",", "\n").splitlines()
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            ref = parse_telegram_chat_ref(text)
        except TelegramChatRefError:
            continue
        key = ref.canonical.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ref.canonical)
        if len(out) >= 400:
            break
    return out


def normalize_since_hours(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 24
    if value in SINCE_HOURS:
        return value
    return min(SINCE_HOURS, key=lambda item: abs(item - max(1, value)))


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def describe_user(entity: Any) -> dict[str, Any]:
    user_id = getattr(entity, "id", None)
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        user_id = 0
    photo = getattr(entity, "photo", None)
    return {
        "telegram_user_id": user_id,
        "username": (getattr(entity, "username", None) or "").strip() or None,
        "first_name": (getattr(entity, "first_name", None) or "").strip() or None,
        "last_name": (getattr(entity, "last_name", None) or "").strip() or None,
        "is_bot": bool(getattr(entity, "bot", False)),
        "is_deleted": bool(getattr(entity, "deleted", False)),
        "is_scam": bool(getattr(entity, "scam", False) or getattr(entity, "fake", False)),
        "is_premium": bool(getattr(entity, "premium", False)),
        "has_photo": bool(photo),
        "is_self": bool(getattr(entity, "is_self", False)),
    }


def user_passes_filters(
    row: dict[str, Any],
    *,
    skip_bots: bool = True,
    skip_deleted: bool = True,
    skip_scam: bool = False,
    only_username: bool = False,
    only_photo: bool = False,
    only_premium: bool = False,
    only_admins: bool = False,
    only_active_stories: bool = False,
) -> bool:
    if not row.get("telegram_user_id") or row.get("is_self"):
        return False
    if skip_bots and row.get("is_bot"):
        return False
    if skip_deleted and row.get("is_deleted"):
        return False
    if skip_scam and row.get("is_scam"):
        return False
    if only_username and not row.get("username"):
        return False
    if only_photo and not row.get("has_photo"):
        return False
    if only_premium and not row.get("is_premium"):
        return False
    if only_admins and not row.get("is_admin"):
        return False
    if only_active_stories and not row.get("has_stories"):
        return False
    return True


def collect_authors_from_messages(
    messages: Iterable[Any],
    *,
    since: datetime,
    member_limit: int,
) -> list[dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    for message in messages:
        date = _naive(getattr(message, "date", None))
        if date and date < since:
            break
        sender = getattr(message, "sender", None)
        if sender is None:
            continue
        row = describe_user(sender)
        if not row["telegram_user_id"]:
            continue
        row["last_message_at"] = date
        row["is_admin"] = bool(row.get("is_admin"))
        found.setdefault(row["telegram_user_id"], row)
        if member_limit > 0 and len(found) >= member_limit:
            break
    return list(found.values())


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _chat_ref(chat: ChatTarget) -> str:
    return chat.invite_link or chat.external_chat_id or chat.title or f"chat:{chat.id}"


async def _log_parse(
    session: AsyncSession,
    *,
    automation_id: int,
    account: SocialAccount,
    target_id: str,
    title: str,
    payload: dict[str, Any],
    result: str = "success",
) -> None:
    session.add(
        AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account.id,
            action_type=ACTION_TYPE,
            target_id=target_id,
            target_type="chat",
            result=result,
            payload={"title": title, **payload},
            created_at=_utc_now(),
        )
    )
    await session.commit()


async def _save_users(
    session: AsyncSession,
    automation_id: int,
    rows: list[dict[str, Any]],
    *,
    source_mode: str,
    chat: ChatTarget | None,
    extra_title: str | None = None,
) -> int:
    saved = 0
    chat_key = str(chat.id) if chat else (extra_title or "target")[:128]
    title = (chat.title if chat else extra_title) or extra_title
    for row in rows:
        uid = int(row["telegram_user_id"])
        existing = await session.scalar(
            select(ParserUser).where(
                ParserUser.custom_automation_id == automation_id,
                ParserUser.telegram_user_id == uid,
                ParserUser.source_chat_id == chat_key,
            )
        )
        if existing:
            existing.username = row.get("username") or existing.username
            existing.first_name = row.get("first_name") or existing.first_name
            existing.last_name = row.get("last_name") or existing.last_name
            existing.is_premium = bool(row.get("is_premium"))
            existing.has_photo = bool(row.get("has_photo"))
            existing.is_admin = bool(row.get("is_admin") or existing.is_admin)
            existing.last_message_at = row.get("last_message_at") or existing.last_message_at
            saved += 1
            continue
        session.add(
            ParserUser(
                custom_automation_id=automation_id,
                telegram_user_id=uid,
                username=row.get("username"),
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                source_mode=source_mode,
                source_chat_id=chat_key,
                source_title=(title or "")[:255] or None,
                is_bot=bool(row.get("is_bot")),
                is_premium=bool(row.get("is_premium")),
                has_photo=bool(row.get("has_photo")),
                is_admin=bool(row.get("is_admin")),
                last_message_at=row.get("last_message_at"),
                created_at=_utc_now(),
            )
        )
        saved += 1
    await session.commit()
    return saved


async def _iter_messages(telethon: Any, entity: Any, *, limit: int, reply_to: int | None = None):
    kwargs: dict[str, Any] = {"limit": limit}
    if reply_to is not None:
        kwargs["reply_to"] = reply_to
    iterator = telethon.iter_messages(entity, **kwargs)
    async for item in iterator:
        yield item


async def _load_sender(telethon: Any, message: Any) -> Any | None:
    sender = getattr(message, "sender", None)
    if sender is not None and getattr(sender, "id", None):
        return sender
    from_id = getattr(message, "from_id", None)
    if from_id is None:
        return None
    try:
        return await telethon.get_entity(from_id)
    except Exception:
        return None


async def collect_live_authors(
    telethon: Any,
    entity: Any,
    *,
    mode: str,
    since: datetime,
    member_limit: int,
    admin_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    cap = member_limit if member_limit > 0 else 1000
    scan_cap = min(max(cap * 8, cap), 4000)

    async def _accept(sender: Any, *, date: datetime | None = None, is_admin: bool = False) -> None:
        row = describe_user(sender)
        if not row["telegram_user_id"]:
            return
        if admin_ids and row["telegram_user_id"] in admin_ids:
            row["is_admin"] = True
        elif is_admin:
            row["is_admin"] = True
        row["last_message_at"] = date
        found.setdefault(row["telegram_user_id"], row)

    if mode == "participants":
        iterator = telethon.iter_participants(entity)
        async for user in iterator:
            await _accept(user, is_admin=bool(getattr(user, "participant", None) and getattr(user.participant, "admin_rights", None)))
            if len(found) >= cap:
                break
        return list(found.values())

    if mode == "comments":
        posts = []
        async for post in _iter_messages(telethon, entity, limit=40):
            posts.append(post)
        for post in posts:
            post_id = getattr(post, "id", None)
            if not post_id:
                continue
            try:
                async for comment in _iter_messages(telethon, entity, limit=200, reply_to=int(post_id)):
                    date = _naive(getattr(comment, "date", None))
                    if date and date < since:
                        break
                    sender = await _load_sender(telethon, comment)
                    if sender:
                        await _accept(sender, date=date)
                    if len(found) >= cap:
                        return list(found.values())
            except Exception as exc:
                logger.debug("Parser comments skipped for post %s: %s", post_id, exc)
        return list(found.values())

    scanned = 0
    async for message in _iter_messages(telethon, entity, limit=scan_cap):
        scanned += 1
        date = _naive(getattr(message, "date", None))
        if date and date < since:
            break
        sender = await _load_sender(telethon, message)
        if sender:
            await _accept(sender, date=date)
        if len(found) >= cap:
            break
        if scanned >= scan_cap:
            break
    return list(found.values())


async def _admin_ids(telethon: Any, entity: Any) -> set[int]:
    ids: set[int] = set()
    getter = getattr(telethon, "get_participants", None) or getattr(telethon, "iter_participants", None)
    if getter is None:
        return ids
    try:
        from telethon.tl.types import ChannelParticipantsAdmins

        async for user in telethon.iter_participants(entity, filter=ChannelParticipantsAdmins()):
            uid = getattr(user, "id", None)
            if uid:
                ids.add(int(uid))
    except Exception as exc:
        logger.debug("Parser admin list skipped: %s", exc)
    return ids


async def _has_active_stories(client: Any, entity: Any) -> bool:
    try:
        from .humanization_session import load_peer_stories

        _peer, stories = await load_peer_stories(client, entity)
        return bool(stories)
    except Exception:
        return False


async def _process_entity(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    cfg: dict[str, Any],
    telethon: Any,
    client: Any,
    entity: Any,
    *,
    chat: ChatTarget | None,
    title: str,
    target_id: str,
) -> int:
    mode = str(cfg.get("source") or "messages").strip().lower()
    if mode not in MODES:
        mode = "messages"
    since = _utc_now() - timedelta(hours=normalize_since_hours(cfg.get("since_hours")))
    try:
        member_limit = int(cfg.get("member_limit") or 1000)
    except (TypeError, ValueError):
        member_limit = 1000
    admin_ids: set[int] = set()
    if cfg.get("only_admins"):
        admin_ids = await _admin_ids(telethon, entity)
    raw = await collect_live_authors(
        telethon,
        entity,
        mode=mode,
        since=since,
        member_limit=max(1, min(member_limit, 10000)),
        admin_ids=admin_ids or None,
    )
    if cfg.get("only_active_stories"):
        for row in raw:
            try:
                peer = await telethon.get_entity(row["telegram_user_id"])
                row["has_stories"] = await _has_active_stories(client, peer)
            except Exception:
                row["has_stories"] = False
    kept = [
        row
        for row in raw
        if user_passes_filters(
            row,
            skip_bots=bool(cfg.get("skip_bots", True)),
            skip_deleted=bool(cfg.get("skip_deleted", True)),
            skip_scam=bool(cfg.get("skip_scam")),
            only_username=bool(cfg.get("only_username")),
            only_photo=bool(cfg.get("only_photo")),
            only_premium=bool(cfg.get("only_premium")),
            only_admins=bool(cfg.get("only_admins")),
            only_active_stories=bool(cfg.get("only_active_stories")),
        )
    ]
    saved = await _save_users(session, automation.id, kept, source_mode=mode, chat=chat, extra_title=title)
    await _log_parse(
        session,
        automation_id=automation.id,
        account=account,
        target_id=target_id,
        title=title,
        payload={"users": saved, "scanned": len(raw), "mode": mode},
    )
    return saved


async def run_parser_pass(automation_id: int, run_config: dict[str, Any] | None = None) -> dict[str, Any]:
    from ...alembic.database import async_session_maker
    from .chat_join_service import join_loaded_chats_for_accounts

    total = 0
    chats_used = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "missing", "users": 0}
        cfg = run_config if isinstance(run_config, dict) else ((automation.module_settings or {}).get("parser") or {})
        if not bool(cfg.get("enabled")):
            return {"status": "skipped", "reason": "disabled", "users": 0}
        if no_accounts_picked(cfg):
            return {"status": "skipped", "reason": "no_accounts", "users": 0}
        if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
            return {"status": "skipped", "reason": "night", "users": 0}
        allowed = set(_as_int_list(cfg.get("account_ids")))
        blocked = set(_as_int_list(cfg.get("blacklisted_account_ids")))
        folder_ids = set(_as_int_list(cfg.get("folder_ids")))
        chat_ids = set(_as_int_list(cfg.get("chat_ids")))
        chats_q = select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id, ChatTarget.is_active.is_(True))
        chats = (await session.execute(chats_q)).scalars().all()
        if folder_ids:
            chats = [chat for chat in chats if chat.folder_id in folder_ids or chat.id in chat_ids]
        elif chat_ids:
            chats = [chat for chat in chats if chat.id in chat_ids]
        extra_targets = normalize_parser_targets(cfg.get("targets"))
        if not chats and not extra_targets:
            return {"status": "skipped", "reason": "no_targets", "users": 0}
        pairs = (
            await session.execute(
                select(SocialAccount, PoolAccount)
                .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
                .where(PoolAccount.custom_automation_id == automation_id)
            )
        ).all()
        accounts: list[tuple[SocialAccount, PoolAccount]] = []
        for account, pool in pairs:
            if allowed and account.id not in allowed:
                continue
            if account.id in blocked:
                continue
            if not account.is_active or account.is_banned or account.is_frozen or getattr(account, "is_spamblocked", False):
                continue
            if not account.session_file_path or not (_media_root() / account.session_file_path).exists():
                continue
            if skip_account_for_module(cfg, account, pool):
                continue
            if account_humanization_should_idle(account):
                continue
            accounts.append((account, pool))
        if not accounts:
            return {"status": "skipped", "reason": "no_accounts", "users": 0}
        if bool(cfg.get("do_join", True)) and chats:
            await join_loaded_chats_for_accounts(
                session,
                automation_id,
                [account.id for account, _pool in accounts],
                chat_ids=[chat.id for chat in chats],
            )
        await session.execute(delete(ParserUser).where(ParserUser.custom_automation_id == automation_id))
        await session.commit()
        try:
            delay_chat = max(0, int(cfg.get("delay_chat") if cfg.get("delay_chat") is not None else 5))
            delay_user = float(cfg.get("delay_user") if cfg.get("delay_user") is not None else 0.5)
        except (TypeError, ValueError):
            delay_chat, delay_user = 5, 0.5
        account_index = 0
        for chat in chats:
            account, _pool = accounts[account_index % len(accounts)]
            account_index += 1
            try:
                async with TelegramAccountClient.for_account(account) as client:
                    telethon = getattr(client, "client", client)

                    async def _work(chat=chat, account=account, telethon=telethon, client=client):
                        entity = None
                        for ident in (chat.invite_link, chat.external_chat_id, chat.title):
                            if not ident:
                                continue
                            try:
                                entity = await client.get_entity(ident)
                                break
                            except Exception:
                                continue
                        if entity is None:
                            raise RuntimeError("chat not resolved")
                        return await _process_entity(
                            session,
                            automation,
                            account,
                            cfg,
                            telethon,
                            client,
                            entity,
                            chat=chat,
                            title=chat.title or _chat_ref(chat),
                            target_id=str(chat.id),
                        )

                    added = await execute_with_telegram_retry(
                        session,
                        account,
                        _work,
                        action_type=ACTION_TYPE,
                        target_id=str(chat.id),
                        target_type="chat",
                        payload={"title": chat.title or _chat_ref(chat)},
                        automation_id=automation.id,
                        pace=False,
                    )
            except Exception as exc:
                logger.warning("Parser chat %s failed: %s", chat.id, exc)
                continue
            if added:
                chats_used += 1
                total += int(added)
            await asyncio.sleep(max(delay_chat, delay_user))
        for target in extra_targets:
            account, _pool = accounts[account_index % len(accounts)]
            account_index += 1
            try:
                async with TelegramAccountClient.for_account(account) as client:
                    telethon = getattr(client, "client", client)

                    async def _extra(target=target, account=account, telethon=telethon, client=client):
                        entity = await client.get_entity(target)
                        return await _process_entity(
                            session,
                            automation,
                            account,
                            cfg,
                            telethon,
                            client,
                            entity,
                            chat=None,
                            title=target,
                            target_id=target,
                        )

                    added = await execute_with_telegram_retry(
                        session,
                        account,
                        _extra,
                        action_type=ACTION_TYPE,
                        target_id=target,
                        target_type="chat",
                        payload={"title": target},
                        automation_id=automation.id,
                        pace=False,
                    )
            except Exception as exc:
                logger.warning("Parser target %s failed: %s", target, exc)
                continue
            if added:
                chats_used += 1
                total += int(added)
            await asyncio.sleep(max(delay_chat, delay_user))
        if total:
            for account, _pool in accounts[:chats_used or 1]:
                record_successful_humanization(account)
                if bool(cfg.get("limit_rate", True)):
                    schedule_account_humanization_rest(account)
            await session.commit()
            from .user_folder_service import snapshot_parser_users

            folder = await snapshot_parser_users(session, automation_id)
            if folder:
                await session.commit()
            return {"status": "ok", "users": total, "chats": chats_used, "user_folder_id": getattr(folder, "id", None)}
    return {"status": "ok", "users": total, "chats": chats_used}
