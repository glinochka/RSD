"""Neurocommenting module screen: picker, settings, launch presets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatTarget,
    CustomAutomation,
    CustomJob,
    CustomPrompt,
    PoolAccount,
    PromptType,
    SocialAccount,
)
from .account_roles import account_is_task_ready
from .chat_addlist_service import import_chat_links
from .chat_folder_service import folder_payloads
from .chat_membership_service import blackbox_unusable_chat
from .job_service import list_jobs
from .lead_keywords import normalize_lead_keywords
from .neurocommenting_service import (
    DEFAULT_NEUROCOMMENTING_PROMPT,
    POST_COMMENT_DELAY_MAX_SECONDS,
    POST_COMMENT_DELAY_MIN_SECONDS,
)
from .prompt_service import activate_prompt, create_named_prompt, list_prompts
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_NC_SETTINGS: dict[str, Any] = {
    "account_ids": [],
    "chat_ids": [],
    "folder_ids": [],
    "post_filter": "new",
    "keywords": [],
    "probability": 100,
    "min_words": 0,
    "max_per_account": None,
    "max_per_chat": 10,
    "delay_before_min": POST_COMMENT_DELAY_MIN_SECONDS,
    "delay_before_max": POST_COMMENT_DELAY_MAX_SECONDS,
    "respect_night_hours": True,
    "prompt_id": None,
    "require_proxy": False,
    "hide_in_work": False,
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


def normalize_nc_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_NC_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["folder_ids"] = _as_int_list(incoming.get("folder_ids"))
    post_filter = str(incoming.get("post_filter") or "new").strip().lower()
    data["post_filter"] = post_filter if post_filter in {"new", "keywords"} else "new"
    data["keywords"] = normalize_lead_keywords(incoming.get("keywords"))
    try:
        data["probability"] = max(0, min(100, int(incoming.get("probability") if incoming.get("probability") is not None else 100)))
    except (TypeError, ValueError):
        data["probability"] = 100
    try:
        data["min_words"] = max(0, min(2000, int(incoming.get("min_words") or 0)))
    except (TypeError, ValueError):
        data["min_words"] = 0
    try:
        max_account = incoming.get("max_per_account")
        data["max_per_account"] = max(1, min(200, int(max_account))) if max_account not in (None, "") else None
    except (TypeError, ValueError):
        data["max_per_account"] = None
    try:
        data["max_per_chat"] = max(1, min(50, int(incoming.get("max_per_chat") or 10)))
    except (TypeError, ValueError):
        data["max_per_chat"] = 10
    try:
        data["delay_before_min"] = max(0, min(3600, int(incoming.get("delay_before_min") or POST_COMMENT_DELAY_MIN_SECONDS)))
    except (TypeError, ValueError):
        data["delay_before_min"] = POST_COMMENT_DELAY_MIN_SECONDS
    try:
        data["delay_before_max"] = max(data["delay_before_min"], min(3600, int(incoming.get("delay_before_max") or POST_COMMENT_DELAY_MAX_SECONDS)))
    except (TypeError, ValueError):
        data["delay_before_max"] = max(data["delay_before_min"], POST_COMMENT_DELAY_MAX_SECONDS)
    data["respect_night_hours"] = bool(incoming.get("respect_night_hours", True))
    try:
        prompt_id = incoming.get("prompt_id")
        data["prompt_id"] = int(prompt_id) if prompt_id else None
    except (TypeError, ValueError):
        data["prompt_id"] = None
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
        presets.append({"name": name[:80], "settings": normalize_nc_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
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
        "eligible": account_is_task_ready(pool, account, "commenting"),
    }


def _chat_row(chat: ChatTarget) -> dict[str, Any]:
    return {
        "id": chat.id,
        "title": chat.title or chat.invite_link or f"#{chat.id}",
        "invite_link": chat.invite_link,
        "mode": chat.mode,
        "join_status": chat.join_status,
        "comments_open": chat.comments_open,
        "folder_id": chat.folder_id,
        "black_boxed": bool(chat.black_boxed_at),
        "members_count": chat.members_count,
    }


async def _log_summary(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    rows = await session.execute(
        select(AutomationActionLog.result, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "neurocommenting",
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


def _issues(settings: dict[str, Any], *, enabled: bool) -> list[str]:
    issues: list[str] = []
    if not enabled:
        issues.append("Модуль нейрокомментинга выключен")
    if not settings.get("account_ids"):
        issues.append("Аккаунты не выбраны")
    if not settings.get("chat_ids") and not settings.get("folder_ids"):
        issues.append("Каналы не указаны")
    if settings.get("post_filter") == "keywords" and not settings.get("keywords"):
        issues.append("Не заданы ключевые слова")
    return issues


async def get_neurocommenting_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_nc_settings((automation.module_settings or {}).get("neurocommenting"))
    await list_prompts(session, automation_id)
    prompts = (
        await session.execute(
            select(CustomPrompt).where(
                CustomPrompt.custom_automation_id == automation_id,
                CustomPrompt.prompt_type == PromptType.NEUROCOMMENTING.value,
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
    black = [chat for chat in chats if chat.black_boxed_at]
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    nc_jobs = [item for item in jobs["items"] if item.get("job_type") == "neurocommenting"][:12]
    return {
        "enabled": bool(automation.is_neurocommenting_enabled),
        "settings": settings,
        "accounts": [_account_row(account, pool) for account, pool in pairs],
        "chats": [_chat_row(chat) for chat in chats if not chat.black_boxed_at],
        "folders": folders,
        "prompts": [
            {
                "id": prompt.id,
                "name": prompt.name,
                "content": prompt.content,
                "is_active": prompt.is_active,
                "is_system": prompt.name == "Neurocommenting",
            }
            for prompt in prompts
        ],
        "jobs": nc_jobs,
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
        "issues": _issues(settings, enabled=bool(automation.is_neurocommenting_enabled)),
    }


async def save_neurocommenting_module(
    session: AsyncSession,
    automation_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_nc_settings(payload)
    if payload.get("enabled") is not None:
        automation.is_neurocommenting_enabled = bool(payload.get("enabled"))
    if settings["prompt_id"]:
        try:
            await activate_prompt(session, automation_id, settings["prompt_id"])
        except ValueError:
            settings["prompt_id"] = None
    blob = dict(automation.module_settings or {})
    blob["neurocommenting"] = settings
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
            chat.mode = "neurocommenting"
            chat.is_active = True
            config = dict(chat.neurocommenting_config or {})
            config["max_per_day"] = settings["max_per_chat"]
            chat.neurocommenting_config = config
            chat.updated_at = _utc_now()
    await session.commit()
    return await get_neurocommenting_module(session, automation_id)


async def add_neurocommenting_channels(session: AsyncSession, automation_id: int, raw_links: str) -> dict[str, Any]:
    added, errors = await import_chat_links(session, automation_id, raw_links, mode="neurocommenting")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_nc_settings((automation.module_settings or {}).get("neurocommenting") if automation else {})
    settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *added]))
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neurocommenting"] = settings
        automation.module_settings = blob
        await session.commit()
    data = await get_neurocommenting_module(session, automation_id)
    data["added_ids"] = added
    data["add_errors"] = errors
    return data


async def save_neurocommenting_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_nc_settings((automation.module_settings or {}).get("neurocommenting"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["neurocommenting"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_neurocommenting_module(session, automation_id)


async def create_neurocommenting_prompt(session: AsyncSession, automation_id: int, name: str, content: str) -> dict[str, Any]:
    prompt = await create_named_prompt(
        session,
        automation_id,
        prompt_type=PromptType.NEUROCOMMENTING.value,
        name=name,
        content=content or DEFAULT_NEUROCOMMENTING_PROMPT,
        activate=True,
    )
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_nc_settings((automation.module_settings or {}).get("neurocommenting") if automation else {})
    settings["prompt_id"] = prompt.id
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neurocommenting"] = settings
        automation.module_settings = blob
        await session.commit()
    return await get_neurocommenting_module(session, automation_id)


async def blackbox_neurocommenting_chat(session: AsyncSession, automation_id: int, *, chat_id: int | None = None, query: str | None = None) -> dict[str, Any]:
    stmt = select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
    if chat_id:
        stmt = stmt.where(ChatTarget.id == chat_id)
    elif query and query.strip():
        needle = f"%{query.strip()}%"
        from sqlalchemy import or_
        stmt = stmt.where(or_(ChatTarget.title.ilike(needle), ChatTarget.invite_link.ilike(needle)))
    else:
        raise ValueError("Укажите канал")
    chat = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if not chat:
        raise ValueError("Канал не найден")
    await blackbox_unusable_chat(session, chat, reason="manual")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_nc_settings((automation.module_settings or {}).get("neurocommenting") if automation else {})
    settings["chat_ids"] = [item for item in settings["chat_ids"] if item != chat.id]
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neurocommenting"] = settings
        automation.module_settings = blob
    await session.commit()
    return await get_neurocommenting_module(session, automation_id)
