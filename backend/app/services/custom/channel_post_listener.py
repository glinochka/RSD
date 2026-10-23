"""Live channel-post listener on keep-alive account sessions.

Work-hour sessions stay connected. This attaches Telethon NewMessage so a
joined neurocommenting account queues a comment when a subscribed channel
posts, instead of waiting for the rotating poller to notice.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import AccountChatMembership, ChatJoinStatus, ChatTarget, SocialAccount

logger = logging.getLogger(__name__)

_HANDLER_FLAG = "_rsd_comment_listener"


def peer_id_keys(chat_id: int | None) -> list[str]:
    """Match ChatTarget.external_chat_id across -100id / id / marked peer forms."""
    if chat_id is None:
        return []
    try:
        raw = int(chat_id)
    except (TypeError, ValueError):
        return []
    keys = [str(raw)]
    if raw < 0:
        keys.append(str(-raw))
        text = str(raw)
        if text.startswith("-100"):
            keys.append(text[4:])
    else:
        keys.append(f"-100{raw}")
        keys.append(str(-raw))
    return list(dict.fromkeys(keys))


def is_channel_post(event: Any) -> bool:
    message = getattr(event, "message", None)
    if message is None:
        return False
    if getattr(event, "out", False) or getattr(message, "out", False):
        return False
    if not (getattr(message, "text", None) or "").strip():
        return False
    if getattr(message, "post", False):
        return True
    return bool(getattr(event, "is_channel", False)) and not bool(getattr(event, "is_group", False))


def attach_comment_listener(wrapper: Any, *, account_id: int, automation_id: int) -> bool:
    """Idempotent: one NewMessage handler per live Telethon client."""
    client = getattr(wrapper, "client", None)
    if client is None:
        return False
    if getattr(client, _HANDLER_FLAG, False):
        return False
    try:
        from telethon import events
    except Exception:
        return False

    async def _on_new_message(event: Any) -> None:
        if not is_channel_post(event):
            return
        try:
            await handle_listened_channel_post(
                automation_id=automation_id,
                account_id=account_id,
                chat_id=getattr(event, "chat_id", None),
                username=getattr(getattr(event, "chat", None), "username", None),
                post_id=getattr(getattr(event, "message", None), "id", None),
                post_text=getattr(getattr(event, "message", None), "text", None) or "",
                posted_at=getattr(getattr(event, "message", None), "date", None),
            )
        except Exception:
            logger.exception(
                "Channel post listener failed automation=%s account=%s",
                automation_id,
                account_id,
            )

    client.add_event_handler(_on_new_message, events.NewMessage(incoming=True))
    setattr(client, _HANDLER_FLAG, True)
    logger.info(
        "Listening for channel posts automation=%s account=%s",
        automation_id,
        account_id,
    )
    return True


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _find_task_chat(
    session: AsyncSession,
    automation_id: int,
    *,
    chat_id: int | None,
    username: str | None,
) -> ChatTarget | None:
    keys = peer_id_keys(chat_id)
    if keys:
        found = await session.scalar(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.black_boxed_at.is_(None),
                ChatTarget.external_chat_id.in_(keys),
            )
        )
        if found is not None:
            return found
    nick = (username or "").strip().lstrip("@").lower()
    if not nick:
        return None
    return await session.scalar(
        select(ChatTarget).where(
            ChatTarget.custom_automation_id == automation_id,
            ChatTarget.black_boxed_at.is_(None),
            or_(
                ChatTarget.invite_link.ilike(f"%/{nick}"),
                ChatTarget.invite_link.ilike(f"%/{nick}?%"),
            ),
        )
    )


async def handle_listened_channel_post(
    *,
    automation_id: int,
    account_id: int,
    chat_id: int | None,
    username: str | None,
    post_id: int | None,
    post_text: str,
    posted_at: datetime | None,
) -> dict[str, Any]:
    if not post_id or not (post_text or "").strip():
        return {"status": "skipped", "reason": "empty"}
    async with async_session_maker() as session:
        return await queue_listened_comment(
            session,
            automation_id=automation_id,
            account_id=account_id,
            chat_id=chat_id,
            username=username,
            post_id=int(post_id),
            post_text=post_text,
            posted_at=_naive_utc(posted_at),
        )


async def queue_listened_comment(
    session: AsyncSession,
    *,
    automation_id: int,
    account_id: int,
    chat_id: int | None,
    username: str | None,
    post_id: int,
    post_text: str,
    posted_at: datetime | None,
) -> dict[str, Any]:
    from .account_pacing import account_may_do_work, farm_overlap_active_hours
    from .chat_membership_service import account_is_joined
    from .job_service import actor_label, chat_label, load_active_job_params, log_active
    from .module_delays import format_delay_ru
    from .neurocommenting_service import (
        POST_COMMENT_DELAY_MAX_SECONDS,
        POST_COMMENT_DELAY_MIN_SECONDS,
        _already_commented,
        _as_int_list,
        _count_chat_comments_today,
        _delay_bounds,
        _word_count,
        chat_comment_daily_limit,
        comment_ready_at,
    )
    from .account_restriction import restriction_blocks_action
    from .pending_action_service import (
        COMMENT_QUEUE_PER_ACCOUNT,
        enqueue_pending_action,
        has_pending_action,
        pending_comment_count,
    )
    from .post_engagement import post_target_id
    from .task_targets import load_work_pool
    from ...alembic.models import CustomAutomation

    if not farm_overlap_active_hours():
        return {"status": "skipped", "reason": "night"}
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None or not automation.is_neurocommenting_enabled:
        return {"status": "skipped", "reason": "feature_disabled"}
    account = await session.get(SocialAccount, account_id)
    if account is None or not account.is_active:
        return {"status": "skipped", "reason": "no_account"}
    if restriction_blocks_action(account, "neurocommenting") or not account_may_do_work(account):
        return {"status": "skipped", "reason": "restricted"}
    if await pending_comment_count(session, automation_id, account_id) >= COMMENT_QUEUE_PER_ACCOUNT:
        return {"status": "skipped", "reason": "account_busy"}
    chat = await _find_task_chat(session, automation_id, chat_id=chat_id, username=username)
    if chat is None:
        return {"status": "skipped", "reason": "unknown_chat"}
    if chat.comments_open is False:
        return {"status": "skipped", "reason": "comments_closed"}
    cfg = await load_active_job_params(session, automation_id, "neurocommenting")
    if cfg is None:
        cfg = ((automation.module_settings or {}).get("neurocommenting") or {})
    allowed = set(_as_int_list(cfg.get("account_ids")))
    if allowed and account_id not in allowed:
        return {"status": "skipped", "reason": "not_assigned"}
    work_pool = await load_work_pool(session, automation_id, cfg, task_key="neurocommenting")
    if work_pool.active and not work_pool.allows(automation, "neurocommenting", account_id, chat.id):
        return {"status": "skipped", "reason": "not_owner"}
    joined = await session.scalar(
        select(AccountChatMembership.id).where(
            AccountChatMembership.chat_target_id == chat.id,
            AccountChatMembership.social_account_id == account_id,
            AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
        )
    )
    if not joined and not await account_is_joined(session, chat.id, account_id):
        return {"status": "skipped", "reason": "not_joined"}
    try:
        min_words = max(0, int(cfg.get("min_words") or 0))
    except (TypeError, ValueError):
        min_words = 0
    if min_words and _word_count(post_text) < min_words:
        return {"status": "skipped", "reason": "min_words"}
    post_filter = str(cfg.get("post_filter") or "new").strip().lower()
    if post_filter == "keywords":
        from .lead_keywords import matched_lead_keyword, normalize_lead_keywords

        keywords = normalize_lead_keywords(cfg.get("keywords"))
        if not keywords or not matched_lead_keyword(post_text, keywords):
            return {"status": "skipped", "reason": "keywords"}
    try:
        probability = max(0, min(100, int(cfg.get("probability") if cfg.get("probability") is not None else 100)))
    except (TypeError, ValueError):
        probability = 100
    if probability < 100 and random.random() * 100 > probability:
        return {"status": "skipped", "reason": "probability"}
    target = post_target_id(chat.id, post_id)
    if await _already_commented(session, automation_id, chat.id, post_id):
        return {"status": "skipped", "reason": "already_commented"}
    if await has_pending_action(session, automation_id, "neurocommenting", target):
        return {"status": "skipped", "reason": "already_queued"}
    per_chat = chat_comment_daily_limit({"max_per_day": cfg.get("max_per_chat")})
    if await _count_chat_comments_today(session, automation_id, chat.id) >= per_chat:
        return {"status": "skipped", "reason": "chat_daily_limit"}
    delay_min, delay_max = _delay_bounds(cfg)
    if delay_min <= 0:
        delay_min, delay_max = float(POST_COMMENT_DELAY_MIN_SECONDS), float(POST_COMMENT_DELAY_MAX_SECONDS)
    wait = random.uniform(delay_min, delay_max)
    posted = posted_at or _utc_now()
    rest_until = getattr(account, "next_action_at", None)
    if rest_until is not None and rest_until <= _utc_now():
        rest_until = None
    delay_until = comment_ready_at(posted_at=posted, wait_seconds=wait, rest_until=rest_until)
    remaining = max(0.0, (delay_until - _utc_now()).total_seconds())
    try:
        prompt_id = int(cfg["prompt_id"]) if cfg.get("prompt_id") else None
    except (TypeError, ValueError):
        prompt_id = None
    pending = await enqueue_pending_action(
        session,
        automation_id=automation_id,
        chat_target=chat,
        account=account,
        action_type="neurocommenting",
        target_id=target,
        payload={"post_id": post_id, "post_text": (post_text or "")[:500], "prompt_id": prompt_id},
    )
    if not pending or pending.status == "done":
        return {"status": "skipped", "reason": "queue_failed" if not pending else "already_queued"}
    if remaining > 1:
        pending.next_attempt_at = delay_until
    await session.commit()
    await log_active(
        automation_id,
        "neurocommenting",
        f"{actor_label(account)} увидел пост в {chat_label(chat)}"
        + (
            f" — комментарий через {format_delay_ru(remaining)}"
            if remaining > 1
            else " — отправит комментарий"
        ),
    )
    return {"status": "queued", "remaining": remaining, "chat_id": chat.id, "post_id": post_id}
