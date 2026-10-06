"""Chat-broadcasts module screen: picker, chain, launch presets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatTarget,
    CustomAutomation,
    PoolAccount,
    SocialAccount,
)
from .chat_broadcast_service import ACTION, normalize_broadcast_messages
from .chat_addlist_service import import_chat_links
from .chat_folder_service import folder_payloads
from .chat_membership_service import blackbox_unusable_chat
from .chat_scope import is_group_chat
from .job_service import list_jobs
from .account_roles import account_is_task_ready
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_BC_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "account_ids": [],
    "chat_ids": [],
    "folder_ids": [],
    "only_joined": True,
    "messages": [],
    "first_mode": "template",
    "skip_errors": True,
    "skip_sent": False,
    "limit_rate": True,
    "respect_night_hours": True,
    "imitate_typing": True,
    "warmup_slow": True,
    "work_mode": "count",
    "max_messages": 100,
    "delay_group_min": 30,
    "delay_group_max": 90,
    "delay_msg_min": 3,
    "delay_msg_max": 8,
    "errors_until_stop": 10,
    "weekdays": [],
    "work_hour_start": None,
    "work_hour_end": None,
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


def _optional_hour(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return max(0, min(23, int(raw)))
    except (TypeError, ValueError):
        return None


def normalize_bc_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_BC_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["enabled"] = bool(incoming.get("enabled")) if incoming.get("enabled") is not None else data["enabled"]
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["folder_ids"] = _as_int_list(incoming.get("folder_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    data["only_joined"] = bool(incoming.get("only_joined", True))
    data["messages"] = normalize_broadcast_messages(incoming.get("messages"))
    mode = str(incoming.get("first_mode") or "template").strip().lower()
    data["first_mode"] = mode if mode in {"template", "ai"} else "template"
    data["skip_errors"] = bool(incoming.get("skip_errors", True))
    data["skip_sent"] = bool(incoming.get("skip_sent"))
    data["limit_rate"] = bool(incoming.get("limit_rate", True))
    data["respect_night_hours"] = bool(incoming.get("respect_night_hours", True))
    data["imitate_typing"] = bool(incoming.get("imitate_typing", True))
    data["warmup_slow"] = bool(incoming.get("warmup_slow", True))
    work_mode = str(incoming.get("work_mode") or "count").strip().lower()
    data["work_mode"] = work_mode if work_mode in {"count", "time"} else "count"
    data["max_messages"] = _clamp_int(incoming.get("max_messages") or 100, 100, lo=1, hi=500)
    data["delay_group_min"] = _clamp_int(incoming.get("delay_group_min") if incoming.get("delay_group_min") is not None else 30, 30, lo=0, hi=3600)
    data["delay_group_max"] = max(data["delay_group_min"], _clamp_int(incoming.get("delay_group_max") if incoming.get("delay_group_max") is not None else 90, 90, lo=0, hi=3600))
    data["delay_msg_min"] = _clamp_int(incoming.get("delay_msg_min") if incoming.get("delay_msg_min") is not None else 3, 3, lo=0, hi=600)
    data["delay_msg_max"] = max(data["delay_msg_min"], _clamp_int(incoming.get("delay_msg_max") if incoming.get("delay_msg_max") is not None else 8, 8, lo=0, hi=600))
    data["errors_until_stop"] = _clamp_int(incoming.get("errors_until_stop") or 10, 10, lo=1, hi=50)
    days: list[int] = []
    for item in incoming.get("weekdays") or []:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6 and day not in days:
            days.append(day)
    data["weekdays"] = days
    data["work_hour_start"] = _optional_hour(incoming.get("work_hour_start"))
    data["work_hour_end"] = _optional_hour(incoming.get("work_hour_end"))
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
        presets.append({"name": name[:80], "settings": normalize_bc_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    eligible = account_is_task_ready(pool, account, "discussion", exclude_spamblocked=True)
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


def _chat_row(chat: ChatTarget) -> dict[str, Any]:
    return {
        "id": chat.id,
        "title": chat.title or chat.invite_link or f"#{chat.id}",
        "invite_link": chat.invite_link,
        "chat_type": chat.chat_type,
        "is_group": is_group_chat(chat),
        "join_status": chat.join_status,
        "folder_id": chat.folder_id,
        "black_boxed": bool(chat.black_boxed_at),
        "members_count": chat.members_count,
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
    delivered_ids = (
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
        "delivered_ids": [int(item) for item in delivered_ids if str(item).isdigit()],
        "failed_ids": [int(item) for item in failed_ids if str(item).isdigit()],
    }


def _issues(settings: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not settings.get("enabled"):
        issues.append("Модуль чат-рассылки выключен")
    if not settings.get("account_ids"):
        issues.append("Выберите хотя бы один аккаунт")
    if not settings.get("chat_ids") and not settings.get("folder_ids") and not settings.get("only_joined"):
        issues.append("Добавьте хотя бы одну группу")
    if settings.get("first_mode") != "ai" and not settings.get("messages"):
        issues.append("Добавьте хотя бы одно сообщение в цепочку")
    return issues


async def get_chat_broadcast_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_bc_settings((automation.module_settings or {}).get("chat_broadcasts"))
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
            select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id).order_by(ChatTarget.created_at.desc()).limit(400)
        )
    ).scalars().all()
    folders = await folder_payloads(session, automation_id)
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    bc_jobs = [item for item in jobs["items"] if item.get("job_type") == ACTION][:12]
    visible = [_chat_row(chat) for chat in chats if not chat.black_boxed_at]
    black = [chat for chat in chats if chat.black_boxed_at]
    return {
        "enabled": bool(settings.get("enabled")),
        "settings": settings,
        "accounts": [_account_row(account, pool) for account, pool in pairs],
        "chats": visible,
        "folders": folders,
        "jobs": bc_jobs,
        "summary": await _log_summary(session, automation_id),
        "blacklist": [
            {
                "id": chat.id,
                "title": chat.title or chat.invite_link or f"#{chat.id}",
                "reason": chat.last_join_error,
                "black_boxed_at": chat.black_boxed_at,
            }
            for chat in black
        ],
        "issues": _issues(settings),
    }


async def save_chat_broadcast_module(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_bc_settings(payload)
    if payload.get("enabled") is not None:
        settings["enabled"] = bool(payload.get("enabled"))
    blob = dict(automation.module_settings or {})
    blob["chat_broadcasts"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_chat_broadcast_module(session, automation_id)


async def add_chat_broadcast_groups(session: AsyncSession, automation_id: int, raw_links: str) -> dict[str, Any]:
    added, errors = await import_chat_links(session, automation_id, raw_links, mode="monitoring")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_bc_settings((automation.module_settings or {}).get("chat_broadcasts") if automation else {})
    settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *added]))
    if automation:
        blob = dict(automation.module_settings or {})
        blob["chat_broadcasts"] = settings
        automation.module_settings = blob
        await session.commit()
    data = await get_chat_broadcast_module(session, automation_id)
    data["added_ids"] = added
    data["add_errors"] = errors
    return data


async def save_chat_broadcast_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_bc_settings((automation.module_settings or {}).get("chat_broadcasts"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["chat_broadcasts"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_chat_broadcast_module(session, automation_id)


async def blackbox_chat_broadcast_chat(session: AsyncSession, automation_id: int, *, chat_id: int | None = None, query: str | None = None) -> dict[str, Any]:
    stmt = select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
    if chat_id:
        stmt = stmt.where(ChatTarget.id == chat_id)
    elif query and query.strip():
        needle = f"%{query.strip()}%"
        stmt = stmt.where(or_(ChatTarget.title.ilike(needle), ChatTarget.invite_link.ilike(needle)))
    else:
        raise ValueError("Укажите группу")
    chat = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if not chat:
        raise ValueError("Группа не найдена")
    await blackbox_unusable_chat(session, chat, reason="manual")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_bc_settings((automation.module_settings or {}).get("chat_broadcasts") if automation else {})
    settings["chat_ids"] = [item for item in settings["chat_ids"] if item != chat.id]
    if automation:
        blob = dict(automation.module_settings or {})
        blob["chat_broadcasts"] = settings
        automation.module_settings = blob
    await session.commit()
    return await get_chat_broadcast_module(session, automation_id)
