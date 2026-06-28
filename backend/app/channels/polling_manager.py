"""Shared polling loop for channel managers (leader lock + per-connection workers)."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from abc import abstractmethod
from typing import Any

from .base import ChannelManager
from .leader_lock import PgLeaderLock

logger = logging.getLogger(__name__)


class PollingChannelManager(ChannelManager):
    """Poll DB for active connections, spawn/stop workers under a Postgres leader lock."""

    def __init__(
        self,
        *,
        lock_key: int,
        lock_name: str,
        poll_interval_seconds: int,
        channel_name: str,
        log_prefix: str,
        restart_on_fingerprint_change: bool = True,
    ) -> None:
        self._stop = asyncio.Event()
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._config_fingerprints: dict[int, str] = {}
        self._leader_lock = PgLeaderLock(lock_key, lock_name)
        self._poll_interval_seconds = max(1, int(poll_interval_seconds))
        self._channel_name = channel_name
        self._log_prefix = log_prefix
        self._restart_on_fingerprint_change = restart_on_fingerprint_change

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @property
    def active_count(self) -> int:
        return len(self._tasks)

    def config_fingerprint(self, cfg: dict[str, Any]) -> str:
        return json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)

    @abstractmethod
    async def fetch_configs(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def run_worker(self, cfg: dict[str, Any], stop: asyncio.Event) -> None:
        ...

    async def _cancel_all_tasks(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._config_fingerprints.clear()

    async def _stop_worker(self, connection_id: int, *, removed: bool) -> None:
        task = self._tasks.pop(connection_id, None)
        self._config_fingerprints.pop(connection_id, None)
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if removed:
            logger.info("%s: removed connection_id=%s", self._log_prefix, connection_id)

    async def _handle_finished_worker(self, connection_id: int, task: asyncio.Task[None]) -> None:
        self._tasks.pop(connection_id, None)
        self._config_fingerprints.pop(connection_id, None)
        with contextlib.suppress(asyncio.CancelledError):
            try:
                task.result()
            except Exception:
                logger.exception(
                    "%s: previous worker crashed connection_id=%s",
                    self._log_prefix,
                    connection_id,
                )

    async def _restart_worker(self, connection_id: int, task: asyncio.Task[None]) -> None:
        logger.info(
            "%s: config changed, restarting worker connection_id=%s",
            self._log_prefix,
            connection_id,
        )
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            try:
                await task
            except Exception:
                logger.exception(
                    "%s: worker failed during restart connection_id=%s",
                    self._log_prefix,
                    connection_id,
                )
        self._tasks.pop(connection_id, None)

    async def _sync_workers(self, configs: list[dict[str, Any]]) -> None:
        wanted = {
            int(cfg["connection_id"])
            for cfg in configs
            if cfg.get("connection_id") is not None
        }

        for connection_id in list(self._tasks):
            if connection_id not in wanted:
                await self._stop_worker(connection_id, removed=True)

        by_id = {
            int(cfg["connection_id"]): cfg
            for cfg in configs
            if cfg.get("connection_id") is not None
        }
        for connection_id, cfg in by_id.items():
            fingerprint = (
                self.config_fingerprint(cfg) if self._restart_on_fingerprint_change else None
            )
            existing = self._tasks.get(connection_id)
            if existing and existing.done():
                await self._handle_finished_worker(connection_id, existing)
                existing = self._tasks.get(connection_id)

            if (
                existing
                and self._restart_on_fingerprint_change
                and fingerprint is not None
                and self._config_fingerprints.get(connection_id) != fingerprint
            ):
                await self._restart_worker(connection_id, existing)
                existing = None

            if existing is None:
                self._tasks[connection_id] = asyncio.create_task(self.run_worker(cfg, self._stop))
                if fingerprint is not None:
                    self._config_fingerprints[connection_id] = fingerprint
                logger.info("%s: started worker connection_id=%s", self._log_prefix, connection_id)

    async def shutdown(self) -> None:
        self._stop.set()
        await self._cancel_all_tasks()
        await self._leader_lock.release()

    async def run_forever(self) -> None:
        logger.info(
            "%s polling every %s sec",
            self._channel_name,
            self._poll_interval_seconds,
        )
        try:
            while not self._stop.is_set():
                try:
                    is_leader = await self._leader_lock.ensure_acquired()
                    if not is_leader:
                        if self._tasks:
                            await self._cancel_all_tasks()
                        logger.info(
                            "%s: another replica holds leader lock, waiting",
                            self._log_prefix,
                        )
                    else:
                        configs = await self.fetch_configs()
                        await self._sync_workers(configs)
                except Exception:
                    logger.exception("%s cycle failed", self._channel_name)

                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            await self._cancel_all_tasks()
            await self._leader_lock.release()
