"""Human-like Telegram activity: DM timing, read receipts, typing, multi-bubble sends,
idle browsing, emoji-only reactions, and occasional message edits.

Design notes
------------
• All public-send paths go through show_typing → send so the typing indicator
  is always proportional to message length.
• Multi-bubble splits at sentence boundaries (30% chance by default) so long
  replies look naturally typed in pieces rather than pasted.
• Idle browsing opens 2-4 random dialogs for 3-8 s each without replying –
  simulates a human scrolling the chat list.
• Message edits happen 10-20 % of the time, 30-120 s after the initial send
  (e.g. fixing a typo or adding a detail).
• "Read but delayed reply" is achieved by mark_dialog_read + returning without
  sending. Callers that want this behaviour call human_mark_read_only().
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import re
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# DM timing constants
# ---------------------------------------------------------------------------
REPLY_DELAY_MIN_SECONDS = 60
REPLY_DELAY_MAX_SECONDS = 240

# Typing simulation
TYPING_MIN_SECONDS = 2.0
TYPING_MAX_SECONDS = 18.0
TYPING_CHARS_PER_SECOND = 7.5
TYPING_REFRESH_SECONDS = 4.5

# Multi-bubble
BUBBLE_SPLIT_CHANCE = 0.30        # 30 % of messages are split into 2-3 parts
BUBBLE_INTER_DELAY_MIN = 2.5      # seconds between bubbles
BUBBLE_INTER_DELAY_MAX = 7.0

# Message edit
EDIT_CHANCE = 0.12                # 12 % chance of editing after send
EDIT_DELAY_MIN = 30               # seconds before edit
EDIT_DELAY_MAX = 120

# Emoji-only standalone reaction
_EMOJI_REACTIONS = ("👍", "🔥", "❤", "👏", "🥰", "💯", "😊", "🙌", "✨", "😂")

# Public-post constants
_PUBLIC_REACTION_CHANCE = 0.14
_PUBLIC_REACTIONS = ("👍", "🔥", "❤", "👏", "🥰")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stable_reply_delay_seconds(external_id: str) -> int:
    """Deterministic delay in [60, 240] so scheduler retries stay consistent."""
    digest = hashlib.sha256(str(external_id).encode("utf-8")).hexdigest()
    span = REPLY_DELAY_MAX_SECONDS - REPLY_DELAY_MIN_SECONDS + 1
    return REPLY_DELAY_MIN_SECONDS + (int(digest[:8], 16) % span)


def message_age_seconds(msg: Any, *, now: datetime | None = None) -> float | None:
    sent_at = getattr(msg, "date", None)
    if sent_at is None:
        return None
    if getattr(sent_at, "tzinfo", None) is not None:
        sent_at = sent_at.astimezone(timezone.utc).replace(tzinfo=None)
    current = now or _utc_now()
    return max(0.0, (current - sent_at).total_seconds())


def is_ready_to_reply(
    msg: Any,
    external_id: str,
    *,
    now: datetime | None = None,
    lab_mode: bool = False,
) -> bool:
    """True only after 1–4 min open delay. Test lab replies immediately."""
    if lab_mode:
        return True
    age = message_age_seconds(msg, now=now)
    if age is None:
        return True
    return age >= stable_reply_delay_seconds(external_id)


def typing_duration_seconds(text: str, *, lab_mode: bool = False) -> float:
    if lab_mode:
        return 0.0
    length = max(len((text or "").strip()), 1)
    raw = length / TYPING_CHARS_PER_SECOND
    jitter = random.uniform(0.85, 1.2)
    return min(TYPING_MAX_SECONDS, max(TYPING_MIN_SECONDS, raw * jitter))


# ---------------------------------------------------------------------------
# Text splitting for multi-bubble sends
# ---------------------------------------------------------------------------

def _split_into_bubbles(text: str, max_parts: int = 3) -> list[str]:
    """Split text at natural sentence/clause boundaries into 2–max_parts parts.

    Falls back to a single part if the text is short or no good split point found.
    """
    text = text.strip()
    if len(text) < 60 or max_parts < 2:
        return [text]

    # Find split candidates: '. ', '! ', '? ', '; ', ' — '
    pattern = re.compile(r'(?<=[.!?;])\s+|(?<=—)\s+')
    segments: list[str] = []
    last = 0
    for m in pattern.finditer(text):
        seg = text[last:m.start()].strip()
        if seg:
            segments.append(seg)
        last = m.end()
    tail = text[last:].strip()
    if tail:
        segments.append(tail)

    if len(segments) < 2:
        return [text]

    # Group segments into max_parts chunks
    target = min(max_parts, len(segments))
    chunk_size = max(1, len(segments) // target)
    parts: list[str] = []
    for i in range(0, len(segments), chunk_size):
        chunk = " ".join(segments[i:i + chunk_size]).strip()
        if chunk:
            parts.append(chunk)
        if len(parts) >= target:
            # Append any remaining text to the last part
            remainder = " ".join(segments[i + chunk_size:]).strip()
            if remainder:
                parts[-1] = parts[-1] + " " + remainder
            break

    return parts if len(parts) >= 2 else [text]


def _make_minor_edit(text: str) -> str:
    """Return a slightly different version of the text (fix trailing punctuation, add detail)."""
    text = text.strip()
    suffixes = ["", " 👍", " ✓", "!", ".", " )"]
    if text.endswith("."):
        text = text[:-1]
    return text + random.choice(suffixes)


# ---------------------------------------------------------------------------
# Core send primitives
# ---------------------------------------------------------------------------

async def mark_dialog_read(
    client: Any,
    entity: Any,
    message: Any | None = None,
    *,
    max_id: int | None = None,
) -> None:
    """Blue ticks: acknowledge read up to the incoming message."""
    telethon = getattr(client, "client", client)
    kwargs = {"clear_mentions": True, "clear_reactions": True}
    if message is not None:
        await telethon.send_read_acknowledge(entity, message, **kwargs)
    elif max_id is not None:
        await telethon.send_read_acknowledge(entity, max_id=int(max_id), **kwargs)
    else:
        await telethon.send_read_acknowledge(entity, **kwargs)


async def show_typing(client: Any, entity: Any, duration: float) -> None:
    """Keep the typing indicator alive for roughly `duration` seconds."""
    if duration <= 0:
        return
    telethon = getattr(client, "client", client)
    remaining = max(float(duration), TYPING_MIN_SECONDS)
    while remaining > 0:
        chunk = min(TYPING_REFRESH_SECONDS, remaining)
        async with telethon.action(entity, "typing"):
            await asyncio.sleep(chunk)
        remaining -= chunk


# ---------------------------------------------------------------------------
# Human mark-read without reply  ("read but didn't respond yet")
# ---------------------------------------------------------------------------

async def human_mark_read_only(
    client: Any,
    entity: Any,
    message: Any | None = None,
    *,
    max_id: int | None = None,
    lab_mode: bool = False,
) -> None:
    """Mark a dialog as read without sending a reply.

    Use when the scheduler decides the account 'saw' the message but will
    reply later (delayed reply pattern).  This keeps blue ticks realistic.
    """
    try:
        await mark_dialog_read(client, entity, message, max_id=max_id)
        if not lab_mode:
            await asyncio.sleep(random.uniform(0.4, 1.2))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Multi-bubble send
# ---------------------------------------------------------------------------

async def human_send_bubbles(
    client: Any,
    entity: Any,
    text: str,
    *,
    max_bubbles: int = 3,
    reply_to: int | None = None,
    lab_mode: bool = False,
) -> list[Any]:
    """Split text into 2-3 parts and send with typing + natural pauses between.

    Returns list of sent message objects.
    """
    telethon = getattr(client, "client", client)
    parts = _split_into_bubbles(text, max_parts=max_bubbles) if not lab_mode else [text]
    messages = []
    for i, part in enumerate(parts):
        if not lab_mode:
            if i > 0:
                await asyncio.sleep(random.uniform(BUBBLE_INTER_DELAY_MIN, BUBBLE_INTER_DELAY_MAX))
            await show_typing(client, entity, typing_duration_seconds(part, lab_mode=False))
        kwargs: dict[str, Any] = {}
        if reply_to is not None and i == 0:
            kwargs["reply_to"] = reply_to
        msg = await telethon.send_message(entity, part, **kwargs)
        messages.append(msg)
    return messages


# ---------------------------------------------------------------------------
# Message editing (human typo-correction pattern)
# ---------------------------------------------------------------------------

async def maybe_edit_message(
    client: Any,
    entity: Any,
    message: Any,
    original_text: str,
    *,
    edit_chance: float = EDIT_CHANCE,
    lab_mode: bool = False,
) -> None:
    """After a short delay (30-120 s), optionally edit the sent message slightly.

    Simulates a human noticing a typo or adding a small detail.
    This runs in the background (fire-and-forget via asyncio.create_task).
    """
    if lab_mode or not message or random.random() > edit_chance:
        return
    msg_id = getattr(message, "id", None)
    if not msg_id:
        return

    async def _do_edit() -> None:
        await asyncio.sleep(random.uniform(EDIT_DELAY_MIN, EDIT_DELAY_MAX))
        try:
            telethon = getattr(client, "client", client)
            edited = _make_minor_edit(original_text)
            if edited != original_text:
                await telethon.edit_message(entity, msg_id, edited)
        except Exception:
            pass  # edits are best-effort

    asyncio.create_task(_do_edit())


# ---------------------------------------------------------------------------
# Standalone emoji reaction (no text comment)
# ---------------------------------------------------------------------------

async def send_emoji_reaction_only(
    client: Any,
    entity: Any,
    *,
    emoji: str | None = None,
    lab_mode: bool = False,
) -> None:
    """Send a standalone emoji message — simulates a quick emotional reaction.

    This is intentionally sent as a text message (not a Telegram reaction),
    so it shows up naturally in the chat history.
    """
    chosen = emoji or random.choice(_EMOJI_REACTIONS)
    if not lab_mode:
        await asyncio.sleep(random.uniform(0.5, 2.5))
    try:
        telethon = getattr(client, "client", client)
        await telethon.send_message(entity, chosen)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Random idle browsing
# ---------------------------------------------------------------------------

async def random_idle_browse(
    client: Any,
    *,
    n_dialogs: int | None = None,
    lab_mode: bool = False,
) -> None:
    """Open 2-4 random dialogs and skim message history without replying.

    Creates the realistic 'account is actively using Telegram' signal without
    any detectable writing pattern.
    """
    if lab_mode:
        return
    count = n_dialogs or random.randint(2, 4)
    telethon = getattr(client, "client", client)
    try:
        dialogs = await telethon.get_dialogs(limit=20)
        if not dialogs:
            return
        sample = random.sample(list(dialogs), min(count, len(dialogs)))
        for dialog in sample:
            try:
                entity = dialog.entity
                await asyncio.sleep(random.uniform(2.0, 6.0))
                # Fetch a few messages (read intent)
                msgs = await telethon.get_messages(entity, limit=random.randint(3, 8))
                if msgs:
                    await asyncio.sleep(random.uniform(1.5, 4.5))
                    # Occasionally mark as read
                    if random.random() < 0.5:
                        last_id = getattr(msgs[0], "id", None)
                        if last_id:
                            try:
                                await telethon.send_read_acknowledge(entity, max_id=last_id)
                            except Exception:
                                pass
            except Exception:
                continue
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Glance + reaction helpers (shared by public send paths)
# ---------------------------------------------------------------------------

async def glance_neighbor_posts(
    client: Any,
    entity: Any,
    around_id: int | None,
    *,
    lab_mode: bool = False,
) -> None:
    """Open 2–3 nearby messages without commenting — people rarely land on one post."""
    if lab_mode:
        return
    telethon = getattr(client, "client", client)
    try:
        want = random.randint(2, 3)
        messages = await telethon.get_messages(entity, limit=want + 1)
        viewed = 0
        for msg in messages or []:
            mid = getattr(msg, "id", None)
            if mid is None or (around_id is not None and int(mid) == int(around_id)):
                continue
            await asyncio.sleep(random.uniform(0.7, 3.2))
            viewed += 1
            if viewed >= want:
                break
    except Exception:
        pass


async def maybe_react_to_post(
    client: Any,
    entity: Any,
    message_id: int | None,
    *,
    lab_mode: bool = False,
) -> None:
    """Occasionally react to the post before leaving a comment."""
    if lab_mode or not message_id or random.random() > _PUBLIC_REACTION_CHANCE:
        return
    telethon = getattr(client, "client", client)
    emoji = random.choice(_PUBLIC_REACTIONS)
    await asyncio.sleep(random.uniform(0.4, 2.2))
    try:
        send_reaction = getattr(telethon, "send_reaction", None)
        if callable(send_reaction):
            await send_reaction(entity, int(message_id), emoji)
            return
        from telethon.tl.functions.messages import SendReactionRequest
        from telethon.tl.types import ReactionEmoji

        await telethon(
            SendReactionRequest(
                peer=entity,
                msg_id=int(message_id),
                reaction=[ReactionEmoji(emoticon=emoji)],
            )
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Standard DM reply  (private messages)
# ---------------------------------------------------------------------------

async def human_send_reply(
    client: Any,
    entity: Any,
    text: str,
    *,
    incoming_message: Any | None = None,
    max_id: int | None = None,
    skip_read: bool = False,
    skip_typing: bool = False,
    lab_mode: bool = False,
    use_bubbles: bool | None = None,
) -> Any:
    """Read receipt → typing (by reply length) → send.

    `lab_mode=True` skips field delays (1–4 min open, typing sleeps). Read ack still sent.
    `use_bubbles=True` forces multi-bubble; None = random 30 % chance for long texts.
    """
    if not skip_read:
        await mark_dialog_read(client, entity, incoming_message, max_id=max_id)
        if not lab_mode:
            await asyncio.sleep(random.uniform(0.4, 1.2))
    telethon = getattr(client, "client", client)

    # Decide bubble split
    split = use_bubbles if use_bubbles is not None else (
        not lab_mode and len(text.strip()) > 80 and random.random() < BUBBLE_SPLIT_CHANCE
    )
    if split:
        parts = _split_into_bubbles(text, max_parts=3)
    else:
        parts = [text]

    msgs = []
    for i, part in enumerate(parts):
        if not skip_typing and not lab_mode:
            await show_typing(client, entity, typing_duration_seconds(part, lab_mode=False))
        elif i > 0 and not lab_mode:
            await asyncio.sleep(random.uniform(BUBBLE_INTER_DELAY_MIN, BUBBLE_INTER_DELAY_MAX))
        msg = await telethon.send_message(entity, part)
        msgs.append(msg)

    last_msg = msgs[-1] if msgs else None
    # Optionally edit the last bubble after a delay
    if last_msg and not lab_mode:
        asyncio.create_task(
            maybe_edit_message(client, entity, last_msg, parts[-1], lab_mode=False)
        )
    return last_msg


# ---------------------------------------------------------------------------
# Public send  (channel comments, group replies)
# ---------------------------------------------------------------------------

async def human_send_public(
    client: Any,
    entity: Any,
    text: str,
    *,
    comment_to: int | None = None,
    reply_to: int | None = None,
    discussion_entity: Any | None = None,
    lab_mode: bool = False,
) -> Any:
    """Glance → read → typing → send for comments and group replies.

    Multi-bubble is NOT used here (channel comments look odd split up).
    """
    telethon = getattr(client, "client", client)
    typing_peer = discussion_entity or entity
    if not lab_mode:
        await asyncio.sleep(random.uniform(1.5, 9.0))
        await glance_neighbor_posts(client, entity, comment_to or reply_to, lab_mode=False)
        if comment_to is not None:
            await maybe_react_to_post(client, entity, comment_to, lab_mode=False)
        if random.random() < 0.75:
            try:
                await mark_dialog_read(client, typing_peer, max_id=comment_to or reply_to)
            except Exception:
                try:
                    await mark_dialog_read(client, entity)
                except Exception:
                    pass
            await asyncio.sleep(random.uniform(0.6, 2.4))
        await show_typing(client, typing_peer, typing_duration_seconds(text, lab_mode=False))
    kwargs: dict[str, Any] = {}
    if comment_to is not None:
        kwargs["comment_to"] = comment_to
    if reply_to is not None:
        kwargs["reply_to"] = reply_to
    msg = await telethon.send_message(entity, text, **kwargs)
    # Small chance to edit the comment after a delay (typo fix)
    if not lab_mode:
        asyncio.create_task(
            maybe_edit_message(client, entity, msg, text, edit_chance=EDIT_CHANCE * 0.7)
        )
    return msg
