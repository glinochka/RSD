"""Per-call cancellation for streaming LLM (barge-in, stage 6)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypeVar

_active: dict[int, asyncio.Event] = {}
T = TypeVar("T")


def register_cancel(call_db_id: int) -> asyncio.Event:
    event = asyncio.Event()
    _active[int(call_db_id)] = event
    return event


def cancel_turn(call_db_id: int) -> bool:
    event = _active.get(int(call_db_id))
    if event is None:
        return False
    event.set()
    return True


def clear_cancel(call_db_id: int) -> None:
    _active.pop(int(call_db_id), None)


def is_cancelled(call_db_id: int) -> bool:
    event = _active.get(int(call_db_id))
    return bool(event and event.is_set())


@asynccontextmanager
async def telephony_turn_scope(call_db_id: int):
    event = register_cancel(call_db_id)
    try:
        yield event
    finally:
        clear_cancel(call_db_id)


async def iter_with_cancel(
    call_db_id: int,
    source: AsyncIterator[T],
) -> AsyncIterator[T]:
    """Yield from async iterator until cancellation."""
    cancel = _active.get(int(call_db_id))
    async for item in source:
        if cancel and cancel.is_set():
            break
        yield item
