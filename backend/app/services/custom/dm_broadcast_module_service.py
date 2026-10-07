"""DM broadcasts module screen: picker, chain, recipients."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    CustomAutomation,
    PoolAccount,
    SocialAccount,
)
from .account_roles import account_is_task_ready
from .module_delays import DELAY_MAX_SECONDS
from .chat_broadcast_service import normalize_broadcast_messages
from .job_service import list_jobs
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

ACTION = "dm_broadcast"

DEFAULT_DM_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "account_ids": [],
    "recipients": [],
    "user_folder_ids": [],
    "messages": [],
    "first_mode": "template",
    "skip_errors": True,
    "skip_sent": False,
    "limit_rate": True,
    "respect_night_hours": True,
    "work_mode": "count",
    "max_messages": 100,
    "delay_peer_min": 30,
    "delay_peer_max": 90,
    "delay_msg_min": 3,
    "delay_msg_max": 8,
    "errors_until_stop": 10,
    "end_at": "",
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


def normalize_dm_recipients(raw: Any) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    chunks: list[str] = []
    if isinstance(raw, str):
        chunks = [raw]
    elif isinstance(raw, list):
        chunks = [str(item) for item in raw]
    for chunk in chunks:
        for line in chunk.replace(",", " ").splitlines():
            for part in line.split():
                token = part.strip()
                if not token:
                    continue
                key = token.lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append(token[:128])
                if len(items) >= 2000:
                    return items
    return items


def normalize_dm_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_DM_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["enabled"] = bool(incoming.get("enabled")) if incoming.get("enabled") is not None else data["enabled"]
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    data["user_folder_ids"] = _as_int_list(incoming.get("user_folder_ids"))
    data["recipients"] = normalize_dm_recipients(incoming.get("recipients"))
    data["messages"] = normalize_broadcast_messages(incoming.get("messages"))
    mode = str(incoming.get("first_mode") or "template").strip().lower()
    data["first_mode"] = mode if mode in {"template", "ai"} else "template"
    data["skip_errors"] = bool(incoming.get("skip_errors", True))
    data["skip_sent"] = bool(incoming.get("skip_sent"))
    data["limit_rate"] = bool(incoming.get("limit_rate", True))
    data["respect_night_hours"] = bool(incoming.get("respect_night_hours", True))
    work_mode = str(incoming.get("work_mode") or "count").strip().lower()
    data["work_mode"] = work_mode if work_mode in {"count", "time"} else "count"
    data["max_messages"] = _clamp_int(incoming.get("max_messages") or 100, 100, lo=1, hi=500)
    data["delay_peer_min"] = _clamp_int(
        incoming.get("delay_peer_min") if incoming.get("delay_peer_min") is not None else 30, 30, lo=0, hi=DELAY_MAX_SECONDS
    )
    data["delay_peer_max"] = max(
        data["delay_peer_min"],
        _clamp_int(incoming.get("delay_peer_max") if incoming.get("delay_peer_max") is not None else 90, 90, lo=0, hi=DELAY_MAX_SECONDS),
    )
    data["delay_msg_min"] = _clamp_int(
        incoming.get("delay_msg_min") if incoming.get("delay_msg_min") is not None else 3, 3, lo=0, hi=DELAY_MAX_SECONDS
    )
    data["delay_msg_max"] = max(
        data["delay_msg_min"],
        _clamp_int(incoming.get("delay_msg_max") if incoming.get("delay_msg_max") is not None else 8, 8, lo=0, hi=DELAY_MAX_SECONDS),
    )
    data["errors_until_stop"] = _clamp_int(incoming.get("errors_until_stop") or 10, 10, lo=1, hi=50)
    data["end_at"] = str(incoming.get("end_at") or "").strip()[:32]
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
        presets.append({"name": name[:80], "settings": normalize_dm_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    eligible = account_is_task_ready(pool, account, "dm", exclude_spamblocked=True)
    return {
        "id": account.id,
        "label": account.display_name or account.username or account.phone_number or f"#{account.id}",
        "username": account.username,
        "phone_number": account.phone_number,
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
            AutomationActionLog.action_type == ACTION,
        ).group_by(AutomationActionLog.result)
    )
    data = {str(result or ""): int(count) for result, count in rows.all()}
    success = data.get("success", 0)
    failed = data.get("error", 0)
    attempts = sum(data.values())
    delivered = (
        await session.execute(
            select(AutomationActionLog.target_id).where(
                AutomationActionLog.custom_automation_id == automation_id,
                AutomationActionLog.action_type == ACTION,
                AutomationActionLog.result == "success",
            ).distinct()
        )
    ).scalars().all()
    failed_ids = (
        await session.execute(
            select(AutomationActionLog.target_id).where(
                AutomationActionLog.custom_automation_id == automation_id,
                AutomationActionLog.action_type == ACTION,
                AutomationActionLog.result == "error",
            ).distinct()
        )
    ).scalars().all()
    return {
        "attempts": attempts,
        "success": success,
        "failed": failed,
        "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
        "delivered_ids": [str(item) for item in delivered if item],
        "failed_ids": [str(item) for item in failed_ids if item],
    }


def _issues(settings: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not settings.get("enabled"):
        issues.append("Модуль ЛС-рассылки выключен")
    if not settings.get("account_ids"):
        issues.append("Выберите хотя бы один аккаунт")
    if not settings.get("recipients") and not settings.get("user_folder_ids"):
        issues.append("Добавьте хотя бы одного получателя")
    if settings.get("first_mode") != "ai" and not settings.get("messages"):
        issues.append("Добавьте хотя бы одно сообщение в цепочку")
    return issues


async def get_dm_broadcast_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_dm_settings((automation.module_settings or {}).get("dm_broadcasts"))
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
    dm_jobs = [item for item in jobs["items"] if item.get("job_type") == ACTION][:12]
    from .user_folder_service import list_user_folders
    return {
        "enabled": bool(settings.get("enabled")),
        "settings": settings,
        "accounts": [_account_row(account, pool) for account, pool in pairs],
        "jobs": dm_jobs,
        "user_folders": await list_user_folders(session, automation_id),
        "summary": await _log_summary(session, automation_id),
        "issues": _issues(settings),
        "added_ids": [],
        "add_errors": [],
    }


async def save_dm_broadcast_module(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_dm_settings(payload)
    if payload.get("enabled") is not None:
        settings["enabled"] = bool(payload.get("enabled"))
    blob = dict(automation.module_settings or {})
    blob["dm_broadcasts"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_dm_broadcast_module(session, automation_id)


async def add_dm_broadcast_recipients(session: AsyncSession, automation_id: int, raw: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_dm_settings((automation.module_settings or {}).get("dm_broadcasts"))
    extra = normalize_dm_recipients(raw)
    settings["recipients"] = list(dict.fromkeys([*settings["recipients"], *extra]))
    blob = dict(automation.module_settings or {})
    blob["dm_broadcasts"] = settings
    automation.module_settings = blob
    await session.commit()
    data = await get_dm_broadcast_module(session, automation_id)
    data["added_ids"] = extra
    return data


async def save_dm_broadcast_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_dm_settings((automation.module_settings or {}).get("dm_broadcasts"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["dm_broadcasts"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_dm_broadcast_module(session, automation_id)
