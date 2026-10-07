"""Mass priming: open a DM, toggle auto-delete, never send a message."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .account_pacing import account_humanization_should_idle, farm_overlap_active_hours, schedule_account_humanization_rest
from .module_account_filters import no_accounts_picked, skip_account_for_module
from .humanization_session import inspect_peer_profile
from .rotation_service import record_successful_humanization
from .telegram_account_client import TelegramAccountClient
from .telegram_error_handler import execute_with_telegram_retry
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref
from ...alembic.models import AutomationActionLog, CustomAutomation, PoolAccount, SocialAccount
from ...config import settings

logger = logging.getLogger(__name__)

TTL_DAY = 86400
TTL_WEEK = 604800
TTL_MONTH = 2678400
TTL_PERIODS = (TTL_DAY, TTL_WEEK, TTL_MONTH)
ACTION_TYPE = "masspriming"


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


def normalize_prime_targets(raw: Any) -> list[str]:
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
        if len(out) >= 300:
            break
    return out


def normalize_ttl_period(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return TTL_DAY
    if value in TTL_PERIODS:
        return value
    return min(TTL_PERIODS, key=lambda item: abs(item - max(0, value))) or TTL_DAY


def is_primeable_user(entity: Any) -> bool:
    if entity is None:
        return False
    name = type(entity).__name__
    if name in {"Channel", "Chat", "ChatForbidden", "ChannelForbidden", "UserEmpty"}:
        return False
    if getattr(entity, "broadcast", False) or getattr(entity, "megagroup", False):
        return False
    if getattr(entity, "bot", False) or getattr(entity, "deleted", False) or getattr(entity, "is_self", False):
        return False
    return True


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _peer_label(entity: Any, fallback: str) -> str:
    username = (getattr(entity, "username", None) or "").strip()
    if username:
        return f"@{username}"
    first = (getattr(entity, "first_name", None) or "").strip()
    last = (getattr(entity, "last_name", None) or "").strip()
    return " ".join(part for part in (first, last) if part) or fallback


async def _counts_since(session: AsyncSession, automation_id: int, account_id: int, since: datetime) -> int:
    count = await session.scalar(
        select(func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.social_account_id == account_id,
            AutomationActionLog.action_type == ACTION_TYPE,
            AutomationActionLog.result == "success",
            AutomationActionLog.created_at >= since,
        )
    )
    return int(count or 0)


async def _seen_recently(
    session: AsyncSession,
    automation_id: int,
    target_id: str,
    *,
    hours: int,
) -> bool:
    filters = [
        AutomationActionLog.custom_automation_id == automation_id,
        AutomationActionLog.action_type == ACTION_TYPE,
        AutomationActionLog.result == "success",
        AutomationActionLog.target_id == target_id,
    ]
    if hours <= 0:
        return False
    filters.append(AutomationActionLog.created_at >= _utc_now() - timedelta(hours=hours))
    row = await session.scalar(select(AutomationActionLog.id).where(*filters))
    return row is not None


async def add_contact(telethon: Any, entity: Any) -> str:
    try:
        from telethon.tl.functions.contacts import AddContactRequest
    except Exception:
        return "skipped"
    if getattr(entity, "contact", False):
        return "already"
    try:
        await telethon(
            AddContactRequest(
                id=entity,
                first_name=(getattr(entity, "first_name", None) or "User")[:64],
                last_name=(getattr(entity, "last_name", None) or "")[:64],
                phone="",
                add_phone_privacy_exception=False,
            )
        )
        return "added"
    except Exception as exc:
        logger.debug("Masspriming AddContact skipped: %s", exc)
        return "skipped"


async def _as_peer(telethon: Any, entity: Any) -> Any:
    getter = getattr(telethon, "get_input_entity", None)
    if callable(getter):
        try:
            return await getter(entity)
        except Exception:
            return entity
    return entity


async def open_private_dialog(telethon: Any, entity: Any) -> bool:
    try:
        from telethon.tl.functions.messages import GetPeerDialogsRequest
        from telethon.tl.types import InputDialogPeer
    except Exception:
        return False
    try:
        peer = await _as_peer(telethon, entity)
        await telethon(GetPeerDialogsRequest(peers=[InputDialogPeer(peer)]))
        return True
    except Exception as exc:
        logger.debug("Masspriming open dialog skipped: %s", exc)
        try:
            await telethon(GetPeerDialogsRequest(peers=[entity]))
            return True
        except Exception:
            return False


async def set_history_ttl(telethon: Any, entity: Any, period: int) -> None:
    from telethon.tl.functions.messages import SetHistoryTTLRequest

    peer = await _as_peer(telethon, entity)
    await telethon(SetHistoryTTLRequest(peer=peer, period=int(period)))


async def prime_peer(
    telethon: Any,
    entity: Any,
    *,
    add_contact_flag: bool,
    ttl_mode: str,
    ttl_period: int,
    sleeper=None,
) -> dict[str, Any]:
    """Open DM and toggle auto-delete. Never sends a text message."""
    pause = sleeper or asyncio.sleep
    await inspect_peer_profile(telethon, entity)
    contact = "skipped"
    if add_contact_flag:
        contact = await add_contact(telethon, entity)
        await pause(random.uniform(0.8, 2.2))
    opened = await open_private_dialog(telethon, entity)
    await pause(random.uniform(0.6, 1.8))
    mode = (ttl_mode or "toggle").strip().lower()
    if mode not in {"toggle", "enable", "disable"}:
        mode = "toggle"
    period = normalize_ttl_period(ttl_period)
    if mode in {"toggle", "enable"}:
        await set_history_ttl(telethon, entity, period)
    if mode == "toggle":
        await pause(random.uniform(1.6, 4.0))
    if mode in {"toggle", "disable"}:
        await set_history_ttl(telethon, entity, 0)
    return {"contact": contact, "opened": opened, "ttl_mode": mode, "ttl_period": period if mode != "disable" else 0}


async def _log_prime(
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
            target_type="user",
            result=result,
            payload={"title": title, **payload},
            created_at=_utc_now(),
        )
    )
    await session.commit()


async def _process_account(
    session: AsyncSession,
    automation: CustomAutomation,
    account: SocialAccount,
    pool: PoolAccount | None,
    cfg: dict[str, Any],
    targets: list[str],
    own_usernames: set[str],
) -> int:
    if not account.session_file_path:
        return 0
    if not (_media_root() / account.session_file_path).exists():
        return 0
    if skip_account_for_module(cfg, account, pool):
        return 0
    if bool(cfg.get("skip_quarantine", True)) and pool and (pool.warmup_status or "idle") in {"rest", "warming"}:
        return 0
    if account_humanization_should_idle(account):
        return 0
    try:
        max_per_account = int(cfg.get("max_per_account") or 0)
    except (TypeError, ValueError):
        max_per_account = 0
    already = await _counts_since(session, automation.id, account.id, _utc_now().replace(hour=0, minute=0, second=0, microsecond=0))
    if max_per_account > 0 and already >= max_per_account:
        return 0
    try:
        max_per_hour = int(cfg.get("max_per_hour") or 0)
    except (TypeError, ValueError):
        max_per_hour = 0
    hourly = await _counts_since(session, automation.id, account.id, _utc_now() - timedelta(hours=1)) if max_per_hour > 0 else 0
    if max_per_hour > 0 and hourly >= max_per_hour:
        return 0
    try:
        skip_hours = int(cfg.get("skip_hours") or 0) if cfg.get("skip_seen", True) else 0
    except (TypeError, ValueError):
        skip_hours = 72 if cfg.get("skip_seen", True) else 0
    try:
        delay_min = max(0, int(cfg.get("delay_min") if cfg.get("delay_min") is not None else 8))
        delay_max = max(delay_min, int(cfg.get("delay_max") if cfg.get("delay_max") is not None else 25))
    except (TypeError, ValueError):
        delay_min, delay_max = 8, 25
    remaining = None if max_per_account <= 0 else max(0, max_per_account - already)
    primed = 0
    async with TelegramAccountClient.for_account(account) as client:
        telethon = getattr(client, "client", client)
        for username in targets:
            if remaining is not None and primed >= remaining:
                break
            if max_per_hour > 0 and hourly + primed >= max_per_hour:
                break
            key = username.lower()
            if key in own_usernames:
                continue
            if await _seen_recently(session, automation.id, key, hours=skip_hours):
                continue
            try:
                entity = await client.get_entity(username)
            except Exception as exc:
                logger.debug("Masspriming resolve %s failed: %s", username, exc)
                await _log_prime(
                    session,
                    automation_id=automation.id,
                    account=account,
                    target_id=key,
                    title=username,
                    payload={"error": str(exc)[:200], "step": "resolve"},
                    result="error",
                )
                continue
            if not is_primeable_user(entity):
                continue
            from .task_dedup import entity_is_bot_or_userbot

            if bool(cfg.get("skip_bots", True)) and await entity_is_bot_or_userbot(client, entity):
                continue
            try:
                outcome = await execute_with_telegram_retry(
                    session,
                    account,
                    lambda ent=entity: prime_peer(
                        telethon,
                        ent,
                        add_contact_flag=bool(cfg.get("add_contact", True)),
                        ttl_mode=str(cfg.get("ttl_mode") or "toggle"),
                        ttl_period=normalize_ttl_period(cfg.get("ttl_period")),
                    ),
                    action_type=ACTION_TYPE,
                    target_id=key,
                    target_type="user",
                    payload={"title": _peer_label(entity, username)},
                    automation_id=automation.id,
                    pace=False,
                )
            except Exception as exc:
                logger.warning("Masspriming %s -> %s failed: %s", account.id, username, exc)
                continue
            await _log_prime(
                session,
                automation_id=automation.id,
                account=account,
                target_id=key,
                title=_peer_label(entity, username),
                payload=outcome if isinstance(outcome, dict) else {},
            )
            primed += 1
            from .job_service import actor_label, log_active

            await log_active(
                automation.id,
                "masspriming",
                f"{actor_label(account)} пропраймил {_peer_label(entity, username)}",
            )
            await asyncio.sleep(random.uniform(delay_min, delay_max))
    if primed:
        record_successful_humanization(account)
        if bool(cfg.get("limit_rate", True)):
            schedule_account_humanization_rest(account)
        await session.commit()
    return primed


async def run_masspriming_pass(automation_id: int, run_config: dict[str, Any] | None = None) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    total = 0
    accounts_used = 0
    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        if not automation:
            return {"status": "skipped", "reason": "missing", "primed": 0}
        cfg = run_config if isinstance(run_config, dict) else ((automation.module_settings or {}).get("masspriming") or {})
        if not bool(cfg.get("enabled")):
            return {"status": "skipped", "reason": "disabled", "primed": 0}
        if no_accounts_picked(cfg):
            return {"status": "skipped", "reason": "no_accounts", "primed": 0}
        if bool(cfg.get("respect_night_hours", True)) and not farm_overlap_active_hours():
            return {"status": "skipped", "reason": "night", "primed": 0}
        targets = normalize_prime_targets(cfg.get("targets"))
        from .task_targets import resolve_user_folder_peers

        extra = await resolve_user_folder_peers(session, automation_id, cfg, usernames_only=True)
        targets = normalize_prime_targets([*targets, *extra])
        if not targets:
            return {"status": "skipped", "reason": "no_targets", "primed": 0}
        allowed = set(_as_int_list(cfg.get("account_ids")))
        blocked = set(_as_int_list(cfg.get("blacklisted_account_ids")))
        pairs = (
            await session.execute(
                select(SocialAccount, PoolAccount)
                .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
                .where(PoolAccount.custom_automation_id == automation_id)
            )
        ).all()
        own = {
            f"@{(account.username or '').strip()}".lower()
            for account, _pool in pairs
            if (account.username or "").strip()
        }
        workers: list[int] = []
        by_id: dict[int, tuple[SocialAccount, PoolAccount | None]] = {}
        for account, pool in pairs:
            if allowed and account.id not in allowed:
                continue
            if account.id in blocked:
                continue
            if not account.is_active or account.is_banned or account.is_frozen or getattr(account, "is_spamblocked", False):
                continue
            if skip_account_for_module(cfg, account, pool):
                continue
            if not account.session_file_path:
                continue
            workers.append(account.id)
            by_id[account.id] = (account, pool)
        if not workers:
            return {"status": "skipped", "reason": "no_accounts", "primed": 0}
        from .task_dedup import load_unique_assign, store_unique_assign, unique_assign

        assignment = unique_assign(workers, targets, load_unique_assign(automation, "masspriming"))
        store_unique_assign(automation, "masspriming", assignment)
        await session.commit()
        for account_id, slice_targets in assignment.items():
            account, pool = by_id[account_id]
            try:
                added = await _process_account(session, automation, account, pool, cfg, slice_targets, own)
            except Exception as exc:
                logger.exception("Masspriming failed for account %s: %s", account.id, exc)
                continue
            if added:
                accounts_used += 1
                total += added
    return {"status": "ok", "primed": total, "accounts": accounts_used}
