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
from .humanization_session import load_feed_peer_stories, load_peer_stories, mark_peer_stories_read
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
    account_id: int,
    target_id: str,
    *,
    hours: int,
) -> bool:
    if hours <= 0:
        return False
    since = _utc_now() - timedelta(hours=hours)
    row = await session.scalar(
        select(AutomationActionLog.id).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type == "masslooking",
            AutomationActionLog.result == "success",
            AutomationActionLog.target_id == target_id,
            AutomationActionLog.created_at >= since,
        )
    )
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
) -> None:
    session.add(
        AutomationActionLog(
            custom_automation_id=automation_id,
            social_account_id=account.id,
            action_type="masslooking",
            target_id=target_id,
            target_type="story_peer",
            result="success",
            payload={"title": title, "stories": stories, "source": source},
            created_at=_utc_now(),
        )
    )
    await session.commit()


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
    if await _seen_recently(session, automation_id, account.id, target_id, hours=skip_hours):
        return 0
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
) -> int:
    if not account.session_file_path:
        return 0
    session_path = _media_root() / account.session_file_path
    if not session_path.exists():
        return 0
    if bool(cfg.get("require_proxy")) and not getattr(account, "telegram_proxy", None):
        return 0
    if account_humanization_should_idle(account):
        return 0
    try:
        max_per_account = int(cfg.get("max_per_account") or 0)
    except (TypeError, ValueError):
        max_per_account = 0
    already = await _views_today(session, automation.id, account.id)
    if max_per_account > 0 and already >= max_per_account:
        return 0
    try:
        max_per_hour = int(cfg.get("max_per_hour") or 0)
    except (TypeError, ValueError):
        max_per_hour = 0
    hourly = await _views_since(session, automation.id, account.id, _utc_now() - timedelta(hours=1)) if max_per_hour > 0 else 0
    if max_per_hour > 0 and hourly >= max_per_hour:
        return 0
    try:
        stories_limit = int(cfg.get("stories_limit") or 0)
    except (TypeError, ValueError):
        stories_limit = 0
    try:
        skip_hours = int(cfg.get("skip_hours") or 0) if cfg.get("skip_seen", True) else 0
    except (TypeError, ValueError):
        skip_hours = 24 if cfg.get("skip_seen", True) else 0
    try:
        delay_min = max(0, int(cfg.get("delay_min") if cfg.get("delay_min") is not None else 2))
        delay_max = max(delay_min, int(cfg.get("delay_max") if cfg.get("delay_max") is not None else 6))
    except (TypeError, ValueError):
        delay_min, delay_max = 2, 6
    remaining = None if max_per_account <= 0 else max(0, max_per_account - already)
    if max_per_hour > 0:
        hour_left = max(0, max_per_hour - hourly)
        remaining = hour_left if remaining is None else min(remaining, hour_left)
    peer_budget = stories_limit if stories_limit > 0 else None
    viewed = 0

    async with TelegramAccountClient.for_account(account) as client:
        telethon = getattr(client, "client", client)
        if bool(cfg.get("view_feed", True)):
            feed = await load_feed_peer_stories(client)
            random.shuffle(feed)
            for packed in feed:
                if remaining is not None and viewed >= remaining:
                    break
                if peer_budget is not None and viewed >= peer_budget:
                    break
                stories = list(getattr(packed, "stories", None) or [])
                peer = getattr(packed, "peer", None)
                peer_key = f"feed:{getattr(peer, 'user_id', None) or getattr(peer, 'channel_id', None) or viewed}"
                if await _seen_recently(session, automation.id, account.id, peer_key, hours=skip_hours):
                    continue
                counted = await mark_peer_stories_read(client, peer, stories, lab_mode=False)
                if not counted:
                    continue
                await _log_view(
                    session,
                    automation_id=automation.id,
                    account=account,
                    target_id=peer_key,
                    title="Лента историй",
                    stories=counted,
                    source="feed",
                )
                viewed += 1
                await asyncio.sleep(random.uniform(delay_min, delay_max))
        for username in targets:
            if remaining is not None and viewed >= remaining:
                break
            if peer_budget is not None and viewed >= peer_budget:
                break
            key = username.lower()
            try:
                entity = await telethon.get_entity(username)
            except Exception as exc:
                logger.debug("Masslooking resolve %s failed: %s", username, exc)
                continue
            added = await _view_entity(
                session,
                client,
                account,
                automation.id,
                entity,
                target_id=key,
                source="target",
                skip_hours=skip_hours,
            )
            if added:
                viewed += 1
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
        if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
            return {"status": "skipped", "reason": "night", "views": 0}
        targets = normalize_story_targets(cfg.get("targets"))
        chat_ids = set(_as_int_list(cfg.get("chat_ids")))
        if chat_ids:
            chats = (
                await session.execute(
                    select(ChatTarget).where(
                        ChatTarget.custom_automation_id == automation_id,
                        ChatTarget.id.in_(chat_ids),
                    )
                )
            ).scalars().all()
            extra = []
            for chat in chats:
                extra.extend([chat.invite_link or "", chat.title or "", chat.external_chat_id or ""])
            targets = normalize_story_targets([*targets, *extra])
        allowed = set(_as_int_list(cfg.get("account_ids")))
        blocked = set(_as_int_list(cfg.get("blacklisted_account_ids")))
        pairs = (
            await session.execute(
                select(SocialAccount, PoolAccount)
                .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
                .where(PoolAccount.custom_automation_id == automation_id)
            )
        ).all()
        for account, _pool in pairs:
            if allowed and account.id not in allowed:
                continue
            if account.id in blocked:
                continue
            if not account.is_active or account.is_banned or account.is_frozen:
                continue
            try:
                added = await _process_account(session, automation, account, cfg, targets)
            except Exception as exc:
                logger.exception("Masslooking failed for account %s: %s", account.id, exc)
                continue
            if added:
                accounts_used += 1
                total += added
    return {"status": "ok", "views": total, "accounts": accounts_used}
