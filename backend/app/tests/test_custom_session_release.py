"""Open transactions must not keep a pool connection after the query is done."""
from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.alembic.database import Base, release_session_before_wait
from app.alembic.models import (
    AccountClass,
    AccountPool,
    CustomAutomation,
    CustomPrompt,
    PoolAccount,
    PromptType,
    SocialAccount,
)
def _load_leader_lock():
    """Load the lock helper without app.channels.__init__.

    That package import pulls every channel manager and overflows the
    interpreter stack once the test app is already imported.
    """
    if "app.channels.leader_lock" in sys.modules:
        return sys.modules["app.channels.leader_lock"].PgLeaderLock
    if "app.channels" not in sys.modules:
        package = types.ModuleType("app.channels")
        package.__path__ = [str(Path(__file__).resolve().parents[1] / "channels")]
        package.__package__ = "app.channels"
        sys.modules["app.channels"] = package
    from app.channels.leader_lock import PgLeaderLock

    return PgLeaderLock


PgLeaderLock = _load_leader_lock()
from app.services.custom.account_roles import default_roles_for_class
from app.services.custom.discussion_service import _generate_reply
from app.services.custom.rotation_service import (
    _needs_reset,
    record_successful_send,
    select_account_for_action,
)

pytestmark = pytest.mark.asyncio


def _engine(path, *, size: int):
    return create_async_engine(
        f"sqlite+aiosqlite:///{path.as_posix()}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=size,
        max_overflow=0,
        pool_timeout=1,
        connect_args={"check_same_thread": False},
    )


async def _schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _reply_response() -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"reply": "ок"}'))])


async def test_leader_ping_closes_transaction_and_release_returns_connection(tmp_path):
    engine = _engine(tmp_path / "leader.sqlite", size=1)
    try:
        lock = PgLeaderLock(4, "userbot")
        lock._conn = await engine.connect()
        await lock._conn.execute(text("SELECT 1"))
        assert lock._conn.in_transaction()
        await lock._end_transaction(lock._conn)
        assert lock._conn.in_transaction() is False

        await lock._conn.execute(text("SELECT 1"))
        await lock._end_transaction(lock._conn)
        assert lock._conn.in_transaction() is False
        assert engine.pool.checkedout() == 1

        await lock.release()
        assert engine.pool.checkedout() == 0
        async with engine.connect() as other:
            await other.execute(text("SELECT 1"))
            await other.commit()
            assert other.in_transaction() is False
    finally:
        await engine.dispose()


async def test_daily_reset_commits_outside_the_callers_transaction(tmp_path):
    engine = _engine(tmp_path / "reset.sqlite", size=2)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
    try:
        await _schema(engine)
        async with factory() as session:
            automation = CustomAutomation(name="Pool", status="active", max_daily_messages_per_account=50)
            session.add(automation)
            await session.flush()
            pool = AccountPool(
                custom_automation_id=automation.id,
                name="default",
                purpose="farm",
                is_default=True,
            )
            account = SocialAccount(
                provider="telegram",
                phone_number="+79990000001",
                username="reset_acc",
                display_name="Reset",
                account_class=AccountClass.ONE_DAY.value,
                encrypted_session="enc",
                session_file_path="sessions/reset_acc.session",
                is_active=True,
                is_banned=False,
                daily_messages_sent=9,
                daily_messages_reset_at=old,
            )
            session.add(pool)
            session.add(account)
            await session.flush()
            session.add(
                PoolAccount(
                    account_pool_id=pool.id,
                    social_account_id=account.id,
                    assigned_class=AccountClass.ONE_DAY.value,
                    custom_automation_id=automation.id,
                    roles=default_roles_for_class(AccountClass.ONE_DAY.value),
                )
            )
            await session.commit()
            account_id = account.id
            automation_id = automation.id

            picked = await select_account_for_action(session, automation_id, "commenting")
            assert picked is not None
            assert picked.id == account_id
            assert picked.daily_messages_sent == 0
            assert picked not in session.dirty
            await session.rollback()

        async with factory() as check:
            fresh = await check.get(SocialAccount, account_id)
            assert fresh is not None
            assert fresh.daily_messages_sent == 0
            assert _needs_reset(fresh.daily_messages_reset_at) is False
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


async def test_prompt_read_returns_connection_before_the_slow_call(tmp_path):
    engine = _engine(tmp_path / "prompt.sqlite", size=1)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    seen: dict[str, bool] = {}
    try:
        await _schema(engine)
        async with factory() as session:
            automation = CustomAutomation(name="Prompts", status="active")
            session.add(automation)
            await session.flush()
            session.add(
                CustomPrompt(
                    custom_automation_id=automation.id,
                    prompt_type=PromptType.DISCUSSION_REPLY.value,
                    name="Reply",
                    content="Ответь на {message_text} в {chat_title}",
                    is_active=True,
                )
            )
            await session.commit()
            automation_id = automation.id
            assert engine.pool.checkedout() == 0

            async def fake_create(**kwargs):
                seen["idle"] = session.in_transaction() is False
                seen["pool"] = engine.pool.checkedout() == 0
                async with engine.connect() as extra:
                    await extra.execute(text("SELECT 1"))
                    await extra.commit()
                seen["second"] = True
                return _reply_response()

            with patch(
                "app.services.custom.discussion_service.ai_client.chat.completions.create",
                new=fake_create,
            ):
                reply = await _generate_reply(
                    session,
                    automation_id,
                    message_text="привет",
                    chat_title="чат",
                )
            assert reply
            assert seen == {"idle": True, "pool": True, "second": True}
            assert session.in_transaction() is False
            assert engine.pool.checkedout() == 0
            await release_session_before_wait(session)
            assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()


async def test_two_concurrent_sends_increment_the_counter_to_two(tmp_path):
    engine = _engine(tmp_path / "sends.sqlite", size=2)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        await _schema(engine)
        async with factory() as session:
            account = SocialAccount(
                provider="telegram",
                phone_number="+79990000002",
                username="two_sends",
                display_name="Two",
                account_class=AccountClass.ONE_DAY.value,
                encrypted_session="enc",
                session_file_path="sessions/two_sends.session",
                is_active=True,
                is_banned=False,
                daily_messages_sent=0,
                daily_messages_reset_at=today,
            )
            session.add(account)
            await session.commit()
            account_id = account.id

        ready = asyncio.Barrier(2)

        async def send() -> None:
            async with factory() as session:
                loaded = await session.get(SocialAccount, account_id)
                await session.commit()
                await ready.wait()
                await record_successful_send(session, loaded)

        await asyncio.gather(send(), send())

        async with factory() as check:
            fresh = await check.get(SocialAccount, account_id)
            assert fresh is not None
            assert fresh.daily_messages_sent == 2
        assert engine.pool.checkedout() == 0
    finally:
        await engine.dispose()
