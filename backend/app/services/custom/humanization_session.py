"""One connected Telegram session of mixed read-activity.

Competitor warmups keep the client online for minutes, then mix browsing,
stories, reactions, drafts and Saved Messages. We do the same inside the
existing idle-browse slot: one account, one TCP session, then rest.

Writes that look like farm tells (GIF/inline bots, random joins, ImportContacts
by phone) are intentionally omitted. Adding a commenter via contacts.addContact
is capped, not a daily quota.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from .account_pacing import (
    STAGE_CAUTIOUS,
    STAGE_NORMAL,
    STAGE_TRUSTED,
    account_humanization_stage,
    humanization_session_action_budget,
    humanization_session_seconds,
    moscow_now,
    post_join_mute_chance,
)
from .human_dm import random_idle_browse, show_typing

logger = logging.getLogger(__name__)

COMMENT_CONTACT_ACTION = "comment_contact"
_SAVED_NOTES = ("не забыть", "ок", "написать позже", ".")
_DRAFT_TEXTS = ("сейчас напишу", "ок, сек", "думаю")
_SEARCH_QUERIES = ("ок", "фото", "завтра")
_SERVICE_USER_IDS = {777000, 42777, 333000}
_CONTACT_DAY_PCT = 26  # ~1/4 of days are eligible, then gap/cap still apply


def _telethon(client: Any) -> Any:
    return getattr(client, "client", client)


async def _pause(lab_mode: bool, lo: float, hi: float) -> None:
    if lab_mode:
        return
    await asyncio.sleep(random.uniform(lo, hi))


def _stable_mod(seed: str, modulo: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(1, modulo)


def lifetime_comment_contact_cap(account_id: int) -> int:
    """Stop after 9–17 adds. Stable per account, not an infinite drip."""
    return 9 + _stable_mod(f"ccap:{int(account_id)}", 9)


def comment_contact_gap_days(account_id: int) -> int:
    """2–5 days after a successful add before another attempt."""
    return 2 + _stable_mod(f"cgap:{int(account_id)}", 4)


def is_comment_contact_day(account_id: int, day=None) -> bool:
    """Most days are off. Eligible days are hashed, not 'every day, N contacts'."""
    current = day or moscow_now().date()
    return _stable_mod(f"cday:{int(account_id)}:{current.isoformat()}", 100) < _CONTACT_DAY_PCT


@dataclass
class CommentContactPolicy:
    allow: bool
    reason: str
    cap: int = 0
    added: int = 0
    known_ids: set[int] = field(default_factory=set)


def comment_contact_policy(
    account: Any | None,
    *,
    added_count: int = 0,
    last_success_at: datetime | None = None,
    attempted_today: bool = False,
    now: datetime | None = None,
) -> CommentContactPolicy:
    """Decide whether this session may add one commenter. Never a fixed daily quota."""
    if account is None or not getattr(account, "id", None):
        return CommentContactPolicy(False, "no_account")
    aid = int(account.id)
    cap = lifetime_comment_contact_cap(aid)
    if account_humanization_stage(account, now=now) == STAGE_CAUTIOUS:
        return CommentContactPolicy(False, "cautious", cap=cap, added=added_count)
    if added_count >= cap:
        return CommentContactPolicy(False, "cap", cap=cap, added=added_count)
    if attempted_today:
        return CommentContactPolicy(False, "already_today", cap=cap, added=added_count)
    local = moscow_now(now)
    if not is_comment_contact_day(aid, local.date()):
        return CommentContactPolicy(False, "not_today", cap=cap, added=added_count)
    if last_success_at is not None:
        then = last_success_at.replace(tzinfo=None) if getattr(last_success_at, "tzinfo", None) else last_success_at
        gap = timedelta(days=comment_contact_gap_days(aid))
        current = now or datetime.utcnow().replace(tzinfo=None)
        if current - then < gap:
            return CommentContactPolicy(False, "gap", cap=cap, added=added_count)
    return CommentContactPolicy(True, "ok", cap=cap, added=added_count)


def _is_addable_user(user: Any, *, me_id: int | None, known_ids: set[int]) -> bool:
    if user is None:
        return False
    name = type(user).__name__
    if name in {"Channel", "Chat", "ChatForbidden", "ChannelForbidden", "UserEmpty"}:
        return False
    if getattr(user, "broadcast", False) or getattr(user, "megagroup", False):
        return False
    if getattr(user, "bot", False) or getattr(user, "deleted", False) or getattr(user, "is_self", False):
        return False
    if getattr(user, "contact", False):
        return False
    uid = int(getattr(user, "id", 0) or 0)
    if uid <= 0 or uid in _SERVICE_USER_IDS or uid in known_ids:
        return False
    if me_id and uid == int(me_id):
        return False
    return True


async def _iter_comment_users(telethon: Any, entity: Any, *, lab_mode: bool) -> list[Any]:
    """Authors of recent group messages or channel comment threads — not post authors."""
    found: list[Any] = []
    seen: set[int] = set()

    def _take(user: Any) -> None:
        uid = int(getattr(user, "id", 0) or 0)
        if uid and uid not in seen:
            seen.add(uid)
            found.append(user)

    is_broadcast = bool(getattr(entity, "broadcast", False))
    try:
        posts = await telethon.get_messages(entity, limit=8 if is_broadcast else 22)
    except Exception:
        return []
    if not is_broadcast:
        for msg in posts or []:
            sender = getattr(msg, "sender", None)
            if sender is not None:
                _take(sender)
        return found
    for post in posts or []:
        replies = getattr(post, "replies", None)
        count = int(getattr(replies, "replies", 0) or 0) if replies is not None else 0
        post_id = getattr(post, "id", None)
        if not post_id or count <= 0:
            continue
        await _pause(lab_mode, 0.6, 2.0)
        thread = None
        try:
            thread = await telethon.get_messages(entity, reply_to=int(post_id), limit=20)
        except Exception:
            thread = None
        if thread is None:
            try:
                from telethon.tl.functions.messages import GetRepliesRequest

                result = await telethon(
                    GetRepliesRequest(
                        peer=entity,
                        msg_id=int(post_id),
                        offset_id=0,
                        offset_date=None,
                        add_offset=0,
                        limit=20,
                        max_id=0,
                        min_id=0,
                        hash=0,
                    )
                )
                thread = list(getattr(result, "messages", None) or [])
                for user in list(getattr(result, "users", None) or []):
                    _take(user)
            except Exception:
                continue
        for msg in thread or []:
            sender = getattr(msg, "sender", None)
            if sender is not None:
                _take(sender)
        if found:
            break
    return found


async def add_commenter_contact(
    client: Any,
    *,
    lab_mode: bool = False,
    account: Any | None = None,
    policy: CommentContactPolicy | None = None,
) -> bool:
    """Add at most one user from comments. contacts.addContact, never ImportContacts."""
    gate = policy or comment_contact_policy(account)
    if not gate.allow:
        return False
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=20)
    except Exception:
        return False
    chats = [
        item
        for item in (dialogs or [])
        if getattr(item, "is_channel", False) or getattr(item, "is_group", False)
    ]
    if not chats:
        return False
    random.shuffle(chats)
    me_id = None
    try:
        me = await telethon.get_me()
        me_id = getattr(me, "id", None)
    except Exception:
        me_id = None
    candidate = None
    for dialog in chats[:4]:
        entity = getattr(dialog, "entity", None)
        if entity is None:
            continue
        await _pause(lab_mode, 1.0, 3.5)
        for user in await _iter_comment_users(telethon, entity, lab_mode=lab_mode):
            if _is_addable_user(user, me_id=me_id, known_ids=gate.known_ids):
                candidate = user
                break
        if candidate is not None:
            break
    if candidate is None:
        client._comment_contact = {"status": "empty"}
        return False
    if lab_mode:
        client._comment_contact = {
            "status": "success",
            "user_id": int(candidate.id),
            "first_name": getattr(candidate, "first_name", None),
        }
        return True
    try:
        from telethon.tl.functions.contacts import AddContactRequest

        await _pause(False, 0.8, 2.4)
        await telethon(
            AddContactRequest(
                id=candidate,
                first_name=(getattr(candidate, "first_name", None) or "User")[:64],
                last_name=(getattr(candidate, "last_name", None) or "")[:64],
                phone="",
                add_phone_privacy_exception=False,
            )
        )
        client._comment_contact = {
            "status": "success",
            "user_id": int(candidate.id),
            "username": getattr(candidate, "username", None),
        }
        return True
    except Exception as exc:
        logger.debug("AddContact skipped: %s", exc)
        client._comment_contact = {"status": "error", "error": str(exc)[:200]}
        return False


async def set_presence(client: Any, *, offline: bool, lab_mode: bool = False) -> bool:
    """account.updateStatus. Lab skips it so tests do not need Telethon types."""
    if lab_mode:
        return False
    try:
        from telethon.tl.functions.account import UpdateStatusRequest

        await _telethon(client)(UpdateStatusRequest(offline=offline))
        return True
    except Exception as exc:
        logger.debug("UpdateStatus(offline=%s) skipped: %s", offline, exc)
        return False


async def browse_open_app(client: Any, account: Any | None, *, lab_mode: bool = False) -> bool:
    stage = account_humanization_stage(account)
    n = {"cautious": (2, 3), "normal": (2, 4), "trusted": (3, 5)}.get(stage, (2, 4))
    await random_idle_browse(client, n_dialogs=random.randint(*n), lab_mode=lab_mode)
    return True


async def scroll_subscribed_channels(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=24)
    except Exception:
        return False
    channels = [
        item
        for item in (dialogs or [])
        if getattr(item, "is_channel", False) or getattr(getattr(item, "entity", None), "broadcast", False)
    ]
    if not channels:
        return False
    sample = random.sample(channels, min(random.randint(1, 3), len(channels)))
    for dialog in sample:
        entity = getattr(dialog, "entity", None)
        if entity is None:
            continue
        await _pause(lab_mode, 1.2, 4.0)
        try:
            msgs = await telethon.get_messages(entity, limit=random.randint(6, 14))
            if msgs and random.random() < 0.65:
                last_id = getattr(msgs[0], "id", None)
                if last_id:
                    await telethon.send_read_acknowledge(entity, max_id=int(last_id))
        except Exception:
            continue
    return True


async def mark_peer_stories_read(client: Any, peer: Any, stories: list[Any], *, lab_mode: bool = False) -> int:
    """ReadStories up to the newest id — the same gesture as opening a tray."""
    items = [item for item in (stories or []) if int(getattr(item, "id", 0) or 0) > 0]
    if not items or peer is None:
        return 0
    max_id = max(int(getattr(item, "id", 0) or 0) for item in items)
    if lab_mode:
        return len(items)
    try:
        from telethon.tl.functions.stories import ReadStoriesRequest
    except Exception:
        return 0
    await _pause(False, 0.8, 2.5)
    try:
        await _telethon(client)(ReadStoriesRequest(peer=peer, max_id=max_id))
        return len(items)
    except Exception as exc:
        logger.debug("ReadStories skipped: %s", exc)
        return 0


async def load_feed_peer_stories(client: Any) -> list[Any]:
    try:
        from telethon.tl.functions.stories import GetAllStoriesRequest
    except Exception:
        return []
    try:
        result = await _telethon(client)(GetAllStoriesRequest())
    except Exception as exc:
        logger.debug("GetAllStories skipped: %s", exc)
        return []
    return list(getattr(result, "peer_stories", None) or [])


async def load_peer_stories(client: Any, entity: Any) -> tuple[Any, list[Any]]:
    try:
        from telethon.tl.functions.stories import GetPeerStoriesRequest
    except Exception:
        return entity, []
    try:
        result = await _telethon(client)(GetPeerStoriesRequest(peer=entity))
    except Exception as exc:
        logger.debug("GetPeerStories skipped: %s", exc)
        return entity, []
    packed = getattr(result, "stories", None)
    peer = getattr(packed, "peer", None) or entity
    stories = list(getattr(packed, "stories", None) or getattr(result, "stories", None) or [])
    if stories and not isinstance(stories[0], (list, tuple)) and not hasattr(stories[0], "id"):
        stories = []
    return peer, stories


async def glance_stories(client: Any, *, lab_mode: bool = False) -> bool:
    peers = await load_feed_peer_stories(client)
    if not peers:
        return True
    viewed = 0
    for peer_stories in random.sample(peers, min(2, len(peers))):
        stories = list(getattr(peer_stories, "stories", None) or [])
        peer = getattr(peer_stories, "peer", None)
        counted = await mark_peer_stories_read(client, peer, stories, lab_mode=lab_mode)
        if counted:
            viewed += 1
    return viewed > 0 or True


async def react_in_subscriptions(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=18)
    except Exception:
        return False
    candidates = [
        item
        for item in (dialogs or [])
        if getattr(item, "is_channel", False) or getattr(item, "is_group", False)
    ]
    if not candidates:
        return False
    dialog = random.choice(candidates)
    entity = getattr(dialog, "entity", None)
    if entity is None:
        return False
    try:
        msgs = await telethon.get_messages(entity, limit=6)
    except Exception:
        return False
    posts = [item for item in (msgs or []) if getattr(item, "id", None)]
    if not posts:
        return False
    post = random.choice(posts)
    if lab_mode:
        return True
    await _pause(False, 0.4, 2.2)
    try:
        send_reaction = getattr(telethon, "send_reaction", None)
        emoji = random.choice(("👍", "🔥", "❤", "👏", "🥰"))
        if callable(send_reaction):
            await send_reaction(entity, int(post.id), emoji)
        else:
            from telethon.tl.functions.messages import SendReactionRequest
            from telethon.tl.types import ReactionEmoji

            await telethon(
                SendReactionRequest(
                    peer=entity,
                    msg_id=int(post.id),
                    reaction=[ReactionEmoji(emoticon=emoji)],
                )
            )
        return True
    except Exception:
        return False


async def typing_without_send(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=12)
    except Exception:
        return False
    users = [item for item in (dialogs or []) if getattr(item, "is_user", False)]
    if not users:
        return False
    entity = getattr(random.choice(users), "entity", None)
    if entity is None or getattr(entity, "bot", False):
        return False
    await show_typing(client, entity, 0.0 if lab_mode else random.uniform(2.0, 6.0))
    return True


async def view_recent_profile(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        from telethon.tl.functions.users import GetFullUserRequest

        dialogs = await telethon.get_dialogs(limit=12)
        users = [item for item in (dialogs or []) if getattr(item, "is_user", False)]
        if not users:
            return False
        entity = getattr(random.choice(users), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 0.5, 1.8)
        await telethon(GetFullUserRequest(entity))
        try:
            await telethon.get_profile_photos(entity, limit=1)
        except Exception:
            pass
        return True
    except Exception:
        return False


async def inspect_peer_profile(client: Any, entity: Any, *, lab_mode: bool = False) -> bool:
    """Open the user profile before stories, priming, or a first DM."""
    telethon = _telethon(client)
    try:
        from telethon.tl.functions.users import GetFullUserRequest

        resolved = entity
        if getattr(resolved, "bot", False) or getattr(resolved, "broadcast", False) or getattr(resolved, "megagroup", False):
            return False
        if not hasattr(resolved, "access_hash"):
            try:
                resolved = await telethon.get_entity(entity)
            except Exception:
                resolved = entity
        if getattr(resolved, "bot", False) or getattr(resolved, "broadcast", False) or getattr(resolved, "megagroup", False):
            return False
        await _pause(lab_mode, 0.4, 1.6)
        await telethon(GetFullUserRequest(resolved))
        try:
            await telethon.get_profile_photos(resolved, limit=1)
        except Exception:
            pass
        await _pause(lab_mode, 0.2, 0.9)
        return True
    except Exception:
        return False


async def search_in_recent_chat(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=10)
        if not dialogs:
            return False
        entity = getattr(random.choice(list(dialogs)), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 0.6, 2.0)
        await telethon.get_messages(entity, limit=5, search=random.choice(_SEARCH_QUERIES))
        return True
    except Exception:
        return False


async def leave_then_clear_draft(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        from telethon.tl.functions.messages import SaveDraftRequest

        dialogs = await telethon.get_dialogs(limit=12)
        users = [item for item in (dialogs or []) if getattr(item, "is_user", False)]
        if not users:
            return False
        entity = getattr(random.choice(users), "entity", None)
        if entity is None or getattr(entity, "bot", False):
            return False
        await telethon(SaveDraftRequest(peer=entity, message=random.choice(_DRAFT_TEXTS)))
        await _pause(lab_mode, 4.0, 14.0)
        await telethon(SaveDraftRequest(peer=entity, message=""))
        return True
    except Exception as exc:
        logger.debug("Draft skipped: %s", exc)
        return False


async def note_in_saved(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        await _pause(lab_mode, 0.8, 2.5)
        await telethon.send_message("me", random.choice(_SAVED_NOTES))
        return True
    except Exception as exc:
        logger.debug("Saved Messages skipped: %s", exc)
        return False


async def mute_peer(client: Any, entity: Any) -> bool:
    try:
        from telethon.tl.functions.account import UpdateNotifySettingsRequest
        from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings

        await _telethon(client)(
            UpdateNotifySettingsRequest(
                peer=InputNotifyPeer(entity),
                settings=InputPeerNotifySettings(mute_until=2_147_483_647, silent=True),
            )
        )
        return True
    except Exception as exc:
        logger.debug("Mute skipped: %s", exc)
        return False


async def settle_after_join(client: Any, entity: Any, account: Any | None = None, *, lab_mode: bool = False) -> dict[str, Any]:
    """After JoinChannel: look at the feed, sometimes mute. Do not disconnect on failure."""
    done: list[str] = []
    if entity is None:
        return {"actions": done}
    await _pause(lab_mode, 2.0, 8.0)
    telethon = _telethon(client)
    try:
        msgs = await telethon.get_messages(entity, limit=random.randint(5, 12))
        done.append("scroll")
        if msgs and random.random() < 0.7:
            last_id = getattr(msgs[0], "id", None)
            if last_id:
                await telethon.send_read_acknowledge(entity, max_id=int(last_id))
                done.append("read")
    except Exception as exc:
        logger.debug("Post-join history skipped: %s", exc)
    if random.random() < post_join_mute_chance(account):
        if await mute_peer(client, entity):
            done.append("mute")
    return {"actions": done}


def _action_catalog(stage: str, *, allowed: set[str] | None = None) -> list[tuple[str, Callable[..., Awaitable[bool]]]]:
    """Stage gates writes. Everyone reads; older accounts may react / draft / Saved."""
    actions: list[tuple[str, Callable[..., Awaitable[bool]]]] = [
        ("scroll_channels", scroll_subscribed_channels),
        ("stories", glance_stories),
        ("view_profile", view_recent_profile),
        ("typing_idle", typing_without_send),
    ]
    if stage in {STAGE_NORMAL, STAGE_TRUSTED}:
        actions.extend(
            [
                ("react", react_in_subscriptions),
                ("search", search_in_recent_chat),
                ("draft", leave_then_clear_draft),
                ("comment_contact", add_commenter_contact),
            ]
        )
    if stage == STAGE_TRUSTED:
        actions.append(("saved", note_in_saved))
    if allowed is not None:
        actions = [(name, fn) for name, fn in actions if name in allowed]
    return actions


async def run_humanization_session(
    client: Any,
    account: Any | None = None,
    *,
    lab_mode: bool = False,
    contact_policy: CommentContactPolicy | None = None,
    allowed_actions: set[str] | None = None,
    intensity: str | None = None,
    session_minutes: int = 0,
) -> dict[str, Any]:
    """Keep one socket open, look alive, then go offline."""
    stage = intensity if intensity in {STAGE_CAUTIOUS, STAGE_NORMAL, STAGE_TRUSTED} else account_humanization_stage(account)
    budget = humanization_session_action_budget(account, stage=stage)
    if session_minutes and not lab_mode:
        target_seconds = float(max(60, min(15 * 60, int(session_minutes) * 60)))
    else:
        target_seconds = 0.0 if lab_mode else humanization_session_seconds(account, stage=stage)
    started = time.monotonic()
    done: list[str] = []
    client._comment_contact = None
    policy = contact_policy or comment_contact_policy(account)

    if await set_presence(client, offline=False, lab_mode=lab_mode):
        done.append("online")

    await browse_open_app(client, account, lab_mode=lab_mode)
    done.append("browse")
    content = 1

    catalog = _action_catalog(stage, allowed=allowed_actions)
    random.shuffle(catalog)
    for name, fn in catalog:
        if content >= budget:
            break
        await _pause(lab_mode, 6.0, 22.0)
        try:
            if name == "comment_contact":
                ok = await fn(client, lab_mode=lab_mode, account=account, policy=policy)
            else:
                ok = await fn(client, lab_mode=lab_mode)
        except TypeError:
            ok = await fn(client)
        except Exception as exc:
            logger.debug("Humanization action %s failed: %s", name, exc)
            continue
        if ok:
            done.append(name)
            content += 1

    elapsed = time.monotonic() - started
    leftover = target_seconds - elapsed
    if leftover > 4 and not lab_mode:
        await asyncio.sleep(min(leftover, 90.0))
        done.append("idle_hold")

    if await set_presence(client, offline=True, lab_mode=lab_mode):
        done.append("offline")

    return {
        "stage": stage,
        "budget": budget,
        "actions": done,
        "seconds": round(time.monotonic() - started, 2),
        "comment_contact": getattr(client, "_comment_contact", None),
    }
