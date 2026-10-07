"""One live Telegram session per account; each enabled task is a stream inside it.

Scheduler no longer runs commenting / broadcasts / warmup as competing loops.
This hub keeps MTProto connected for the work window, then round-robins task
streams and humanization on the same client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.database import async_session_maker
from ...alembic.models import CustomAutomation, PoolAccount, SocialAccount
from .account_roles import account_is_live
from .telegram_account_client import TelegramAccountClient
from .work_mode import apply_work_mode, in_configured_work_hours, in_daily_idle_gap, reset_work_mode

logger = logging.getLogger(__name__)

StreamFn = Callable[[int], Awaitable[Any]]

_hubs: dict[int, "AccountSessionHub"] = {}


class AccountSessionHub:
    def __init__(self, automation_id: int) -> None:
        self.automation_id = automation_id
        self.clients: dict[int, TelegramAccountClient] = {}
        self.cursor = 0

    async def sync(self, accounts: list[SocialAccount]) -> dict[str, int]:
        wanted = {account.id: account for account in accounts if account_is_live(account)}
        opened = 0
        closed = 0
        for account_id, client in list(self.clients.items()):
            account = wanted.get(account_id)
            connected = bool(client.client and getattr(client.client, "is_connected", lambda: False)())
            if account is None or _session_should_sleep(account) or not connected:
                await self._close(account_id)
                closed += 1
        for account in wanted.values():
            if account.id in self.clients:
                continue
            if _session_should_sleep(account):
                continue
            if await self._open(account):
                opened += 1
        return {"opened": opened, "closed": closed, "live": len(self.clients)}

    async def _open(self, account: SocialAccount) -> bool:
        from .proxy_service import recover_dead_proxy, record_proxy_success
        from .telegram_error_handler import looks_like_proxy_dead

        try:
            wrapper = TelegramAccountClient.for_account(account)
            await wrapper.keep_alive()
            self.clients[account.id] = wrapper
            async with async_session_maker() as session:
                fresh = await session.get(SocialAccount, account.id)
                if fresh is not None:
                    await record_proxy_success(session, fresh)
                    await session.commit()
            return True
        except Exception as exc:
            if not looks_like_proxy_dead(exc):
                logger.warning("Account session open failed %s: %s", account.id, exc)
                return False
            logger.warning("Proxy dead for account %s, rotating: %s", account.id, exc)
            await self._close(account.id)
            async with async_session_maker() as session:
                fresh = await session.get(SocialAccount, account.id)
                rotated = await recover_dead_proxy(session, fresh) if fresh is not None else None
                if rotated is not None:
                    await session.commit()
                    await session.refresh(fresh)
            if fresh is None or rotated is None:
                return False
            await asyncio.sleep(2)
            try:
                wrapper = TelegramAccountClient.for_account(fresh)
                await wrapper.keep_alive()
                self.clients[account.id] = wrapper
                return True
            except Exception as retry_exc:
                logger.warning("Reconnect after proxy rotate failed %s: %s", account.id, retry_exc)
                return False

    async def close(self) -> None:
        for account_id in list(self.clients):
            await self._close(account_id)

    async def _close(self, account_id: int) -> None:
        client = self.clients.pop(account_id, None)
        if client is None:
            return
        try:
            await client.drop_alive()
        except Exception:
            logger.debug("Account session close failed %s", account_id, exc_info=True)


def _session_should_sleep(account: SocialAccount) -> bool:
    if in_daily_idle_gap(getattr(account, "id", None)):
        return True
    return not in_configured_work_hours(account_id=getattr(account, "id", None))


async def _load_accounts(session: AsyncSession, automation_id: int) -> list[SocialAccount]:
    rows = (
        await session.execute(
            select(SocialAccount, PoolAccount)
            .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
            .where(
                PoolAccount.custom_automation_id == automation_id,
                PoolAccount.removed_at.is_(None),
            )
        )
    ).all()
    return [account for account, _pool in rows if account_is_live(account)]


def _module_on(blob: dict[str, Any], key: str, fallback: bool = False) -> bool:
    data = blob.get(key) if isinstance(blob.get(key), dict) else {}
    if data.get("enabled") is not None:
        return bool(data.get("enabled"))
    return fallback


def _enabled_streams(automation: CustomAutomation) -> list[tuple[str, StreamFn]]:
    from .account_idle_browse_service import run_idle_browse_pass
    from .account_peer_dialog_service import run_peer_dialog_pass
    from .account_warmup_service import run_account_warmup_pass
    from .chat_join_service import run_join_pending_for_automation
    from .chat_broadcast_service import run_chat_broadcast_pass
    from .discussion_service import run_discussion_pass
    from .dm_broadcast_service import run_dm_broadcast_pass
    from .masslooking_service import run_masslooking_pass
    from .masspriming_service import run_masspriming_pass
    from .neurocommenting_service import run_neurocommenting_pass
    from .shilling_service import run_shilling_pass

    blob = automation.module_settings or {}
    streams: list[tuple[str, StreamFn]] = [
        ("join", run_join_pending_for_automation),
    ]
    if _module_on(blob, "neurocommenting", bool(automation.is_neurocommenting_enabled)):
        streams.append(("neurocommenting", run_neurocommenting_pass))
    if _module_on(blob, "neurochatting", bool(automation.is_digital_footprint_enabled)):
        streams.append(("neurochatting", run_discussion_pass))
    if _module_on(blob, "neuroshilling", bool(automation.is_shilling_enabled)):
        streams.append(("shilling", run_shilling_pass))
    if _module_on(blob, "chat_broadcasts"):
        streams.append(("chat_broadcast", run_chat_broadcast_pass))
    if _module_on(blob, "dm_broadcasts"):
        streams.append(("dm_broadcast", run_dm_broadcast_pass))
    if _module_on(blob, "masslooking"):
        streams.append(("masslooking", run_masslooking_pass))
    if _module_on(blob, "masspriming"):
        streams.append(("masspriming", run_masspriming_pass))
    from .warmup_module_service import runtime_warmup_cfg, warmup_scheduler_active

    wu = runtime_warmup_cfg(automation)
    if warmup_scheduler_active(automation):
        if wu.get("do_warmup_dms") is not False:
            streams.append(("account_warmup", run_account_warmup_pass))
        streams.append(("idle_browse", run_idle_browse_pass))
        if wu.get("do_peer_dialogs") is not False:
            streams.append(("peer_dialog", run_peer_dialog_pass))
    return streams


async def close_account_sessions(automation_id: int) -> None:
    hub = _hubs.pop(automation_id, None)
    if hub:
        await hub.close()


def _work_streams(automation: CustomAutomation) -> list[tuple[str, StreamFn]]:
    return [(name, fn) for name, fn in _enabled_streams(automation) if name != "join"]


async def run_account_sessions(automation_id: int) -> dict[str, Any]:
    """One tick: keep sessions, always join/addlist, then the next work stream."""
    token = None
    try:
        async with async_session_maker() as session:
            automation = await session.get(CustomAutomation, automation_id)
            if not automation:
                await close_account_sessions(automation_id)
                return {"status": "skipped", "reason": "missing"}
            token = apply_work_mode(automation)
            accounts = await _load_accounts(session, automation_id)
            streams = _enabled_streams(automation)
        hub = _hubs.setdefault(automation_id, AccountSessionHub(automation_id))
        sync = await hub.sync(accounts)
        if not hub.clients:
            return {"status": "sleeping", **sync}
        join_fn = next((fn for name, fn in streams if name == "join"), None)
        work = [(name, fn) for name, fn in streams if name != "join"]
        join_result = await join_fn(automation_id) if join_fn else None
        if not work:
            return {"status": "ok", "stream": "join", "join": join_result, "result": join_result, **sync}
        name, fn = work[hub.cursor % len(work)]
        hub.cursor += 1
        result = await fn(automation_id)
        return {"status": "ok", "stream": name, "join": join_result, "result": result, **sync}
    except Exception as exc:
        logger.exception("Account session tick failed for %s: %s", automation_id, exc)
        return {"status": "error", "error": str(exc)[:240]}
    finally:
        if token is not None:
            reset_work_mode(token)
