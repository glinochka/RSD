"""Task-scoped chat joins via Telegram shareable folders (t.me/addlist).

Free accounts: 2 shareable folders × 100 chats.
Premium: 20 folders × 200 chats.
https://telegram.org/tour/chat-folders
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import (
    AccountChatMembership,
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
) -> dict[int, list[int]]:
    """Keep valid previous assignments, then fill least-loaded accounts.

    New workers receive leftover and overflow pending chats. Already assigned
    chats stay with their account so we do not yank memberships.
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
    for aid, old in (previous or {}).items():
        if int(aid) not in assignment:
            continue
        for cid in old or []:
            chat_id = int(cid)
            if chat_id not in chats or chat_id in assigned:
                continue
            if len(assignment[int(aid)]) >= even:
                continue
            assignment[int(aid)].append(chat_id)
            assigned.add(chat_id)
    remaining = [cid for cid in chats if cid not in assigned]
    for cid in remaining:
        eligible = [aid for aid in accounts if len(assignment[aid]) < min(even, cap)]
        if not eligible:
            eligible = [aid for aid in accounts if len(assignment[aid]) < cap]
        if not eligible:
            break
        aid = min(eligible, key=lambda item: (len(assignment[item]), item))
        assignment[aid].append(cid)
        assigned.add(cid)
    return assignment


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


def _plans_blob(automation: CustomAutomation) -> dict[str, Any]:
    blob = dict(automation.module_settings or {})
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
        chats = await resolve_task_chat_ids(session, automation.id, spec.get("settings") or spec)
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
    summary = {"tasks": 0, "joined": 0, "folders": 0}
    for spec in await collect_task_join_specs_resolved(session, automation):
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
) -> dict[str, Any]:
    alive = {account.id: account for account in await list_alive_session_accounts(session, automation.id)}
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
    chat_map = {chat.id: chat for chat in chats}
    if not workers or not chat_map:
        return {"joined": 0, "folders": 0}
    plans = _plans_blob(automation)
    previous_raw = ((plans.get(task_key) or {}).get("assignments") if isinstance(plans.get(task_key), dict) else {}) or {}
    previous = {int(key): _int_list(value) for key, value in previous_raw.items()}
    assignment = even_redistribute(workers, list(chat_map.keys()), previous)
    await _upsert_actor_memberships(session, automation.id, assignment)
    stored_task = plans.get(task_key) if isinstance(plans.get(task_key), dict) else {}
    stored_folders = (stored_task or {}).get("folders") if isinstance(stored_task, dict) else {}
    premium_cache = dict((stored_task or {}).get("premium") or {})
    pending_by_account: dict[int, list[int]] = {}
    union_pending: list[int] = []
    for account_id, assigned in assignment.items():
        pending = [cid for cid in assigned if not await account_is_joined(session, cid, account_id)]
        pending_by_account[account_id] = pending
        union_pending.extend(pending)
    host = await _pick_host(session, alive, workers, list(dict.fromkeys(union_pending)) or list(chat_map.keys()))
    if host:
        from .chat_join_service import _try_join_chat

        for chat_id in dict.fromkeys(union_pending):
            chat = chat_map.get(chat_id)
            if not chat or await account_is_joined(session, chat_id, host.id):
                continue
            try:
                result = await _try_join_chat(session, chat, host)
                if result.get("status") == "joined":
                    host_membership = await get_membership(session, chat_id, host.id)
                    if host_membership:
                        host_membership.join_status = ChatJoinStatus.JOINED.value
                        host_membership.joined_at = _utc_now()
                        host_membership.updated_at = _utc_now()
            except Exception as exc:
                logger.debug("Host bootstrap join skipped chat=%s: %s", chat_id, exc)
    folders: dict[str, list[dict[str, Any]]] = {}
    joined = 0
    created_folders = 0
    for account_id, assigned in assignment.items():
        account = alive.get(account_id)
        pending = pending_by_account.get(account_id) or []
        previous_folders = list((stored_folders or {}).get(str(account_id)) or [])
        if not account or not assigned:
            folders[str(account_id)] = []
            continue
        reusable, covered = _reusable_folders(previous_folders, assigned)
        fresh = [cid for cid in pending if cid not in covered]
        if not pending:
            folders[str(account_id)] = reusable or previous_folders
            continue
        try:
            if reusable:
                from .telegram_account_client import TelegramAccountClient

                async with TelegramAccountClient.for_account(account) as client:
                    for row in reusable:
                        slug = str(row.get("slug") or "")
                        if slug:
                            await _join_addlist(client, slug)
                joined += await _mark_joined(session, account_id, [cid for cid in pending if cid in covered])
            exported: list[dict[str, Any]] = list(reusable)
            if fresh:
                cached = premium_cache.get(str(account_id))
                premium = bool(cached) if cached is not None else await _account_is_premium(account)
                premium_cache[str(account_id)] = premium
                per_folder, _folder_cap = addlist_capacity(premium=premium)
                batches = chunk_ids(fresh, per_folder)
                new_rows = await _export_and_join_batches(
                    host=host,
                    worker=account,
                    chats=[chat_map[cid] for cid in fresh if cid in chat_map],
                    batches=batches,
                )
                exported.extend(new_rows)
                created_folders += len(new_rows)
                joined += await _mark_joined(
                    session, account_id, [cid for row in new_rows for cid in _int_list(row.get("chat_ids"))]
                )
            folders[str(account_id)] = exported
        except Exception as exc:
            logger.warning("Addlist join failed task=%s account=%s: %s", task_key, account_id, exc)
            folders[str(account_id)] = reusable
    plans[task_key] = {
        "assignments": {str(key): value for key, value in assignment.items()},
        "folders": folders,
        "premium": premium_cache,
        "host_account_id": host.id if host else workers[0],
        "updated_at": _utc_now().isoformat(),
    }
    _store_plans(automation, plans)
    await session.commit()
    return {"joined": joined, "folders": created_folders, "assignment": assignment}


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


async def _mark_joined(session: AsyncSession, account_id: int, chat_ids: list[int]) -> int:
    marked = 0
    now = _utc_now()
    for chat_id in dict.fromkeys(chat_ids):
        membership = await get_membership(session, chat_id, account_id)
        if not membership:
            continue
        if membership.join_status != ChatJoinStatus.JOINED.value:
            membership.join_status = ChatJoinStatus.JOINED.value
            membership.joined_at = membership.joined_at or now
            membership.last_join_error = None
            membership.next_join_attempt_at = None
            membership.updated_at = now
            marked += 1
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
) -> list[dict[str, Any]]:
    from .telegram_account_client import TelegramAccountClient

    by_id = {chat.id: chat for chat in chats}
    rows: list[dict[str, Any]] = []
    if not host:
        host = worker
    async with TelegramAccountClient.for_account(host) as host_client:
        for chunk in batches:
            subset = [by_id[cid] for cid in chunk if cid in by_id]
            if not subset:
                continue
            slug, filter_id = await _export_folder_for_chats(host_client, subset)
            if not slug:
                continue
            if host.id != worker.id:
                async with TelegramAccountClient.for_account(worker) as worker_client:
                    await _join_addlist(worker_client, slug)
            else:
                await _join_addlist(host_client, slug)
            rows.append(
                {
                    "slug": slug,
                    "url": addlist_url(slug),
                    "filter_id": filter_id,
                    "chat_ids": [chat.id for chat in subset],
                }
            )
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


async def _export_folder_for_chats(client: Any, chats: list[ChatTarget]) -> tuple[str | None, int | None]:
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
    filter_id = 2
    while filter_id in used:
        filter_id += 1
    title = f"UBT {chats[0].id}"[:12]
    dialog_filter = _build_dialog_filter(filter_id, title, peers)
    await telethon(UpdateDialogFilterRequest(id=filter_id, filter=dialog_filter))
    exported = await telethon(
        ExportChatlistInviteRequest(
            chatlist=types.InputChatlistDialogFilter(filter_id=filter_id),
            title=title,
            peers=peers,
        )
    )
    invite = getattr(exported, "invite", exported)
    url = str(getattr(invite, "url", "") or "")
    slug = parse_addlist_slug(url)
    return slug, filter_id


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


async def _join_addlist(client: Any, slug: str) -> None:
    from telethon.tl.functions.chatlists import JoinChatlistInviteRequest

    telethon = getattr(client, "client", client)
    peers, _title = await _check_addlist_peers(client, slug)
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

    for spec in plans.values():
        if not isinstance(spec, dict):
            continue
        folders = spec.get("folders") or {}
        for account_key, rows in folders.items():
            account = alive.get(int(account_key))
            if not account or not rows:
                continue
            try:
                async with TelegramAccountClient.for_account(account) as client:
                    for row in rows:
                        slug = str(row.get("slug") or "")
                        if not slug:
                            continue
                        await _join_addlist(client, slug)
                        for chat_id in _int_list(row.get("chat_ids")):
                            membership = await get_membership(session, chat_id, account.id)
                            if membership and membership.join_status != ChatJoinStatus.JOINED.value:
                                membership.join_status = ChatJoinStatus.JOINED.value
                                membership.joined_at = _utc_now()
                                membership.last_join_error = None
                                membership.next_join_attempt_at = None
                                membership.updated_at = _utc_now()
                                joined += 1
            except Exception as exc:
                logger.warning("Pending addlist join failed account=%s: %s", account.id, exc)
    if joined:
        await session.commit()
    return {"joined": joined}
