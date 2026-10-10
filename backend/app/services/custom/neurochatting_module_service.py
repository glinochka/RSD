"""Neurochatting module screen: picker, settings, launch presets for group discussion."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatTarget,
    CustomAutomation,
    CustomPrompt,
    PoolAccount,
    PromptType,
    SocialAccount,
)
from .chat_addlist_service import import_chat_links
from .chat_folder_service import folder_payloads
from .chat_membership_service import blackbox_unusable_chat
from .chat_scope import is_group_chat
from .discussion_service import DEFAULT_DISCUSSION_PROMPT
from .job_service import list_jobs
from .module_delays import DELAY_MAX_SECONDS, JOIN_DELAY_MAX_DEFAULT, JOIN_DELAY_MIN_DEFAULT, clamp_join_delay_pair
from .lead_keywords import normalize_lead_keywords
from .prompt_service import activate_prompt, create_named_prompt, list_prompts
from .account_roles import account_is_task_ready
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_CHAT_SETTINGS: dict[str, Any] = {
    "account_ids": [],
    "chat_ids": [],
    "folder_ids": [],
    "reply_mode": "interval",
    "keywords": [],
    "reply_condition": "",
    "probability": 30,
    "work_mode": "count",
    "work_always": False,
    "max_per_chat": 1,
    "max_replies_per_run": 1,
    "only_joined": False,
    "respect_night_hours": True,
    "delay_before_min": 42,
    "delay_before_max": 78,
    "join_delay_min": JOIN_DELAY_MIN_DEFAULT,
    "join_delay_max": JOIN_DELAY_MAX_DEFAULT,
    "prompt_id": None,
    "require_proxy": False,
    "hide_in_work": False,
    "context_depth": 5,
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


def normalize_chat_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_CHAT_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["folder_ids"] = _as_int_list(incoming.get("folder_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    reply_mode = str(incoming.get("reply_mode") or "interval").strip().lower()
    data["reply_mode"] = reply_mode if reply_mode in {"interval", "triggers"} else "interval"
    data["keywords"] = normalize_lead_keywords(incoming.get("keywords"))
    data["reply_condition"] = str(incoming.get("reply_condition") or "").strip()[:500]
    data["probability"] = _clamp_int(
        incoming.get("probability") if incoming.get("probability") is not None else 30,
        30,
        lo=0,
        hi=100,
    )
    work_mode = str(incoming.get("work_mode") or "count").strip().lower()
    data["work_mode"] = work_mode if work_mode in {"count", "time"} else "count"
    data["work_always"] = bool(incoming.get("work_always"))
    data["max_per_chat"] = _clamp_int(incoming.get("max_per_chat") or 1, 1, lo=1, hi=20)
    data["max_replies_per_run"] = _clamp_int(incoming.get("max_replies_per_run") or 1, 1, lo=1, hi=10)
    data["only_joined"] = bool(incoming.get("only_joined"))
    data["respect_night_hours"] = bool(incoming.get("respect_night_hours", True))
    data["delay_before_min"] = _clamp_int(incoming.get("delay_before_min") if incoming.get("delay_before_min") is not None else 42, 42, lo=0, hi=DELAY_MAX_SECONDS)
    data["delay_before_max"] = max(
        data["delay_before_min"],
        _clamp_int(incoming.get("delay_before_max") if incoming.get("delay_before_max") is not None else 78, 78, lo=0, hi=DELAY_MAX_SECONDS),
    )
    data["join_delay_min"], data["join_delay_max"] = clamp_join_delay_pair(incoming)
    try:
        prompt_id = incoming.get("prompt_id")
        data["prompt_id"] = int(prompt_id) if prompt_id else None
    except (TypeError, ValueError):
        data["prompt_id"] = None
    data["require_proxy"] = bool(incoming.get("require_proxy"))
    data["hide_in_work"] = bool(incoming.get("hide_in_work"))
    data["context_depth"] = _clamp_int(
        incoming.get("context_depth") if incoming.get("context_depth") is not None else 5,
        5,
        lo=0,
        hi=20,
    )
    presets = []
    for item in incoming.get("presets") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        snapshot = dict(item.get("settings") or {})
        snapshot["presets"] = []
        presets.append({"name": name[:80], "settings": normalize_chat_settings(snapshot)})
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
        "warmup_status": pool.warmup_status or "idle",
        "proxy_label": proxy_label(getattr(account, "telegram_proxy", None)),
        "has_proxy": bool(account.telegram_proxy or pool.proxy_id),
        "is_active": bool(account.is_active),
        "is_banned": bool(account.is_banned),
        "is_frozen": bool(account.is_frozen),
        "is_spamblocked": bool(account.is_spamblocked),
        "is_channel_banned": bool(account.is_channel_banned),
        "in_work": in_work,
        "daily_messages_sent": current_daily_messages_sent(account),
        "eligible": eligible,
    }


def _chat_row(chat: ChatTarget) -> dict[str, Any]:
    return {
        "id": chat.id,
        "title": chat.title or chat.invite_link or f"#{chat.id}",
        "invite_link": chat.invite_link,
        "mode": chat.mode,
        "join_status": chat.join_status,
        "chat_type": chat.chat_type,
        "is_group": is_group_chat(chat),
        "folder_id": chat.folder_id,
        "black_boxed": bool(chat.black_boxed_at),
        "members_count": chat.members_count,
    }


async def _log_summary(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    rows = await session.execute(
        select(AutomationActionLog.result, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "discussion",
        ).group_by(AutomationActionLog.result)
    )
    data = {str(result or ""): int(count) for result, count in rows.all()}
    success = data.get("success", 0)
    failed = data.get("error", 0)
    attempts = sum(data.values())
    return {
        "attempts": attempts,
        "success": success,
        "failed": failed,
        "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
    }


def _issues(settings: dict[str, Any], *, enabled: bool, chats: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if not enabled:
        issues.append("Модуль нейрочаттинга выключен")
    if not settings.get("account_ids"):
        issues.append("Аккаунты не выбраны")
    if not settings.get("chat_ids") and not settings.get("folder_ids"):
        issues.append("Группы не указаны")
    if settings.get("reply_mode") == "triggers" and not settings.get("keywords"):
        issues.append("Не заданы триггеры")
    selected = {item["id"] for item in chats if item["id"] in set(settings.get("chat_ids") or [])}
    if selected and not any(item["id"] in selected and item.get("is_group") for item in chats):
        issues.append("Нейрочаттинг отвечает только в группах — среди выбранных нет чатов")
    folder_ids = set(settings.get("folder_ids") or [])
    if folder_ids:
        in_folders = [item for item in chats if item.get("folder_id") in folder_ids]
        if in_folders and not any(item.get("is_group") for item in in_folders):
            issues.append("Нейрочаттинг отвечает только в группах — в выбранных папках нет чатов")
    return issues


async def get_neurochatting_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_chat_settings((automation.module_settings or {}).get("neurochatting"))
    await list_prompts(session, automation_id)
    prompts = (
        await session.execute(
            select(CustomPrompt).where(
                CustomPrompt.custom_automation_id == automation_id,
                CustomPrompt.prompt_type == PromptType.DISCUSSION_REPLY.value,
            ).order_by(CustomPrompt.is_active.desc(), CustomPrompt.created_at.desc())
        )
    ).scalars().all()
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
    visible = [_chat_row(chat) for chat in chats if not chat.black_boxed_at]
    black = [chat for chat in chats if chat.black_boxed_at]
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    chat_jobs = [item for item in jobs["items"] if item.get("job_type") == "discussion"][:12]
    accounts = [_account_row(account, pool) for account, pool in pairs]
    return {
        "enabled": bool(automation.is_digital_footprint_enabled),
        "settings": settings,
        "accounts": accounts,
        "chats": visible,
        "folders": folders,
        "prompts": [
            {
                "id": prompt.id,
                "name": prompt.name,
                "content": prompt.content,
                "is_active": prompt.is_active,
                "is_system": prompt.name in {"Discussion Reply", "Discussion reply", "Искусственная активность в чатах"},
            }
            for prompt in prompts
        ],
        "jobs": chat_jobs,
        "summary": await _log_summary(session, automation_id),
        "blacklist": [
            {
                "id": chat.id,
                "title": chat.title or chat.invite_link or f"#{chat.id}",
                "reason": chat.last_join_error or chat.comments_check_error,
                "black_boxed_at": chat.black_boxed_at,
            }
            for chat in black
        ],
        "issues": _issues(settings, enabled=bool(automation.is_digital_footprint_enabled), chats=visible),
    }


async def save_neurochatting_module(
    session: AsyncSession,
    automation_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_chat_settings(payload)
    if payload.get("enabled") is not None:
        automation.is_digital_footprint_enabled = bool(payload.get("enabled"))
    if settings["prompt_id"]:
        try:
            await activate_prompt(session, automation_id, settings["prompt_id"])
        except ValueError:
            settings["prompt_id"] = None
    blob = dict(automation.module_settings or {})
    blob["neurochatting"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    if settings["chat_ids"]:
        chats = (
            await session.execute(
                select(ChatTarget).where(
                    ChatTarget.custom_automation_id == automation_id,
                    ChatTarget.id.in_(settings["chat_ids"]),
                )
            )
        ).scalars().all()
        for chat in chats:
            if chat.mode == "inactive":
                continue
            chat.mode = "discussion"
            chat.is_active = True
            config = dict(chat.discussion_config or {})
            config["reply_probability"] = settings["probability"] / 100.0
            chat.discussion_config = config
            chat.updated_at = _utc_now()
    await session.commit()
    return await get_neurochatting_module(session, automation_id)


async def add_neurochatting_groups(session: AsyncSession, automation_id: int, raw_links: str) -> dict[str, Any]:
    added, errors = await import_chat_links(session, automation_id, raw_links, mode="discussion")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_chat_settings((automation.module_settings or {}).get("neurochatting") if automation else {})
    settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *added]))
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neurochatting"] = settings
        automation.module_settings = blob
        await session.commit()
    data = await get_neurochatting_module(session, automation_id)
    data["added_ids"] = added
    data["add_errors"] = errors
    return data


async def save_neurochatting_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_chat_settings((automation.module_settings or {}).get("neurochatting"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["neurochatting"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_neurochatting_module(session, automation_id)


async def create_neurochatting_prompt(session: AsyncSession, automation_id: int, name: str, content: str) -> dict[str, Any]:
    prompt = await create_named_prompt(
        session,
        automation_id,
        prompt_type=PromptType.DISCUSSION_REPLY.value,
        name=name,
        content=content or DEFAULT_DISCUSSION_PROMPT,
        activate=True,
    )
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_chat_settings((automation.module_settings or {}).get("neurochatting") if automation else {})
    settings["prompt_id"] = prompt.id
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neurochatting"] = settings
        automation.module_settings = blob
        await session.commit()
    return await get_neurochatting_module(session, automation_id)


async def blackbox_neurochatting_chat(session: AsyncSession, automation_id: int, *, chat_id: int | None = None, query: str | None = None) -> dict[str, Any]:
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
    settings = normalize_chat_settings((automation.module_settings or {}).get("neurochatting") if automation else {})
    settings["chat_ids"] = [item for item in settings["chat_ids"] if item != chat.id]
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neurochatting"] = settings
        automation.module_settings = blob
    await session.commit()
    return await get_neurochatting_module(session, automation_id)
