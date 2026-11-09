"""One proxy address for a content-factory account.

The address comes from proxies of this automation that are still free.
A Telegram account's set and its current proxy stay taken. Another factory
account's address stays taken. A dead address is not replaced with a neighbour.
"""
from __future__ import annotations

from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomContentFactoryAccount, CustomProxy, PoolAccount
from .content_factory_antifraud import now_utc
from .proxy_service import (
    connection_payload,
    is_proxy_healthy,
    list_active_proxies,
    probe_proxy_tcp,
    proxy_set_id_list,
    telethon_proxy_dict,
)

PROXY_MISSING = "Нет прокси"


def proxy_public_label(proxy: CustomProxy | None, *, ok: bool) -> str:
    if not ok or proxy is None:
        return PROXY_MISSING
    scheme = str(proxy.scheme or "socks5").strip() or "socks5"
    return f"{scheme}://{proxy.host}:{proxy.port}"


def httpx_proxy_url(proxy: CustomProxy | None) -> str:
    """Connection string for httpx. Callers must not log it: it can carry a password."""
    payload = telethon_proxy_dict(connection_payload(proxy))
    if not payload:
        return ""
    scheme = str(payload.get("proxy_type") or "socks5")
    host = str(payload.get("addr") or "").strip()
    port = int(payload.get("port") or 0)
    if not host or port < 1:
        return ""
    host_part = f"[{host}]" if ":" in host else host
    user = str(payload.get("username") or "").strip()
    if not user:
        return f"{scheme}://{host_part}:{port}"
    auth = quote(user, safe="")
    password = payload.get("password")
    if password:
        auth += ":" + quote(str(password), safe="")
    return f"{scheme}://{auth}@{host_part}:{port}"


def _sync_proxy_error(account: CustomContentFactoryAccount, *, missing: bool) -> None:
    account.proxy_problem = missing
    current = str(account.last_error or "").strip()
    if missing:
        if not current:
            account.last_error = PROXY_MISSING
        return
    if current == PROXY_MISSING:
        account.last_error = None


async def blocked_proxy_ids(
    session: AsyncSession,
    automation_id: int,
    *,
    keep_account_id: int | None = None,
) -> set[int]:
    """Telegram sets, Telegram current addresses, and other factory accounts."""
    blocked: set[int] = set()
    pools = await session.execute(
        select(PoolAccount).where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.removed_at.is_(None),
        )
    )
    for pool in pools.scalars().all():
        blocked.update(proxy_set_id_list(pool))
        if pool.proxy_id:
            blocked.add(int(pool.proxy_id))
    factory_rows = await session.execute(
        select(CustomContentFactoryAccount.proxy_id).where(
            CustomContentFactoryAccount.custom_automation_id == automation_id,
            CustomContentFactoryAccount.proxy_id.is_not(None),
        )
    )
    for proxy_id in factory_rows.scalars().all():
        if proxy_id:
            blocked.add(int(proxy_id))
    if keep_account_id:
        own = await session.get(CustomContentFactoryAccount, int(keep_account_id))
        if own and own.proxy_id:
            blocked.discard(int(own.proxy_id))
    return blocked


def _usable_row(proxy: CustomProxy | None, account: CustomContentFactoryAccount, blocked: set[int]) -> bool:
    if proxy is None:
        return False
    if int(proxy.custom_automation_id) != int(account.custom_automation_id):
        return False
    if not proxy.is_active or bool(proxy.is_dedicated):
        return False
    if int(proxy.id) in blocked:
        return False
    return True


async def _proxy_alive(proxy: CustomProxy) -> bool:
    return await probe_proxy_tcp(proxy.host, int(proxy.port), timeout=3.0)


async def _pick_free(session: AsyncSession, automation_id: int, blocked: set[int]) -> CustomProxy | None:
    rows = await list_active_proxies(session, automation_id)
    free = [
        row
        for row in rows
        if row.is_active and not bool(row.is_dedicated) and int(row.id) not in blocked
    ]
    free.sort(key=lambda row: (0 if is_proxy_healthy(row) else 1, int(row.id)))
    for row in free:
        if await _proxy_alive(row):
            blocked.add(int(row.id))
            return row
    return None


async def ensure_factory_proxy(
    session: AsyncSession,
    account: CustomContentFactoryAccount,
) -> CustomProxy | None:
    """Keep this account's address. Pick a free one only when it has none."""
    blocked = await blocked_proxy_ids(
        session,
        account.custom_automation_id,
        keep_account_id=account.id,
    )
    current = await session.get(CustomProxy, int(account.proxy_id)) if account.proxy_id else None
    if _usable_row(current, account, blocked):
        alive = await _proxy_alive(current)
        _sync_proxy_error(account, missing=not alive)
        account.updated_at = now_utc()
        return current if alive else None
    account.proxy_id = None
    chosen = await _pick_free(session, account.custom_automation_id, blocked)
    if chosen is None:
        _sync_proxy_error(account, missing=True)
        account.updated_at = now_utc()
        return None
    account.proxy_id = chosen.id
    _sync_proxy_error(account, missing=False)
    account.updated_at = now_utc()
    return chosen


async def bind_preferred_proxy(
    session: AsyncSession,
    account: CustomContentFactoryAccount,
    proxy_id: int,
) -> CustomProxy | None:
    """Stick to the address this handshake already used. Do not borrow another."""
    blocked = await blocked_proxy_ids(
        session,
        account.custom_automation_id,
        keep_account_id=account.id,
    )
    proxy = await session.get(CustomProxy, int(proxy_id))
    if not _usable_row(proxy, account, blocked):
        account.proxy_id = None
        _sync_proxy_error(account, missing=True)
        account.updated_at = now_utc()
        return None
    alive = await _proxy_alive(proxy)
    account.proxy_id = proxy.id
    _sync_proxy_error(account, missing=not alive)
    account.updated_at = now_utc()
    return proxy if alive else None


async def reserve_factory_proxy(session: AsyncSession, automation_id: int) -> CustomProxy | None:
    blocked = await blocked_proxy_ids(session, automation_id)
    return await _pick_free(session, automation_id, blocked)


async def handshake_proxy(
    session: AsyncSession,
    automation_id: int,
    *,
    account_id: int | None = None,
) -> CustomProxy | None:
    """Proxy for a YouTube code exchange.

    A new login has no account_id and never uses an address already stored on
    another factory account. It takes one free address; the caller writes that
    same id on the new row. A repeat of a known channel uses only that row's
    address. A dead or unusable own address is not replaced. No free address
    means the caller must not exchange the code and must not create a row.
    """
    if account_id:
        account = await session.get(CustomContentFactoryAccount, int(account_id))
        if (
            account is None
            or int(account.custom_automation_id) != int(automation_id)
            or account.platform != "youtube"
        ):
            return None
        if not account.proxy_id:
            return await reserve_factory_proxy(session, automation_id)
        blocked = await blocked_proxy_ids(session, automation_id, keep_account_id=account.id)
        current = await session.get(CustomProxy, int(account.proxy_id))
        if not _usable_row(current, account, blocked) or not await _proxy_alive(current):
            return None
        return current
    return await reserve_factory_proxy(session, automation_id)


async def proxy_url_for_account(
    session: AsyncSession,
    account: CustomContentFactoryAccount,
) -> str:
    proxy = await ensure_factory_proxy(session, account)
    if proxy is None or account.proxy_problem:
        return ""
    return httpx_proxy_url(proxy)
