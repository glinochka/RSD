"""Task-scoped chat joins via Telegram shareable folders (t.me/addlist).

Free accounts: 2 shareable folders × 100 chats.
Premium: 20 folders × 200 chats.
https://telegram.org/tour/chat-folders
"""
from __future__ import annotations

import logging
import math
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AccountChatMembership,
    ChatFolder,
    ChatJoinStatus,
    ChatMode,
    ChatSource,
    ChatTarget,
    CustomAutomation,
    MembershipPurpose,
    SocialAccount,
)
from .chat_membership_service import (
    ACTION_JOIN_PRIORITY,
    ACTOR_PURPOSE,
    account_is_joined,
    get_membership,
)
from .chat_target_dedup import find_existing_chat_target
from .rotation_service import list_alive_session_accounts
from .telegram_invite import TelegramChatRefError, parse_telegram_chat_ref

logger = logging.getLogger(__name__)

ADDLIST_CHATS_DEFAULT = 100
ADDLIST_CHATS_PREMIUM = 200
ADDLIST_FOLDERS_DEFAULT = 2
ADDLIST_FOLDERS_PREMIUM = 20
TASK_JOINS_KEY = "_task_joins"
TASK_WAVES_KEY = "_join_waves"
HOST_BOOTSTRAP_JOINS_PER_TICK = 1
_SHARED_PLAN_KEYS = {"_shared", "_waves"}
TASK_CHATS_PER_ACCOUNT = 50
JOIN_WAVE_MIN = 10
JOIN_WAVE_MAX = 15


def pool_actor_status(account: SocialAccount | None) -> str:
    """Short reason the pool row is not currently working."""
    if account is None:
        return "нет в базе"
    if not account.is_active:
        return "выключен"
    if account.is_banned:
        return "бан"
    if getattr(account, "is_frozen", False):
        return "заморозка"
    from .account_pacing import account_is_flood_quarantined

    if account_is_flood_quarantined(account):
        return "карантин"
    if not (account.session_file_path or getattr(account, "encrypted_session", None)):
        return "нет сессии"
    return ""


def pool_actor_selectable(account: SocialAccount | None) -> bool:
    """True if the account can stay on a task even while FloodWait parks joins."""
    if account is None or not account.is_active or account.is_banned:
        return False
    if getattr(account, "is_frozen", False):
        return False
    return bool(account.session_file_path or getattr(account, "encrypted_session", None))


def join_account_is_parked(account: SocialAccount | None, *, now: datetime | None = None) -> bool:
    """True while Telegram FloodWait still holds this account. Comment rest does not block joins."""
    from .account_pacing import account_is_flood_quarantined

    return account_is_flood_quarantined(account, now=now)


async def _skip_join_for_flood(session: AsyncSession, account: SocialAccount | None) -> bool:
    if not account:
        return True
    if join_account_is_parked(account):
        return True
    now = _utc_now()
    nxt = await session.scalar(
        select(func.max(AccountChatMembership.next_join_attempt_at)).where(
            AccountChatMembership.social_account_id == account.id,
            AccountChatMembership.next_join_attempt_at.is_not(None),
        )
    )
    return nxt is not None and nxt > now


def _flood_seconds(raw: Any, default: int = 300) -> int:
    seconds = getattr(raw, "seconds", None)
    if seconds:
        try:
            return max(1, int(seconds))
        except (TypeError, ValueError):
            pass
    text = str(raw or "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        try:
            return max(1, int(digits[:6]))
        except ValueError:
            pass
    return default


def _is_flood_error(exc: BaseException) -> bool:
    return "flood" in type(exc).__name__.lower() or "floodwait" in str(exc).lower()


def _park_join_flood(account: SocialAccount, raw: Any = None) -> None:
    from .account_pacing import schedule_flood_quarantine

    del raw
    schedule_flood_quarantine(account)


def _log_job_type(task_key: str) -> str:
    return {
        "neurocommenting": "neurocommenting",
        "chat_monitoring": "chat_monitoring",
        "neurochatting": "discussion",
        "neuroshilling": "shilling",
        "chat_broadcasts": "chat_broadcast",
        "parser": "parser",
        "masslooking": "masslooking",
        "warmup": "warmup",
    }.get(task_key, "join")


_TASK_SETTINGS_KEY = {
    "neurocommenting": "neurocommenting",
    "chat_monitoring": "chat_monitoring",
    "neurochatting": "neurochatting",
    "neuroshilling": "neuroshilling",
    "chat_broadcasts": "chat_broadcasts",
    "parser": "parser",
    "masslooking": "masslooking",
    "warmup": "warmup",
}


def module_settings_for_task(automation: CustomAutomation | None, task_key: str) -> dict[str, Any]:
    blob = getattr(automation, "module_settings", None) or {}
    key = _TASK_SETTINGS_KEY.get(task_key, task_key)
    data = blob.get(key) if isinstance(blob, dict) else None
    return dict(data) if isinstance(data, dict) else {}


def task_join_delay_seconds(automation: CustomAutomation | None, task_key: str) -> float:
    """Pause between task joins from join_delay_min/max — not comment delays."""
    import random

    from .module_delays import clamp_join_delay_pair

    lo, hi = clamp_join_delay_pair(module_settings_for_task(automation, task_key))
    return float(random.uniform(lo, hi))

_ADDLIST_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/addlist/([A-Za-z0-9_-]{8,64})",
    re.IGNORECASE,
)


def parse_addlist_slug(raw: str | None) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    match = _ADDLIST_RE.search(text)
    if match:
        return match.group(1)
    parsed = urlparse(text if "://" in text else f"https://{text}")
    parts = [part for part in unquote(parsed.path or "").split("/") if part]
    if len(parts) >= 2 and parts[0].lower() == "addlist" and re.fullmatch(r"[A-Za-z0-9_-]{8,64}", parts[1]):
        return parts[1]
    return None


def addlist_url(slug: str) -> str:
    return f"https://t.me/addlist/{slug}"


def chat_addlist_slug(chat: ChatTarget | None) -> str | None:
    if chat is None:
        return None
    blob = chat.monitoring_config if isinstance(getattr(chat, "monitoring_config", None), dict) else {}
    slug = parse_addlist_slug(blob.get("addlist_slug") if isinstance(blob, dict) else None)
    if slug:
        return slug
    return parse_addlist_slug(getattr(chat, "invite_link", None))


def set_chat_addlist_slug(chat: ChatTarget, slug: str) -> None:
    blob = dict(chat.monitoring_config or {}) if isinstance(chat.monitoring_config, dict) else {}
    blob["addlist_slug"] = slug
    chat.monitoring_config = blob
    if not parse_addlist_slug(chat.invite_link):
        chat.invite_link = addlist_url(slug)


def addlist_capacity(*, premium: bool = False) -> tuple[int, int]:
    if premium:
        return ADDLIST_CHATS_PREMIUM, ADDLIST_FOLDERS_PREMIUM
    return ADDLIST_CHATS_DEFAULT, ADDLIST_FOLDERS_DEFAULT


def chunk_ids(items: list[int], size: int) -> list[list[int]]:
    if size <= 0:
        return [list(items)] if items else []
    return [items[index:index + size] for index in range(0, len(items), size)]


def even_redistribute(
    account_ids: list[int],
    chat_ids: list[int],
    previous: dict[int, list[int]] | None = None,
    *,
    premium: bool = False,
    max_per_account: int | None = None,
    shuffle: bool = True,
    rng: Any = None,
    folder_of: dict[int, int] | None = None,
) -> dict[int, list[int]]:
    """Keep valid previous assignments, then fill least-loaded accounts.

    New workers receive leftover and overflow pending chats. Already assigned
    chats stay with their account so we do not yank memberships.
    Incoming unassigned chats are shuffled so two folders mix in the working 50
    instead of the first file filling every slot and the second sitting in reserve.
    Previous owners keep their chats up to the cap so adding accounts only
    draws from leftover / reserve.
    Remaining chats prefer an account that already holds the same folder.
    """
    accounts = [int(item) for item in dict.fromkeys(account_ids or []) if int(item) > 0]
    chats = [int(item) for item in dict.fromkeys(chat_ids or []) if int(item) > 0]
    if not accounts or not chats:
        return {aid: [] for aid in accounts}
    per_folder, folders = addlist_capacity(premium=premium)
    cap = int(max_per_account) if max_per_account is not None else per_folder * folders
    cap = max(1, cap)
    even = max(1, min(cap, math.ceil(len(chats) / len(accounts))))
    assignment: dict[int, list[int]] = {aid: [] for aid in accounts}
    assigned: set[int] = set()
    chat_set = set(chats)
    for aid, old in (previous or {}).items():
        if int(aid) not in assignment:
            continue
        for cid in old or []:
            chat_id = int(cid)
            if chat_id not in chat_set or chat_id in assigned:
                continue
            if len(assignment[int(aid)]) >= cap:
                continue
            assignment[int(aid)].append(chat_id)
            assigned.add(chat_id)
    folder_map = {int(cid): int(fid) for cid, fid in (folder_of or {}).items() if fid}
    account_folders: dict[int, set[int]] = {aid: set() for aid in accounts}
    for aid, ids in assignment.items():
        for cid in ids:
            fid = folder_map.get(int(cid))
            if fid:
                account_folders[aid].add(fid)
    remaining = [cid for cid in chats if cid not in assigned]
    if shuffle:
        mixed = list(remaining)
        picker = rng or random
        try:
            picker.shuffle(mixed)
            remaining = mixed
        except Exception:
            remaining = mixed
    for cid in remaining:
        eligible = [aid for aid in accounts if len(assignment[aid]) < min(even, cap)]
        if not eligible:
            eligible = [aid for aid in accounts if len(assignment[aid]) < cap]
        if not eligible:
            break
        fid = folder_map.get(int(cid))
        if fid:
            preferred = [aid for aid in eligible if fid in account_folders[aid]]
            if preferred:
                eligible = preferred
        aid = min(eligible, key=lambda item: (len(assignment[item]), item))
        assignment[aid].append(cid)
        assigned.add(cid)
        if fid:
            account_folders[aid].add(fid)
    return assignment


def claim_joined_folders(
    previous: dict[int, list[int]] | None,
    joined: dict[int, list[int]] | None,
    folder_of: dict[int, int] | None,
    chat_ids: list[int],
    *,
    max_per_account: int = TASK_CHATS_PER_ACCOUNT,
) -> dict[int, list[int]]:
    """Give an account the folder it already joined, and take those chats off others."""
    cap = max(1, int(max_per_account or TASK_CHATS_PER_ACCOUNT))
    folders = {int(cid): int(fid) for cid, fid in (folder_of or {}).items() if fid}
    folder_scores: dict[int, dict[int, int]] = {}
    for aid, ids in (joined or {}).items():
        owner = int(aid)
        for cid in ids or []:
            fid = folders.get(int(cid))
            if not fid:
                continue
            by_account = folder_scores.setdefault(fid, {})
            by_account[owner] = by_account.get(owner, 0) + 1
    claimed_folder = {
        fid: max(scores.items(), key=lambda item: (item[1], -item[0]))[0]
        for fid, scores in folder_scores.items()
        if scores
    }
    if not claimed_folder:
        return {int(aid): list(ids or []) for aid, ids in (previous or {}).items()}
    claimed: dict[int, list[int]] = {aid: [] for aid in dict.fromkeys(claimed_folder.values())}
    seen: set[int] = set()
    for aid, ids in (joined or {}).items():
        if int(aid) not in claimed:
            continue
        for cid in ids or []:
            chat_id = int(cid)
            if chat_id in seen:
                continue
            if claimed_folder.get(folders.get(chat_id)) != int(aid):
                continue
            if len(claimed[int(aid)]) >= cap:
                continue
            claimed[int(aid)].append(chat_id)
            seen.add(chat_id)
    for cid in chat_ids:
        chat_id = int(cid)
        if chat_id in seen:
            continue
        owner = claimed_folder.get(folders.get(chat_id))
        if not owner or len(claimed[owner]) >= cap:
            continue
        claimed[owner].append(chat_id)
        seen.add(chat_id)
    out: dict[int, list[int]] = {}
    for aid, ids in (previous or {}).items():
        if int(aid) in claimed:
            continue
        out[int(aid)] = [int(cid) for cid in ids or [] if int(cid) not in seen]
    for aid, ids in claimed.items():
        out[int(aid)] = list(ids)
    return out


def apply_task_chat_assignment(
    account_ids: list[int],
    chat_ids: list[int],
    previous: dict[int, list[int]] | None = None,
    manual: dict[int, list[int]] | None = None,
    *,
    max_per_account: int = TASK_CHATS_PER_ACCOUNT,
    shuffle: bool = True,
    rng: Any = None,
    folder_of: dict[int, int] | None = None,
) -> dict[int, list[int]]:
    """Honor an explicit per-account split; otherwise even-redistribute.

    Each account gets at most ``max_per_account`` chats. Overflow is left
    unassigned for ``split_task_assignment`` to put into the reserve pool.
    """
    accounts = [int(item) for item in dict.fromkeys(account_ids or []) if int(item) > 0]
    chats = [int(item) for item in dict.fromkeys(chat_ids or []) if int(item) > 0]
    cap = max(1, int(max_per_account or TASK_CHATS_PER_ACCOUNT))
    if not accounts:
        return {}
    if manual:
        assignment: dict[int, list[int]] = {aid: [] for aid in accounts}
        assigned: set[int] = set()
        chat_set = set(chats)
        for aid in accounts:
            for cid in manual.get(aid) or []:
                chat_id = int(cid)
                if chat_id not in chat_set or chat_id in assigned:
                    continue
                if len(assignment[aid]) >= cap:
                    continue
                assignment[aid].append(chat_id)
                assigned.add(chat_id)
        return assignment
    return even_redistribute(
        accounts,
        chats,
        previous,
        max_per_account=cap,
        shuffle=shuffle,
        rng=rng,
        folder_of=folder_of,
    )


def split_task_assignment(
    account_ids: list[int],
    chat_ids: list[int],
    previous: dict[int, list[int]] | None = None,
    manual: dict[int, list[int]] | None = None,
    stored_reserve: list[int] | None = None,
    *,
    max_per_account: int = TASK_CHATS_PER_ACCOUNT,
    shuffle: bool = True,
    rng: Any = None,
    folder_of: dict[int, int] | None = None,
) -> tuple[dict[int, list[int]], list[int]]:
    """Assign up to 50 chats per account; leftovers become the reserve pool."""
    chats = [int(item) for item in dict.fromkeys(chat_ids or []) if int(item) > 0]
    assignment = apply_task_chat_assignment(
        account_ids,
        chats,
        previous=previous,
        manual=manual,
        max_per_account=max_per_account,
        shuffle=shuffle,
        rng=rng,
        folder_of=folder_of,
    )
    assigned: set[int] = set()
    for ids in assignment.values():
        assigned.update(ids)
    reserve_source = [int(item) for item in dict.fromkeys([*(stored_reserve or []), *chats]) if int(item) > 0]
    reserve = [cid for cid in reserve_source if cid not in assigned]
    return assignment, reserve


def sibling_previous(
    plans: dict[str, Any] | None,
    task_key: str,
    account_ids: list[int],
) -> dict[int, list[int]]:
    """Chats already given to these accounts in other tasks — keep the same owners."""
    workers = {int(aid) for aid in account_ids or [] if int(aid) > 0}
    owner: dict[int, int] = {}
    for other_key, spec in (plans or {}).items():
        if str(other_key) in _SHARED_PLAN_KEYS or str(other_key) == str(task_key):
            continue
        if not isinstance(spec, dict):
            continue
        for key, value in (spec.get("assignments") or {}).items():
            try:
                aid = int(key)
            except (TypeError, ValueError):
                continue
            if aid not in workers:
                continue
            for cid in _int_list(value):
                owner.setdefault(cid, aid)
    out: dict[int, list[int]] = {}
    for cid, aid in owner.items():
        out.setdefault(aid, []).append(cid)
    return out


async def load_joined_assignment(
    session: AsyncSession,
    automation_id: int,
    account_ids: list[int],
    chat_ids: list[int],
) -> dict[int, list[int]]:
    """Chats these accounts already joined — keep them when mixing a pool."""
    accounts = [int(aid) for aid in account_ids or [] if int(aid) > 0]
    chats = [int(cid) for cid in chat_ids or [] if int(cid) > 0]
    if not accounts or not chats:
        return {}
    rows = (
        await session.execute(
            select(
                AccountChatMembership.social_account_id,
                AccountChatMembership.chat_target_id,
            ).where(
                AccountChatMembership.custom_automation_id == automation_id,
                AccountChatMembership.social_account_id.in_(accounts),
                AccountChatMembership.chat_target_id.in_(chats),
                AccountChatMembership.join_status == ChatJoinStatus.JOINED.value,
            )
        )
    ).all()
    out: dict[int, list[int]] = {}
    for account_id, chat_id in rows:
        out.setdefault(int(account_id), []).append(int(chat_id))
    return out


def warmup_task_joins_enabled(automation: CustomAutomation | None) -> bool:
    """Warmup may join only the chats/folders selected on that module."""
    from .task_targets import has_chat_pool
    from .warmup_module_service import runtime_warmup_cfg, warmup_scheduler_active

    if not warmup_scheduler_active(automation):
        return False
    cfg = runtime_warmup_cfg(automation)
    return cfg.get("do_joins") is not False and has_chat_pool(cfg)


def spec_is_live(spec: dict[str, Any] | None, active: set[str] | None, *, warmup_joins: bool = False) -> bool:
    """Join plans follow running tasks, not leftover module flags or uploaded folders."""
    key = str((spec or {}).get("task_key") or "")
    if not key:
        return False
    live = {str(item) for item in (active or set())}
    if key == "warmup":
        return warmup_joins or "warmup" in live
    return _log_job_type(key) in live


def collect_plan_addlists(plans: dict[str, Any] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, spec in (plans or {}).items():
        if str(key) in _SHARED_PLAN_KEYS or not isinstance(spec, dict):
            continue
        folders = spec.get("folders") if isinstance(spec.get("folders"), dict) else {}
        for rows in folders.values():
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                slug = str(row.get("slug") or "").strip()
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                items.append(row)
    return items


def addlists_from_chat_targets(chats: list[ChatTarget] | None) -> list[dict[str, Any]]:
    by_slug: dict[str, list[int]] = {}
    for chat in chats or []:
        slug = chat_addlist_slug(chat)
        if not slug:
            continue
        by_slug.setdefault(slug, []).append(int(chat.id))
    return [
        {"slug": slug, "url": addlist_url(slug), "chat_ids": ids}
        for slug, ids in by_slug.items()
    ]


def best_addlist_for_chats(
    rows: list[dict[str, Any]] | None,
    chat_ids: list[int],
) -> tuple[dict[str, Any] | None, list[int]]:
    """Pick the addlist that covers the most pending chats."""
    wanted = {int(cid) for cid in chat_ids or [] if int(cid) > 0}
    best: dict[str, Any] | None = None
    best_cover: list[int] = []
    for row in rows or []:
        if not isinstance(row, dict) or not str(row.get("slug") or "").strip():
            continue
        cover = [cid for cid in _int_list(row.get("chat_ids")) if cid in wanted]
        if len(cover) > len(best_cover):
            best = row
            best_cover = cover
    return best, best_cover


def covering_addlist_rows(plans: dict[str, Any] | None, chat_ids: list[int]) -> list[dict[str, Any]]:
    wanted = {int(cid) for cid in chat_ids or [] if int(cid) > 0}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in collect_plan_addlists(plans):
        slug = str(row.get("slug") or "").strip()
        if not slug or slug in seen:
            continue
        if not wanted.intersection(_int_list(row.get("chat_ids"))):
            continue
        seen.add(slug)
        rows.append(row)
    return rows


def merge_sibling_folders(
    plans: dict[str, Any] | None,
    assignment: dict[int, list[int]],
    stored_folders: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy ready addlists from other tasks onto this assignment."""
    out: dict[str, Any] = dict(stored_folders or {})
    for aid, ids in (assignment or {}).items():
        key = str(int(aid))
        rows = [row for row in (out.get(key) or []) if isinstance(row, dict)]
        seen = {str(row.get("slug") or "") for row in rows}
        for row in covering_addlist_rows(plans, ids):
            slug = str(row.get("slug") or "").strip()
            if not slug or slug in seen:
                continue
            rows.append(
                {
                    "slug": slug,
                    "url": str(row.get("url") or addlist_url(slug)),
                    "filter_id": row.get("filter_id"),
                    "chat_ids": _int_list(row.get("chat_ids")),
                }
            )
            seen.add(slug)
        if rows:
            out[key] = rows
    return out


def attach_addlist_row(plans: dict[str, Any], account_id: int, row: dict[str, Any] | None) -> None:
    if not row or not str(row.get("slug") or "").strip():
        return
    slug = str(row.get("slug") or "").strip()
    folder_chats = set(_int_list(row.get("chat_ids")))
    payload = {
        "slug": slug,
        "url": str(row.get("url") or addlist_url(slug)),
        "filter_id": row.get("filter_id"),
        "chat_ids": _int_list(row.get("chat_ids")),
        "title": str(row.get("title") or "").strip() or None,
        "manual": bool(row.get("manual")),
    }
    for key, spec in list((plans or {}).items()):
        if str(key) in _SHARED_PLAN_KEYS or not isinstance(spec, dict):
            continue
        assigned = {
            cid
            for value in (spec.get("assignments") or {}).values()
            for cid in _int_list(value)
        }
        account_ids: set[int] = set()
        for item in spec.get("assignments") or {}:
            try:
                account_ids.add(int(item))
            except (TypeError, ValueError):
                continue
        if int(account_id) not in account_ids:
            continue
        if assigned and folder_chats and not (folder_chats & assigned):
            continue
        folders = dict(spec.get("folders") or {})
        rows = [item for item in (folders.get(str(account_id)) or []) if isinstance(item, dict)]
        replaced = False
        next_rows: list[dict[str, Any]] = []
        for item in rows:
            if str(item.get("slug") or "") == slug:
                next_rows.append(payload)
                replaced = True
            else:
                next_rows.append(item)
        if not replaced:
            next_rows.append(payload)
        folders[str(account_id)] = next_rows
        spec["folders"] = folders
        plans[key] = spec


def merge_assignment_previous(*sources: dict[int, list[int]] | None) -> dict[int, list[int]]:
    """Later sources win when the same chat appears in more than one plan."""
    owner: dict[int, int] = {}
    for src in sources:
        if not src:
            continue
        for aid, ids in src.items():
            try:
                account_id = int(aid)
            except (TypeError, ValueError):
                continue
            for cid in ids or []:
                try:
                    owner[int(cid)] = account_id
                except (TypeError, ValueError):
                    continue
    out: dict[int, list[int]] = {}
    for cid, aid in owner.items():
        out.setdefault(aid, []).append(cid)
    return out


def load_join_waves(automation: CustomAutomation | None) -> dict[str, Any]:
    blob = getattr(automation, "module_settings", None) or {}
    data = blob.get(TASK_WAVES_KEY) if isinstance(blob, dict) else None
    return dict(data) if isinstance(data, dict) else {}


def store_join_waves(automation: CustomAutomation, waves: dict[str, Any]) -> None:
    blob = dict(automation.module_settings or {})
    blob[TASK_WAVES_KEY] = waves
    automation.module_settings = blob
    automation.updated_at = _utc_now()


def account_wave_state(
    automation: CustomAutomation | None,
    account_id: int,
    plans: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One rest/wave clock per account across all tasks."""
    shared = load_join_waves(automation)
    wave = dict(shared.get(str(account_id)) or {}) if isinstance(shared.get(str(account_id)), dict) else {}
    rest = parse_wave_rest_until(wave.get("rest_until"))
    if rest:
        return wave
    latest = wave
    latest_rest = rest
    for spec in (plans or {}).values():
        if not isinstance(spec, dict):
            continue
        rows = spec.get("waves") if isinstance(spec.get("waves"), dict) else {}
        row = rows.get(str(account_id)) if isinstance(rows, dict) else None
        if not isinstance(row, dict):
            continue
        until = parse_wave_rest_until(row.get("rest_until"))
        if until and (latest_rest is None or until > latest_rest):
            latest_rest = until
            latest = dict(row)
    return latest


def pick_join_wave(pending_ids: list[int], *, rng: Any = None, size: int | None = None) -> list[int]:
    """Random 10–15 chats (or all remaining) for one join wave."""
    pool = [int(item) for item in dict.fromkeys(pending_ids or []) if int(item) > 0]
    if not pool:
        return []
    picker = rng or random
    want = int(size) if size is not None else picker.randint(JOIN_WAVE_MIN, JOIN_WAVE_MAX)
    take = min(len(pool), max(1, want))
    if take >= len(pool):
        shuffled = list(pool)
        picker.shuffle(shuffled)
        return shuffled
    return picker.sample(pool, take)


def wave_quota_hit(wave: dict[str, Any] | None, already_joined: int = 0) -> bool:
    """True when this day's successful joins already reached the wave target."""
    data = wave if isinstance(wave, dict) else {}
    tracked = data.get("joined")
    target = int(data.get("size") or JOIN_WAVE_MIN)
    if tracked is not None:
        return int(tracked) >= max(1, target)
    return int(already_joined or 0) >= JOIN_WAVE_MIN


def wave_rest_until(now: datetime | None = None) -> datetime:
    """No more joins for the rest of this Moscow day and the next full day."""
    from .account_pacing import moscow_day_start_utc

    stamp = now or _utc_now()
    return moscow_day_start_utc(stamp) + timedelta(days=2)


def parse_wave_rest_until(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value


def normalize_chat_assignments(raw: Any) -> dict[str, list[int]]:
    """account_id -> chat_ids, as stored on module settings."""
    blob = raw if isinstance(raw, dict) else {}
    out: dict[str, list[int]] = {}
    for key, value in blob.items():
        try:
            aid = int(key)
        except (TypeError, ValueError):
            continue
        if aid <= 0:
            continue
        out[str(aid)] = _int_list(value)
    return out


def split_link_tokens(raw: str | None) -> list[str]:
    tokens: list[str] = []
    for line in str(raw or "").replace(",", " ").splitlines():
        tokens.extend(part.strip() for part in line.split() if part.strip())
    return tokens


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _int_list(raw: Any) -> list[int]:
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


_JOB_TYPE_TO_TASK = {
    "neurocommenting": "neurocommenting",
    "chat_monitoring": "chat_monitoring",
    "discussion": "neurochatting",
    "shilling": "neuroshilling",
    "chat_broadcast": "chat_broadcasts",
    "parser": "parser",
    "masslooking": "masslooking",
    "warmup": "warmup",
}


def host_export_chat_ids(pending: list[int] | None, assigned: list[int] | None) -> list[int]:
    """Chats the host must export: still-pending plus already-joined assigned."""
    return list(dict.fromkeys([*(pending or []), *(assigned or [])]))


def joins_complete_by_job_type(automation: CustomAutomation | None) -> dict[str, bool]:
    plans = _plans_blob(automation) if automation is not None else {}
    out: dict[str, bool] = {}
    for job_type, task_key in _JOB_TYPE_TO_TASK.items():
        spec = plans.get(task_key)
        if isinstance(spec, dict) and "joins_complete" in spec:
            out[job_type] = bool(spec.get("joins_complete"))
        else:
            out[job_type] = False
    return out


def _plans_blob(automation: CustomAutomation | None) -> dict[str, Any]:
    blob = dict(getattr(automation, "module_settings", None) or {})
    plans = blob.get(TASK_JOINS_KEY)
    return dict(plans) if isinstance(plans, dict) else {}


def _store_plans(automation: CustomAutomation, plans: dict[str, Any]) -> None:
    blob = dict(automation.module_settings or {})
    blob[TASK_JOINS_KEY] = plans
    automation.module_settings = blob
    automation.updated_at = _utc_now()


def collect_task_join_specs(automation: CustomAutomation) -> list[dict[str, Any]]:
    """Enabled modules that need selected workers to join a chat pool.

    Folder ids are expanded by ``collect_task_join_specs_resolved``.
    """
    blob = automation.module_settings or {}
    specs: list[dict[str, Any]] = []

    def _push(key: str, settings: dict[str, Any], chat_ids: list[int], *, skip: bool = False) -> None:
        if skip or not settings.get("enabled"):
            return
        chats = _int_list(chat_ids)
        folders = _int_list(settings.get("folder_ids"))
        if chats or folders:
            specs.append({
                "task_key": key,
                "account_ids": _int_list(settings.get("account_ids")),
                "chat_ids": chats,
                "settings": settings,
            })

    nc = blob.get("neurocommenting") if isinstance(blob.get("neurocommenting"), dict) else {}
    if nc.get("enabled") or getattr(automation, "is_neurocommenting_enabled", False):
        settings = dict(nc)
        settings["enabled"] = True
        _push("neurocommenting", settings, settings.get("chat_ids") or [])

    monitor = blob.get("chat_monitoring") if isinstance(blob.get("chat_monitoring"), dict) else {}
    if monitor.get("enabled") or getattr(automation, "is_chat_monitoring_enabled", False):
        settings = dict(monitor)
        settings["enabled"] = True
        _push("chat_monitoring", settings, settings.get("chat_ids") or [])

    chatting = blob.get("neurochatting") if isinstance(blob.get("neurochatting"), dict) else {}
    if chatting.get("enabled") or getattr(automation, "is_digital_footprint_enabled", False):
        settings = dict(chatting)
        settings["enabled"] = True
        _push("neurochatting", settings, settings.get("chat_ids") or [], skip=bool(settings.get("only_joined")))

    shill = blob.get("neuroshilling") if isinstance(blob.get("neuroshilling"), dict) else {}
    if shill.get("enabled") or getattr(automation, "is_shilling_enabled", False):
        settings = dict(shill)
        settings["enabled"] = True
        _push("neuroshilling", settings, [*(settings.get("chat_ids") or []), *(settings.get("channel_ids") or [])])

    bc = blob.get("chat_broadcasts") if isinstance(blob.get("chat_broadcasts"), dict) else {}
    _push("chat_broadcasts", bc, bc.get("chat_ids") or [], skip=bool(bc.get("only_joined", True)))

    parser = blob.get("parser") if isinstance(blob.get("parser"), dict) else {}
    _push("parser", parser, parser.get("chat_ids") or [], skip=parser.get("do_join") is False)

    warmup = blob.get("warmup") if isinstance(blob.get("warmup"), dict) else {}
    if getattr(automation, "account_warmup_enabled", False):
        settings = dict(warmup)
        settings["enabled"] = True
        _push("warmup", settings, settings.get("chat_ids") or [], skip=settings.get("do_joins") is False)
    looking = blob.get("masslooking") if isinstance(blob.get("masslooking"), dict) else {}
    _push("masslooking", looking, looking.get("chat_ids") or [])
    return specs


async def collect_task_join_specs_resolved(session: AsyncSession, automation: CustomAutomation) -> list[dict[str, Any]]:
    from .rotation_service import list_alive_session_accounts
    from .task_targets import resolve_task_chat_ids

    resolved: list[dict[str, Any]] = []
    live_ids: list[int] | None = None
    for spec in collect_task_join_specs(automation):
        chats = await resolve_task_chat_ids(
            session,
            automation.id,
            spec.get("settings") or spec,
            task_key=spec.get("task_key"),
        )
        if not chats:
            continue
        accounts = _int_list(spec.get("account_ids"))
        if not accounts:
            if live_ids is None:
                live_ids = [account.id for account in await list_alive_session_accounts(session, automation.id)]
            accounts = list(live_ids)
        if not accounts:
            continue
        resolved.append({**spec, "chat_ids": chats, "account_ids": accounts})
    return resolved


async def import_chat_links(
    session: AsyncSession,
    automation_id: int,
    raw_links: str,
    *,
    mode: str | None = None,
) -> tuple[list[int], list[str]]:
    from .chat_join_service import create_chat_from_link

    added: list[int] = []
    errors: list[str] = []
    for token in split_link_tokens(raw_links):
        slug = parse_addlist_slug(token)
        if slug:
            ids, errs = await import_addlist_chats(session, automation_id, slug, mode=mode)
            added.extend(ids)
            errors.extend(errs)
            continue
        try:
            chat = await create_chat_from_link(session, automation_id, token, mode=mode)
            added.append(chat.id)
        except ValueError as exc:
            message = str(exc)
            if "уже добавлен" in message.lower():
                existing = await _existing_from_token(session, automation_id, token)
                if existing:
                    added.append(existing.id)
                    continue
            errors.append(f"{token}: {exc}")
        except Exception as exc:
            errors.append(f"{token}: {exc}")
    return list(dict.fromkeys(added)), errors


async def _existing_from_token(session: AsyncSession, automation_id: int, token: str) -> ChatTarget | None:
    try:
        parsed = parse_telegram_chat_ref(token)
    except TelegramChatRefError:
        return None
    return await find_existing_chat_target(
        session,
        automation_id,
        invite_link=parsed.canonical,
        external_chat_id=parsed.value if parsed.kind == "channel_id" else None,
    )


def _peer_chat_fields(peer: Any) -> tuple[str | None, str | None, str | None]:
    username = (getattr(peer, "username", None) or "").strip()
    title = getattr(peer, "title", None) or getattr(peer, "first_name", None)
    channel_id = getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None) or getattr(peer, "id", None)
    invite = f"https://t.me/{username}" if username else None
    external = f"-100{channel_id}" if channel_id and not username else (str(channel_id) if channel_id else None)
    if not invite and channel_id:
        invite = f"https://t.me/c/{channel_id}"
    return invite, external, str(title) if title else None


async def import_addlist_chats(
    session: AsyncSession,
    automation_id: int,
    slug: str,
    *,
    mode: str | None = None,
) -> tuple[list[int], list[str]]:
    from .telegram_account_client import TelegramAccountClient

    accounts = await list_alive_session_accounts(session, automation_id)
    if not accounts:
        return [], [f"https://t.me/addlist/{slug}: нужен живой аккаунт, чтобы раскрыть папку"]
    peers: list[Any] = []
    title = ""
    try:
        async with TelegramAccountClient.for_account(accounts[0]) as client:
            peers, title = await _check_addlist_peers(client, slug)
    except Exception as exc:
        logger.warning("Addlist preview failed slug=%s: %s", slug, exc)
        return [], [f"https://t.me/addlist/{slug}: {exc}"]
    if not peers:
        return [], [f"https://t.me/addlist/{slug}: папка пустая или недоступна"]
    added: list[int] = []
    now = _utc_now()
    for peer in peers:
        invite, external, chat_title = _peer_chat_fields(peer)
        existing = await find_existing_chat_target(
            session, automation_id, invite_link=invite, external_chat_id=external, title=chat_title
        )
        if existing:
            set_chat_addlist_slug(existing, slug)
            added.append(existing.id)
            continue
        chat = ChatTarget(
            custom_automation_id=automation_id,
            provider="telegram",
            invite_link=invite or addlist_url(slug),
            external_chat_id=external,
            title=chat_title or title or slug,
            mode=(mode or "").strip() or ChatMode.MONITORING.value,
            source=ChatSource.MANUAL.value,
            join_status=ChatJoinStatus.PENDING.value,
            join_attempts=0,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(chat)
        await session.flush()
        set_chat_addlist_slug(chat, slug)
        added.append(chat.id)
    await session.commit()
    return list(dict.fromkeys(added)), []


async def _check_addlist_peers(client: Any, slug: str) -> tuple[list[Any], str]:
    from telethon.tl.functions.chatlists import CheckChatlistInviteRequest

    telethon = getattr(client, "client", client)
    result = await telethon(CheckChatlistInviteRequest(slug=slug))
    title = str(getattr(result, "title", "") or getattr(getattr(result, "filter", None), "title", "") or "")
    peers = list(getattr(result, "peers", None) or getattr(result, "missing_peers", None) or [])
    already = list(getattr(result, "already_peers", None) or [])
    return peers or already, title


async def ensure_task_joins_for_automation(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return {"tasks": 0}
    from .job_service import list_active_job_types

    active = await list_active_job_types(automation_id)
    warmup_joins = warmup_task_joins_enabled(automation)
    summary = {"tasks": 0, "joined": 0, "folders": 0}
    for spec in await collect_task_join_specs_resolved(session, automation):
        if not spec_is_live(spec, active, warmup_joins=warmup_joins):
            continue
        result = await ensure_task_join_plan(
            session,
            automation,
            spec["task_key"],
            spec["account_ids"],
            spec["chat_ids"],
        )
        summary["tasks"] += 1
        summary["joined"] += int(result.get("joined") or 0)
        summary["folders"] += int(result.get("folders") or 0)
    return summary


async def ensure_task_join_plan(
    session: AsyncSession,
    automation: CustomAutomation,
    task_key: str,
    account_ids: list[int],
    chat_ids: list[int],
    *,
    mix: bool = False,
) -> dict[str, Any]:
    """Keep per-account pools (max 50) and a reserve; joins happen in 15–20 waves."""
    alive = {
        account.id: account
        for account in await list_alive_session_accounts(session, automation.id, exclude_flood=False)
    }
    workers = [aid for aid in account_ids if aid in alive]
    chats = (
        await session.execute(
            select(ChatTarget).where(
                ChatTarget.custom_automation_id == automation.id,
                ChatTarget.id.in_(chat_ids or [0]),
                ChatTarget.black_boxed_at.is_(None),
            )
        )
    ).scalars().all()
    from .task_targets import chat_matches_resource_kind, task_resource_kind

    kind = task_resource_kind(task_key)
    typed = [
        chat
        for chat in chats
        if chat_matches_resource_kind(chat, kind)
        and (getattr(chat, "mod_status", None) or "") != "moderated"
    ]
    typed_by_id = {chat.id: chat for chat in typed}
    chat_map = {
        chat.id: chat
        for chat in typed
        if not (kind == "channel" and chat.comments_open is False)
    }
    if not workers or not typed_by_id:
        return {"joined": 0, "folders": 0}
    plans = _plans_blob(automation)
    stored_task = plans.get(task_key) if isinstance(plans.get(task_key), dict) else {}
    previous_raw = (stored_task or {}).get("assignments") or {}
    previous = {int(key): _int_list(value) for key, value in previous_raw.items()}
    settings_assign = normalize_chat_assignments(
        module_settings_for_task(automation, task_key).get("chat_assignments")
    )
    joined_map = await load_joined_assignment(session, automation.id, workers, list(typed_by_id.keys()))
    extra_ids = [
        cid
        for ids in list(previous.values()) + list(joined_map.values()) + list(settings_assign.values())
        for cid in ids
        if cid not in chat_map
    ]
    for cid, chat in typed_by_id.items():
        if cid in {item for ids in joined_map.values() for item in ids}:
            chat_map[cid] = chat
    if extra_ids:
        extra_chats = (
            await session.execute(
                select(ChatTarget).where(
                    ChatTarget.custom_automation_id == automation.id,
                    ChatTarget.id.in_(extra_ids),
                    ChatTarget.black_boxed_at.is_(None),
                )
            )
        ).scalars().all()
        for chat in extra_chats:
            if (getattr(chat, "mod_status", None) or "") == "moderated":
                continue
            if not chat_matches_resource_kind(chat, kind):
                continue
            chat_map[chat.id] = chat
        joined_map = await load_joined_assignment(session, automation.id, workers, list(chat_map.keys()))
    if mix:
        previous = merge_assignment_previous(
            sibling_previous(plans, task_key, workers),
            joined_map,
        )
    else:
        previous = merge_assignment_previous(
            previous,
            settings_assign,
            sibling_previous(plans, task_key, workers),
            joined_map,
        )
    folder_of = {
        int(chat.id): int(chat.folder_id)
        for chat in chat_map.values()
        if getattr(chat, "folder_id", None)
    }
    previous = claim_joined_folders(
        previous,
        joined_map,
        folder_of,
        list(chat_map.keys()),
        max_per_account=TASK_CHATS_PER_ACCOUNT,
    )
    assignment, reserve = split_task_assignment(
        workers,
        list(chat_map.keys()),
        previous=previous,
        stored_reserve=_int_list((stored_task or {}).get("reserve")),
        folder_of=folder_of,
    )
    await _upsert_actor_memberships(session, automation.id, assignment)
    stored_folders = (stored_task or {}).get("folders") if isinstance(stored_task, dict) else {}
    if not isinstance(stored_folders, dict):
        stored_folders = {}
    stored_folders = merge_sibling_folders(plans, assignment, stored_folders)
    joined = await load_joined_assignment(
        session,
        automation.id,
        list(assignment.keys()),
        [cid for ids in assignment.values() for cid in ids],
    )
    joined_pairs = {(int(aid), int(cid)) for aid, ids in joined.items() for cid in ids}
    pending_left = sum(
        1
        for aid, ids in assignment.items()
        for cid in ids
        if (int(aid), int(cid)) not in joined_pairs
    )
    key = _TASK_SETTINGS_KEY.get(task_key, task_key)
    blob = dict(automation.module_settings or {})
    settings = dict(blob.get(key) or {}) if isinstance(blob.get(key), dict) else {}
    settings["chat_assignments"] = {str(aid): ids for aid, ids in assignment.items()}
    settings["reserve_chat_ids"] = reserve
    blob[key] = settings
    automation.module_settings = blob
    plans[task_key] = {
        "assignments": {str(aid): ids for aid, ids in assignment.items()},
        "reserve": reserve,
        "folders": stored_folders,
        "waves": dict((stored_task or {}).get("waves") or {}) if isinstance((stored_task or {}).get("waves"), dict) else {},
        "premium": dict((stored_task or {}).get("premium") or {}),
        "host_account_id": (stored_task or {}).get("host_account_id") or workers[0],
        "joins_complete": pending_left == 0 and bool(assignment),
        "pending_joins": pending_left,
        "manual": False if mix else bool((stored_task or {}).get("manual")),
        "updated_at": _utc_now().isoformat(),
    }
    _store_plans(automation, plans)
    await session.commit()
    return {"joined": 0, "folders": 0, "assignment": assignment, "reserve": reserve}


async def _bootstrap_host_for_export(
    session: AsyncSession,
    *,
    host: SocialAccount,
    chat_map: dict[int, ChatTarget],
    needed_ids: list[int],
    folder_slugs: dict[int, str],
    job_type: str,
    automation: CustomAutomation,
    task_key: str,
    stored_folders: dict[str, Any],
) -> int:
    """Host joins chats it is not in, then grows a shareable folder for workers.

    Telegram cannot mint an addlist from vacuum: the host must already sit in
    the peers. After each JoinChannel we UpdateDialogFilter + export/edit the
    invite so the next account joins the grown folder instead of starting over.
    """
    from .telegram_account_client import TelegramAccountClient
    from .job_service import actor_label, chat_label, log_active
    from .account_pacing import account_membership_should_idle, farm_overlap_active_hours
    from .work_mode import work_mode_from_automation
    from .chat_membership_service import apply_account_join_cooldown

    automation_id = automation.id
    if await _skip_join_for_flood(session, host):
        return 0
    marked = 0
    missing = [cid for cid in needed_ids if not await account_is_joined(session, cid, host.id)]
    if not missing:
        await _grow_host_folder_after_join(
            session,
            host=host,
            chat_map=chat_map,
            needed_ids=needed_ids,
            stored_folders=stored_folders,
        )
        return 0
    if account_membership_should_idle(host):
        return 0
    if not farm_overlap_active_hours(mode=work_mode_from_automation(automation)):
        return 0
    slugs = list(dict.fromkeys(folder_slugs[cid] for cid in missing if folder_slugs.get(cid)))
    if slugs:
        try:
            async with TelegramAccountClient.for_account(host) as client:
                for slug in slugs:
                    await _join_addlist(client, slug)
                    covered = [cid for cid, value in folder_slugs.items() if value == slug]
                    marked += await _mark_joined(
                        session, host.id, covered, automation_id=automation_id
                    )
                    await log_active(
                        automation_id,
                        job_type,
                        f"{actor_label(host)} вступил в исходную папку t.me/addlist/{slug} "
                        f"(хост, чтобы раздать пулы)",
                    )
        except Exception as exc:
            if _is_flood_error(exc):
                _park_join_flood(host, exc)
                return marked
            logger.warning("Host folder addlist join failed account=%s: %s", host.id, exc)
        if marked:
            await _grow_host_folder_after_join(
                session,
                host=host,
                chat_map=chat_map,
                needed_ids=needed_ids,
                stored_folders=stored_folders,
            )
            delay = task_join_delay_seconds(automation, task_key)
            await apply_account_join_cooldown(
                session, automation_id, host.id, wait_seconds=delay
            )
            return marked
    remaining = [
        cid
        for cid in missing
        if not await account_is_joined(session, cid, host.id)
    ]
    if not remaining:
        await _grow_host_folder_after_join(
            session,
            host=host,
            chat_map=chat_map,
            needed_ids=needed_ids,
            stored_folders=stored_folders,
        )
        return marked
    from .chat_join_service import _try_join_chat

    joined_now = 0
    for chat_id in remaining:
        if joined_now >= HOST_BOOTSTRAP_JOINS_PER_TICK:
            break
        chat = chat_map.get(chat_id)
        if not chat:
            continue
        try:
            result = await _try_join_chat(session, chat, host)
            if result.get("status") == "rate_limited":
                _park_join_flood(host, result.get("error"))
                break
            if result.get("status") != "joined":
                continue
            marked += await _mark_joined(
                session, host.id, [chat_id], automation_id=automation_id
            )
            joined_now += 1
            grown = await _grow_host_folder_after_join(
                session,
                host=host,
                chat_map=chat_map,
                needed_ids=needed_ids,
                stored_folders=stored_folders,
            )
            delay = task_join_delay_seconds(automation, task_key)
            await apply_account_join_cooldown(
                session, automation_id, host.id, wait_seconds=delay
            )
            extra = ""
            if grown and grown.get("slug"):
                extra = f", папка обновлена t.me/addlist/{grown['slug']} ({len(_int_list(grown.get('chat_ids')))} чатов)"
            await log_active(
                automation_id,
                job_type,
                f"{actor_label(host)} вступил в {chat_label(chat)} "
                f"(хост, пауза {int(delay)}с{extra})",
            )
        except Exception as exc:
            if _is_flood_error(exc):
                _park_join_flood(host, exc)
                break
            logger.debug("Host bootstrap join skipped chat=%s: %s", chat_id, exc)
    return marked


async def _grow_host_folder_after_join(
    session: AsyncSession,
    *,
    host: SocialAccount,
    chat_map: dict[int, ChatTarget],
    needed_ids: list[int],
    stored_folders: dict[str, Any],
) -> dict[str, Any] | None:
    """Rebuild the host shareable folder from chats it already sits in."""
    from .telegram_account_client import TelegramAccountClient

    joined_ids = [
        cid for cid in dict.fromkeys(needed_ids)
        if cid in chat_map and await account_is_joined(session, cid, host.id)
    ]
    if not joined_ids:
        return None
    previous = _latest_folder_row(stored_folders.get(str(host.id)))
    joined_ids = merge_folder_chat_ids(previous, joined_ids)
    premium = await _account_is_premium(host)
    per_folder, _cap = addlist_capacity(premium=premium)
    chunk = [cid for cid in joined_ids[:per_folder] if cid in chat_map]
    chats = [chat_map[cid] for cid in chunk]
    try:
        async with TelegramAccountClient.for_account(host) as client:
            slug, filter_id = await _upsert_shareable_folder(
                client,
                chats,
                filter_id=int(previous["filter_id"]) if previous and previous.get("filter_id") else None,
                slug=str(previous["slug"]) if previous and previous.get("slug") else None,
            )
    except Exception as exc:
        logger.warning("Host folder grow failed account=%s: %s", host.id, exc)
        return None
    if not slug:
        return None
    row = {
        "slug": slug,
        "url": addlist_url(slug),
        "filter_id": filter_id,
        "chat_ids": chunk,
    }
    for chat in chats:
        set_chat_addlist_slug(chat, slug)
    stored_folders[str(host.id)] = [row]
    return row


def _latest_folder_row(stored: Any) -> dict[str, Any] | None:
    rows = stored if isinstance(stored, list) else []
    for row in reversed(rows):
        if isinstance(row, dict) and row.get("slug"):
            return row
    return None


def merge_folder_chat_ids(previous: dict[str, Any] | None, extra: list[int]) -> list[int]:
    """Grow a folder's chat set: keep what was already exported, append new joins."""
    return list(dict.fromkeys(_int_list((previous or {}).get("chat_ids")) + list(extra or [])))


async def _upsert_actor_memberships(
    session: AsyncSession,
    automation_id: int,
    assignment: dict[int, list[int]],
) -> None:
    now = _utc_now()
    for account_id, chat_ids in assignment.items():
        for chat_id in chat_ids:
            membership = await get_membership(session, chat_id, account_id)
            if membership:
                if membership.purpose != ACTOR_PURPOSE:
                    membership.purpose = ACTOR_PURPOSE
                    membership.priority = max(int(membership.priority or 0), ACTION_JOIN_PRIORITY)
                    membership.updated_at = now
                continue
            session.add(
                AccountChatMembership(
                    custom_automation_id=automation_id,
                    social_account_id=account_id,
                    chat_target_id=chat_id,
                    join_status=ChatJoinStatus.PENDING.value,
                    purpose=ACTOR_PURPOSE,
                    priority=ACTION_JOIN_PRIORITY,
                    join_attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )
    await session.flush()


def _reusable_folders(
    stored: list[dict[str, Any]],
    assigned: list[int],
) -> tuple[list[dict[str, Any]], set[int]]:
    assigned_set = set(assigned)
    reusable: list[dict[str, Any]] = []
    covered: set[int] = set()
    for row in stored or []:
        ids = _int_list(row.get("chat_ids"))
        slug = str(row.get("slug") or "")
        if not slug or not ids:
            continue
        if all(cid in assigned_set for cid in ids):
            reusable.append(row)
            covered.update(ids)
    return reusable, covered


async def _mark_joined(
    session: AsyncSession,
    account_id: int,
    chat_ids: list[int],
    *,
    automation_id: int | None = None,
    purpose: str = ACTOR_PURPOSE,
) -> int:
    marked = 0
    now = _utc_now()
    for chat_id in dict.fromkeys(chat_ids):
        membership = await get_membership(session, chat_id, account_id)
        if not membership:
            if not automation_id:
                continue
            session.add(
                AccountChatMembership(
                    custom_automation_id=automation_id,
                    social_account_id=account_id,
                    chat_target_id=chat_id,
                    join_status=ChatJoinStatus.JOINED.value,
                    purpose=purpose,
                    priority=ACTION_JOIN_PRIORITY if purpose == ACTOR_PURPOSE else 0,
                    join_attempts=0,
                    joined_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            marked += 1
            continue
        if membership.join_status != ChatJoinStatus.JOINED.value:
            membership.join_status = ChatJoinStatus.JOINED.value
            membership.joined_at = membership.joined_at or now
            membership.last_join_error = None
            membership.next_join_attempt_at = None
            membership.updated_at = now
            marked += 1
    await session.flush()
    return marked


async def _pick_host(
    session: AsyncSession,
    alive: dict[int, SocialAccount],
    workers: list[int],
    chat_ids: list[int],
) -> SocialAccount | None:
    best: SocialAccount | None = None
    best_n = -1
    for account_id in workers:
        account = alive.get(account_id)
        if not account:
            continue
        joined = 0
        for chat_id in chat_ids:
            if await account_is_joined(session, chat_id, account_id):
                joined += 1
        if joined > best_n:
            best_n = joined
            best = account
    return best


async def _account_is_premium(account: SocialAccount) -> bool:
    from .telegram_account_client import TelegramAccountClient

    try:
        async with TelegramAccountClient.for_account(account) as client:
            me = await client.client.get_me()
            return bool(getattr(me, "premium", False))
    except Exception:
        return False


async def _export_and_join_batches(
    *,
    host: SocialAccount | None,
    worker: SocialAccount,
    chats: list[ChatTarget],
    batches: list[list[int]],
    previous: list[dict[str, Any]] | None = None,
    chat_map: dict[int, ChatTarget] | None = None,
) -> list[dict[str, Any]]:
    from .telegram_account_client import TelegramAccountClient

    by_id = {**(chat_map or {}), **{chat.id: chat for chat in chats}}
    rows: list[dict[str, Any]] = []
    if not host:
        host = worker
    prior = _latest_folder_row(previous)
    async with TelegramAccountClient.for_account(host) as host_client:
        for chunk in batches:
            union_ids = merge_folder_chat_ids(prior, chunk)
            subset = [by_id[cid] for cid in union_ids if cid in by_id]
            if not subset:
                continue
            slug, filter_id = await _upsert_shareable_folder(
                host_client,
                subset,
                filter_id=int(prior["filter_id"]) if prior and prior.get("filter_id") else None,
                slug=str(prior["slug"]) if prior and prior.get("slug") else None,
            )
            if not slug:
                continue
            if host.id != worker.id:
                async with TelegramAccountClient.for_account(worker) as worker_client:
                    await _join_addlist(worker_client, slug)
            row = {
                "slug": slug,
                "url": addlist_url(slug),
                "filter_id": filter_id,
                "chat_ids": [chat.id for chat in subset],
            }
            rows.append(row)
            prior = row
            for chat in subset:
                set_chat_addlist_slug(chat, slug)
    return rows


async def _resolve_input_peers(client: Any, chats: list[ChatTarget]) -> list[Any]:
    from .telegram_invite import chat_entity_key

    telethon = getattr(client, "client", client)
    peers: list[Any] = []
    for chat in chats:
        try:
            entity = await telethon.get_input_entity(chat_entity_key(chat))
            peers.append(entity)
        except Exception:
            continue
    return peers


async def _upsert_shareable_folder(
    client: Any,
    chats: list[ChatTarget],
    *,
    filter_id: int | None = None,
    slug: str | None = None,
    title: str | None = None,
) -> tuple[str | None, int | None]:
    """Create or grow a Telegram folder + addlist. Host must already be in `chats`."""
    from telethon.tl import types
    from telethon.tl.functions.chatlists import ExportChatlistInviteRequest
    from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest

    telethon = getattr(client, "client", client)
    peers = await _resolve_input_peers(client, chats)
    if not peers:
        return None, None
    filters = await telethon(GetDialogFiltersRequest())
    existing = list(getattr(filters, "filters", None) or [])
    used = {int(getattr(item, "id", 0) or 0) for item in existing}
    raw_title = str(title or "").strip() or f"UBT {chats[0].id}"
    title = raw_title[:32]
    if filter_id and filter_id in used:
        chosen = int(filter_id)
    else:
        chosen = 2
        while chosen in used:
            chosen += 1
    dialog_filter = _build_dialog_filter(chosen, title, peers)
    await telethon(UpdateDialogFilterRequest(id=chosen, filter=dialog_filter))
    chatlist = types.InputChatlistDialogFilter(filter_id=chosen)
    if slug:
        try:
            from telethon.tl.functions.chatlists import EditExportedInviteRequest

            edited = await telethon(
                EditExportedInviteRequest(chatlist=chatlist, slug=slug, peers=peers, title=title)
            )
            invite = getattr(edited, "invite", edited)
            url = str(getattr(invite, "url", "") or "")
            kept = parse_addlist_slug(url) or slug
            return kept, chosen
        except Exception as exc:
            logger.debug("EditExportedInvite failed slug=%s: %s", slug, exc)
    exported = await telethon(
        ExportChatlistInviteRequest(chatlist=chatlist, title=title, peers=peers)
    )
    invite = getattr(exported, "invite", exported)
    url = str(getattr(invite, "url", "") or "")
    return parse_addlist_slug(url), chosen


async def _export_folder_for_chats(client: Any, chats: list[ChatTarget]) -> tuple[str | None, int | None]:
    return await _upsert_shareable_folder(client, chats)


def _build_dialog_filter(filter_id: int, title: str, peers: list[Any]) -> Any:
    from telethon.tl import types

    kwargs = {
        "id": filter_id,
        "title": title,
        "pinned_peers": [],
        "include_peers": peers,
        "exclude_peers": [],
        "contacts": False,
        "non_contacts": False,
        "groups": False,
        "broadcasts": False,
        "bots": False,
        "exclude_muted": False,
        "exclude_read": False,
        "exclude_archived": False,
    }
    try:
        return types.DialogFilter(**kwargs)
    except TypeError:
        kwargs["title"] = types.TextWithEntities(text=title, entities=[])
        return types.DialogFilter(**kwargs)


async def _join_addlist(client: Any, slug: str, chats: list[ChatTarget] | None = None) -> None:
    from telethon.tl.functions.chatlists import JoinChatlistInviteRequest

    telethon = getattr(client, "client", client)
    peers, _title = await _check_addlist_peers(client, slug)
    if chats:
        wanted = await _resolve_input_peers(client, chats)
        if wanted:
            peers = wanted
    await telethon(JoinChatlistInviteRequest(slug=slug, peers=peers or []))


async def join_pending_addlists(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    """Apply stored addlist slugs for workers that still have pending actor memberships."""
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        return {"joined": 0}
    plans = _plans_blob(automation)
    joined = 0
    alive = {account.id: account for account in await list_alive_session_accounts(session, automation_id)}
    from .telegram_account_client import TelegramAccountClient
    from .chat_membership_service import apply_account_join_cooldown

    for task_key, spec in plans.items():
        if not isinstance(spec, dict):
            continue
        folders = spec.get("folders") or {}
        host_id = spec.get("host_account_id")
        for account_key, rows in folders.items():
            account = alive.get(int(account_key))
            if not account or not rows:
                continue
            if host_id and int(account_key) == int(host_id):
                continue
            if await _skip_join_for_flood(session, account):
                continue
            row = _latest_folder_row(rows)
            slug = str((row or {}).get("slug") or "")
            if not slug:
                continue
            try:
                async with TelegramAccountClient.for_account(account) as client:
                    await _join_addlist(client, slug)
                marked = 0
                for chat_id in _int_list((row or {}).get("chat_ids")):
                    membership = await get_membership(session, chat_id, account.id)
                    if membership and membership.join_status != ChatJoinStatus.JOINED.value:
                        membership.join_status = ChatJoinStatus.JOINED.value
                        membership.joined_at = _utc_now()
                        membership.last_join_error = None
                        membership.next_join_attempt_at = None
                        membership.updated_at = _utc_now()
                        marked += 1
                joined += marked
                delay = task_join_delay_seconds(automation, str(task_key))
                await apply_account_join_cooldown(
                    session, automation_id, account.id, wait_seconds=delay
                )
            except Exception as exc:
                if _is_flood_error(exc):
                    _park_join_flood(account, exc)
                logger.warning("Pending addlist join failed account=%s: %s", account.id, exc)
    if joined:
        await session.commit()
    return {"joined": joined}


_TASK_TITLES = {
    "neurocommenting": "Нейрокомментинг",
    "neurochatting": "Нейрочаттинг",
    "neuroshilling": "Нейрошиллинг",
    "chat_broadcasts": "Чат-рассылки",
    "parser": "Парсер",
    "masslooking": "Масслукинг",
    "warmup": "Прогрев",
}


async def export_manual_addlist(
    session: AsyncSession,
    automation: CustomAutomation,
    *,
    account_id: int,
    chat_ids: list[int],
    task_key: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Build a t.me/addlist from chats this account already joined."""
    from .job_service import actor_label, log_active
    from .rotation_service import list_alive_session_accounts
    from .telegram_account_client import TelegramAccountClient

    wanted = _int_list(chat_ids)
    if not wanted:
        raise ValueError("Выберите каналы или чаты, в которых аккаунт уже состоит")
    roster = {account.id: account for account in await list_alive_session_accounts(session, automation.id, exclude_flood=False)}
    extra = await session.get(SocialAccount, int(account_id))
    if extra is not None:
        roster[int(extra.id)] = extra
    account = roster.get(int(account_id))
    if account is None:
        raise ValueError("Аккаунт не найден")
    chats = list(
        (
            await session.execute(
                select(ChatTarget).where(
                    ChatTarget.custom_automation_id == automation.id,
                    ChatTarget.id.in_(wanted),
                    ChatTarget.black_boxed_at.is_(None),
                )
            )
        ).scalars().all()
    )
    chat_map = {int(chat.id): chat for chat in chats}
    missing = [cid for cid in wanted if cid not in chat_map]
    if missing:
        raise ValueError("Часть выбранных чатов не найдена в этой автоматизации")
    joined: list[ChatTarget] = []
    skipped: list[str] = []
    for cid in wanted:
        chat = chat_map[cid]
        if await account_is_joined(session, cid, account.id):
            joined.append(chat)
        else:
            skipped.append(str(getattr(chat, "title", None) or chat.invite_link or f"#{cid}"))
    if not joined:
        raise ValueError("Аккаунт ещё не состоит в выбранных чатах")
    premium = await _account_is_premium(account)
    per_folder, _cap = addlist_capacity(premium=premium)
    if len(joined) > per_folder:
        joined = joined[:per_folder]
    label = str(title or "").strip() or f"UBT {actor_label(account)}"
    try:
        async with TelegramAccountClient.for_account(account) as client:
            slug, filter_id = await _upsert_shareable_folder(client, joined, title=label)
    except Exception as exc:
        logger.warning("Manual addlist failed account=%s: %s", account.id, exc)
        raise ValueError("Telegram не собрал папку. Проверьте сессию аккаунта.") from exc
    if not slug:
        raise ValueError("Telegram не вернул ссылку addlist")
    row = {
        "slug": slug,
        "url": addlist_url(slug),
        "filter_id": filter_id,
        "chat_ids": [int(chat.id) for chat in joined],
        "title": label,
        "manual": True,
    }
    for chat in joined:
        set_chat_addlist_slug(chat, slug)
    plans = _plans_blob(automation)
    key = str(task_key or "").strip() or "neurocommenting"
    spec = dict(plans.get(key) or {}) if isinstance(plans.get(key), dict) else {}
    folders = dict(spec.get("folders") or {})
    rows = [item for item in (folders.get(str(account.id)) or []) if isinstance(item, dict)]
    rows.append(row)
    folders[str(account.id)] = rows
    spec["folders"] = folders
    plans[key] = spec
    attach_addlist_row(plans, account.id, row)
    _store_plans(automation, plans)
    await session.commit()
    job_type = _log_job_type(key)
    if job_type != "join":
        await log_active(
            automation.id,
            job_type,
            f"{actor_label(account)} собрал addlist {row['url']} ({len(row['chat_ids'])} чатов)",
        )
    if skipped:
        logger.info("Manual addlist skipped unjoined chats account=%s: %s", account.id, skipped[:8])
    return {
        "task_key": key,
        "task_title": label,
        "account_id": account.id,
        "slug": slug,
        "url": row["url"],
        "chat_ids": row["chat_ids"],
        "chat_count": len(row["chat_ids"]),
        "skipped": skipped,
    }


def list_task_addlists(automation: CustomAutomation | None) -> list[dict[str, Any]]:
    """Collected t.me/addlist links for already-built Telegram folders."""
    if automation is None:
        return []
    plans = _plans_blob(automation)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task_key, spec in plans.items():
        if str(task_key) in _SHARED_PLAN_KEYS or not isinstance(spec, dict):
            continue
        folders = spec.get("folders") or {}
        title = _TASK_TITLES.get(str(task_key), str(task_key))
        for account_key, rows in folders.items():
            try:
                account_id = int(account_key)
            except (TypeError, ValueError):
                account_id = 0
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                slug = str(row.get("slug") or "").strip()
                url = str(row.get("url") or "").strip() or (addlist_url(slug) if slug else "")
                if not url or url in seen:
                    continue
                seen.add(url)
                items.append(
                    {
                        "task_key": str(task_key),
                        "task_title": str(row.get("title") or title),
                        "account_id": account_id,
                        "slug": slug,
                        "url": url,
                        "chat_ids": _int_list(row.get("chat_ids")),
                        "chat_count": len(_int_list(row.get("chat_ids"))),
                    }
                )
    return items


def _pool_chat_card(chat: ChatTarget, folders: dict[int, str], *, joined: bool = False) -> dict[str, Any]:
    title = str(getattr(chat, "title", None) or "").strip()
    link = str(getattr(chat, "invite_link", None) or "").strip()
    username = str(getattr(chat, "username", None) or "").strip().lstrip("@")
    if not link and username:
        link = f"https://t.me/{username}"
    folder_id = getattr(chat, "folder_id", None)
    try:
        folder_id = int(folder_id) if folder_id is not None else None
    except (TypeError, ValueError):
        folder_id = None
    return {
        "id": int(chat.id),
        "title": title or link or (f"@{username}" if username else "") or f"чат #{chat.id}",
        "link": link,
        "folder_id": folder_id,
        "folder_name": folders.get(folder_id) if folder_id else None,
        "joined": bool(joined),
    }


async def _sync_live_job_pool(session: AsyncSession, automation: CustomAutomation, task_key: str) -> None:
    from .job_service import VISIBLE_ACTIVE_STATUSES, log_active
    from ...alembic.models import CustomJob

    job_type = _log_job_type(task_key)
    if job_type == "join":
        return
    settings = module_settings_for_task(automation, task_key)
    jobs = (
        await session.execute(
            select(CustomJob).where(
                CustomJob.custom_automation_id == automation.id,
                CustomJob.job_type == job_type,
                CustomJob.status.in_(tuple(VISIBLE_ACTIVE_STATUSES)),
            )
        )
    ).scalars().all()
    if not jobs:
        return
    slice_keys = (
        "account_ids",
        "folder_ids",
        "chat_ids",
        "channel_ids",
        "chat_assignments",
        "reserve_chat_ids",
    )
    for job in jobs:
        merged = dict(job.params or {})
        for key in slice_keys:
            if key in settings:
                merged[key] = settings.get(key)
        job.params = merged
        job.updated_at = _utc_now()
    assigned = sum(len(_int_list(ids)) for ids in (settings.get("chat_assignments") or {}).values())
    reserve = len(_int_list(settings.get("reserve_chat_ids")))
    await log_active(
        automation.id,
        job_type,
        f"Пул обновлён: {len(_int_list(settings.get('account_ids')))} аккаунтов, "
        f"{assigned} каналов в работе, {reserve} в запасе",
    )


async def serialize_task_pool(
    session: AsyncSession,
    automation: CustomAutomation,
    task_key: str,
) -> dict[str, Any]:
    from .chat_folder_service import folder_payloads
    from .job_service import VISIBLE_ACTIVE_STATUSES, actor_label
    from .rotation_service import list_alive_session_accounts
    from ...alembic.models import CustomJob

    settings = module_settings_for_task(automation, task_key)
    plans = _plans_blob(automation)
    stored = plans.get(task_key) if isinstance(plans.get(task_key), dict) else {}
    assignments = {
        int(key): _int_list(value)
        for key, value in ((stored or {}).get("assignments") or settings.get("chat_assignments") or {}).items()
    }
    reserve_ids = _int_list((stored or {}).get("reserve") or settings.get("reserve_chat_ids"))
    account_ids = _int_list(settings.get("account_ids")) or list(assignments.keys())
    folder_ids = _int_list(settings.get("folder_ids"))
    wanted = list(dict.fromkeys([cid for ids in assignments.values() for cid in ids] + reserve_ids))
    chats = []
    if wanted:
        chats = list(
            (
                await session.execute(
                    select(ChatTarget).where(
                        ChatTarget.custom_automation_id == automation.id,
                        ChatTarget.id.in_(wanted),
                    )
                )
            ).scalars().all()
        )
    chat_map = {int(chat.id): chat for chat in chats}
    folder_rows = await folder_payloads(session, automation.id)
    folder_names = {int(item["id"]): str(item.get("name") or "") for item in folder_rows}
    joined = await load_joined_assignment(session, automation.id, account_ids, wanted)
    joined_set = {(aid, cid) for aid, ids in joined.items() for cid in ids}
    roster = {
        account.id: account
        for account in await list_alive_session_accounts(session, automation.id, exclude_flood=False)
    }
    missing_ids = [aid for aid in account_ids if aid not in roster]
    if missing_ids:
        extra = (
            await session.execute(select(SocialAccount).where(SocialAccount.id.in_(missing_ids)))
        ).scalars().all()
        for row in extra:
            roster[int(row.id)] = row
    account_items: list[dict[str, Any]] = []
    for aid in account_ids:
        account = roster.get(aid)
        cards = []
        joined_count = 0
        for cid in assignments.get(aid) or []:
            chat = chat_map.get(cid)
            is_joined = (aid, cid) in joined_set
            if is_joined:
                joined_count += 1
            if chat is None:
                cards.append(
                    {
                        "id": cid,
                        "title": f"чат #{cid}",
                        "link": "",
                        "folder_id": None,
                        "folder_name": None,
                        "joined": is_joined,
                    }
                )
                continue
            cards.append(_pool_chat_card(chat, folder_names, joined=is_joined))
        account_items.append(
            {
                "id": aid,
                "label": actor_label(account) if account else f"аккаунт #{aid}",
                "username": getattr(account, "username", None) if account else None,
                "phone_number": getattr(account, "phone_number", None) if account else None,
                "assigned": cards,
                "assigned_count": len(cards),
                "joined_count": joined_count,
                "status": pool_actor_status(account),
            }
        )
    reserve_cards = []
    for cid in reserve_ids:
        chat = chat_map.get(cid)
        if chat is None:
            reserve_cards.append(
                {
                    "id": cid,
                    "title": f"чат #{cid}",
                    "link": "",
                    "folder_id": None,
                    "folder_name": None,
                    "joined": False,
                }
            )
            continue
        reserve_cards.append(_pool_chat_card(chat, folder_names, joined=False))
    mix_map: dict[Any, dict[str, Any]] = {}
    for card in [item for row in account_items for item in row["assigned"]] + reserve_cards:
        key = card.get("folder_id") or 0
        row = mix_map.setdefault(
            key,
            {
                "id": card.get("folder_id"),
                "name": card.get("folder_name") or "Без папки",
                "total": 0,
                "assigned": 0,
                "reserve": 0,
            },
        )
        row["total"] += 1
    assigned_ids = {cid for ids in assignments.values() for cid in ids}
    for card in [item for row in account_items for item in row["assigned"]]:
        key = card.get("folder_id") or 0
        mix_map[key]["assigned"] += 1
    for card in reserve_cards:
        key = card.get("folder_id") or 0
        mix_map[key]["reserve"] += 1
    job_type = _log_job_type(task_key)
    live = False
    if job_type != "join":
        live = bool(
            await session.scalar(
                select(func.count(CustomJob.id)).where(
                    CustomJob.custom_automation_id == automation.id,
                    CustomJob.job_type == job_type,
                    CustomJob.status.in_(tuple(VISIBLE_ACTIVE_STATUSES)),
                )
            )
        )
    available_accounts = []
    selected_accounts = set(account_ids)
    seen_available: set[int] = set()
    for account in roster.values():
        if account.id in seen_available:
            continue
        seen_available.add(account.id)
        available_accounts.append(
            {
                "id": account.id,
                "label": actor_label(account),
                "username": getattr(account, "username", None),
                "phone_number": getattr(account, "phone_number", None),
                "eligible": pool_actor_selectable(account),
                "status": pool_actor_status(account),
                "selected": account.id in selected_accounts,
            }
        )
    pending_left = int((stored or {}).get("pending_joins") or 0)
    from .task_targets import task_resource_kind

    return {
        "task_key": task_key,
        "resource_kind": task_resource_kind(task_key),
        "cap": TASK_CHATS_PER_ACCOUNT,
        "account_ids": account_ids,
        "folder_ids": folder_ids,
        "chat_ids": _int_list(settings.get("chat_ids")),
        "assignments": {str(aid): ids for aid, ids in assignments.items()},
        "reserve_chat_ids": reserve_ids,
        "accounts": account_items,
        "reserve": reserve_cards,
        "folder_mix": list(mix_map.values()),
        "available_accounts": available_accounts,
        "available_folders": [
            {**item, "selected": int(item["id"]) in set(folder_ids)}
            for item in folder_rows
        ],
        "pending_joins": pending_left,
        "joins_complete": bool((stored or {}).get("joins_complete")),
        "live": bool(live),
        "assigned_count": len(assigned_ids),
        "reserve_count": len(reserve_ids),
    }


async def expand_task_pool(
    session: AsyncSession,
    automation: CustomAutomation,
    task_key: str,
    *,
    account_ids: list[int] | None = None,
    folder_ids: list[int] | None = None,
    chat_ids: list[int] | None = None,
    mode: str = "fill",
) -> dict[str, Any]:
    """Add accounts/folders to a running task and optionally remix unjoined chats."""
    from .task_targets import resolve_task_chat_ids

    key = _TASK_SETTINGS_KEY.get(task_key, task_key)
    blob = dict(automation.module_settings or {})
    settings = dict(blob.get(key) or {}) if isinstance(blob.get(key), dict) else {}
    if account_ids is not None:
        settings["account_ids"] = _int_list(account_ids)
    if folder_ids is not None:
        settings["folder_ids"] = _int_list(folder_ids)
    if chat_ids is not None:
        settings["chat_ids"] = _int_list(chat_ids)
    mix = str(mode or "fill").strip().lower() == "mix"
    if mix:
        settings["chat_assignments"] = {}
    blob[key] = settings
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    resolved = await resolve_task_chat_ids(
        session,
        automation.id,
        settings,
        task_key=task_key,
    )
    await ensure_task_join_plan(
        session,
        automation,
        task_key,
        _int_list(settings.get("account_ids")),
        resolved,
        mix=mix,
    )
    automation = await session.get(CustomAutomation, automation.id) or automation
    await _sync_live_job_pool(session, automation, task_key)
    await session.commit()
    return await serialize_task_pool(session, automation, task_key)


async def save_task_assignments(
    session: AsyncSession,
    automation: CustomAutomation,
    task_key: str,
    assignments: dict[int, list[int]],
) -> dict[str, Any]:
    """Persist a manual per-account chat split and merge ids into module settings."""
    key = _TASK_SETTINGS_KEY.get(task_key, task_key)
    blob = dict(automation.module_settings or {})
    settings = dict(blob.get(key) or {}) if isinstance(blob.get(key), dict) else {}
    plans = _plans_blob(automation)
    stored = dict(plans.get(task_key) or {}) if isinstance(plans.get(task_key), dict) else {}
    account_ids = [int(aid) for aid in (assignments or {}).keys() if int(aid) > 0]
    union = [cid for ids in (assignments or {}).values() for cid in _int_list(ids)]
    mapped, reserve = split_task_assignment(
        account_ids,
        union,
        manual={int(aid): _int_list(ids) for aid, ids in (assignments or {}).items() if int(aid) > 0},
        stored_reserve=_int_list(stored.get("reserve") or settings.get("reserve_chat_ids")),
    )
    clean = {str(int(aid)): ids for aid, ids in mapped.items() if int(aid) > 0}
    settings["chat_assignments"] = clean
    settings["reserve_chat_ids"] = reserve
    assigned_union: list[int] = []
    seen: set[int] = set()
    for ids in clean.values():
        for cid in ids:
            if cid in seen:
                continue
            seen.add(cid)
            assigned_union.append(cid)
    if assigned_union or reserve:
        current = _int_list(settings.get("chat_ids"))
        settings["chat_ids"] = list(dict.fromkeys(current + assigned_union + reserve))
    blob[key] = settings
    stored["assignments"] = {k: v for k, v in clean.items()}
    stored["reserve"] = reserve
    stored["manual"] = True
    stored["updated_at"] = _utc_now().isoformat()
    plans[task_key] = stored
    blob[TASK_JOINS_KEY] = plans
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    await _upsert_actor_memberships(session, automation.id, mapped)
    await session.commit()
    return {
        "assignments": clean,
        "chat_ids": settings.get("chat_ids") or [],
        "reserve_chat_ids": reserve,
    }


def _chat_usable_in_pool(chat: ChatTarget | None) -> bool:
    if chat is None or getattr(chat, "black_boxed_at", None):
        return False
    if (getattr(chat, "mod_status", None) or "") == "moderated":
        return False
    if chat.comments_open is False:
        return False
    return True


async def _take_reserve_replacement(
    session: AsyncSession,
    automation_id: int,
    reserve: list[int],
    used: set[int],
) -> tuple[int | None, list[int]]:
    kept: list[int] = []
    picked: int | None = None
    for cid in reserve:
        if cid in used:
            kept.append(cid)
            continue
        chat = await session.get(ChatTarget, cid)
        if not _chat_usable_in_pool(chat) or int(getattr(chat, "custom_automation_id", 0) or 0) != automation_id:
            continue
        if picked is None:
            picked = cid
            continue
        kept.append(cid)
    return picked, kept


async def replace_blackboxed_task_chat(session: AsyncSession, chat_target: ChatTarget) -> int:
    """If a pool chat is blacklisted, pull a replacement from the reserve."""
    automation_id = int(getattr(chat_target, "custom_automation_id", 0) or 0)
    if automation_id <= 0:
        return 0
    automation = await session.get(CustomAutomation, automation_id)
    if automation is None:
        return 0
    dead_id = int(chat_target.id)
    plans = _plans_blob(automation)
    blob = dict(automation.module_settings or {})
    replaced = 0
    changed_any = False
    for task_key, spec in list(plans.items()):
        if not isinstance(spec, dict):
            continue
        assignments = {int(key): _int_list(value) for key, value in (spec.get("assignments") or {}).items()}
        reserve = _int_list(spec.get("reserve"))
        used = {cid for ids in assignments.values() for cid in ids if cid != dead_id}
        task_changed = False
        for aid, ids in list(assignments.items()):
            if dead_id not in ids:
                continue
            next_ids = [cid for cid in ids if cid != dead_id]
            pick, reserve = await _take_reserve_replacement(session, automation_id, reserve, used)
            if pick:
                next_ids.append(pick)
                used.add(pick)
                await _upsert_actor_memberships(session, automation_id, {aid: [pick]})
                replaced += 1
            assignments[aid] = next_ids
            task_changed = True
        reserve = [cid for cid in reserve if cid != dead_id]
        if not task_changed and dead_id not in reserve:
            continue
        spec["assignments"] = {str(aid): ids for aid, ids in assignments.items()}
        spec["reserve"] = reserve
        spec["updated_at"] = _utc_now().isoformat()
        plans[task_key] = spec
        key = _TASK_SETTINGS_KEY.get(str(task_key), str(task_key))
        settings = dict(blob.get(key) or {}) if isinstance(blob.get(key), dict) else {}
        settings["chat_assignments"] = spec["assignments"]
        settings["reserve_chat_ids"] = reserve
        blob[key] = settings
        changed_any = True
    if not changed_any:
        return 0
    blob[TASK_JOINS_KEY] = plans
    automation.module_settings = blob
    automation.updated_at = _utc_now()
    return replaced
