"""PostgreSQL advisory lock helper for single-leader workers."""
from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from ..alembic.database import engine

logger = logging.getLogger(__name__)


class PgLeaderLock:
    """Keep a session-level advisory lock on a dedicated DB connection."""

    def __init__(self, key: int, name: str) -> None:
        self._key = int(key)
        self._name = name
        self._conn: AsyncConnection | None = None
        self._unsupported_backend = False

    async def _end_transaction(self, conn: AsyncConnection) -> None:
        """Advisory locks are session-level and survive COMMIT.

        Leaving the ping transaction open shows up as idle in transaction
        with last query SELECT 1 for as long as the worker lives.
        """
        if not conn.in_transaction():
            return
        try:
            await conn.commit()
        except Exception:
            try:
                await conn.rollback()
            except Exception:
                logger.debug("leader lock '%s': rollback failed", self._name, exc_info=True)
            raise

    async def ensure_acquired(self) -> bool:
        if self._unsupported_backend:
            return True
        if self._conn is not None:
            try:
                await self._conn.execute(text("SELECT 1"))
                await self._end_transaction(self._conn)
                return True
            except Exception:
                logger.warning("leader lock '%s': DB connection lost, releasing lock", self._name)
                await self.release()

        conn: AsyncConnection | None = None
        try:
            conn = await engine.connect()
            acquired = bool(
                await conn.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": self._key},
                )
            )
            if not acquired:
                await self._end_transaction(conn)
                await conn.close()
                return False
            await self._end_transaction(conn)
            self._conn = conn
            logger.info("leader lock '%s': acquired", self._name)
            return True
        except Exception as exc:
            if conn is not None and self._conn is None:
                try:
                    await conn.close()
                except Exception:
                    logger.debug("leader lock '%s': close after error failed", self._name, exc_info=True)
            # Non-Postgres backends don't support pg advisory locks.
            msg = str(exc).lower()
            if "pg_try_advisory_lock" in msg or "does not exist" in msg or "not supported" in msg:
                self._unsupported_backend = True
                logger.warning(
                    "leader lock '%s': advisory locks unsupported, running without lock",
                    self._name,
                )
                return True
            raise

    async def release(self) -> None:
        if self._conn is None:
            return
        conn = self._conn
        self._conn = None
        try:
            await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self._key})
            await self._end_transaction(conn)
            logger.info("leader lock '%s': released", self._name)
        except Exception:
            logger.debug("leader lock '%s': unlock failed", self._name, exc_info=True)
        finally:
            await conn.close()
