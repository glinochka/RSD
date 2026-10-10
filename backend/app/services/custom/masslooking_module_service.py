"""Masslooking module screen: picker, targets, launch presets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatTarget,
    CustomAutomation,
    PoolAccount,
    SocialAccount,
)
from .job_service import list_jobs
from .module_delays import DELAY_MAX_SECONDS, JOIN_DELAY_MAX_DEFAULT, JOIN_DELAY_MIN_DEFAULT, clamp_join_delay_pair
from .chat_folder_service import folder_payloads
from .masslooking_service import normalize_story_targets
from .account_roles import account_is_task_ready
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_LOOK_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "account_ids": [],
    "chat_ids": [],
    "folder_ids": [],
    "targets": [],
    "view_feed": True,
    "stories_limit": 0,
    "max_per_account": 50,
    "skip_seen": True,
    "skip_hours": 24,
    "delay_min": 2,
    "delay_max": 6,
    "join_delay_min": JOIN_DELAY_MIN_DEFAULT,
    "join_delay_max": JOIN_DELAY_MAX_DEFAULT,
    "max_per_hour": 30,
    "respect_night_hours": True,
    "limit_rate": True,
    "require_proxy": False,
    "hide_in_work": False,
    "blacklisted_account_ids": [],
    "presets": [],
}


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


def _clamp_int(raw: Any, default: int, *, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(raw)))
    except (TypeError, ValueError):
        return default


def normalize_look_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_LOOK_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["enabled"] = bool(incoming.get("enabled")) if incoming.get("enabled") is not None else data["enabled"]
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["folder_ids"] = _as_int_list(incoming.get("folder_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    data["targets"] = normalize_story_targets(incoming.get("targets"))
    data["view_feed"] = bool(incoming.get("view_feed", True))
    data["stories_limit"] = _clamp_int(incoming.get("stories_limit") if incoming.get("stories_limit") is not None else 0, 0, lo=0, hi=500)
    data["max_per_account"] = _clamp_int(incoming.get("max_per_account") if incoming.get("max_per_account") is not None else 50, 50, lo=0, hi=500)
    data["skip_seen"] = bool(incoming.get("skip_seen", True))
    data["skip_hours"] = _clamp_int(incoming.get("skip_hours") if incoming.get("skip_hours") is not None else 24, 24, lo=1, hi=168)
    data["delay_min"] = _clamp_int(incoming.get("delay_min") if incoming.get("delay_min") is not None else 2, 2, lo=0, hi=DELAY_MAX_SECONDS)
    data["delay_max"] = max(
        data["delay_min"],
        _clamp_int(incoming.get("delay_max") if incoming.get("delay_max") is not None else 6, 6, lo=0, hi=DELAY_MAX_SECONDS),
    )
    data["join_delay_min"], data["join_delay_max"] = clamp_join_delay_pair(incoming)
    data["max_per_hour"] = _clamp_int(incoming.get("max_per_hour") if incoming.get("max_per_hour") is not None else 30, 30, lo=0, hi=500)
    data["respect_night_hours"] = bool(incoming.get("respect_night_hours", True))
    data["limit_rate"] = bool(incoming.get("limit_rate", True))
    data["require_proxy"] = bool(incoming.get("require_proxy"))
    data["hide_in_work"] = bool(incoming.get("hide_in_work"))
    presets = []
    for item in incoming.get("presets") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        snapshot = dict(item.get("settings") or {})
        snapshot["presets"] = []
        presets.append({"name": name[:80], "settings": normalize_look_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    eligible = account_is_task_ready(pool, account, "looking", exclude_spamblocked=True)
    return {
        "id": account.id,
        "label": account.display_name or account.username or account.phone_number or f"#{account.id}",
        "username": account.username,
        "phone_number": account.phone_number,
        "warmup_status": pool.warmup_status or "idle",
        "proxy_label": proxy_label(getattr(account, "telegram_proxy", None)),
        "has_proxy": bool(account.telegram_proxy or pool.proxy_id),
        "is_active": bool(account.is_active),
        "is_banned": bool(account.is_banned),
        "is_frozen": bool(account.is_frozen),
        "is_spamblocked": bool(account.is_spamblocked),
        "in_work": in_work,
        "daily_messages_sent": current_daily_messages_sent(account),
        "eligible": eligible,
    }


def _chat_row(chat: ChatTarget) -> dict[str, Any]:
    return {
        "id": chat.id,
        "title": chat.title or chat.invite_link or f"#{chat.id}",
        "invite_link": chat.invite_link,
        "chat_type": chat.chat_type,
        "folder_id": chat.folder_id,
        "join_status": chat.join_status,
        "members_count": chat.members_count,
    }


async def _log_summary(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    rows = await session.execute(
        select(AutomationActionLog.result, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "masslooking",
        ).group_by(AutomationActionLog.result)
    )
    data = {str(result or ""): int(count) for result, count in rows.all()}
    success = data.get("success", 0)
    failed = data.get("error", 0)
    attempts = sum(data.values())
    recent = (
        await session.execute(
            select(AutomationActionLog)
            .where(
                AutomationActionLog.custom_automation_id == automation_id,
                AutomationActionLog.action_type == "masslooking",
            )
            .order_by(AutomationActionLog.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return {
        "attempts": attempts,
        "success": success,
        "failed": failed,
        "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
        "recent": [
            {
                "id": item.id,
                "target": item.target_id,
                "title": (item.payload or {}).get("title") or item.target_id,
                "stories": (item.payload or {}).get("stories") or 0,
                "source": (item.payload or {}).get("source") or "",
                "result": item.result,
                "created_at": item.created_at,
            }
            for item in recent
        ],
    }


def _issues(settings: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not settings.get("enabled"):
        issues.append("Модуль масслукинга выключен")
    if not settings.get("account_ids"):
        issues.append("Выберите хотя бы один аккаунт")
    if not settings.get("targets") and not settings.get("chat_ids") and not settings.get("folder_ids") and not settings.get("view_feed"):
        issues.append("Добавьте хотя бы один канал, папку или @username")
    return issues


async def get_masslooking_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_look_settings((automation.module_settings or {}).get("masslooking"))
    pairs = (
        await session.execute(
            select(SocialAccount, PoolAccount)
            .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(PoolAccount.custom_automation_id == automation_id)
            .order_by(SocialAccount.updated_at.desc())
            .limit(300)
        )
    ).all()
    chats = (
        await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation_id,
                ChatTarget.black_boxed_at.is_(None),
            ).order_by(ChatTarget.created_at.desc()).limit(400)
        )
    ).scalars().all()
    folders = await folder_payloads(session, automation_id)
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    look_jobs = [item for item in jobs["items"] if item.get("job_type") == "masslooking"][:12]
    return {
        "enabled": bool(settings.get("enabled")),
        "settings": settings,
        "accounts": [_account_row(account, pool) for account, pool in pairs],
        "chats": [_chat_row(chat) for chat in chats],
        "folders": folders,
        "jobs": look_jobs,
        "summary": await _log_summary(session, automation_id),
        "issues": _issues(settings),
    }


async def save_masslooking_module(
    session: AsyncSession,
    automation_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_look_settings(payload)
    if payload.get("enabled") is not None:
        settings["enabled"] = bool(payload.get("enabled"))
    blob = dict(automation.module_settings or {})
    blob["masslooking"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_masslooking_module(session, automation_id)


async def save_masslooking_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_look_settings((automation.module_settings or {}).get("masslooking"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["masslooking"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_masslooking_module(session, automation_id)
