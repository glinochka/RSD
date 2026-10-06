"""Neuroshilling module screen: two-account Q/A in groups and under posts."""
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
from .account_roles import account_is_task_ready
from .chat_addlist_service import import_chat_links
from .chat_folder_service import folder_payloads
from .chat_membership_service import blackbox_unusable_chat
from .chat_scope import is_broadcast_channel, is_group_chat
from .job_service import list_jobs
from .prompt_service import activate_prompt, create_named_prompt, list_prompts, update_prompt
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent
from .shilling_service import (
    REPLY_DELAY_MAX_SECONDS,
    REPLY_DELAY_MIN_SECONDS,
    encode_shilling_lines,
    generate_shilling_from_topic,
    parse_shilling_lines,
)

DEFAULT_SHILL_SETTINGS: dict[str, Any] = {
    "account_ids": [],
    "chat_ids": [],
    "folder_ids": [],
    "channel_ids": [],
    "chat_shilling": True,
    "post_shilling": True,
    "unique_messages": True,
    "skip_fresh": True,
    "require_proxy": False,
    "hide_in_work": False,
    "delay_min": int(REPLY_DELAY_MIN_SECONDS),
    "delay_max": int(REPLY_DELAY_MAX_SECONDS),
    "prompt_id": None,
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


def normalize_shill_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_SHILL_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["folder_ids"] = _as_int_list(incoming.get("folder_ids"))
    data["channel_ids"] = _as_int_list(incoming.get("channel_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    data["chat_shilling"] = bool(incoming.get("chat_shilling", True))
    data["post_shilling"] = bool(incoming.get("post_shilling", True))
    data["unique_messages"] = bool(incoming.get("unique_messages", True))
    data["skip_fresh"] = bool(incoming.get("skip_fresh", True))
    data["require_proxy"] = bool(incoming.get("require_proxy"))
    data["hide_in_work"] = bool(incoming.get("hide_in_work"))
    data["delay_min"] = _clamp_int(incoming.get("delay_min") if incoming.get("delay_min") is not None else int(REPLY_DELAY_MIN_SECONDS), int(REPLY_DELAY_MIN_SECONDS), lo=0, hi=600)
    data["delay_max"] = max(data["delay_min"], _clamp_int(incoming.get("delay_max") if incoming.get("delay_max") is not None else int(REPLY_DELAY_MAX_SECONDS), int(REPLY_DELAY_MAX_SECONDS), lo=0, hi=600))
    try:
        prompt_id = incoming.get("prompt_id")
        data["prompt_id"] = int(prompt_id) if prompt_id else None
    except (TypeError, ValueError):
        data["prompt_id"] = None
    presets = []
    for item in incoming.get("presets") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        snapshot = dict(item.get("settings") or {})
        snapshot["presets"] = []
        presets.append({"name": name[:80], "settings": normalize_shill_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    eligible = account_is_task_ready(pool, account, "shilling", exclude_spamblocked=True)
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
        "is_channel": is_broadcast_channel(chat),
        "join_status": chat.join_status,
        "comments_open": chat.comments_open,
        "folder_id": chat.folder_id,
        "black_boxed": bool(chat.black_boxed_at),
        "members_count": chat.members_count,
    }


async def _log_summary(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    rows = await session.execute(
        select(AutomationActionLog.result, AutomationActionLog.action_type, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type.in_(("shilling_chat", "shilling_post")),
        ).group_by(AutomationActionLog.result, AutomationActionLog.action_type)
    )
    chat_ok = chat_fail = post_ok = post_fail = 0
    for result, action_type, count in rows.all():
        value = int(count)
        if action_type == "shilling_chat" and result == "success":
            chat_ok += value
        elif action_type == "shilling_chat" and result == "error":
            chat_fail += value
        elif action_type == "shilling_post" and result == "success":
            post_ok += value
        elif action_type == "shilling_post" and result == "error":
            post_fail += value
    success = chat_ok + post_ok
    failed = chat_fail + post_fail
    attempts = success + failed
    return {
        "attempts": attempts,
        "success": success,
        "failed": failed,
        "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
        "chats": chat_ok,
        "posts": post_ok,
    }


def _issues(settings: dict[str, Any], *, enabled: bool, setup: str, reply: str, accounts: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if not enabled:
        issues.append("Модуль нейрошиллинга выключен")
    selected = [item for item in accounts if item["id"] in set(settings.get("account_ids") or [])]
    if len(selected) < 2:
        issues.append("Выберите хотя бы два аккаунта")
    if not settings.get("chat_shilling") and not settings.get("post_shilling"):
        issues.append("Включите шиллинг в чатах или в комментариях")
    if not setup.strip() or not reply.strip():
        issues.append("Заполните вопрос и ответ диалога")
    return issues


def _prompt_row(prompt: CustomPrompt) -> dict[str, Any]:
    setup, reply = parse_shilling_lines(prompt.content)
    return {
        "id": prompt.id,
        "name": prompt.name,
        "setup": setup,
        "reply": reply,
        "is_active": prompt.is_active,
        "is_system": prompt.name == "Shilling",
    }


async def get_neuroshilling_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_shill_settings((automation.module_settings or {}).get("neuroshilling"))
    await list_prompts(session, automation_id)
    prompts = (
        await session.execute(
            select(CustomPrompt).where(
                CustomPrompt.custom_automation_id == automation_id,
                CustomPrompt.prompt_type == PromptType.SHILLING.value,
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
    accounts = [_account_row(account, pool) for account, pool in pairs]
    prompt_rows = [_prompt_row(prompt) for prompt in prompts]
    active = next((item for item in prompt_rows if item["is_active"]), prompt_rows[0] if prompt_rows else {"setup": "", "reply": "", "id": None})
    if settings.get("prompt_id"):
        picked = next((item for item in prompt_rows if item["id"] == settings["prompt_id"]), None)
        if picked:
            active = picked
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    shill_jobs = [item for item in jobs["items"] if item.get("job_type") == "shilling"][:12]
    visible = [_chat_row(chat) for chat in chats if not chat.black_boxed_at]
    black = [chat for chat in chats if chat.black_boxed_at]
    return {
        "enabled": bool(automation.is_shilling_enabled),
        "settings": settings,
        "setup": active.get("setup") or "",
        "reply": active.get("reply") or "",
        "accounts": accounts,
        "chats": visible,
        "folders": folders,
        "prompts": prompt_rows,
        "jobs": shill_jobs,
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
        "issues": _issues(settings, enabled=bool(automation.is_shilling_enabled), setup=active.get("setup") or "", reply=active.get("reply") or "", accounts=accounts),
        "check": None,
    }


async def _save_lines(session: AsyncSession, automation_id: int, settings: dict[str, Any], setup: str | None, reply: str | None) -> None:
    if setup is None and reply is None:
        return
    prompts = (
        await session.execute(
            select(CustomPrompt).where(
                CustomPrompt.custom_automation_id == automation_id,
                CustomPrompt.prompt_type == PromptType.SHILLING.value,
            ).order_by(CustomPrompt.is_active.desc(), CustomPrompt.created_at.desc())
        )
    ).scalars().all()
    current = None
    if settings.get("prompt_id"):
        current = next((item for item in prompts if item.id == settings["prompt_id"]), None)
    if current is None:
        current = next((item for item in prompts if item.is_active), prompts[0] if prompts else None)
    old_setup, old_reply = parse_shilling_lines(current.content if current else "")
    body = encode_shilling_lines(setup if setup is not None else old_setup, reply if reply is not None else old_reply)
    if current:
        updated = await update_prompt(session, automation_id, current.id, content=body, is_active=True)
        settings["prompt_id"] = updated.id
    else:
        created = await create_named_prompt(session, automation_id, prompt_type=PromptType.SHILLING.value, name="Мой шиллинг", content=body, activate=True)
        settings["prompt_id"] = created.id


async def save_neuroshilling_module(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_shill_settings(payload)
    if payload.get("enabled") is not None:
        automation.is_shilling_enabled = bool(payload.get("enabled"))
    await _save_lines(session, automation_id, settings, payload.get("setup"), payload.get("reply"))
    if settings["prompt_id"]:
        try:
            await activate_prompt(session, automation_id, settings["prompt_id"])
        except ValueError:
            settings["prompt_id"] = None
    blob = dict(automation.module_settings or {})
    blob["neuroshilling"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_neuroshilling_module(session, automation_id)


async def add_neuroshilling_targets(session: AsyncSession, automation_id: int, raw_links: str, *, kind: str = "auto") -> dict[str, Any]:
    added_chats: list[int] = []
    added_channels: list[int] = []
    mode = "neurocommenting" if kind == "channel" else "shilling" if kind == "group" else None
    added, errors = await import_chat_links(session, automation_id, raw_links, mode=mode)
    for chat_id in added:
        chat = await session.get(ChatTarget, chat_id)
        if not chat:
            continue
        if is_broadcast_channel(chat) or kind == "channel":
            added_channels.append(chat.id)
        else:
            added_chats.append(chat.id)
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_shill_settings((automation.module_settings or {}).get("neuroshilling") if automation else {})
    settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *added_chats]))
    settings["channel_ids"] = list(dict.fromkeys([*settings["channel_ids"], *added_channels]))
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neuroshilling"] = settings
        automation.module_settings = blob
        await session.commit()
    data = await get_neuroshilling_module(session, automation_id)
    data["added_ids"] = [*added_chats, *added_channels]
    data["add_errors"] = errors
    return data


async def save_neuroshilling_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_shill_settings((automation.module_settings or {}).get("neuroshilling"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["neuroshilling"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_neuroshilling_module(session, automation_id)


async def generate_neuroshilling_lines(session: AsyncSession, automation_id: int, topic: str) -> dict[str, Any]:
    setup, reply = await generate_shilling_from_topic(topic)
    if not setup or not reply:
        raise ValueError("Не удалось сгенерировать реплики")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_shill_settings((automation.module_settings or {}).get("neuroshilling") if automation else {})
    await _save_lines(session, automation_id, settings, setup, reply)
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neuroshilling"] = settings
        automation.module_settings = blob
        await session.commit()
    return await get_neuroshilling_module(session, automation_id)


def check_neuroshilling_payload(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("settings") or {}
    accounts = [item for item in (data.get("accounts") or []) if item["id"] in set(settings.get("account_ids") or [])]
    groups = len(settings.get("chat_ids") or [])
    channels = len(settings.get("channel_ids") or [])
    return {
        "accounts": len(accounts),
        "groups": groups,
        "channels": channels,
        "replies": 2 if (data.get("setup") and data.get("reply")) else 0,
        "ok": not (data.get("issues") or []),
        "issues": data.get("issues") or [],
    }


async def blackbox_neuroshilling_chat(session: AsyncSession, automation_id: int, *, chat_id: int | None = None, query: str | None = None) -> dict[str, Any]:
    stmt = select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id)
    if chat_id:
        stmt = stmt.where(ChatTarget.id == chat_id)
    elif query and query.strip():
        needle = f"%{query.strip()}%"
        stmt = stmt.where(or_(ChatTarget.title.ilike(needle), ChatTarget.invite_link.ilike(needle)))
    else:
        raise ValueError("Укажите чат")
    chat = (await session.execute(stmt.limit(1))).scalar_one_or_none()
    if not chat:
        raise ValueError("Чат не найден")
    await blackbox_unusable_chat(session, chat, reason="manual")
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_shill_settings((automation.module_settings or {}).get("neuroshilling") if automation else {})
    settings["chat_ids"] = [item for item in settings["chat_ids"] if item != chat.id]
    settings["channel_ids"] = [item for item in settings["channel_ids"] if item != chat.id]
    if automation:
        blob = dict(automation.module_settings or {})
        blob["neuroshilling"] = settings
        automation.module_settings = blob
    await session.commit()
    return await get_neuroshilling_module(session, automation_id)
