"""Warmup module screen: enroll, humanization session, peer dialogs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AutomationActionLog,
    ChatFolder,
    ChatTarget,
    CustomAutomation,
    PoolAccount,
    SocialAccount,
)
from .account_pacing import account_humanization_stage
from .account_warmup_service import (
    enroll_pool_account,
    normalize_warmup_messages,
    normalize_warmup_usernames,
)
from .chat_join_service import create_chat_from_link
from .job_service import list_jobs
from .proxy_service import proxy_label
from .rotation_service import current_daily_messages_sent

DEFAULT_WARMUP_SETTINGS: dict[str, Any] = {
    "account_ids": [],
    "chat_ids": [],
    "mode": "auto",
    "intensity": "auto",
    "do_warmup_dms": True,
    "do_peer_dialogs": True,
    "do_reactions": True,
    "do_read_channels": True,
    "do_stories": True,
    "do_comment_contacts": True,
    "do_joins": True,
    "session_minutes": 0,
    "require_proxy": False,
    "hide_in_work": False,
    "blacklisted_account_ids": [],
    "presets": [],
}

STATUS_LABELS = {
    "idle": "Без прогрева",
    "rest": "Карантин",
    "warming": "В прогреве",
    "complete": "Прогрет",
}
STAGE_LABELS = {
    "cautious": "Осторожный",
    "normal": "Нормальный",
    "trusted": "Доверенный",
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


def normalize_warmup_settings(raw: Any) -> dict[str, Any]:
    data = dict(DEFAULT_WARMUP_SETTINGS)
    incoming = raw if isinstance(raw, dict) else {}
    data["account_ids"] = _as_int_list(incoming.get("account_ids"))
    data["chat_ids"] = _as_int_list(incoming.get("chat_ids"))
    data["blacklisted_account_ids"] = _as_int_list(incoming.get("blacklisted_account_ids"))
    mode = str(incoming.get("mode") or "auto").strip().lower()
    data["mode"] = mode if mode in {"auto", "manual"} else "auto"
    intensity = str(incoming.get("intensity") or "auto").strip().lower()
    data["intensity"] = intensity if intensity in {"auto", "cautious", "normal", "trusted"} else "auto"
    data["do_warmup_dms"] = bool(incoming.get("do_warmup_dms", True))
    data["do_peer_dialogs"] = bool(incoming.get("do_peer_dialogs", True))
    data["do_reactions"] = bool(incoming.get("do_reactions", True))
    data["do_read_channels"] = bool(incoming.get("do_read_channels", True))
    data["do_stories"] = bool(incoming.get("do_stories", True))
    data["do_comment_contacts"] = bool(incoming.get("do_comment_contacts", True))
    data["do_joins"] = bool(incoming.get("do_joins", True))
    data["session_minutes"] = _clamp_int(incoming.get("session_minutes") if incoming.get("session_minutes") is not None else 0, 0, lo=0, hi=15)
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
        presets.append({"name": name[:80], "settings": normalize_warmup_settings(snapshot)})
        if len(presets) >= 20:
            break
    data["presets"] = presets
    return data


def runtime_warmup_cfg(automation: CustomAutomation | None) -> dict[str, Any]:
    raw = ((getattr(automation, "module_settings", None) or {}).get("warmup") or {}) if automation else {}
    return normalize_warmup_settings(raw)


def account_allowed(cfg: dict[str, Any], account_id: int) -> bool:
    allowed = set(_as_int_list(cfg.get("account_ids")))
    blocked = set(_as_int_list(cfg.get("blacklisted_account_ids")))
    if account_id in blocked:
        return False
    return not allowed or account_id in allowed


def session_action_allowlist(cfg: dict[str, Any] | None) -> set[str] | None:
    data = cfg or {}
    if not data:
        return None
    names: set[str] = {"typing_idle", "draft", "saved", "view_profile", "search"}
    if data.get("do_read_channels", True):
        names.add("scroll_channels")
    if data.get("do_stories", True):
        names.add("stories")
    if data.get("do_reactions", True):
        names.add("react")
    if data.get("do_comment_contacts", True):
        names.add("comment_contact")
    return names


def _account_row(account: SocialAccount, pool: PoolAccount) -> dict[str, Any]:
    in_work = bool(account.is_active and (current_daily_messages_sent(account) or 0) > 0)
    status = (pool.warmup_status or "idle").strip().lower()
    stage = account_humanization_stage(account)
    eligible = bool(
        account.session_file_path
        and account.is_active
        and not account.is_banned
        and not account.is_frozen
        and not account.is_spamblocked
    )
    return {
        "id": account.id,
        "label": account.display_name or account.username or account.phone_number or f"#{account.id}",
        "username": account.username,
        "phone_number": account.phone_number,
        "roles": pool.roles or [],
        "proxy_label": proxy_label(getattr(account, "telegram_proxy", None)),
        "has_proxy": bool(account.telegram_proxy or pool.proxy_id),
        "is_active": bool(account.is_active),
        "is_banned": bool(account.is_banned),
        "is_frozen": bool(account.is_frozen),
        "in_work": in_work,
        "daily_messages_sent": current_daily_messages_sent(account),
        "warmup_status": status,
        "warmup_label": STATUS_LABELS.get(status, status),
        "warmup_dialog_count": int(pool.warmup_dialog_count or 0),
        "warmup_started_at": pool.warmup_started_at,
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
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


async def _log_summary(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    rows = await session.execute(
        select(AutomationActionLog.result, AutomationActionLog.action_type, func.count(AutomationActionLog.id)).where(
            AutomationActionLog.custom_automation_id == automation_id,
            AutomationActionLog.action_type.in_(("account_warmup", "peer_dialog", "comment_contact")),
        ).group_by(AutomationActionLog.result, AutomationActionLog.action_type)
    )
    by_type = {"account_warmup": 0, "peer_dialog": 0, "comment_contact": 0}
    success = failed = 0
    for result, action_type, count in rows.all():
        value = int(count)
        if result == "success":
            success += value
            if action_type in by_type:
                by_type[action_type] += value
        elif result == "error":
            failed += value
    attempts = success + failed
    return {
        "attempts": attempts,
        "success": success,
        "failed": failed,
        "success_pct": round((success / attempts) * 100, 1) if attempts else 0.0,
        "dms": by_type["account_warmup"],
        "peers": by_type["peer_dialog"],
        "contacts": by_type["comment_contact"],
    }


def _issues(*, enabled: bool, accounts: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if not enabled:
        issues.append("Прогрев выключен")
    live = [item for item in accounts if item.get("eligible")]
    if not live:
        issues.append("Нет рабочих аккаунтов")
    return issues


async def get_warmup_module(session: AsyncSession, automation_id: int, *, is_admin: bool = False) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = runtime_warmup_cfg(automation)
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
            select(ChatTarget).where(ChatTarget.custom_automation_id == automation_id, ChatTarget.black_boxed_at.is_(None)).order_by(ChatTarget.created_at.desc()).limit(400)
        )
    ).scalars().all()
    folders = (
        await session.execute(
            select(ChatFolder).where(ChatFolder.custom_automation_id == automation_id).order_by(ChatFolder.created_at.desc())
        )
    ).scalars().all()
    accounts = [_account_row(account, pool) for account, pool in pairs]
    usernames = normalize_warmup_usernames(automation.account_warmup_usernames)
    messages = normalize_warmup_messages(automation.account_warmup_messages)
    jobs = await list_jobs(session, automation_id, bucket="all", category="account", limit=80)
    wu_jobs = [item for item in jobs["items"] if item.get("job_type") == "warmup"][:12]
    warnings: list[str] = []
    if settings.get("do_warmup_dms") and not usernames:
        warnings.append("Нет доверенных юзернеймов для диалогов прогрева — их задаёт администратор")
    selected = [item for item in accounts if item["id"] in set(settings.get("account_ids") or [])] or [item for item in accounts if item.get("eligible")]
    if settings.get("do_peer_dialogs") and len(selected) < 2:
        warnings.append("Для диалогов между аккаунтами нужно минимум 2 аккаунта")
    return {
        "enabled": bool(automation.account_warmup_enabled),
        "is_admin": bool(is_admin),
        "settings": settings,
        "accounts": accounts,
        "chats": [_chat_row(chat) for chat in chats],
        "folders": [{"id": folder.id, "name": folder.name} for folder in folders],
        "jobs": wu_jobs,
        "summary": await _log_summary(session, automation_id),
        "username_count": len(usernames),
        "usernames": usernames if is_admin else [],
        "messages": messages if is_admin else [],
        "issues": _issues(enabled=bool(automation.account_warmup_enabled), accounts=accounts),
        "warnings": warnings,
        "stages": {
            "cautious": sum(1 for item in accounts if item["stage"] == "cautious"),
            "normal": sum(1 for item in accounts if item["stage"] == "normal"),
            "trusted": sum(1 for item in accounts if item["stage"] == "trusted"),
        },
    }


async def save_warmup_module(session: AsyncSession, automation_id: int, payload: dict[str, Any], *, is_admin: bool = False) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = normalize_warmup_settings(payload)
    if payload.get("enabled") is not None:
        automation.account_warmup_enabled = bool(payload.get("enabled"))
    if is_admin:
        if payload.get("usernames") is not None:
            automation.account_warmup_usernames = normalize_warmup_usernames(payload.get("usernames"))
        if payload.get("messages") is not None:
            automation.account_warmup_messages = normalize_warmup_messages(payload.get("messages"))
    blob = dict(automation.module_settings or {})
    blob["warmup"] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await session.commit()
    return await get_warmup_module(session, automation_id, is_admin=is_admin)


async def enroll_warmup_accounts(session: AsyncSession, automation_id: int, account_ids: list[int] | None = None) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    wanted = set(_as_int_list(account_ids))
    rows = (
        await session.execute(
            select(PoolAccount).where(PoolAccount.custom_automation_id == automation_id)
        )
    ).scalars().all()
    enrolled = 0
    for pool in rows:
        if wanted and pool.social_account_id not in wanted:
            continue
        if enroll_pool_account(automation, pool):
            enrolled += 1
    await session.commit()
    return {"enrolled": enrolled}


async def add_warmup_targets(session: AsyncSession, automation_id: int, raw_links: str) -> dict[str, Any]:
    added: list[int] = []
    errors: list[str] = []
    chunks: list[str] = []
    for line in (raw_links or "").replace(",", " ").splitlines():
        chunks.extend(part.strip() for part in line.split() if part.strip())
    for link in chunks:
        try:
            chat = await create_chat_from_link(session, automation_id, link, mode=None)
            added.append(chat.id)
        except ValueError as exc:
            errors.append(f"{link}: {exc}")
        except Exception as exc:
            errors.append(f"{link}: {exc}")
    automation = await session.get(CustomAutomation, automation_id)
    settings = runtime_warmup_cfg(automation)
    settings["chat_ids"] = list(dict.fromkeys([*settings["chat_ids"], *added]))
    if automation:
        blob = dict(automation.module_settings or {})
        blob["warmup"] = settings
        automation.module_settings = blob
        await session.commit()
    data = await get_warmup_module(session, automation_id)
    data["added_ids"] = added
    data["add_errors"] = errors
    return data


async def save_warmup_preset(session: AsyncSession, automation_id: int, name: str) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("Automation not found")
    settings = runtime_warmup_cfg(automation)
    title = (name or "").strip() or f"Заготовка {len(settings['presets']) + 1}"
    snapshot = {key: value for key, value in settings.items() if key != "presets"}
    settings["presets"] = [*settings["presets"], {"name": title[:80], "settings": snapshot}][-20:]
    blob = dict(automation.module_settings or {})
    blob["warmup"] = settings
    automation.module_settings = blob
    await session.commit()
    return await get_warmup_module(session, automation_id)


async def run_warmup_module_pass(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker
    from .account_idle_browse_service import run_idle_browse_pass
    from .account_peer_dialog_service import run_peer_dialog_pass
    from .account_warmup_service import run_account_warmup_pass

    async with async_session_maker() as session:
        automation = await session.get(CustomAutomation, automation_id)
        cfg = runtime_warmup_cfg(automation)
        if automation and cfg.get("account_ids"):
            await enroll_warmup_accounts(session, automation_id, cfg.get("account_ids"))
    result: dict[str, Any] = {}
    if cfg.get("do_warmup_dms", True):
        result["dms"] = await run_account_warmup_pass(automation_id)
    result["session"] = await run_idle_browse_pass(automation_id)
    if cfg.get("do_peer_dialogs", True):
        result["peers"] = await run_peer_dialog_pass(automation_id)
    return result
