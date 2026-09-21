"""Neurocommenting: pool accounts leave relevant comments on posts."""
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import in_account_active_hours
from .chat_inspect_service import probe_comments_readonly
from .chat_membership_service import (
    ensure_watcher_membership,
    get_reader_account,
    is_chat_watchable,
    list_watchable_chats,
    recover_reader_after_error,
    retire_reader_and_replace,
)
from .chat_scope import apply_entity_metadata, is_broadcast_channel, is_lab_chat, is_paused, commit_chat_scan
from .pending_action_service import ensure_accounts_ready, has_pending_action
from .post_engagement import NEUROCOMMENTING, SHILLING, SKIP, claim_post_engagement, post_target_id
from .rotation_service import (
    current_daily_messages_sent,
    moscow_day_start_utc_naive,
    record_successful_send,
    select_account_for_action,
)
from .shilling_service import perform_post_shilling
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from .telegram_invite import chat_entity_key
from ...alembic.models import AutomationActionLog, ChatTarget, CustomAutomation, CustomPrompt, PromptType, SocialAccount
from ...config import settings
from ...services.ai_authoring import ai_client
from .prompt_service import render_prompt

logger = logging.getLogger(__name__)


DEFAULT_NEUROCOMMENTING_PROMPT = """Ты — участник Telegram-чата/канала. Тебе показали пост.
Напиши короткий, естественный, релевантный комментарий (1-2 предложения), который продолжает дискуссию или добавляет ценность.
Не спами, не используй хештеги, не предлагай ссылки.

Пост:
{post_text}

Контекст чата:
{chat_title}

Верни ТОЛЬКО JSON:
{
  "comment": "текст комментария"
}"""


# Channel history is the last ~30 posts. Without a recency cut we slowly
# comment/shill under weeks-old posts when a channel is first scanned.
POST_MAX_AGE = timedelta(hours=2)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _message_posted_at(msg) -> datetime | None:
    raw = getattr(msg, "date", None)
    if not isinstance(raw, datetime):
        return None
    if raw.tzinfo is not None:
        return raw.astimezone(timezone.utc).replace(tzinfo=None)
    return raw


def is_fresh_channel_post(msg, *, now: datetime | None = None, lab_mode: bool = False) -> bool:
    """Lab may use any post. Production also accepts posts newer than the listen cursor."""
    if lab_mode:
        return True
    posted = _message_posted_at(msg)
    if posted is None:
        return False
    current = now or _utc_now()
    return posted >= current - POST_MAX_AGE


def post_cursor_id(chat_target) -> int:
    raw = str(getattr(chat_target, "last_message_id", None) or "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def set_post_cursor(chat_target, message_id: int) -> None:
    latest = int(message_id)
    if latest <= 0:
        return
    if latest > post_cursor_id(chat_target):
        chat_target.last_message_id = str(latest)


def collect_new_channel_posts(history, chat_target, *, lab_mode: bool = False, now: datetime | None = None):
    """Keep only posts the watcher has not seen yet. First scan arms the cursor."""
    messages = []
    for msg in history or []:
        if not msg or not getattr(msg, "text", None) or getattr(msg, "id", None) is None:
            continue
        messages.append(msg)
    messages.sort(key=lambda item: int(item.id))
    latest = int(messages[-1].id) if messages else 0
    if lab_mode:
        fresh = [item for item in messages if is_fresh_channel_post(item, now=now, lab_mode=True)]
        return fresh, latest, None
    cursor = post_cursor_id(chat_target)
    if latest and cursor <= 0:
        return [], latest, "armed_cursor"
    new_posts = [
        item
        for item in messages
        if int(item.id) > cursor and is_fresh_channel_post(item, now=now, lab_mode=False)
    ]
    return new_posts, latest, None


async def _skip_chat(session: AsyncSession, chat_target: ChatTarget, reason: str) -> dict[str, Any]:
    await commit_chat_scan(session, chat_target)
    return {"status": "skipped", "reason": reason}


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def _load_prompt(session: AsyncSession, automation_id: int) -> str:
    prompt = await session.scalar(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
            CustomPrompt.prompt_type == PromptType.NEUROCOMMENTING.value,
            CustomPrompt.is_active.is_(True),
        ).order_by(CustomPrompt.created_at.desc())
    )
    if prompt and prompt.content:
        return str(prompt.content).strip()
    return DEFAULT_NEUROCOMMENTING_PROMPT


async def _generate_comment(
    session: AsyncSession,
    automation_id: int,
    *,
    post_text: str,
    chat_title: str,
) -> str:
    prompt = render_prompt(
        await _load_prompt(session, automation_id),
        {"post_text": post_text or "", "chat_title": chat_title or ""},
    )
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.8,
        )
        data = _extract_json(response.choices[0].message.content or "")
        comment = str(data.get("comment") or "").strip()
        return comment[:500]
    except Exception as exc:
        logger.warning("Comment generation failed: %s", exc)
        return ""


def account_comment_daily_limit(automation: CustomAutomation | None, *, lab_mode: bool = False) -> int:
    if lab_mode:
        return 10**9
    return max(1, int(getattr(automation, "max_daily_messages_per_account", None) or 50))


def chat_comment_daily_limit(config: dict | None, *, lab_mode: bool = False) -> int:
    if lab_mode:
        return 10**9
    raw = (config or {}).get("max_per_day")
    if raw is None or raw == "":
        return 10
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 10


def account_reached_daily_cap(account: SocialAccount | None, limit: int) -> bool:
    return current_daily_messages_sent(account) >= limit


async def _count_chat_comments_today(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
) -> int:
    started = moscow_day_start_utc_naive()
    count = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "neurocommenting",
            AutomationActionLog.result == "success",
            AutomationActionLog.target_id.like(f"{chat_target_id}:%"),
            AutomationActionLog.created_at >= started,
        )
    )
    return int(count or 0)


async def _already_commented(
    session: AsyncSession,
    automation_id: int,
    chat_target_id: int,
    message_id: int,
) -> bool:
    target_id = f"{chat_target_id}:{message_id}"
    count = await session.scalar(
        select(AutomationActionLog).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "neurocommenting",
            AutomationActionLog.target_id == target_id,
            AutomationActionLog.result == "success",
        )
    )
    return count is not None


async def _send_comment(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    account: SocialAccount,
    post_id: int,
    text: str,
    *,
    post_text: str = "",
) -> bool:
    if not account.session_file_path:
        return False
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return False

    payload = {
        "chat_target_id": chat_target.id,
        "chat_title": chat_target.title,
        "post_id": post_id,
        "post_text": (post_text or "")[:500],
        "text": text,
    }
    try:
        async with TelegramAccountClient.for_account(account) as client:
            entity = await client.get_entity(
                chat_entity_key(chat_target)
            )
            from .chat_join_service import join_linked_discussion

            await join_linked_discussion(client, entity)
            await execute_with_telegram_retry(
                session,
                account,
                lambda: client.client.send_message(entity, text, comment_to=post_id),
                action_type="neurocommenting",
                target_id=f"{chat_target.id}:{post_id}",
                target_type="chat_post",
                payload=payload,
                automation_id=automation_id,
            )
    except Exception as exc:
        logger.warning("Send comment failed for chat %s post %s: %s", chat_target.id, post_id, exc)
        return False

    record_successful_send(account)
    log = AutomationActionLog(
        custom_automation_id=automation_id,
        social_account_id=account.id,
        action_type="neurocommenting",
        target_id=f"{chat_target.id}:{post_id}",
        target_type="chat_post",
        result="success",
        payload=payload,
        created_at=_utc_now(),
    )
    session.add(log)
    await session.commit()
    return True


async def process_chat_target(
    session: AsyncSession,
    automation_id: int,
    chat_target: ChatTarget,
    *,
    max_comments_per_run: int = 1,
    include_lab: bool = False,
    lab_mode: bool = False,
) -> dict[str, Any]:
    if is_lab_chat(chat_target) and not (include_lab or lab_mode):
        return await _skip_chat(session, chat_target, "lab")
    if is_paused(chat_target):
        return await _skip_chat(session, chat_target, "paused")
    if chat_target.chat_type and not is_broadcast_channel(chat_target):
        return await _skip_chat(session, chat_target, "not_channel")
    if chat_target.comments_open is False:
        return await _skip_chat(session, chat_target, "comments_closed")
    if not await is_chat_watchable(session, chat_target):
        await ensure_watcher_membership(session, automation_id, chat_target, include_lab=include_lab or lab_mode)
        return await _skip_chat(session, chat_target, "not_watchable")

    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return await _skip_chat(session, chat_target, "automation_missing")
    neuro_enabled = bool(automation.is_neurocommenting_enabled) or lab_mode
    shilling_enabled = bool(automation.is_shilling_enabled) and not lab_mode
    if not neuro_enabled and not shilling_enabled:
        return await _skip_chat(session, chat_target, "feature_disabled")

    config = chat_target.neurocommenting_config or {}
    chat_limit = chat_comment_daily_limit(config, lab_mode=lab_mode)
    account_limit = account_comment_daily_limit(automation, lab_mode=lab_mode)
    chat_sent_today = 0 if lab_mode else await _count_chat_comments_today(session, automation_id, chat_target.id)
    tried: set[int] = set()
    account = None
    posts = []
    while True:
        account = await get_reader_account(session, chat_target, exclude_account_ids=tried)
        if not account:
            return await _skip_chat(session, chat_target, "no_account")
        if not account.session_file_path:
            tried.add(account.id)
            continue
        session_path = _media_root() / account.session_file_path
        if not session_path.exists():
            tried.add(account.id)
            continue
        tried.add(account.id)
        posts = []
        try:
            async with TelegramAccountClient.for_account(account) as client:
                probe = await probe_comments_readonly(client, chat_target)
                if probe.members_count:
                    chat_target.members_count = probe.members_count
                if probe.last_activity_at:
                    chat_target.last_activity_at = probe.last_activity_at
                if probe.comments_open is not None:
                    chat_target.comments_open = probe.comments_open
                chat_target.comments_checked_at = _utc_now()
                chat_target.comments_check_error = probe.error
                if probe.chat_read_lost:
                    await retire_reader_and_replace(
                        session, chat_target, account.id, error=probe.error
                    )
                    continue
                if probe.account_blocked:
                    return await _skip_chat(session, chat_target, "account_blocked")
                if probe.comments_open is False:
                    return await _skip_chat(session, chat_target, "comments_closed")
                entity = await client.get_entity(
                    chat_entity_key(chat_target)
                )
                apply_entity_metadata(chat_target, entity)
                if not is_broadcast_channel(chat_target):
                    return await _skip_chat(session, chat_target, "not_channel")
                history = await client.client.get_messages(entity, limit=20)
                posts, latest_id, cursor_reason = collect_new_channel_posts(
                    history, chat_target, lab_mode=lab_mode
                )
                filtered = []
                for msg in posts:
                    sender = getattr(msg, "sender", None)
                    sender_id = getattr(sender, "id", None)
                    if sender_id == account.id or (sender_id and str(sender_id) in (account.username or "")):
                        continue
                    filtered.append(msg)
                posts = filtered
                if latest_id:
                    set_post_cursor(chat_target, latest_id)
                if cursor_reason == "armed_cursor":
                    return await _skip_chat(session, chat_target, "armed_cursor")
                if not lab_mode and not in_account_active_hours():
                    return await _skip_chat(session, chat_target, "night")
            break
        except Exception as exc:
            logger.warning("Fetch posts for chat %s failed: %s", chat_target.id, exc)
            if await recover_reader_after_error(session, chat_target, account, exc):
                continue
            await commit_chat_scan(session, chat_target)
            return {"status": "error", "error": str(exc)}

    if not account:
        return await _skip_chat(session, chat_target, "no_account")

    posts.sort(key=lambda msg: int(msg.id))
    sent = 0
    shilled = 0
    if not lab_mode and chat_sent_today >= chat_limit:
        chat_target.last_scanned_at = _utc_now()
        chat_target.updated_at = _utc_now()
        await session.commit()
        return {"status": "ok", "sent": 0, "shilled": 0, "reason": "chat_daily_limit"}
    for post in posts:
        if await _already_commented(session, automation_id, chat_target.id, post.id):
            continue
        if sent + shilled >= max_comments_per_run:
            break
        if not lab_mode and chat_sent_today + sent >= chat_limit:
            break

        claimed = await claim_post_engagement(
            session,
            automation_id=automation_id,
            chat_target_id=chat_target.id,
            post_id=post.id,
            account_id=account.id,
            neuro_enabled=neuro_enabled,
            shilling_enabled=shilling_enabled,
            lab_mode=lab_mode,
        )
        if claimed == SKIP:
            continue
        if claimed == SHILLING:
            result = await perform_post_shilling(
                session,
                automation,
                chat_target,
                post.id,
                post_text=post.text or "",
            )
            if result.get("status") == "ok":
                shilled += 1
            continue
        if claimed != NEUROCOMMENTING or not neuro_enabled:
            continue
        tried_actors: set[int] = set()
        actor = None
        ready = False
        while True:
            actor = await select_account_for_action(
                session,
                automation_id,
                "commenting",
                consume_quota=False,
                exclude_account_ids=tried_actors or None,
                ignore_rest=lab_mode,
            )
            if not actor or account_reached_daily_cap(actor, account_limit):
                actor = None
                break
            tried_actors.add(actor.id)
            ready = await ensure_accounts_ready(
                session,
                automation_id,
                chat_target,
                [actor],
                action_type="neurocommenting",
                target_id=post_target_id(chat_target.id, post.id),
                payload={"post_id": post.id, "post_text": (post.text or "")[:500]},
            )
            if ready:
                break
            if await has_pending_action(
                session, automation_id, "neurocommenting", post_target_id(chat_target.id, post.id)
            ):
                break
        if not ready:
            continue
        if not actor:
            continue

        comment = await _generate_comment(session, automation_id, post_text=post.text, chat_title=chat_target.title or "")
        if not comment:
            continue

        success = await _send_comment(
            session, automation_id, chat_target, actor, post.id, comment, post_text=post.text or ""
        )
        if success:
            sent += 1

    chat_target.last_scanned_at = _utc_now()
    chat_target.updated_at = _utc_now()
    await session.commit()
    return {"status": "ok", "sent": sent, "shilled": shilled}


async def run_neurocommenting_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    total_sent = 0
    chat_count = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not (
            automation.is_neurocommenting_enabled or automation.is_shilling_enabled
        ):
            logger.info("Post engagement disabled or automation not found for %s", automation_id)
            return {"status": "skipped", "reason": "feature_disabled", "chats_processed": 0, "comments_sent": 0}

        chats = [
            chat
            for chat in await list_watchable_chats(
                session,
                automation_id,
                limit=settings.CUSTOM_ACTION_SCAN_BATCH,
            )
            if is_broadcast_channel(chat) or not chat.chat_type
        ]
        for chat_target in chats:
            try:
                res = await process_chat_target(
                    session, automation_id, chat_target, max_comments_per_run=random.randint(1, 2)
                )
                chat_count += 1
                if res.get("sent"):
                    total_sent += int(res["sent"])
            except Exception as exc:
                logger.exception("Neurocommenting failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chat_count, "comments_sent": total_sent}


async def run_lab_neurocommenting_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    total_sent = 0
    chat_count = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation or not (automation.test_channel_username or "").strip():
            return {"status": "skipped", "reason": "no_lab_channel", "chats_processed": 0, "comments_sent": 0}

        chats = [
            chat
            for chat in await list_watchable_chats(session, automation_id, include_lab=True)
            if is_lab_chat(chat) and is_broadcast_channel(chat)
        ]
        for chat_target in chats:
            try:
                res = await process_chat_target(
                    session,
                    automation_id,
                    chat_target,
                    lab_mode=True,
                    max_comments_per_run=10,
                )
                chat_count += 1
                if res.get("sent"):
                    total_sent += int(res["sent"])
            except Exception as exc:
                logger.exception("Lab neurocommenting failed for chat %s: %s", chat_target.id, exc)

    return {"chats_processed": chat_count, "comments_sent": total_sent}
