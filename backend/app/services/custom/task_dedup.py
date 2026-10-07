"""Unique target assignment and userbot detection for UBT modules."""
from __future__ import annotations

import re
from typing import Any, TypeVar

from .chat_addlist_service import TASK_JOINS_KEY, even_redistribute

T = TypeVar("T")
UNIQUE_ASSIGN_KEY = "_unique_assign"

_BIO_LINK_RE = re.compile(
    r"(?i)(?:"
    r"https?://|"
    r"tg://|"
    r"(?:t|telegram)\.(?:me|dog)/|"
    r"www\.|"
    r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?"
    r")"
)


def bio_has_link(raw: Any) -> bool:
    text = " ".join(str(raw or "").split())
    return bool(text and _BIO_LINK_RE.search(text))


def looks_like_userbot(entity: Any = None, *, about: str | None = None, is_bot: bool | None = None) -> bool:
    if is_bot is None and entity is not None:
        is_bot = bool(getattr(entity, "bot", False))
    if is_bot:
        return True
    if about is None and entity is not None:
        about = getattr(entity, "about", None)
    return bio_has_link(about)


async def fetch_user_about(client: Any, entity: Any) -> str:
    telethon = getattr(client, "client", client)
    try:
        from telethon.tl.functions.users import GetFullUserRequest

        full = await telethon(GetFullUserRequest(entity))
        about = getattr(getattr(full, "full_user", None), "about", None) or getattr(full, "about", None)
        return str(about or "")
    except Exception:
        return str(getattr(entity, "about", None) or "")


async def entity_is_bot_or_userbot(client: Any, entity: Any) -> bool:
    if looks_like_userbot(entity):
        return True
    about = await fetch_user_about(client, entity)
    return bio_has_link(about)


def unique_assign(
    account_ids: list[int],
    items: list[T],
    previous: dict[int, list[T]] | None = None,
) -> dict[int, list[T]]:
    """Give each target to exactly one account. Keep previous owners when still valid."""
    accounts = [int(item) for item in dict.fromkeys(account_ids or []) if int(item) > 0]
    unique_items: list[T] = []
    seen: set[Any] = set()
    for item in items or []:
        if item in seen:
            continue
        seen.add(item)
        unique_items.append(item)
    if not accounts:
        return {}
    if not unique_items:
        return {aid: [] for aid in accounts}
    index = {item: i for i, item in enumerate(unique_items)}
    prev_idx: dict[int, list[int]] = {}
    for aid, old in (previous or {}).items():
        prev_idx[int(aid)] = [index[item] + 1 for item in old or [] if item in index]
    assigned = even_redistribute(
        accounts,
        list(range(1, len(unique_items) + 1)),
        prev_idx,
        max_per_account=len(unique_items),
    )
    return {aid: [unique_items[i - 1] for i in idxs] for aid, idxs in assigned.items()}


def load_unique_assign(automation: Any, task_key: str) -> dict[int, list[Any]]:
    blob = (getattr(automation, "module_settings", None) or {}).get(UNIQUE_ASSIGN_KEY) or {}
    raw = blob.get(task_key) if isinstance(blob, dict) else {}
    out: dict[int, list[Any]] = {}
    for key, value in (raw or {}).items():
        try:
            out[int(key)] = list(value or [])
        except (TypeError, ValueError):
            continue
    return out


def store_unique_assign(automation: Any, task_key: str, assignment: dict[int, list[Any]]) -> None:
    blob = dict(getattr(automation, "module_settings", None) or {})
    plans = dict(blob.get(UNIQUE_ASSIGN_KEY) or {})
    plans[task_key] = {str(key): list(value) for key, value in assignment.items()}
    blob[UNIQUE_ASSIGN_KEY] = plans
    automation.module_settings = blob


def _join_assignments(automation: Any, task_key: str) -> dict[int, list[int]]:
    blob = (getattr(automation, "module_settings", None) or {}).get(TASK_JOINS_KEY) or {}
    spec = blob.get(task_key) if isinstance(blob, dict) else {}
    raw = (spec or {}).get("assignments") if isinstance(spec, dict) else {}
    out: dict[int, list[int]] = {}
    for key, value in (raw or {}).items():
        try:
            aid = int(key)
        except (TypeError, ValueError):
            continue
        ids: list[int] = []
        for item in value or []:
            try:
                ids.append(int(item))
            except (TypeError, ValueError):
                continue
        out[aid] = ids
    return out


def has_join_plan(automation: Any, task_key: str) -> bool:
    return bool(_join_assignments(automation, task_key))


def persist_unique_chats(automation: Any, task_key: str, account_ids: list[int], chat_ids: list[int]) -> None:
    if has_join_plan(automation, task_key):
        return
    assignment = unique_assign(account_ids, chat_ids, load_unique_assign(automation, task_key))
    store_unique_assign(automation, task_key, assignment)


def chat_owner_ids(automation: Any, task_key: str, chat_id: int) -> set[int] | None:
    """Accounts that own this chat in the join/unique plan. None = no plan yet."""
    assignments = _join_assignments(automation, task_key) or load_unique_assign(automation, task_key)
    if not assignments:
        return None
    owners: set[int] = set()
    want = int(chat_id)
    for aid, items in assignments.items():
        for item in items or []:
            try:
                if int(item) == want:
                    owners.add(int(aid))
                    break
            except (TypeError, ValueError):
                continue
    return owners


def account_owns_chat(automation: Any, task_key: str, account_id: int, chat_id: int) -> bool:
    owners = chat_owner_ids(automation, task_key, chat_id)
    if owners is None:
        return True
    return int(account_id) in owners
