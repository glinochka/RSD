"""After mass session upload: style accounts by class templates and join loaded chats."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ...alembic.database import async_session_maker
from ...alembic.models import AccountClass, CustomAutomation
from .bulk_profile_service import BulkProfileUpdateWorker
from .chat_join_service import join_loaded_chats_for_accounts
from .rotation_service import list_alive_session_accounts

logger = logging.getLogger(__name__)

_JOBS: dict[int, dict[str, Any]] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _job(automation_id: int) -> dict[str, Any]:
    return _JOBS.setdefault(
        automation_id,
        {
            "status": "idle",
            "alive": 0,
            "profiles_done": 0,
            "chats_joined": 0,
            "error": None,
        },
    )


def get_prepare_status(automation_id: int) -> dict[str, Any]:
    return dict(_job(automation_id))


def mark_prepare_running(automation_id: int) -> dict[str, Any]:
    state = _job(automation_id)
    if state.get("status") == "running":
        return dict(state)
    state.update({"status": "running", "error": None})
    return dict(state)


def merge_setup_template(
    templates: dict[str, Any] | None,
    account_class: str | None,
    *,
    bio_template: str = "",
    generate_unique: bool = False,
    avatar_relative_path: str | None = None,
) -> dict[str, Any]:
    data = dict(templates or {})
    key = (account_class or "*").strip() or "*"
    prev = dict(data.get(key) or {})
    prev["bio_template"] = bio_template
    prev["generate_unique"] = bool(generate_unique)
    if avatar_relative_path:
        prev["avatar_relative_path"] = avatar_relative_path
    data[key] = prev
    return data


async def prepare_accounts(automation_id: int) -> dict[str, Any]:
    state = _job(automation_id)
    state.update(
        {
            "status": "running",
            "alive": 0,
            "profiles_done": 0,
            "chats_joined": 0,
            "error": None,
        }
    )
    worker = BulkProfileUpdateWorker()
    try:
        async with async_session_maker() as session:
            automation = await session.get(CustomAutomation, automation_id)
            if not automation:
                raise ValueError("automation not found")
            templates = dict(automation.account_setup_templates or {})
            alive = await list_alive_session_accounts(session, automation_id)
            state["alive"] = len(alive)
            default_tmpl = dict(templates.get("*") or {})
            class_ids: dict[str, list[int]] = {item.value: [] for item in AccountClass}
            for account in alive:
                key = account.account_class or AccountClass.ONE_DAY.value
                class_ids.setdefault(key, []).append(account.id)

        for class_name, account_ids in class_ids.items():
            if not account_ids:
                continue
            tmpl = dict(templates.get(class_name) or default_tmpl or {})
            if not tmpl:
                continue
            bio = str(tmpl.get("bio_template") or "")
            generate_unique = bool(tmpl.get("generate_unique"))
            avatar = tmpl.get("avatar_relative_path")
            if not bio and not generate_unique and not avatar:
                continue
            results = await worker.process_accounts(
                automation_id,
                account_ids,
                avatar_relative_path=avatar,
                bio_template=bio,
                generate_unique=generate_unique,
            )
            state["profiles_done"] = int(state.get("profiles_done") or 0) + sum(
                1 for row in results if row.get("status") == "success"
            )

        async with async_session_maker() as session:
            join_result = await join_loaded_chats_for_accounts(session, automation_id)
        state["chats_joined"] = int(join_result.get("joined_chats") or 0)
        state["status"] = "completed"
        state["finished_at"] = _utc_now().isoformat()
    except Exception as exc:
        logger.exception("Account prepare failed for automation %s: %s", automation_id, exc)
        state["status"] = "error"
        state["error"] = str(exc)[:255]
    return dict(state)
