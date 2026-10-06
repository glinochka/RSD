"""Parser module screen: file folders, live user harvest, filters."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatFolder,
    ChatTarget,
    CustomAutomation,
    ParserUser,
    PoolAccount,
    SocialAccount,
)
from .chat_folder_service import list_folders
from .user_folder_service import list_user_folders
from .chat_import_service import import_chats_from_file
from .chat_addlist_service import import_chat_links, split_link_tokens
from .job_service import list_jobs
from .parser_service import normalize_parser_targets, normalize_since_hours
from .account_roles import account_is_task_ready
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_PARSER_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "source": "messages",
    "account_ids": [],
    "chat_ids": [],
    "folder_ids": [],
    "targets": [],
    "do_join": True,
    "since_hours": 24,
    "member_limit": 1000,
    "skip_bots": True,
    "skip_deleted": True,
    "skip_scam": False,
    "only_username": False,
    "only_photo": False,
    "only_premium": False,
    "only_admins": False,
    "only_active_stories": False,
    "delay_chat": 5,
    "delay_user": 1,
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


def normalize_parser_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_PARSER_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["enabled"] = bool(incoming.get("enabled")) if incoming.get("enabled") is not None else data["enabled"]
    source = str(incoming.get("source") or "messages").strip().lower()
    data["source"] = source if source in {"messages", "participants", "comments"} else "messages"
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["folder_ids"] = _as_int_list(incoming.get("folder_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    data["targets"] = normalize_parser_targets(incoming.get("targets"))
    data["do_join"] = bool(incoming.get("do_join", True))
    data["since_hours"] = normalize_since_hours(incoming.get("since_hours") if incoming.get("since_hours") is not None else 24)
    data["member_limit"] = _clamp_int(incoming.get("member_limit") if incoming.get("member_limit") is not None else 1000, 1000, lo=1, hi=10000)
    data["skip_bots"] = bool(incoming.get("skip_bots", True))
    data["skip_deleted"] = bool(incoming.get("skip_deleted", True))
    data["skip_scam"] = bool(incoming.get("skip_scam"))
    data["only_username"] = bool(incoming.get("only_username"))
    data["only_photo"] = bool(incoming.get("only_photo"))
    data["only_premium"] = bool(incoming.get("only_premium"))
    data["only_admins"] = bool(incoming.get("only_admins"))
    data["only_active_stories"] = bool(incoming.get("only_active_stories"))
    data["delay_chat"] = _clamp_int(incoming.get("delay_chat") if incoming.get("delay_chat") is not None else 5, 5, lo=0, hi=120)
    data["delay_user"] = _clamp_int(incoming.get("delay_user") if incoming.get("delay_user") is not None else 1, 1, lo=0, hi=30)
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
        presets.append({"name": name[:80], "settings": normalize_parser_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    eligible = account_is_task_ready(pool, account, "parser", exclude_spamblocked=True)
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


def _chat_row(chat: ChatTarget) -> dict[str, Any]:
    return {
        "id": chat.id,
        "title": chat.title or chat.invite_link or f"#{chat.id}",
        "invite_link": chat.invite_link,
        "chat_type": chat.chat_type,
        "join_status": chat.join_status,
        "folder_id": chat.folder_id,
        "members_count": chat.members_count,
    }


def _user_row(item: ParserUser) -> dict[str, Any]:
    username = item.username
    return {
        "id": item.id,
        "telegram_user_id": item.telegram_user_id,
        "username": username,
        "link": f"https://t.me/{username}" if username else None,
        "first_name": item.first_name,
        "last_name": item.last_name,
        "title": " ".join(part for part in (item.first_name, item.last_name) if part) or (f"@{username}" if username else str(item.telegram_user_id)),
        "source_mode": item.source_mode,
        "source_title": item.source_title,
        "is_premium": item.is_premium,
        "has_photo": item.has_photo,
        "is_admin": item.is_admin,
        "last_message_at": item.last_message_at,
        "created_at": item.created_at,
    }


def _issues(settings: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not settings.get("enabled"):
        issues.append("Парсер выключен")
    if not settings.get("account_ids"):
        issues.append("Выберите хотя бы один аккаунт")
    if not settings.get("chat_ids") and not settings.get("folder_ids") and not settings.get("targets"):
        issues.append("Добавьте чаты: файл-папка, папка или список ссылок")
    return issues


async def list_parser_results(
    session: AsyncSession,
    automation_id: int,
    *,
    query: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    conditions = [ParserUser.custom_automation_id == automation_id]
    needle = (query or "").strip().lstrip("@").lower()
    if needle:
        conditions.append(
            (ParserUser.username.ilike(f"%{needle}%"))
            | (ParserUser.first_name.ilike(f"%{needle}%"))
            | (ParserUser.last_name.ilike(f"%{needle}%"))
            | (ParserUser.source_title.ilike(f"%{needle}%"))
        )
    total = await session.scalar(select(func.count(ParserUser.id)).where(*conditions))
    rows = (
        await session.execute(
            select(ParserUser)
            .where(*conditions)
            .order_by(ParserUser.created_at.desc())
            .limit(max(1, min(int(limit or 200), 2000)))
            .offset(max(0, int(offset or 0)))
        )
    ).scalars().all()
    return {"items": [_user_row(item) for item in rows], "total": int(total or 0)}


async def clear_parser_results(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    await session.execute(delete(ParserUser).where(ParserUser.custom_automation_id == automation_id))
    await session.commit()
    return await get_parser_module(session, automation_id)


async def get_parser_module(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_parser_settings((automation.module_settings or {}).get("parser"))
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
            select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id, ChatTarget.is_active.is_(True)).order_by(ChatTarget.created_at.desc()).limit(500)
        )
    ).scalars().all()
    folder_rows = await list_folders(session, automation_id)
    jobs = await list_jobs(session, automation_id, bucket="all", category="module", limit=80)
    parser_jobs = [item for item in jobs["items"] if item.get("job_type") == "parser"][:12]
    counts = await session.execute(
        select(AutomationActionLog.result, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type == "parser",
        ).group_by(AutomationActionLog.result)
    )
    data = {str(result or ""): int(count) for result, count in counts.all()}
    success = data.get("success", 0)
    failed = data.get("error", 0)
    attempts = sum(data.values())
    results = await list_parser_results(session, automation_id, limit=80)
    return {
        "enabled": bool(settings.get("enabled")),
        "settings": settings,
        "accounts": [_account_row(account, pool) for account, pool in pairs],
        "chats": [_chat_row(chat) for chat in chats],
        "folders": [{"id": folder.id, "name": folder.name, "count": count} for folder, count in folder_rows],
        "user_folders": await list_user_folders(session, automation_id),
        "jobs": parser_jobs,
        "results": results["items"],
        "results_total": results["total"],
        "summary": {
            "attempts": attempts,
            "success": success,
            "failed": failed,
            "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
            "users": results["total"],
        },
        "issues": _issues(settings),
    }


async def save_parser_module(session: AsyncSession, automation_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_parser_settings(payload)
    if payload.get("enabled") is not None:
        settings["enabled"] = bool(payload.get("enabled"))
    blob = dict(automation.module_settings or {})
    blob["parser"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_parser_module(session, automation_id)


async def save_parser_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_parser_settings((automation.module_settings or {}).get("parser"))
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["parser"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_parser_module(session, automation_id)


def file_to_import_payload(filename: str, content: bytes) -> tuple[str, bytes]:
    name = (filename or "chats.txt").lower()
    if name.endswith((".csv", ".xlsx", ".xls")):
        return filename, content
    text = content.decode("utf-8-sig", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    buf = io.StringIO()
    buf.write("invite_link\n")
    for line in lines:
        buf.write(line.replace(",", " ") + "\n")
    stem = Path(filename or "chats").stem or "chats"
    return f"{stem}.csv", buf.getvalue().encode("utf-8")


async def import_parser_file(
    session: AsyncSession,
    automation_id: int,
    *,
    filename: str,
    content: bytes,
) -> dict[str, Any]:
    from .chat_folder_service import folder_name_from_filename

    import_name, payload = file_to_import_payload(filename, content)
    job = await import_chats_from_file(
        session,
        automation_id=automation_id,
        filename=import_name,
        content=payload,
        quality_filter=False,
    )
    folder_name = folder_name_from_filename(import_name)
    folder = await session.scalar(
        select(ChatFolder).where(
            ChatFolder.custom_automation_id == automation_id,
            ChatFolder.name == folder_name[:255],
        )
    )
    chat_ids = []
    if folder:
        chat_ids = [
            int(item)
            for item in (
                await session.execute(
                    select(ChatTarget.id).where(
                        ChatTarget.custom_automation_id == automation_id,
                        ChatTarget.folder_id == folder.id,
                    )
                )
            ).scalars().all()
        ]
        automation = await session.get(CustomAutomation, automation_id)
        settings = normalize_parser_settings((automation.module_settings or {}).get("parser") if automation else {})
        settings["folder_ids"] = list(dict.fromkeys([*settings["folder_ids"], folder.id]))
        settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *chat_ids]))
        if automation:
            blob = dict(automation.module_settings or {})
            blob["parser"] = settings
            automation.module_settings = blob
            await session.commit()
    data = await get_parser_module(session, automation_id)
    data["import_job"] = {
        "id": job.id,
        "file_name": job.file_name,
        "processed_rows": job.processed_rows,
        "duplicate_rows": job.duplicate_rows,
        "error_rows": job.error_rows,
        "folder_id": folder.id if folder else None,
        "folder_name": folder.name if folder else folder_name,
    }
    return data


async def add_parser_targets(session: AsyncSession, automation_id: int, raw_links: str) -> dict[str, Any]:
    chunks = split_link_tokens(raw_links)
    added, errors = await import_chat_links(session, automation_id, raw_links, mode=None)
    automation = await session.get(CustomAutomation, automation_id)
    settings = normalize_parser_settings((automation.module_settings or {}).get("parser") if automation else {})
    settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *added]))
    settings["targets"] = normalize_parser_targets([*settings["targets"], *chunks])
    if automation:
        blob = dict(automation.module_settings or {})
        blob["parser"] = settings
        automation.module_settings = blob
        await session.commit()
    data = await get_parser_module(session, automation_id)
    data["added_ids"] = added
    data["add_errors"] = errors
    return data
