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
    PHASE_OBSERVE,
    PHASE_RAMP,
    PHASE_REPLY,
    PHASE_SETTLE,
    STAGE_CAUTIOUS,
    STAGE_NORMAL,
    STAGE_TRUSTED,
    account_humanization_stage,
    account_in_settle_rest,
    account_may_keep_alive,
    account_may_humanize,
    account_upload_phase,
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
SEED_CHANNEL_QUERIES = (
    "Рифмы и Панчи",
    "Топор Live",
    "Казань на максималках",
)
PUBLIC_SEARCH_QUERIES = SEED_CHANNEL_QUERIES + (
    "MDK",
    "Лентач",
    "Пикабу",
    "Подслушано",
    "Нетипичная Махачкала",
)
_PUBLIC_SEARCH = PUBLIC_SEARCH_QUERIES
SEED_CHANNEL_JOIN_ACTION = "seed_channel_join"
_CHAT_QUESTIONS = (
    "А как у вас обычно с этим бывает, кто недавно проходил?",
    "Подскажите по теме: с чего лучше начать, если новичок?",
    "Кто уже пробовал — есть смысл или так себе?",
    "А что сейчас актуально по этой теме, не устарело?",
)
_FARM_REPLIES = (
    "У меня так же почти, просто дольше возился.",
    "Норм вопрос. Я через неделю втянулся.",
    "Да, у нас похожая история была.",
    "Согласен, у меня так же вышло.",
)
CHAT_QUESTION_ACTION = "chat_question"
CHAT_REPLY_ACTION = "chat_question_reply"
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
    phase = account_upload_phase(account, now=now)
    if phase in {PHASE_OBSERVE, PHASE_REPLY}:
        if added_count >= 1:
            return CommentContactPolicy(False, "early_cap", cap=1, added=added_count)
        if attempted_today:
            return CommentContactPolicy(False, "already_today", cap=1, added=added_count)
        return CommentContactPolicy(True, "ok", cap=1, added=added_count)
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
    """Open the story tray like a person: one peer, slowly. Not a feed sweep."""
    peers = await load_feed_peer_stories(client)
    if not peers:
        return True
    if lab_mode:
        return True
    await _pause(False, 2.0, 7.0)
    # Sometimes just open the tray and leave — people skip stories.
    if random.random() < 0.30:
        return True
    packed = random.choice(peers)
    stories = list(getattr(packed, "stories", None) or [])
    peer = getattr(packed, "peer", None)
    await _pause(False, 6.0, 18.0)
    counted = await mark_peer_stories_read(client, peer, stories, lab_mode=False)
    if counted:
        await _pause(False, 2.0, 8.0)
    return True


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


async def sit_afk(client: Any, *, lab_mode: bool = False) -> bool:
    del client
    await _pause(lab_mode, 18.0, 70.0)
    return True


def _channel_posts(dialogs: list[Any]) -> list[Any]:
    return [
        item
        for item in (dialogs or [])
        if getattr(item, "is_channel", False) or getattr(getattr(item, "entity", None), "broadcast", False)
    ]


def _user_dialogs(dialogs: list[Any]) -> list[Any]:
    return [
        item
        for item in (dialogs or [])
        if getattr(item, "is_user", False) and not getattr(getattr(item, "entity", None), "bot", False)
    ]


def _group_dialogs(dialogs: list[Any]) -> list[Any]:
    return [
        item
        for item in (dialogs or [])
        if getattr(item, "is_group", False) or getattr(getattr(item, "entity", None), "megagroup", False)
    ]


async def read_channel_comments(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=18)
        channels = _channel_posts(dialogs)
        if not channels:
            return False
        entity = getattr(random.choice(channels), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 1.0, 3.5)
        posts = await telethon.get_messages(entity, limit=8)
        threaded = [item for item in (posts or []) if getattr(getattr(item, "replies", None), "replies", 0)]
        if not threaded:
            return bool(posts)
        post = random.choice(threaded)
        await _pause(lab_mode, 1.5, 4.0)
        comments = await telethon.get_messages(entity, limit=12, reply_to=getattr(post, "id", None))
        if comments and random.random() < 0.35:
            try:
                await telethon.send_reaction(entity, comments[0], random.choice(("👍", "🔥", "❤", "😂")))
            except Exception:
                pass
        return True
    except Exception:
        return False


async def react_in_dm(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=14)
        users = _user_dialogs(dialogs)
        if not users:
            return False
        entity = getattr(random.choice(users), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 0.8, 2.4)
        msgs = await telethon.get_messages(entity, limit=6)
        incoming = [item for item in (msgs or []) if not getattr(item, "out", False)]
        if not incoming:
            return False
        await telethon.send_reaction(entity, incoming[0], random.choice(("👍", "❤", "🔥", "😂", "👏")))
        return True
    except Exception:
        return False


async def forward_to_saved(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=16)
        pool = _channel_posts(dialogs) + _user_dialogs(dialogs)
        if not pool:
            return False
        entity = getattr(random.choice(pool), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 0.8, 2.8)
        msgs = await telethon.get_messages(entity, limit=5)
        if not msgs:
            return False
        await telethon.forward_messages("me", msgs[0], entity)
        return True
    except Exception as exc:
        logger.debug("Forward to Saved skipped: %s", exc)
        return False


async def pin_recent_dm(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=12)
        users = _user_dialogs(dialogs)
        if not users:
            return False
        entity = getattr(random.choice(users), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 0.6, 2.0)
        msgs = await telethon.get_messages(entity, limit=4)
        if not msgs:
            return False
        pin = getattr(telethon, "pin_message", None)
        if callable(pin):
            await pin(entity, msgs[0], notify=False)
            return True
        from telethon.tl.functions.messages import UpdatePinnedMessageRequest

        await telethon(UpdatePinnedMessageRequest(peer=entity, id=int(msgs[0].id), silent=True))
        return True
    except Exception:
        return False


def _seed_query_tokens(query: str) -> list[str]:
    return [token for token in (query or "").lower().replace("ё", "е").split() if len(token) >= 3]


def seed_channel_match_score(chat: Any, query: str) -> int:
    """Higher is better. 0 = do not join this search hit."""
    if chat is None or getattr(chat, "bot", False):
        return 0
    if type(chat).__name__ in {"User", "UserEmpty"}:
        return 0
    title = str(getattr(chat, "title", None) or "").lower().replace("ё", "е")
    username = str(getattr(chat, "username", None) or "").lower()
    if not title and not username:
        return 0
    tokens = _seed_query_tokens(query)
    needle = (query or "").lower().replace("ё", "е")
    score = 0
    if needle and needle in title:
        score += 60
    if tokens and all(token in title for token in tokens):
        score += 40
    elif tokens and sum(1 for token in tokens if token in title) >= max(1, len(tokens) - 1):
        score += 15
    if username and any(token in username for token in tokens):
        score += 10
    if getattr(chat, "broadcast", False):
        score += 12
    if getattr(chat, "megagroup", False) and not getattr(chat, "broadcast", False):
        score += 4
    return score if score >= 40 else 0


def pick_seed_channel(chats: list[Any], query: str) -> Any | None:
    ranked = [(seed_channel_match_score(chat, query), chat) for chat in chats or []]
    ranked = [item for item in ranked if item[0] > 0]
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


async def search_and_join_seed_channel(
    client: Any,
    query: str,
    *,
    lab_mode: bool = False,
    account: Any | None = None,
) -> dict[str, Any]:
    """Search a public title, join the best channel hit, then read a bit of the feed."""
    telethon = _telethon(client)
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.tl.functions.channels import JoinChannelRequest

    await _pause(lab_mode, 1.2, 3.5)
    result = await telethon(SearchRequest(q=query, limit=8))
    chats = list(getattr(result, "chats", None) or [])
    target = pick_seed_channel(chats, query)
    if target is None:
        return {"status": "no_match", "query": query}
    await _pause(lab_mode, 1.5, 4.5)
    try:
        entity = await telethon.get_entity(target)
    except Exception:
        entity = target
    already = False
    try:
        await telethon(JoinChannelRequest(entity))
    except Exception as exc:
        name = type(exc).__name__
        if "UserAlreadyParticipant" in name or "already" in str(exc).lower():
            already = True
        else:
            return {"status": "error", "query": query, "error": str(exc)[:200]}
    if not lab_mode:
        await settle_after_join(client, entity, account, lab_mode=lab_mode)
    return {
        "status": "already" if already else "ok",
        "query": query,
        "title": getattr(entity, "title", None) or getattr(target, "title", None),
        "username": getattr(entity, "username", None) or getattr(target, "username", None),
        "chat_id": getattr(entity, "id", None) or getattr(target, "id", None),
    }


async def search_public_channels(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        from telethon.tl.functions.contacts import SearchRequest

        query = random.choice(_PUBLIC_SEARCH)
        await _pause(lab_mode, 1.2, 3.5)
        result = await telethon(SearchRequest(q=query, limit=8))
        chats = list(getattr(result, "chats", None) or [])
        if not chats:
            return True
        target = random.choice(chats)
        await _pause(lab_mode, 1.5, 4.5)
        try:
            entity = await telethon.get_entity(target)
        except Exception:
            entity = target
        msgs = await telethon.get_messages(entity, limit=random.randint(5, 10))
        if msgs and random.random() < 0.55:
            last_id = getattr(msgs[0], "id", None)
            if last_id:
                await telethon.send_read_acknowledge(entity, max_id=int(last_id))
        return True
    except Exception as exc:
        logger.debug("Public search skipped: %s", exc)
        return False


async def open_commenter_profile(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        from telethon.tl.functions.users import GetFullUserRequest

        dialogs = await telethon.get_dialogs(limit=14)
        channels = _channel_posts(dialogs)
        if not channels:
            return False
        entity = getattr(random.choice(channels), "entity", None)
        if entity is None:
            return False
        posts = await telethon.get_messages(entity, limit=6)
        threaded = [item for item in (posts or []) if getattr(getattr(item, "replies", None), "replies", 0)]
        if not threaded:
            return False
        comments = await telethon.get_messages(entity, limit=10, reply_to=getattr(threaded[0], "id", None))
        senders = [
            getattr(item, "sender", None)
            for item in (comments or [])
            if getattr(item, "sender", None) and not getattr(item.sender, "bot", False) and not getattr(item.sender, "is_self", False)
        ]
        if not senders:
            return False
        await _pause(lab_mode, 0.8, 2.2)
        await telethon(GetFullUserRequest(random.choice(senders)))
        return True
    except Exception:
        return False


async def block_random_commenter(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        from telethon.tl.functions.contacts import BlockRequest

        dialogs = await telethon.get_dialogs(limit=12)
        channels = _channel_posts(dialogs)
        if not channels:
            return False
        entity = getattr(random.choice(channels), "entity", None)
        posts = await telethon.get_messages(entity, limit=5) if entity else []
        threaded = [item for item in (posts or []) if getattr(getattr(item, "replies", None), "replies", 0)]
        if not threaded:
            return False
        comments = await telethon.get_messages(entity, limit=8, reply_to=getattr(threaded[0], "id", None))
        senders = [
            getattr(item, "sender", None)
            for item in (comments or [])
            if getattr(item, "sender", None)
            and not getattr(item.sender, "bot", False)
            and not getattr(item.sender, "is_self", False)
            and not getattr(item.sender, "contact", False)
        ]
        if not senders:
            return False
        await _pause(lab_mode, 0.8, 2.0)
        await telethon(BlockRequest(id=random.choice(senders)))
        return True
    except Exception:
        return False


async def archive_random_chat(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=16)
        pool = [item for item in (dialogs or []) if not getattr(item, "archived", False)]
        if not pool:
            return False
        entity = getattr(random.choice(pool), "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 0.5, 1.8)
        edit = getattr(telethon, "edit_folder", None)
        if callable(edit):
            await edit(entity, 1)
            return True
        return False
    except Exception:
        return False


async def ask_themed_chat_question(client: Any, *, lab_mode: bool = False) -> bool:
    telethon = _telethon(client)
    try:
        dialogs = await telethon.get_dialogs(limit=16)
        groups = _group_dialogs(dialogs)
        if not groups:
            return False
        dialog = random.choice(groups)
        entity = getattr(dialog, "entity", None)
        if entity is None:
            return False
        await _pause(lab_mode, 2.0, 6.0)
        text = random.choice(_CHAT_QUESTIONS)
        sent = await telethon.send_message(entity, text)
        client._chat_question = {
            "status": "success",
            "chat_id": getattr(entity, "id", None),
            "message_id": getattr(sent, "id", None),
            "text": text,
        }
        return True
    except Exception as exc:
        logger.debug("Chat question skipped: %s", exc)
        return False


async def reply_farm_chat_question(
    client: Any,
    *,
    lab_mode: bool = False,
    farm_questions: list[dict[str, Any]] | None = None,
) -> bool:
    questions = [item for item in (farm_questions or []) if item.get("chat_id") and item.get("message_id")]
    if not questions:
        return False
    telethon = _telethon(client)
    target = random.choice(questions)
    try:
        await _pause(lab_mode, 1.5, 5.0)
        entity = await telethon.get_entity(int(target["chat_id"]))
        await telethon.send_message(entity, random.choice(_FARM_REPLIES), reply_to=int(target["message_id"]))
        client._chat_reply = {
            "status": "success",
            "chat_id": target.get("chat_id"),
            "message_id": target.get("message_id"),
        }
        return True
    except Exception as exc:
        logger.debug("Farm chat reply skipped: %s", exc)
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


def _observe_catalog() -> list[tuple[str, Callable[..., Awaitable[bool]]]]:
    return [
        ("scroll_channels", scroll_subscribed_channels),
        ("stories", glance_stories),
        ("view_profile", view_recent_profile),
        ("typing_idle", typing_without_send),
        ("afk", sit_afk),
        ("read_comments", read_channel_comments),
        ("open_commenter", open_commenter_profile),
        ("react", react_in_subscriptions),
        ("comment_contact", add_commenter_contact),
    ]


def _session_mix_stage(stage: str, phase: str | None) -> str:
    """After primary warmup, first-week accounts still get the full non-spam mix."""
    if phase == PHASE_RAMP and stage == STAGE_CAUTIOUS:
        return STAGE_NORMAL
    return stage


def _inter_action_pause_range(stage: str, phase: str | None) -> tuple[float, float]:
    """Seconds between gestures. Slow on purpose — people do not tap every 2s."""
    if phase in {PHASE_OBSERVE, PHASE_REPLY}:
        return (8.0, 24.0)
    if stage == STAGE_TRUSTED:
        return (16.0, 48.0)
    if stage == STAGE_NORMAL:
        return (12.0, 38.0)
    return (10.0, 28.0)


def _action_catalog(
    stage: str,
    *,
    allowed: set[str] | None = None,
    phase: str | None = None,
) -> list[tuple[str, Callable[..., Awaitable[bool]]]]:
    """Stage gates writes. Day 1 only reads/reacts/contacts; no first DMs."""
    if phase in {PHASE_OBSERVE, PHASE_REPLY}:
        actions = _observe_catalog()
        if phase == PHASE_REPLY:
            actions.append(("react_dm", react_in_dm))
        if allowed is not None:
            actions = [(name, fn) for name, fn in actions if name in allowed]
        return actions
    stage = _session_mix_stage(stage, phase)
    actions: list[tuple[str, Callable[..., Awaitable[bool]]]] = [
        ("scroll_channels", scroll_subscribed_channels),
        ("stories", glance_stories),
        ("view_profile", view_recent_profile),
        ("typing_idle", typing_without_send),
        ("afk", sit_afk),
        ("read_comments", read_channel_comments),
        ("search_public", search_public_channels),
        ("open_commenter", open_commenter_profile),
    ]
    if stage in {STAGE_NORMAL, STAGE_TRUSTED}:
        actions.extend(
            [
                ("react", react_in_subscriptions),
                ("search", search_in_recent_chat),
                ("draft", leave_then_clear_draft),
                ("comment_contact", add_commenter_contact),
                ("react_dm", react_in_dm),
                ("forward_saved", forward_to_saved),
                ("archive_chat", archive_random_chat),
                ("reply_farm", reply_farm_chat_question),
            ]
        )
    if stage == STAGE_TRUSTED:
        actions.extend(
            [
                ("saved", note_in_saved),
                ("pin_dm", pin_recent_dm),
                ("block_commenter", block_random_commenter),
                ("ask_chat", ask_themed_chat_question),
            ]
        )
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
    farm_questions: list[dict[str, Any]] | None = None,
    stay_online: bool | None = None,
) -> dict[str, Any]:
    """Keep one socket open and look alive. Ramp accounts stay online for the work day."""
    phase = account_upload_phase(account)
    if not lab_mode and (account_in_settle_rest(account) or phase == PHASE_SETTLE or not account_may_humanize(account)):
        return {
            "stage": account_humanization_stage(account),
            "budget": 0,
            "actions": [],
            "seconds": 0,
            "comment_contact": None,
            "chat_question": None,
            "chat_reply": None,
        }
    stage = intensity if intensity in {STAGE_CAUTIOUS, STAGE_NORMAL, STAGE_TRUSTED} else account_humanization_stage(account)
    mix_stage = _session_mix_stage(stage, phase)
    keep_presence = account_may_keep_alive(account) if stay_online is None else bool(stay_online)
    budget = humanization_session_action_budget(account, stage=mix_stage)
    if session_minutes and not lab_mode:
        target_seconds = float(max(60, min(15 * 60, int(session_minutes) * 60)))
    else:
        target_seconds = 0.0 if lab_mode else humanization_session_seconds(account, stage=mix_stage)
    started = time.monotonic()
    done: list[str] = []
    client._comment_contact = None
    policy = contact_policy or comment_contact_policy(account)

    if await set_presence(client, offline=False, lab_mode=lab_mode):
        done.append("online")

    await browse_open_app(client, account, lab_mode=lab_mode)
    done.append("browse")
    content = 1

    catalog = _action_catalog(stage, allowed=allowed_actions, phase=phase)
    from .account_restriction import LIMITED_KINDS, restriction_kind

    if restriction_kind(account) in LIMITED_KINDS:
        catalog = [(name, fn) for name, fn in catalog if name not in {"react_dm", "pin_dm"}]
    random.shuffle(catalog)
    pause_lo, pause_hi = _inter_action_pause_range(mix_stage, phase)
    for name, fn in catalog:
        if content >= budget:
            break
        await _pause(lab_mode, pause_lo, pause_hi)
        try:
            if name == "comment_contact":
                ok = await fn(client, lab_mode=lab_mode, account=account, policy=policy)
            elif name == "reply_farm":
                ok = await fn(client, lab_mode=lab_mode, farm_questions=farm_questions)
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
    if leftover > 4 and not lab_mode and not keep_presence:
        await asyncio.sleep(min(leftover, 90.0))
        done.append("idle_hold")

    if not keep_presence:
        if await set_presence(client, offline=True, lab_mode=lab_mode):
            done.append("offline")

    return {
        "stage": stage,
        "budget": budget,
        "actions": done,
        "seconds": round(time.monotonic() - started, 2),
        "comment_contact": getattr(client, "_comment_contact", None),
        "chat_question": getattr(client, "_chat_question", None),
        "chat_reply": getattr(client, "_chat_reply", None),
    }
