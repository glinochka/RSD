"""Masslooking: pool accounts view stories of chosen peers and/or the stories feed."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import (
    account_humanization_should_idle,
    farm_overlap_active_hours,
    schedule_account_humanization_rest,
)
from .module_account_filters import no_accounts_picked, skip_account_for_module
from .module_delays import DELAY_MAX_SECONDS
from .humanization_session import inspect_peer_profile, load_feed_peer_stories, load_peer_stories, mark_peer_stories_read
from .rotation_service import record_successful_humanization
from .telegram_account_client import TelegramAccountClient
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import AutomationActionLog, ChatTarget, CustomAutomation, PoolAccount, SocialAccount
from ...config import settings

logger = logging.getLogger(__name__)


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


def like_roll_hits(probability: int, roll: float) -> bool:
    try:
        chance = max(0, min(100, int(probability)))
    except (TypeError, ValueError):
        chance = 0
    return float(roll) * 100 < chance


def story_peer_keys(targets: Any, folder_peers: list[str] | None = None) -> list[str]:
    """Usernames and numeric ids. One key per person, stable for distribution."""
    keys: list[str] = []
    seen: set[str] = set()
    raw_items: list[str] = []
    raw_items.extend(normalize_story_targets(targets))
    raw_items.extend(folder_peers or [])
    for raw in raw_items:
        text = str(raw or "").strip()
        if not text:
            continue
        if text.lower().startswith("id:"):
            key = text.lower()
        elif text.lstrip("-").isdigit():
            key = f"id:{int(text)}"
        else:
            named = normalize_story_targets([text])
            if not named:
                continue
            key = named[0].lower()
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def normalize_story_targets(raw: Any) -> list[str]:
    if isinstance(raw, str):
        values = raw.splitlines()
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
        if ref.kind != "username":
            continue
        key = f"@{ref.value}".lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(f"@{ref.value}")
        if len(out) >= 200:
            break
    return out


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _peer_label(entity: Any, fallback: str) -> str:
    username = (getattr(entity, "username", None) or "").strip()
    if username:
        return f"@{username}"
    title = (getattr(entity, "title", None) or getattr(entity, "first_name", None) or "").strip()
    return title or fallback


async def _views_since(session: AsyncSession, automation_id: int, account_id: int, since: datetime) -> int:
    count = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type == "masslooking",
            AutomationActionLog.result == "success",
            AutomationActionLog.created_at >= since,
        )
    )
    return int(count or 0)


async def _views_today(session: AsyncSession, automation_id: int, account_id: int) -> int:
    start = _utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return await _views_since(session, automation_id, account_id, start)


async def _seen_recently(
    session: AsyncSession,
    automation_id: int,
    target_id: str,
    *,
    hours: int,
    account_id: int | None = None,
) -> bool:
    filters = [
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.action_type == "masslooking",
        AutomationActionLog.result == "success",
        AutomationActionLog.target_id == target_id,
    ]
    if hours <= 0:
        return False
    if account_id is not None:
        filters.append(AutomationActionLog.social_account_id == account_id)
    filters.append(AutomationActionLog.created_at >= _utc_now() - timedelta(hours=hours))
    row = await session.scalar(select(AutomationActionLog.id).where(*filters))
    return row is not None


async def _log_view(
    session: AsyncSession,
    *,
    automation_id: int,
    account: SocialAccount,
    target_id: str,
    title: str,
    stories: int,
    source: str,
    extra: dict[str, Any] | None = None,
) -> None:
    session.add(
        AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account.id,
            action_type="masslooking",
            target_id=target_id,
            target_type="story_peer",
            result="success",
            payload={"title": title, "stories": stories, "source": source, **(extra or {})},
            created_at=_utc_now(),
        )
    )
    await session.commit()


async def _resolve_peer(client: TelegramAccountClient, token: str) -> Any:
    telethon = getattr(client, "client", client)
    if token.startswith("id:"):
        return await telethon.get_entity(int(token.split(":", 1)[1]))
    return await telethon.get_entity(token)


async def _react_to_story(client: Any, peer: Any, story_id: int) -> bool:
    try:
        from telethon.tl.functions.stories import SendReactionRequest
        from telethon.tl.types import ReactionEmoji
    except Exception:
        return False
    try:
        await getattr(client, "client", client)(
            SendReactionRequest(
                peer=peer,
                story_id=int(story_id),
                reaction=ReactionEmoji(emoticon="❤"),
                add_to_recent=True,
            )
        )
        return True
    except Exception as exc:
        logger.debug("Story reaction skipped: %s", exc)
        return False


async def _view_entity(
    session: AsyncSession,
    client: TelegramAccountClient,
    account: SocialAccount,
    automation_id: int,
    entity: Any,
    *,
    target_id: str,
    source: str,
    skip_hours: int,
) -> int:
    if await _seen_recently(session, automation_id, target_id, hours=skip_hours):
        return 0
    await inspect_peer_profile(client, entity)
    peer, stories = await load_peer_stories(client, entity)
    counted = await mark_peer_stories_read(client, peer or entity, stories, lab_mode=False)
    if not counted:
        return 0
    await _log_view(
        session,
        automation_id=automation_id,
        account=account,
        target_id=target_id,
        title=_peer_label(entity, target_id),
        stories=counted,
        source=source,
    )
    return 1


async def _process_account(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    cfg: dict[str, Any],
    targets: list[str],
    pool: PoolAccount | None = None,
) -> int:
    if not account.session_file_path:
        return 0
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return 0
    if skip_account_for_module(cfg, account, pool):
        return 0
    if account_humanization_should_idle(account):
        return 0
    from .daily_quota import account_blocked_for_task, quota_bounds, rolled_daily_actions, task_actions_today
    from .masspriming_service import add_contact, is_primeable_user

    if await account_blocked_for_task(session, automation.id, account, "masslooking", cfg, default_max=50, hi=500):
        return 0
    bounds = quota_bounds(cfg, default_max=50, hi=500)
    already = await task_actions_today(session, automation.id, account.id, ("masslooking",))
    if bounds is None:
        remaining = None
    else:
        remaining = max(0, rolled_daily_actions(account.id, "masslooking", bounds[0], bounds[1]) - already)
    try:
        max_per_hour = int(cfg.get("max_per_hour") or 0)
    except (TypeError, ValueError):
        max_per_hour = 0
    hourly = await _views_since(session, automation.id, account.id, _utc_now() - timedelta(hours=1)) if max_per_hour > 0 else 0
    if max_per_hour > 0 and hourly >= max_per_hour:
        return 0
    try:
        skip_hours = int(cfg.get("skip_hours") or 0) if cfg.get("skip_seen", True) else 0
    except (TypeError, ValueError):
        skip_hours = 24 if cfg.get("skip_seen", True) else 0
    try:
        delay_min = max(0, min(DELAY_MAX_SECONDS, int(cfg.get("delay_min") if cfg.get("delay_min") is not None else 8)))
        delay_max = max(delay_min, min(DELAY_MAX_SECONDS, int(cfg.get("delay_max") if cfg.get("delay_max") is not None else 20)))
    except (TypeError, ValueError):
        delay_min, delay_max = 8, 20
    if max_per_hour > 0:
        hour_left = max(0, max_per_hour - hourly)
        remaining = hour_left if remaining is None else min(remaining, hour_left)
    try:
        like_probability = max(0, min(100, int(cfg.get("like_probability") if cfg.get("like_probability") is not None else 30)))
    except (TypeError, ValueError):
        like_probability = 30
    viewed = 0

    async with TelegramAccountClient.for_account(account) as client:
        telethon = getattr(client, "client", client)
        for token in targets:
            if remaining is not None and viewed >= remaining:
                break
            key = token.lower()
            if await _seen_recently(session, automation.id, key, hours=skip_hours, account_id=account.id):
                continue
            try:
                entity = await _resolve_peer(client, token)
            except Exception as exc:
                logger.debug("Masslooking resolve %s failed: %s", token, exc)
                continue
            if not is_primeable_user(entity):
                continue
            from .task_dedup import entity_is_bot_or_userbot

            if bool(cfg.get("skip_bots", True)) and await entity_is_bot_or_userbot(client, entity):
                continue
            await inspect_peer_profile(client, entity)
            contact = await add_contact(telethon, entity)
            peer, stories = await load_peer_stories(client, entity)
            counted = 0
            liked = False
            if stories:
                counted = await mark_peer_stories_read(client, peer or entity, stories, lab_mode=False)
                newest = max(stories, key=lambda item: int(getattr(item, "id", 0) or 0))
                story_id = int(getattr(newest, "id", 0) or 0)
                if counted and story_id and like_roll_hits(like_probability, random.random()):
                    liked = await _react_to_story(client, peer or entity, story_id)
            title = _peer_label(entity, token)
            await _log_view(
                session,
                automation_id=automation.id,
                account=account,
                target_id=key,
                title=title,
                stories=counted,
                source="contact",
                extra={"contact": contact, "liked": liked},
            )
            viewed += 1
            from .job_service import actor_label, log_active

            if counted and liked:
                detail = f"посмотрел и лайкнул сторис {title}"
            elif counted:
                detail = f"посмотрел сторис {title}"
            else:
                detail = f"добавил {title} в контакты, сторис нет"
            await log_active(automation.id, "masslooking", f"{actor_label(account)} {detail}")
            await asyncio.sleep(random.uniform(delay_min, delay_max))
    if viewed:
        record_successful_humanization(account)
        if bool(cfg.get("limit_rate", True)):
            schedule_account_humanization_rest(account)
        await session.commit()
    return viewed


async def run_masslooking_pass(automation_id: int, run_config: dict[str, Any] | None = None) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    total = 0
    accounts_used = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "missing", "views": 0}
        cfg = run_config if isinstance(run_config, dict) else ((automation.module_settings or {}).get("masslooking") or {})
        if not bool(cfg.get("enabled")):
            return {"status": "skipped", "reason": "disabled", "views": 0}
        if no_accounts_picked(cfg):
            return {"status": "skipped", "reason": "no_accounts", "views": 0}
        if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
            return {"status": "skipped", "reason": "night", "views": 0}
        from .task_targets import resolve_user_folder_peers

        folder_peers = await resolve_user_folder_peers(session, automation_id, cfg, usernames_only=False)
        targets = story_peer_keys(cfg.get("targets"), folder_peers)
        if not targets:
            return {"status": "skipped", "reason": "no_targets", "views": 0}
        allowed = set(_as_int_list(cfg.get("account_ids")))
        blocked = set(_as_int_list(cfg.get("blacklisted_account_ids")))
        pairs = (
            await session.execute(
                select(SocialAccount, PoolAccount)
                .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
                .where(PoolAccount.custom_automation_id == automation_id)
            )
        ).all()
        workers: list[int] = []
        by_id: dict[int, tuple[SocialAccount, PoolAccount | None]] = {}
        for account, _pool in pairs:
            if allowed and account.id not in allowed:
                continue
            if account.id in blocked:
                continue
            if not account.is_active or account.is_banned or account.is_frozen:
                continue
            if skip_account_for_module(cfg, account, _pool):
                continue
            if not account.session_file_path:
                continue
            workers.append(account.id)
            by_id[account.id] = (account, _pool)
        if not workers:
            return {"status": "skipped", "reason": "no_accounts", "views": 0}
        from .task_dedup import load_unique_assign, store_unique_assign, unique_assign

        assignment = unique_assign(workers, targets, load_unique_assign(automation, "masslooking"))
        store_unique_assign(automation, "masslooking", assignment)
        await session.commit()
        for account_id, slice_targets in assignment.items():
            account, pool = by_id[account_id]
            try:
                added = await _process_account(session, automation, account, cfg, slice_targets, pool)
            except Exception as exc:
                logger.exception("Masslooking failed for account %s: %s", account.id, exc)
                continue
            if added:
                accounts_used += 1
                total += added
    return {"status": "ok", "views": total, "accounts": accounts_used}
