"""Masspriming module screen: accounts, @username targets, TTL toggle."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AutomationActionLog, CustomAutomation, PoolAccount, SocialAccount
from .job_service import list_jobs
from .module_delays import DELAY_MAX_SECONDS
from .masspriming_service import TTL_DAY, normalize_prime_targets, normalize_ttl_period
from .account_roles import account_is_task_ready
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_PRIME_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "account_ids": [],
    "targets": [],
    "user_folder_ids": [],
    "add_contact": True,
    "ttl_mode": "toggle",
    "ttl_period": TTL_DAY,
    "skip_seen": True,
    "skip_hours": 72,
    "max_per_account": 20,
    "max_per_hour": 8,
    "delay_min": 8,
    "delay_max": 25,
    "respect_night_hours": True,
    "limit_rate": True,
    "skip_quarantine": True,
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


def normalize_prime_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_PRIME_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["enabled"] = bool(incoming.get("enabled")) if incoming.get("enabled") is not None else data["enabled"]
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    data["user_folder_ids"] = _as_int_list(incoming.get("user_folder_ids"))
    data["targets"] = normalize_prime_targets(incoming.get("targets"))
    data["add_contact"] = bool(incoming.get("add_contact", True))
    mode = str(incoming.get("ttl_mode") or "toggle").strip().lower()
    data["ttl_mode"] = mode if mode in {"toggle", "enable", "disable"} else "toggle"
    data["ttl_period"] = normalize_ttl_period(incoming.get("ttl_period") if incoming.get("ttl_period") is not None else TTL_DAY)
    data["skip_seen"] = bool(incoming.get("skip_seen", True))
    data["skip_hours"] = _clamp_int(incoming.get("skip_hours") if incoming.get("skip_hours") is not None else 72, 72, lo=1, hi=168)
    data["max_per_account"] = _clamp_int(incoming.get("max_per_account") if incoming.get("max_per_account") is not None else 20, 20, lo=0, hi=200)
    data["max_per_hour"] = _clamp_int(incoming.get("max_per_hour") if incoming.get("max_per_hour") is not None else 8, 8, lo=0, hi=80)
    data["delay_min"] = _clamp_int(incoming.get("delay_min") if incoming.get("delay_min") is not None else 8, 8, lo=0, hi=DELAY_MAX_SECONDS)
    data["delay_max"] = max(
        data["delay_min"],
        _clamp_int(incoming.get("delay_max") if incoming.get("delay_max") is not None else 25, 25, lo=0, hi=DELAY_MAX_SECONDS),
    )
    data["respect_night_hours"] = bool(incoming.get("respect_night_hours", True))
    data["limit_rate"] = bool(incoming.get("limit_rate", True))
    data["skip_quarantine"] = bool(incoming.get("skip_quarantine", True))
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
        presets.append({"name": name[:80], "settings": normalize_prime_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    eligible = account_is_task_ready(pool, account, "commenting", exclude_spamblocked=True)
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
        "in_work": in_work,
        "daily_messages_sent": current_daily_messages_sent(account),
        "eligible": eligible,
    }


async def _log_summary(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    rows = await session.execute(
        select(AutomationActionLog.result, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "masspriming",
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
                AutomationActionLog.action_type == "masspriming",
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
                "ttl_mode": (item.payload or {}).get("ttl_mode"),
                "contact": (item.payload or {}).get("contact"),
                "result": item.result,
                "created_at": item.created_at,
            }
            for item in recent
        ],
    }


def _issues(settings: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not settings.get("enabled"):
        issues.append("Модуль масспрайминга выключен")
    if not settings.get("account_ids"):
        issues.append("Выберите хотя бы один аккаунт")
    if not settings.get("targets") and not settings.get("user_folder_ids"):
        issues.append("Добавьте хотя бы один @username")
    return issues


async def get_masspriming_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_prime_settings((automation.module_settings or {}).get("masspriming"))
    pairs = (
        await session.execute(
            select(SocialAccount, PoolAccount)
            .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(PoolAccount.custom_automation_id == automation_id)
            .order_by(SocialAccount.updated_at.desc())
            .limit(300)
        )
    ).all()
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    prime_jobs = [item for item in jobs["items"] if item.get("job_type") == "masspriming"][:12]
    from .user_folder_service import list_user_folders
    return {
        "enabled": bool(settings.get("enabled")),
        "settings": settings,
        "accounts": [_account_row(account, pool) for account, pool in pairs],
        "jobs": prime_jobs,
        "user_folders": await list_user_folders(session, automation_id),
        "summary": await _log_summary(session, automation_id),
        "issues": _issues(settings),
    }


async def save_masspriming_module(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_prime_settings(payload)
    if payload.get("enabled") is not None:
        settings["enabled"] = bool(payload.get("enabled"))
    blob = dict(automation.module_settings or {})
    blob["masspriming"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_masspriming_module(session, automation_id)


async def save_masspriming_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_prime_settings((automation.module_settings or {}).get("masspriming"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["masspriming"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_masspriming_module(session, automation_id)
