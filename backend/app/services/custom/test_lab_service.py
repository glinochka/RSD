"""Admin-only test lab: join targets, shill, neurocomment, fake DMP — no delays."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_roles import effective_roles
from .chat_join_service import create_chat_from_link, join_loaded_chats_for_accounts, preview_chat_entity
from .chat_membership_service import ensure_memberships_for_chat
from .chat_scope import apply_entity_metadata, is_broadcast_channel, is_lab_chat, unwrap_telegram_chat
from .chat_target_dedup import find_existing_chat_target
from .dmp_one_service import process_dmp_lead
from .neurocommenting_service import _generate_comment, _send_comment, process_chat_target
from .rotation_service import select_account_for_action
from .shilling_service import perform_post_shilling, process_shilling_chat
from .telegram_account_client import normalize_telegram_phone
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import (
    AccountRole as AccountRoleEnum,
    ChatJoinStatus,
    ChatMode,
    ChatSource,
    ChatTarget,
    CustomAutomation,
    CustomLead,
    LeadStatus,
    PoolAccount,
    SocialAccount,
)

logger = logging.getLogger(__name__)

CHANNEL_WATCH_SECONDS = 300
CHANNEL_WATCH_POLL_SECONDS = 8
CHANNEL_ACTIVITY_NEURO = "neurocommenting"
CHANNEL_ACTIVITY_SHILLING = "shilling"

ListPostsFn = Callable[..., Awaitable[list[Any]]]
SleepFn = Callable[[float], Awaitable[None]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def lab_result(
    *,
    ok: bool,
    detail: str,
    status: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    extra.pop("ok", None)
    extra.pop("status", None)
    extra.pop("detail", None)
    return {
        "ok": ok,
        "detail": detail,
        **extra,
        "status": status or ("success" if ok else "error"),
    }


def normalize_target_username(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    try:
        parsed = parse_telegram_chat_ref(value)
        if parsed.kind == "username":
            return parsed.value.lstrip("@")
        return parsed.canonical
    except TelegramChatRefError:
        return value.lstrip("@").split("/")[-1].strip()


def _chat_username_matches(chat: ChatTarget, username: str | None) -> bool:
    want = normalize_target_username(username).lower()
    if not want:
        return False
    for raw in (chat.invite_link, chat.external_chat_id, chat.title):
        if not raw:
            continue
        text = str(raw).strip()
        try:
            parsed = parse_telegram_chat_ref(text)
            if parsed.kind == "username" and parsed.value.lower() == want:
                return True
            if parsed.canonical.lower().rstrip("/").endswith(f"/{want}"):
                return True
        except TelegramChatRefError:
            pass
        if text.lower().lstrip("@").split("/")[-1] == want:
            return True
    return False


def pick_lab_channel(automation: CustomAutomation, chats: list[ChatTarget]) -> ChatTarget | None:
    active = [chat for chat in chats if is_lab_chat(chat) and chat.is_active]
    for chat in active:
        if chat.mode == ChatMode.NEUROCOMMENTING.value:
            return chat
    want = automation.test_channel_username
    if want:
        for chat in active:
            if _chat_username_matches(chat, want):
                return chat
    return next((chat for chat in active if is_broadcast_channel(chat)), None)


def pick_lab_group(automation: CustomAutomation, chats: list[ChatTarget]) -> ChatTarget | None:
    active = [chat for chat in chats if is_lab_chat(chat) and chat.is_active]
    for chat in active:
        if chat.mode == ChatMode.SHILLING.value:
            return chat
    want = automation.test_chat_username
    if want:
        for chat in active:
            if _chat_username_matches(chat, want):
                return chat
    return next((chat for chat in active if not is_broadcast_channel(chat)), None)


def serialize_lab(automation: CustomAutomation, chats: list[ChatTarget] | None = None) -> dict[str, Any]:
    chats = chats or []
    channel = pick_lab_channel(automation, chats)
    group = pick_lab_group(automation, chats)
    return {
        "channel_username": automation.test_channel_username or "",
        "chat_username": automation.test_chat_username or "",
        "channel": _chat_payload(channel),
        "chat": _chat_payload(group),
        "watch": current_channel_watch(automation.id),
    }


def _chat_payload(chat: ChatTarget | None) -> dict[str, Any] | None:
    if not chat:
        return None
    return {
        "id": chat.id,
        "title": chat.title,
        "username": chat.invite_link or chat.external_chat_id,
        "chat_type": chat.chat_type,
        "join_status": chat.join_status,
        "last_join_error": chat.last_join_error,
    }


async def list_lab_chats(session: AsyncSession, automation_id: int) -> list[ChatTarget]:
    result = await session.execute(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.source == ChatSource.TEST.value,
            ChatTarget.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def _upsert_lab_chat(
    session: AsyncSession,
    automation_id: int,
    username: str,
    *,
    mode: str,
) -> ChatTarget:
    parsed = parse_telegram_chat_ref(username)
    entity = await preview_chat_entity(session, automation_id, parsed)
    external_id = None
    unwrapped = unwrap_telegram_chat(entity) or entity
    if getattr(unwrapped, "id", None) is not None:
        external_id = str(unwrapped.id)

    existing = await find_existing_chat_target(
        session,
        automation_id,
        invite_link=parsed.canonical,
        external_chat_id=external_id,
    )
    if existing is None:
        existing = await session.scalar(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.invite_link == parsed.canonical,
            )
        )

    previous = await session.scalar(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.source == ChatSource.TEST.value,
            ChatTarget.mode == mode,
            ChatTarget.is_active.is_(True),
        )
    )
    if previous and existing and previous.id != existing.id:
        previous.is_active = False
        previous.mode = ChatMode.INACTIVE.value
    elif previous and existing is None and (previous.invite_link or "") != parsed.canonical:
        previous.is_active = False
        previous.mode = ChatMode.INACTIVE.value

    if existing:
        existing.source = ChatSource.TEST.value
        existing.mode = mode
        existing.is_active = True
        existing.invite_link = parsed.canonical
        apply_entity_metadata(existing, entity)
        if external_id:
            existing.external_chat_id = external_id
        await ensure_memberships_for_chat(
            session,
            automation_id,
            existing,
            include_lab=True,
        )
        await session.commit()
        await session.refresh(existing)
        return existing

    try:
        chat = await create_chat_from_link(session, automation_id, username, mode=mode)
    except ValueError as exc:
        if "уже добавлен" not in str(exc).lower():
            raise
        # Race / alternate key: reuse whatever dedup finds now.
        chat = await find_existing_chat_target(
            session,
            automation_id,
            invite_link=parsed.canonical,
            external_chat_id=external_id,
        )
        if chat is None:
            raise
    chat.source = ChatSource.TEST.value
    chat.mode = mode
    chat.is_active = True
    chat.invite_link = parsed.canonical
    apply_entity_metadata(chat, entity)
    if external_id:
        chat.external_chat_id = external_id
    await ensure_memberships_for_chat(session, automation_id, chat, include_lab=True)
    await session.commit()
    await session.refresh(chat)
    return chat


async def save_lab_targets(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    channel_username: str | None,
    chat_username: str | None,
) -> dict[str, Any]:
    channel_username = normalize_target_username(channel_username)
    chat_username = normalize_target_username(chat_username)
    automation.test_channel_username = channel_username or None
    automation.test_chat_username = chat_username or None
    automation.updated_at = _utc_now()
    await session.commit()
    await session.refresh(automation)

    if channel_username:
        try:
            await _upsert_lab_chat(session, automation.id, channel_username, mode=ChatMode.NEUROCOMMENTING.value)
        except ValueError as exc:
            raise ValueError(f"Канал @{channel_username}: {exc}") from exc
    if chat_username:
        try:
            await _upsert_lab_chat(session, automation.id, chat_username, mode=ChatMode.SHILLING.value)
        except ValueError as exc:
            raise ValueError(f"Чат @{chat_username}: {exc}") from exc
    chats = await list_lab_chats(session, automation.id)
    return serialize_lab(automation, chats)


async def join_lab_targets(
    session: AsyncSession,
    automation_id: int,
    *,
    channel_username: str | None = None,
    chat_username: str | None = None,
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        return lab_result(ok=False, detail="Автоматизация не найдена.")
    if channel_username is not None or chat_username is not None:
        try:
            await save_lab_targets(
                session,
                automation,
                channel_username=channel_username,
                chat_username=chat_username,
            )
        except ValueError as exc:
            return lab_result(ok=False, detail=str(exc))
    chats = await list_lab_chats(session, automation_id)
    if not chats:
        return lab_result(ok=False, detail="Укажите канал или чат и нажмите «Вступить».")
    result = await join_loaded_chats_for_accounts(
        session,
        automation_id,
        chat_ids=[chat.id for chat in chats],
        include_lab=True,
        rate_limit=False,
        ignore_retry_delay=True,
    )
    joined_pairs = int(result.get("joined_pairs") or 0)
    attempts = int(result.get("attempts") or 0)
    accounts = int(result.get("accounts") or 0)
    total = int(result.get("chats") or len(chats))
    full_targets = int(result.get("full_targets") or 0)
    failed_pairs = int(result.get("failed_pairs") or 0)
    rate_limited_pairs = int(result.get("rate_limited_pairs") or 0)
    per_target = list(result.get("per_target") or [])

    def _target_label(item: dict[str, Any]) -> str:
        for key in ("title", "invite_link"):
            value = str(item.get(key) or "").strip()
            if value:
                return value.replace("https://t.me/", "@")
        return f"#{item.get('chat_target_id')}"

    parts = [
        f"{_target_label(item)}: {item.get('joined', 0)}/{item.get('total', 0)} аккаунтов"
        for item in per_target
    ]
    summary = "; ".join(parts) if parts else f"{joined_pairs} вступлений"

    if joined_pairs > 0 or full_targets > 0:
        all_in = (
            accounts > 0
            and full_targets >= total
            and all(int(item.get("joined") or 0) >= accounts for item in per_target)
        )
        if all_in:
            detail = f"Все {accounts} аккаунтов вступили в {total} целей ({summary})."
            ok = True
        else:
            extra = []
            if rate_limited_pairs:
                extra.append(f"рейт-лимит Telegram: {rate_limited_pairs}")
            if failed_pairs:
                extra.append(f"ошибки: {failed_pairs}")
            suffix = f" ({'; '.join(extra)})" if extra else ""
            detail = (
                f"Частично: {summary}. "
                f"Полностью готово {full_targets} из {total} целей{suffix}."
            )
            ok = full_targets > 0
        return lab_result(ok=ok, detail=detail, **result)
    if attempts == 0:
        detail = "Нет живых аккаунтов с сессией Telegram в пуле — добавьте и авторизуйте аккаунты."
    elif rate_limited_pairs:
        detail = (
            f"Telegram ограничил вступление (FloodWait) для {rate_limited_pairs} пар. "
            "Подождите и нажмите «Вступить» снова."
        )
    else:
        detail = (
            f"Не удалось подтвердить вступление ни в одну цель ({summary}). "
            "Проверьте сессии аккаунтов и @username."
        )
    return lab_result(
        ok=False,
        detail=detail,
        **result,
    )


async def _has_role(session: AsyncSession, automation_id: int, role: str, *, min_count: int = 1) -> bool:
    result = await session.execute(
        select(SocialAccount, PoolAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.is_banned.is_(False),
        )
    )
    count = 0
    for social, pool in result.all():
        if role in effective_roles(pool, social):
            count += 1
            if count >= min_count:
                return True
    return False


async def activate_lab_shilling(session: AsyncSession, automation: CustomAutomation) -> dict[str, Any]:
    chats = await list_lab_chats(session, automation.id)
    chat = pick_lab_group(automation, chats)
    if chat is None:
        return lab_result(ok=False, detail="Нет целевого чата. Укажите чат и нажмите «Вступить».")
    if not await _has_role(session, automation.id, AccountRoleEnum.SHILLING.value, min_count=2):
        return lab_result(ok=False, detail="Нужно минимум 2 живых аккаунта с функцией «Шиллинг».")
    sent = 0
    results = []
    if chat.join_status != ChatJoinStatus.JOINED.value:
        results.append({"chat_id": chat.id, "status": "not_joined"})
    else:
        outcome = await process_shilling_chat(
            session,
            automation,
            chat,
            include_lab=True,
            skip_schedule=True,
            delay_seconds=0,
        )
        results.append({"chat_id": chat.id, **outcome})
        if outcome.get("status") == "ok":
            sent += 1
    if sent:
        return lab_result(ok=True, detail=f"Шиллинг в чате выполнен ({sent} диалогов).", sent=sent, results=results)
    reasons = [item.get("reason") or item.get("status") for item in results]
    detail = "Шиллинг в чате не выполнен."
    unique = []
    for reason in reasons:
        text = str(reason) if reason else ""
        if text and text not in unique:
            unique.append(text)
    if unique:
        detail = f"{detail} {'; '.join(unique)}"
    return lab_result(ok=False, detail=detail, sent=0, results=results)


async def run_lab_neurocommenting(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    """Immediate scan — kept for scheduler compatibility."""
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        return lab_result(ok=False, detail="Автоматизация не найдена.")
    chats = await list_lab_chats(session, automation_id)
    channel = pick_lab_channel(automation, chats)
    if channel is None:
        return lab_result(ok=False, detail="Нет целевого канала.")
    sent = 0
    results = []
    outcome = await process_chat_target(
        session,
        automation_id,
        channel,
        lab_mode=True,
        max_comments_per_run=10,
    )
    results.append({"chat_id": channel.id, **outcome})
    sent += int(outcome.get("sent") or 0)
    if sent:
        return lab_result(ok=True, detail=f"Комментарии отправлены: {sent}.", sent=sent, results=results)
    return lab_result(ok=False, detail="Комментарии не отправлены.", sent=0, results=results)


async def simulate_dmp(
    session: AsyncSession,
    automation: CustomAutomation,
    phone: str,
) -> dict[str, Any]:
    phone = normalize_telegram_phone(phone) or (phone or "").strip()
    if not phone:
        return lab_result(ok=False, detail="Введите номер получателя.")

    result = await session.execute(
        select(SocialAccount, PoolAccount)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(PoolAccount.custom_automation_id == automation.id)
    )
    rows = list(result.all())
    target_account = None
    for social, _pool in rows:
        number = normalize_telegram_phone(social.phone_number or "") or (social.phone_number or "")
        if number and number == phone:
            target_account = social
            break

    contact_value = phone
    contact_type = "phone"
    if target_account:
        if target_account.username:
            contact_type = "telegram"
            contact_value = target_account.username.lstrip("@")
        elif target_account.phone_number:
            contact_type = "phone"
            contact_value = target_account.phone_number

    has_dmp_role = False
    for social, pool in rows:
        if AccountRoleEnum.DMP.value in effective_roles(pool, social):
            has_dmp_role = True
            break
    if not has_dmp_role:
        return lab_result(ok=False, detail="Нет живого аккаунта с функцией «DMP».")

    lead = CustomLead(
        custom_automation_id=automation.id,
        source="dmp_one",
        contact_type=contact_type,
        contact_value=contact_value,
        full_name=target_account.display_name if target_account else None,
        dmp_raw_data={"phone": phone, "lab": True, "found_account_id": target_account.id if target_account else None},
        status=LeadStatus.NEW.value,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(lead)
    await session.flush()
    outcome = await process_dmp_lead(session, automation, lead)
    outreach = outcome.get("outreach")
    payload = {
        **outcome,
        "lead_id": lead.id,
        "found_account_id": target_account.id if target_account else None,
    }
    for key in ("ok", "status", "detail"):
        payload.pop(key, None)
    if outreach or outcome.get("status") in {"warming", "transferred", "converted"}:
        return lab_result(
            ok=True,
            detail=f"DMP выполнен для @{contact_value.lstrip('@') if contact_type == 'telegram' else contact_value}.",
            **payload,
        )
    reason = outcome.get("reason") or outcome.get("status") or "неизвестно"
    return lab_result(
        ok=False,
        detail=f"DMP не выполнен: {reason}.",
        **payload,
    )


@dataclass
class ChannelWatch:
    automation_id: int
    activity: str
    status: str
    detail: str
    started_at: float
    wait_seconds: int
    seen_ids: set[int] = field(default_factory=set)
    post_id: int | None = None
    ok: bool | None = None
    task: asyncio.Task[None] | None = None

    def as_dict(self) -> dict[str, Any]:
        elapsed = max(0, int(time.monotonic() - self.started_at))
        left = max(0, self.wait_seconds - elapsed) if self.status == "waiting" else 0
        return lab_result(
            ok=bool(self.ok) if self.ok is not None else False,
            status=self.status,
            detail=self.detail,
            activity=self.activity,
            seconds_left=left,
            post_id=self.post_id,
        )


_WATCHES: dict[int, ChannelWatch] = {}
_WATCH_LOCK = asyncio.Lock()


def current_channel_watch(automation_id: int) -> dict[str, Any] | None:
    watch = _WATCHES.get(automation_id)
    if watch is None:
        return None
    return watch.as_dict()


async def _list_channel_posts(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    limit: int = 20,
) -> list[Any]:
    account = await select_account_for_action(session, automation_id, "commenting", consume_quota=False)
    if account is None:
        account = await select_account_for_action(session, automation_id, "shilling", consume_quota=False)
    if account is None:
        raise RuntimeError("Нет живых аккаунтов для чтения канала.")
    from .chat_inspect_service import probe_comments_readonly
    from .chat_scope import apply_entity_metadata
    from .telegram_account_client import TelegramAccountClient
    from .telegram_invite import chat_entity_key

    async with TelegramAccountClient.for_account(account) as client:
        entity = await client.get_entity(chat_entity_key(chat_target))
        apply_entity_metadata(chat_target, entity)
        history = await client.client.get_messages(entity, limit=limit)
    posts = [msg for msg in history if msg and getattr(msg, "id", None) is not None]
    posts.sort(key=lambda msg: int(msg.id))
    return posts


async def start_channel_activity(
    session: AsyncSession,
    automation: CustomAutomation,
    activity: str,
    *,
    wait_seconds: int = CHANNEL_WATCH_SECONDS,
    poll_seconds: int = CHANNEL_WATCH_POLL_SECONDS,
    list_posts: ListPostsFn | None = None,
    sleeper: SleepFn | None = None,
    spawn: bool = True,
) -> dict[str, Any]:
    activity = (activity or "").strip().lower()
    if activity not in {CHANNEL_ACTIVITY_NEURO, CHANNEL_ACTIVITY_SHILLING}:
        return lab_result(ok=False, detail="Выберите нейрокомментинг или шиллинг в комментариях.")

    chats = await list_lab_chats(session, automation.id)
    channel = pick_lab_channel(automation, chats)
    if channel is None:
        want = (automation.test_channel_username or "").strip()
        if want:
            return lab_result(
                ok=False,
                detail=f"Канал @{want.lstrip('@')} не сохранён. Нажмите «Вступить» ещё раз или проверьте @username.",
            )
        return lab_result(ok=False, detail="Нет целевого канала. Укажите канал и нажмите «Вступить».")
    if channel.join_status != ChatJoinStatus.JOINED.value:
        return lab_result(ok=False, detail="Аккаунты ещё не вступили в канал. Сначала нажмите «Вступить».")

    if activity == CHANNEL_ACTIVITY_NEURO:
        if not await _has_role(session, automation.id, AccountRoleEnum.NEUROCOMMENTING.value):
            return lab_result(ok=False, detail="Нет живых аккаунтов с функцией «Нейрокомментинг».")
    elif not await _has_role(session, automation.id, AccountRoleEnum.SHILLING.value, min_count=2):
        return lab_result(ok=False, detail="Для шиллинга в комментариях нужно минимум 2 живых аккаунта с функцией «Шиллинг».")

    list_posts_fn = list_posts or (
        lambda s, _automation, chat, limit=20: _list_channel_posts(s, automation.id, chat, limit=limit)
    )
    try:
        existing = await list_posts_fn(session, automation, channel, limit=20)
    except Exception as exc:
        logger.exception("test lab failed to snapshot channel posts")
        return lab_result(ok=False, detail=f"Не удалось прочитать канал: {exc}")

    seen_ids = {int(getattr(post, "id")) for post in existing if getattr(post, "id", None) is not None}
    label = "нейрокомментинг" if activity == CHANNEL_ACTIVITY_NEURO else "шиллинг в комментариях"
    watch = ChannelWatch(
        automation_id=automation.id,
        activity=activity,
        status="waiting",
        detail=f"Ждём новый пост в канале (до {wait_seconds // 60} мин.), затем запустим {label}.",
        started_at=time.monotonic(),
        wait_seconds=wait_seconds,
        seen_ids=seen_ids,
        ok=None,
    )
    async with _WATCH_LOCK:
        previous = _WATCHES.get(automation.id)
        if previous and previous.task and not previous.task.done():
            previous.task.cancel()
        _WATCHES[automation.id] = watch
        if spawn:
            watch.task = asyncio.create_task(
                _run_channel_watch(
                    automation.id,
                    channel.id,
                    activity,
                    wait_seconds=wait_seconds,
                    poll_seconds=poll_seconds,
                    list_posts=list_posts,
                    sleeper=sleeper,
                )
            )
    return watch.as_dict()


async def get_channel_activity_status(automation_id: int) -> dict[str, Any]:
    watch = current_channel_watch(automation_id)
    if watch is None:
        return lab_result(ok=False, status="idle", detail="Ожидание поста не запущено.")
    return watch


async def _run_channel_watch(
    automation_id: int,
    channel_id: int,
    activity: str,
    *,
    wait_seconds: int,
    poll_seconds: int,
    list_posts: ListPostsFn | None,
    sleeper: SleepFn | None,
) -> None:
    from ...alembic.database import async_session_maker

    sleep = sleeper or asyncio.sleep
    deadline = time.monotonic() + wait_seconds
    first_tick = True
    try:
        while time.monotonic() < deadline:
            if not first_tick:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                await sleep(min(poll_seconds, remaining))
            first_tick = False
            async with async_session_maker() as session:
                automation = await session.get(CustomAutomation, automation_id)
                channel = await session.get(ChatTarget, channel_id)
                watch = _WATCHES.get(automation_id)
                if automation is None or channel is None or watch is None or watch.activity != activity:
                    return
                list_posts_fn = list_posts or (
                    lambda s, _automation, chat, limit=8: _list_channel_posts(s, automation_id, chat, limit=limit)
                )
                try:
                    posts = await list_posts_fn(session, automation, channel, limit=8)
                except Exception as exc:
                    watch.status = "error"
                    watch.ok = False
                    watch.detail = f"Не удалось прочитать канал: {exc}"
                    return
                fresh = [
                    post
                    for post in posts
                    if getattr(post, "id", None) is not None and int(post.id) not in watch.seen_ids
                ]
                if not fresh:
                    continue
                post = fresh[0]
                watch.post_id = int(post.id)
                outcome = await _react_to_post(session, automation, channel, post, activity)
                await session.commit()
                watch.ok = bool(outcome.get("ok"))
                watch.status = "success" if watch.ok else "error"
                watch.detail = str(outcome.get("detail") or "Активность не выполнена.")
                watch.post_id = int(outcome.get("post_id") or post.id)
                return
        watch = _WATCHES.get(automation_id)
        if watch is not None and watch.status == "waiting":
            watch.status = "timeout"
            watch.ok = False
            watch.detail = "За 5 минут новый пост не вышел. Активность не выполнялась."
    except asyncio.CancelledError:
        watch = _WATCHES.get(automation_id)
        if watch is not None and watch.status == "waiting":
            watch.status = "error"
            watch.ok = False
            watch.detail = "Ожидание остановлено."
        raise
    except Exception:
        logger.exception("test lab channel watch failed")
        watch = _WATCHES.get(automation_id)
        if watch is not None:
            watch.status = "error"
            watch.ok = False
            watch.detail = "Внутренняя ошибка ожидания поста."


async def _react_to_post(
    session: AsyncSession,
    automation: CustomAutomation,
    channel: ChatTarget,
    post: Any,
    activity: str,
) -> dict[str, Any]:
    post_id = int(getattr(post, "id"))
    post_text = str(getattr(post, "text", None) or getattr(post, "message", None) or "")

    if activity == CHANNEL_ACTIVITY_SHILLING:
        outcome = await perform_post_shilling(
            session,
            automation,
            channel,
            post_id,
            post_text=post_text,
            delay_seconds=0,
            lab_mode=True,
        )
        if outcome.get("status") == "ok":
            return lab_result(
                ok=True,
                detail="Шиллинг в комментариях выполнен.",
                **{**outcome, "post_id": post_id},
            )
        reason = outcome.get("reason") or outcome.get("status") or "неизвестно"
        if reason == "other_action":
            claimed = str(outcome.get("claimed") or "")
            labels = {"skip": "пропуск по каденсу", "neurocommenting": "нейрокомментинг"}
            reason = f"пост уже помечен как {labels.get(claimed, claimed or 'другое действие')}"
        return lab_result(
            ok=False,
            detail=f"Шиллинг в комментариях не выполнен: {reason}.",
            **{**outcome, "post_id": post_id},
        )

    account = await select_account_for_action(session, automation.id, "commenting", consume_quota=False)
    if account is None:
        return lab_result(ok=False, detail="Нет живых аккаунтов с функцией «Нейрокомментинг».", post_id=post_id)
    comment = await _generate_comment(
        session,
        automation.id,
        post_text=post_text,
        chat_title=channel.title or "",
    )
    if not comment:
        return lab_result(ok=False, detail="Не удалось сгенерировать комментарий.", post_id=post_id)
    sent = await _send_comment(
        session,
        automation.id,
        channel,
        account,
        post_id,
        comment,
        post_text=post_text,
    )
    if sent:
        return lab_result(ok=True, detail="Комментарий оставлен.", post_id=post_id, comment=comment)
    return lab_result(ok=False, detail="Не удалось отправить комментарий.", post_id=post_id)


def reset_channel_watches() -> None:
    for watch in list(_WATCHES.values()):
        if watch.task and not watch.task.done():
            watch.task.cancel()
    _WATCHES.clear()
