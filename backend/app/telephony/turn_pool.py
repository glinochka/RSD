"""Dedicated concurrency pool for telephony turns (stage 5)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import TypeVar

from ..config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_pool: asyncio.Semaphore | None = None


def _pool_size() -> int:
    return max(1, int(settings.TELEPHONY_DEDICATED_POOL_SIZE))


def get_telephony_pool() -> asyncio.Semaphore:
    global _pool
    if _pool is None:
        size = _pool_size()
        _pool = asyncio.Semaphore(size)
        logger.info("telephony turn pool size=%s", size)
    return _pool


async def run_in_telephony_pool(coro: Awaitable[T]) -> T:
    if not settings.TELEPHONY_DEDICATED_POOL_ENABLED:
        return await coro
    async with get_telephony_pool():
        return await coro
