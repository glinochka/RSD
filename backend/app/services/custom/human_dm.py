"""Human-like Telegram DM timing: delay, read receipts, typing, send."""
from __future__ import annotations

import asyncio
import hashlib
import random
from datetime import datetime, timezone
from typing import Any

# Open chat after 1–4 minutes (stable per message id)
REPLY_DELAY_MIN_SECONDS = 60
REPLY_DELAY_MAX_SECONDS = 240

# Typing simulation bounds
TYPING_MIN_SECONDS = 2.0
TYPING_MAX_SECONDS = 18.0
TYPING_CHARS_PER_SECOND = 7.5
TYPING_REFRESH_SECONDS = 4.5


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
    """Field only: wait 1–4 minutes. Test lab replies immediately."""
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


async def mark_dialog_read(
    client: Any,
    entity: Any,
    message: Any | None = None,
    *,
    max_id: int | None = None,
) -> None:
    """Blue ticks: acknowledge read up to the incoming message."""
    telethon = getattr(client, "client", client)
    kwargs = {
        "clear_mentions": True,
        "clear_reactions": True,
    }
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
) -> None:
    """Read receipt → typing (by reply length) → send.

    `lab_mode=True` skips field delays (1–4 min open, typing sleeps). Read ack still sent.
    """
    if not skip_read:
        await mark_dialog_read(client, entity, incoming_message, max_id=max_id)
        if not lab_mode:
            await asyncio.sleep(random.uniform(0.4, 1.2))
    if not skip_typing and not lab_mode:
        await show_typing(client, entity, typing_duration_seconds(text, lab_mode=False))
    telethon = getattr(client, "client", client)
    await telethon.send_message(entity, text)
