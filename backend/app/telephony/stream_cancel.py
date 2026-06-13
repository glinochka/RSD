"""Per-call cancellation for streaming LLM/TTS (barge-in, stage 5–6)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypeVar

_active_db: dict[int, asyncio.Event] = {}
_active_call: dict[str, asyncio.Event] = {}
T = TypeVar("T")


def register_cancel(call_db_id: int) -> asyncio.Event:
    event = asyncio.Event()
    _active_db[int(call_db_id)] = event
    return event


def register_cancel_call_id(call_id: str) -> asyncio.Event:
    event = asyncio.Event()
    key = str(call_id).strip()
    if key:
        _active_call[key] = event
    return event


def cancel_turn(call_db_id: int) -> bool:
    event = _active_db.get(int(call_db_id))
    if event is None:
        return False
    event.set()
    return True


def cancel_turn_by_call_id(call_id: str) -> bool:
    key = str(call_id).strip()
    if not key:
        return False
    event = _active_call.get(key)
    if event is None:
        return False
    event.set()
    return True


def clear_cancel(call_db_id: int) -> None:
    _active_db.pop(int(call_db_id), None)


def clear_cancel_call_id(call_id: str) -> None:
    _active_call.pop(str(call_id).strip(), None)


def is_cancelled(call_db_id: int) -> bool:
    event = _active_db.get(int(call_db_id))
    return bool(event and event.is_set())


def is_cancelled_call_id(call_id: str) -> bool:
    event = _active_call.get(str(call_id).strip())
    return bool(event and event.is_set())


@asynccontextmanager
async def telephony_turn_scope(call_db_id: int, *, external_call_id: str | None = None):
    register_cancel(call_db_id)
    if external_call_id:
        register_cancel_call_id(external_call_id)
    try:
        yield _active_db.get(int(call_db_id))
    finally:
        clear_cancel(call_db_id)
        if external_call_id:
            clear_cancel_call_id(external_call_id)


async def iter_with_cancel(
    call_db_id: int,
    source: AsyncIterator[T],
    *,
    external_call_id: str | None = None,
) -> AsyncIterator[T]:
    """Yield from async iterator until cancellation."""
    cancel = _active_db.get(int(call_db_id))
    call_cancel = _active_call.get(str(external_call_id or "").strip()) if external_call_id else None
    async for item in source:
        if cancel and cancel.is_set():
            break
        if call_cancel and call_cancel.is_set():
            break
        yield item
