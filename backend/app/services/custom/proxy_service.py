"""Parse, store and evenly assign SOCKS/HTTP proxies to /custom accounts."""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .proxy_geo import (
    country_from_phone,
    normalize_country,
    proxy_fit_key,
    region_for_country,
    split_country_tail,
)
from ...alembic.models import (
    CustomAutomation,
    CustomContentFactoryAccount,
    CustomProxy,
    PoolAccount,
    SocialAccount,
)
from ...utils.crypto import decrypt_token, encrypt_token


logger = getLogger(__name__)

MAX_PROXIES = 500
PROXY_SET_MIN = 2
PROXY_SET_MAX = 4
_UNHEALTHY_TTL = timedelta(minutes=30)
_ROTATE_GAP = timedelta(seconds=90)
_FACTORY_PROXY_HOLDER = -1
_last_rotate_at: dict[int, datetime] = {}
_rotate_locks: dict[int, asyncio.Lock] = {}
_rotate_locks_guard = asyncio.Lock()
_ALLOWED_SCHEMES = {"socks5": "socks5", "socks4": "socks4", "http": "http", "https": "http", "socks5h": "socks5"}
_URL_LINE_RE = re.compile(
    r"^(?P<scheme>https?|socks5h?|socks4)://(?P<body>.+)$",
    re.IGNORECASE,
)
_USER_AT_V6_RE = re.compile(
    r"^(?P<username>[^:@\s]+):(?P<password>[^@]*?)@\[(?P<host>[0-9a-fA-F:]+)\]:(?P<port>\d+)$"
)
_USER_AT_RE = re.compile(
    r"^(?P<username>[^:@\s]+):(?P<password>[^@]*?)@(?P<host>[^:\[\]\s]+):(?P<port>\d+)$"
)
_HOST_PORT_V6_RE = re.compile(r"^\[(?P<host>[0-9a-fA-F:]+)\]:(?P<port>\d+)$")
_HOST_PORT_RE = re.compile(r"^(?P<host>[^:\[\]\s]+):(?P<port>\d+)$")
_IPV6_AUTH_RE = re.compile(
    r"^\[(?P<host>[0-9a-fA-F:]+)\]:(?P<port>\d+):(?P<username>[^:]*):(?P<password>.*)$"
)


class ProxyParseError(ValueError):
    """Raised when a pasted proxy list cannot be applied."""


class ProxyChoiceError(ValueError):
    """Raised when a connect/upload proxy pick is invalid."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_scheme(value: str | None) -> str:
    raw = (value or "socks5").strip().lower()
    if raw.endswith(":"):
        raw = raw[:-1]
    mapped = _ALLOWED_SCHEMES.get(raw)
    if not mapped:
        raise ValueError(f"Неподдерживаемый тип прокси: {value}")
    return mapped


def _parse_port(value: Any) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Порт должен быть числом") from exc
    if port < 1 or port > 65535:
        raise ValueError("Порт вне диапазона 1–65535")
    return port


def _parse_host(value: str | None) -> str:
    host = (value or "").strip().strip("[]")
    if not host or " " in host:
        raise ValueError("Пустой хост")
    return host


def detect_ip_version(host: str) -> int | None:
    try:
        return ipaddress.ip_address((host or "").strip().strip("[]")).version
    except ValueError:
        return None


def vendor_socks5_port(port: int) -> int | None:
    """HTTP 1xxxx → SOCKS5 2xxxx used by several IPv6 shops. 1080/8080 stay."""
    if port < 10000 or port > 65535:
        return None
    text = str(port)
    if text[0] != "1":
        return None
    bumped = int("2" + text[1:])
    if bumped > 65535:
        return None
    return bumped


def proxy_fingerprint(scheme: str, host: str, port: int, username: str | None) -> str:
    raw = f"{scheme}|{host.lower()}|{port}|{(username or '').lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _split_country_field(parts: list[str]) -> tuple[list[str], str | None]:
    if len(parts) < 5:
        return parts, None
    last = parts[-1].strip()
    code = normalize_country(last)
    if not code:
        return parts, None
    if len(last) > 2 and not last.isalpha():
        return parts, None
    return parts[:-1], code


def _parsed(
    scheme: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    *,
    country_code: str | None = None,
    scheme_explicit: bool = False,
) -> dict[str, Any]:
    username = (username or "").strip() or None
    password = password if password else None
    host = _parse_host(host)
    return {
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "country_code": country_code,
        "region": region_for_country(country_code),
        "ip_version": detect_ip_version(host),
        "scheme_explicit": scheme_explicit,
        "fingerprint": proxy_fingerprint(scheme, host, port, username),
    }


def parse_proxy_line(raw: str) -> dict[str, Any]:
    stripped = (raw or "").strip()
    if not stripped or stripped.startswith("#"):
        raise ValueError("empty")
    line, tail_country = split_country_tail(stripped)
    if not line:
        raise ValueError("empty")
    url_match = _URL_LINE_RE.match(line)
    if url_match:
        parsed = urlparse(line)
        scheme = _normalize_scheme(parsed.scheme)
        host = _parse_host(parsed.hostname)
        if parsed.port is None:
            raise ValueError("В URL нет порта")
        return _parsed(
            scheme,
            host,
            _parse_port(parsed.port),
            unquote(parsed.username) if parsed.username else None,
            unquote(parsed.password) if parsed.password else None,
            country_code=tail_country,
            scheme_explicit=True,
        )
    at_v6 = _USER_AT_V6_RE.match(line)
    if at_v6:
        return _parsed(
            "socks5",
            at_v6.group("host"),
            _parse_port(at_v6.group("port")),
            at_v6.group("username"),
            at_v6.group("password") or None,
            country_code=tail_country,
        )
    if "@" in line and "://" not in line:
        match = _USER_AT_RE.match(line)
        if not match:
            raise ValueError("Ожидается user:pass@host:port")
        return _parsed(
            "socks5",
            match.group("host"),
            _parse_port(match.group("port")),
            match.group("username"),
            match.group("password") or None,
            country_code=tail_country,
        )
    v6_auth = _IPV6_AUTH_RE.match(line)
    if v6_auth:
        return _parsed(
            "socks5",
            v6_auth.group("host"),
            _parse_port(v6_auth.group("port")),
            v6_auth.group("username") or None,
            v6_auth.group("password") or None,
            country_code=tail_country,
        )
    host_v6 = _HOST_PORT_V6_RE.match(line)
    if host_v6:
        return _parsed(
            "socks5",
            host_v6.group("host"),
            _parse_port(host_v6.group("port")),
            None,
            None,
            country_code=tail_country,
        )
    parts = line.split(":")
    parts, field_country = _split_country_field(parts)
    country = tail_country or field_country
    if len(parts) == 2:
        return _parsed("socks5", parts[0], _parse_port(parts[1]), None, None, country_code=country)
    if len(parts) >= 4:
        return _parsed(
            "socks5",
            parts[0],
            _parse_port(parts[1]),
            parts[2] or None,
            ":".join(parts[3:]) or None,
            country_code=country,
        )
    match = _HOST_PORT_RE.match(line)
    if not match:
        raise ValueError("Ожидается host:port, user:pass@host:port или socks5://user:pass@host:port")
    return _parsed(
        "socks5",
        match.group("host"),
        _parse_port(match.group("port")),
        None,
        None,
        country_code=country,
    )


def parse_proxy_list(raw_text: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, raw_line in enumerate((raw_text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parsed = parse_proxy_line(line)
        except ValueError as exc:
            if str(exc) == "empty":
                continue
            errors.append(f"Строка {index}: {exc}")
            continue
        if parsed["fingerprint"] in seen:
            continue
        seen.add(parsed["fingerprint"])
        items.append(parsed)
    return items, errors


async def probe_socks5_handshake(
    host: str,
    port: int,
    *,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 2.0,
) -> bool:
    """True if the port speaks SOCKS5 (optionally with user/pass)."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout)
    except Exception:
        return False
    try:
        if username:
            writer.write(b"\x05\x01\x02")
        else:
            writer.write(b"\x05\x01\x00")
        await writer.drain()
        hello = await asyncio.wait_for(reader.readexactly(2), timeout)
        if hello[0] != 5:
            return False
        if hello[1] == 0:
            return True
        if hello[1] != 2 or not username:
            return False
        user = (username or "").encode("utf-8")[:255]
        secret = (password or "").encode("utf-8")[:255]
        writer.write(bytes([1, len(user)]) + user + bytes([len(secret)]) + secret)
        await writer.drain()
        auth = await asyncio.wait_for(reader.readexactly(2), timeout)
        return auth[0] == 1 and auth[1] == 0
    except Exception:
        return False
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def apply_vendor_socks_port(item: dict[str, Any]) -> dict[str, Any]:
    """If SOCKS5 on a 1xxxx HTTP port is dead, bump the first digit (11625→21625)."""
    if item.get("scheme") != "socks5":
        return item
    bumped = vendor_socks5_port(int(item["port"]))
    if bumped is None:
        return item
    original_ok = await probe_socks5_handshake(
        item["host"],
        int(item["port"]),
        username=item.get("username"),
        password=item.get("password"),
    )
    if original_ok:
        return item
    bumped_ok = await probe_socks5_handshake(
        item["host"],
        bumped,
        username=item.get("username"),
        password=item.get("password"),
    )
    if not bumped_ok:
        return item
    item = dict(item)
    item["port"] = bumped
    item["fingerprint"] = proxy_fingerprint(item["scheme"], item["host"], bumped, item.get("username"))
    return item


async def normalize_imported_proxies(
    items: list[dict[str, Any]],
    *,
    default_country: str | None = None,
) -> list[dict[str, Any]]:
    default = normalize_country(default_country)
    sem = asyncio.Semaphore(20)

    async def _one(item: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            fixed = await apply_vendor_socks_port(item)
        country = fixed.get("country_code") or default
        fixed["country_code"] = country
        fixed["region"] = region_for_country(country)
        return fixed

    if not items:
        return []
    return list(await asyncio.gather(*(_one(item) for item in items)))


def proxy_label(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    host = str(payload.get("host") or "").strip()
    port = payload.get("port")
    scheme = str(payload.get("scheme") or "socks5").strip() or "socks5"
    if not host or not port:
        return None
    return f"{scheme}://{host}:{port}"


def proxy_row_label(proxy: CustomProxy | None) -> str | None:
    if proxy is None:
        return None
    return f"{proxy.scheme}://{proxy.host}:{proxy.port}"


def connection_payload(proxy: CustomProxy | None) -> dict[str, Any] | None:
    if proxy is None:
        return None
    return {
        "proxy_id": proxy.id,
        "scheme": proxy.scheme,
        "host": proxy.host,
        "port": proxy.port,
        "username": proxy.username,
        "password_enc": proxy.password_enc,
    }


def telethon_proxy_dict(payload: dict | None) -> dict[str, Any] | None:
    """Shape expected by Telethon 1.36+ / python-socks."""
    if not isinstance(payload, dict):
        return None
    host = str(payload.get("host") or payload.get("addr") or "").strip()
    try:
        port = int(payload.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    if not host or port < 1:
        return None
    scheme = str(payload.get("scheme") or payload.get("proxy_type") or "socks5").strip().lower()
    if scheme in {"https", "socks5h"}:
        scheme = "http" if scheme == "https" else "socks5"
    if scheme not in {"socks5", "socks4", "http"}:
        scheme = "socks5"
    password = payload.get("password")
    if not password and payload.get("password_enc"):
        try:
            password = decrypt_token(str(payload["password_enc"]))
        except Exception:
            logger.warning("Could not decrypt proxy password for %s:%s", host, port)
            password = None
    result: dict[str, Any] = {
        "proxy_type": scheme,
        "addr": host,
        "port": port,
        "rdns": True,
    }
    username = str(payload.get("username") or "").strip()
    if username:
        result["username"] = username
    if password:
        result["password"] = str(password)
    return result


def telethon_proxy_from_account(account) -> dict[str, Any] | None:
    return telethon_proxy_dict(getattr(account, "telegram_proxy", None))


def _encrypt_password(password: str | None) -> str | None:
    raw = (password or "").strip()
    if not raw:
        return None
    return encrypt_token(raw)


def _is_dedicated(proxy: CustomProxy | None) -> bool:
    return bool(proxy is not None and getattr(proxy, "is_dedicated", False))


async def list_active_proxies(session: AsyncSession, automation_id: int) -> list[CustomProxy]:
    result = await session.execute(
        select(CustomProxy)
        .where(
            CustomProxy.custom_automation_id == automation_id,
            CustomProxy.is_active.is_(True),
        )
        .order_by(CustomProxy.id.asc())
    )
    return list(result.scalars().all())


async def list_pool_proxies(session: AsyncSession, automation_id: int) -> list[CustomProxy]:
    return [row for row in await list_active_proxies(session, automation_id) if not _is_dedicated(row)]


async def count_active_proxies(session: AsyncSession, automation_id: int) -> int:
    return len(await list_pool_proxies(session, automation_id))


async def upsert_dedicated_proxy(
    session: AsyncSession,
    automation_id: int,
    raw_line: str,
) -> CustomProxy:
    try:
        parsed = parse_proxy_line(raw_line)
    except ValueError as exc:
        raise ProxyChoiceError(f"Не удалось разобрать прокси: {exc}") from exc
    parsed = (await normalize_imported_proxies([parsed]))[0]
    existing = await session.scalar(
        select(CustomProxy).where(
            CustomProxy.custom_automation_id == automation_id,
            CustomProxy.fingerprint == parsed["fingerprint"],
        )
    )
    now = _utc_now()
    password_enc = _encrypt_password(parsed.get("password"))
    if existing:
        existing.scheme = parsed["scheme"]
        existing.host = parsed["host"]
        existing.port = parsed["port"]
        existing.username = parsed["username"]
        existing.password_enc = password_enc
        existing.country_code = parsed.get("country_code")
        existing.region = parsed.get("region")
        existing.ip_version = parsed.get("ip_version")
        existing.is_active = True
        existing.updated_at = now
        await session.flush()
        return existing
    row = CustomProxy(
        custom_automation_id=automation_id,
        scheme=parsed["scheme"],
        host=parsed["host"],
        port=parsed["port"],
        username=parsed["username"],
        password_enc=password_enc,
        fingerprint=parsed["fingerprint"],
        country_code=parsed.get("country_code"),
        region=parsed.get("region"),
        ip_version=parsed.get("ip_version"),
        is_dedicated=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def resolve_account_proxy_choice(
    session: AsyncSession,
    automation_id: int,
    *,
    proxy_id: int | None = None,
    proxy_line: str | None = None,
    phone: str | None = None,
    account: SocialAccount | None = None,
) -> CustomProxy | None:
    line = (proxy_line or "").strip()
    if line:
        return await upsert_dedicated_proxy(session, automation_id, line)
    if proxy_id:
        try:
            chosen_id = int(proxy_id)
        except (TypeError, ValueError) as exc:
            raise ProxyChoiceError("Некорректный идентификатор прокси") from exc
        proxy = await session.get(CustomProxy, chosen_id)
        if proxy is None or not proxy.is_active or int(proxy.custom_automation_id) != int(automation_id):
            raise ProxyChoiceError("Прокси не найден в пуле этой автоматизации")
        return proxy
    return await pick_least_loaded_proxy(
        session,
        automation_id,
        account=account,
        phone=phone,
    )


def bind_account_proxy(
    pool_account: PoolAccount,
    social_account: SocialAccount,
    proxy: CustomProxy | None,
) -> None:
    pool_account.proxy_id = proxy.id if proxy else None
    social_account.telegram_proxy = connection_payload(proxy)


def proxy_set_sizes(account_count: int, proxy_count: int) -> list[int]:
    """How many exclusive proxies each account gets. 2–4 when the pool allows it."""
    accounts = max(0, int(account_count or 0))
    proxies = max(0, int(proxy_count or 0))
    if accounts <= 0:
        return []
    if proxies <= 0:
        return [0] * accounts
    base = min(PROXY_SET_MAX, proxies // accounts)
    leftover = proxies - base * accounts
    sizes: list[int] = []
    for _ in range(accounts):
        extra = 1 if leftover > 0 and base < PROXY_SET_MAX else 0
        if extra:
            leftover -= 1
        sizes.append(base + extra)
    return sizes


def proxy_set_id_list(pool_account: PoolAccount | None) -> list[int]:
    raw = getattr(pool_account, "proxy_set_ids", None) or []
    out: list[int] = []
    seen: set[int] = set()
    for value in raw:
        try:
            ident = int(value)
        except (TypeError, ValueError):
            continue
        if ident <= 0 or ident in seen:
            continue
        seen.add(ident)
        out.append(ident)
    return out


def _store_proxy_set(pool_account: PoolAccount, proxy_ids: list[int]) -> None:
    pool_account.proxy_set_ids = [int(item) for item in proxy_ids if int(item) > 0]


def _rank_proxies(
    rows: list[CustomProxy],
    account: SocialAccount | None,
    loads: dict[int, int],
    *,
    country: str | None = None,
) -> list[CustomProxy]:
    if country is None:
        country = country_from_phone(getattr(account, "phone_number", None))
    return sorted(
        rows,
        key=lambda row: (
            *proxy_fit_key(country, getattr(row, "country_code", None)),
            loads.get(row.id, 0),
            row.id,
        ),
    )


async def _bind_released_proxy(
    pool_account: PoolAccount,
    social_account: SocialAccount,
    proxy: CustomProxy | None,
) -> bool:
    """Bind only after the live socket is gone when the exit IP changes."""
    new_id = proxy.id if proxy is not None else None
    if pool_account.proxy_id == new_id:
        bind_account_proxy(pool_account, social_account, proxy)
        return True
    if not await _drop_live_session(social_account):
        logger.warning(
            "Skip proxy bind for account %s: the session is still in use",
            social_account.id,
        )
        return False
    bind_account_proxy(pool_account, social_account, proxy)
    return True


async def _factory_reserved_proxy_ids(session: AsyncSession, automation_id: int) -> set[int]:
    """Current address of a content-factory account in this automation.

    Empty when that account has no proxy. Same reservation as a Telegram
    account's current proxy: not a set member, not a backup, not a login exit.
    """
    result = await session.execute(
        select(CustomContentFactoryAccount.proxy_id).where(
            CustomContentFactoryAccount.custom_automation_id == automation_id,
            CustomContentFactoryAccount.proxy_id.is_not(None),
        )
    )
    return {int(proxy_id) for proxy_id in result.scalars().all() if proxy_id}


async def _pool_accounts_for_rebalance(
    session: AsyncSession,
    automation_id: int,
) -> list[tuple[PoolAccount, SocialAccount]]:
    result = await session.execute(
        select(PoolAccount, SocialAccount)
        .join(SocialAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.removed_at.is_(None),
        )
        .order_by(PoolAccount.id.asc())
    )
    return list(result.all())


def _ids_held_by_account(pool_account: PoolAccount, live_ids: set[int]) -> list[int]:
    """Set members plus the exit the account is on now, when those rows still exist."""
    ids: list[int] = []
    seen: set[int] = set()
    for pid in proxy_set_id_list(pool_account):
        if pid in live_ids and pid not in seen:
            ids.append(pid)
            seen.add(pid)
    if pool_account.proxy_id:
        pid = int(pool_account.proxy_id)
        if pid in live_ids and pid not in seen:
            ids.append(pid)
            seen.add(pid)
    return ids


def _held_by_others(proxy_id: int, pool_id: int, owners: dict[int, set[int]]) -> bool:
    return any(holder != pool_id for holder in owners.get(proxy_id, ()))


def _release_proxy_claim(
    pool_id: int,
    previous: list[int],
    new_ids: list[int],
    owners: dict[int, set[int]],
    free_by_id: dict[int, CustomProxy],
    by_id: dict[int, CustomProxy],
) -> None:
    kept = {int(pid) for pid in new_ids}
    for pid in previous:
        if pid in kept:
            continue
        holders = owners.get(pid)
        if not holders or pool_id not in holders:
            continue
        holders.discard(pool_id)
        if holders:
            continue
        row = by_id.get(pid)
        if row is not None and not _is_dedicated(row):
            free_by_id.setdefault(pid, row)
    for pid in kept:
        owners.setdefault(pid, set()).add(pool_id)
        free_by_id.pop(pid, None)


async def rebalance_proxies(
    session: AsyncSession,
    automation_id: int,
    *,
    proxies: list[CustomProxy] | None = None,
) -> dict[str, Any]:
    """Give accounts that have no set an exclusive share. A live address stays reserved.

    The new set is stored only after the exit is released, or when the exit does not
    change. If the socket is still up, the old set and the current address stay.
    """
    all_active = await list_active_proxies(session, automation_id)
    by_id = {row.id: row for row in all_active}
    shared_source = proxies if proxies is not None else all_active
    shared = [row for row in shared_source if not _is_dedicated(row) and row.id in by_id]
    shared_ids = {row.id for row in shared}
    accounts = await _pool_accounts_for_rebalance(session, automation_id)
    assigned = 0
    live_ids = set(by_id)
    held: dict[int, list[int]] = {}
    owners: dict[int, set[int]] = {}
    for pool_account, _social in accounts:
        ids = _ids_held_by_account(pool_account, live_ids)
        held[pool_account.id] = ids
        for pid in ids:
            owners.setdefault(pid, set()).add(pool_account.id)
    for pid in await _factory_reserved_proxy_ids(session, automation_id):
        if pid in live_ids:
            owners.setdefault(pid, set()).add(_FACTORY_PROXY_HOLDER)
    free_by_id = {row.id: row for row in shared if not owners.get(row.id)}
    needing: list[tuple[PoolAccount, SocialAccount]] = []

    async def _commit_kept(
        pool_account: PoolAccount,
        social: SocialAccount,
        kept_ids: list[int],
        active: CustomProxy | None,
    ) -> None:
        nonlocal assigned
        if active is None or not kept_ids:
            return
        if not await _bind_released_proxy(pool_account, social, active):
            return
        _store_proxy_set(pool_account, kept_ids)
        _release_proxy_claim(
            pool_account.id,
            held.get(pool_account.id, []),
            kept_ids,
            owners,
            free_by_id,
            by_id,
        )
        held[pool_account.id] = list(kept_ids)
        assigned += 1

    async def _clear_after_release(pool_account: PoolAccount, social: SocialAccount) -> None:
        if pool_account.proxy_id is None and not proxy_set_id_list(pool_account):
            return
        if not await _drop_live_session(social):
            return
        previous = held.get(pool_account.id, [])
        bind_account_proxy(pool_account, social, None)
        _store_proxy_set(pool_account, [])
        _release_proxy_claim(pool_account.id, previous, [], owners, free_by_id, by_id)
        held[pool_account.id] = []

    def _exclusive_pin(pool_account: PoolAccount) -> CustomProxy | None:
        if not pool_account.proxy_id:
            return None
        pid = int(pool_account.proxy_id)
        if pid not in shared_ids or owners.get(pid) != {pool_account.id}:
            return None
        return by_id.get(pid)

    for pool_account, social in accounts:
        current = by_id.get(pool_account.proxy_id)
        raw_ids = proxy_set_id_list(pool_account)
        dedicated_id = int(current.id) if _is_dedicated(current) else None
        if dedicated_id is None:
            for pid in raw_ids:
                proxy = by_id.get(pid)
                if proxy is not None and _is_dedicated(proxy) and not _held_by_others(pid, pool_account.id, owners):
                    dedicated_id = int(pid)
                    break
        if dedicated_id is not None:
            backups = [
                pid
                for pid in raw_ids
                if pid != dedicated_id
                and pid in shared_ids
                and not _held_by_others(pid, pool_account.id, owners)
            ]
            kept = [dedicated_id, *backups]
            active = current if current is not None and int(current.id) in set(kept) else by_id.get(dedicated_id)
            await _commit_kept(pool_account, social, kept, active)
            continue
        owned = [
            pid
            for pid in raw_ids
            if pid in shared_ids and not _held_by_others(pid, pool_account.id, owners)
        ]
        if owned:
            active = current if current is not None and current.id in owned else by_id[owned[0]]
            await _commit_kept(pool_account, social, owned, active)
            continue
        needing.append((pool_account, social))

    if not needing:
        return {"proxy_count": len(shared), "assigned": assigned}

    pin_count = sum(1 for pool_account, _social in needing if _exclusive_pin(pool_account) is not None)
    if not free_by_id and pin_count == 0:
        for pool_account, social in needing:
            await _clear_after_release(pool_account, social)
        return {"proxy_count": len(shared), "assigned": assigned}

    available = len(free_by_id) + pin_count
    sizes = proxy_set_sizes(len(needing), available)
    loads = {pid: 0 for pid in free_by_id}
    for pool_account, _social in needing:
        pin = _exclusive_pin(pool_account)
        if pin is not None:
            loads.setdefault(pin.id, 0)
    for (pool_account, social), size in zip(needing, sizes):
        pin = _exclusive_pin(pool_account)
        if size <= 0:
            if pin is None:
                await _clear_after_release(pool_account, social)
            continue
        candidates = list(free_by_id.values())
        if pin is not None and pin.id not in free_by_id:
            candidates.append(pin)
        if not candidates:
            continue
        chosen_rows = _rank_proxies(candidates, social, loads)[:size]
        if not chosen_rows:
            continue
        if not await _bind_released_proxy(pool_account, social, chosen_rows[0]):
            continue
        new_ids = [row.id for row in chosen_rows]
        _store_proxy_set(pool_account, new_ids)
        pool_account.proxy_problem = False
        loads[chosen_rows[0].id] = loads.get(chosen_rows[0].id, 0) + 1
        _release_proxy_claim(
            pool_account.id,
            held.get(pool_account.id, []),
            new_ids,
            owners,
            free_by_id,
            by_id,
        )
        held[pool_account.id] = new_ids
        assigned += 1
    return {"proxy_count": len(shared), "assigned": assigned}


async def _dominant_account_country(session: AsyncSession, automation_id: int) -> str | None:
    result = await session.execute(
        select(SocialAccount.phone_number)
        .join(PoolAccount, PoolAccount.social_account_id == SocialAccount.id)
        .where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.removed_at.is_(None),
        )
    )
    counts: dict[str, int] = {}
    for phone in result.scalars().all():
        code = country_from_phone(phone)
        if not code:
            continue
        counts[code] = counts.get(code, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


async def _account_country_for_pick(
    session: AsyncSession,
    automation_id: int,
    *,
    account: SocialAccount | None = None,
    phone: str | None = None,
    account_country: str | None = None,
) -> str | None:
    country = normalize_country(account_country) or country_from_phone(
        phone or getattr(account, "phone_number", None)
    )
    if country:
        return country
    return await _dominant_account_country(session, automation_id)


def proxy_purity_stats(
    *,
    accounts_with_proxy: int,
    distribution: list[dict[str, Any]],
) -> dict[str, int]:
    """0–100: how little the same proxy is reused across assigned accounts."""
    assigned = int(accounts_with_proxy or 0)
    used = [int(item.get("account_count") or 0) for item in distribution if int(item.get("account_count") or 0) > 0]
    unique_used = len(used)
    peak = max(used) if used else 0
    if assigned <= 0:
        score = 100
    else:
        score = max(0, min(100, int(round(100.0 * unique_used / assigned))))
    return {
        "proxy_purity": score,
        "proxy_unique_used": unique_used,
        "proxy_peak_load": peak,
    }


def _best_proxy_for_account(
    rows: list[CustomProxy],
    account: SocialAccount | None,
    loads: dict[int, int],
    *,
    country: str | None = None,
) -> CustomProxy:
    return _rank_proxies(rows, account, loads, country=country)[0]


async def _foreign_proxy_ids(
    session: AsyncSession,
    automation_id: int,
    *,
    account: SocialAccount | None = None,
    phone: str | None = None,
) -> set[int]:
    """Addresses already in someone else's set or on someone else's account.

    A backup counts. The account that is logging in keeps its own addresses.
    """
    roster = await _pool_accounts_for_rebalance(session, automation_id)
    own: set[int] = set()
    if account is not None:
        own.add(int(account.id))
    phone_text = (phone or "").strip()
    if phone_text:
        for _pool, social in roster:
            if (getattr(social, "phone_number", None) or "").strip() == phone_text:
                own.add(int(social.id))
    occupied: set[int] = set()
    for pool, social in roster:
        if int(social.id) in own:
            continue
        occupied.update(proxy_set_id_list(pool))
        if pool.proxy_id:
            occupied.add(int(pool.proxy_id))
    occupied.update(await _factory_reserved_proxy_ids(session, automation_id))
    return occupied


async def pick_least_loaded_proxy(
    session: AsyncSession,
    automation_id: int,
    *,
    proxies: list[CustomProxy] | None = None,
    account: SocialAccount | None = None,
    phone: str | None = None,
    account_country: str | None = None,
) -> CustomProxy | None:
    source = proxies if proxies is not None else await list_active_proxies(session, automation_id)
    occupied = await _foreign_proxy_ids(session, automation_id, account=account, phone=phone)
    rows = [row for row in source if not _is_dedicated(row) and row.id not in occupied]
    if not rows:
        return None
    healthy = [row for row in rows if is_proxy_healthy(row)]
    rows = healthy or rows
    country = await _account_country_for_pick(
        session,
        automation_id,
        account=account,
        phone=phone,
        account_country=account_country,
    )
    return _best_proxy_for_account(rows, account, {row.id: 0 for row in rows}, country=country)


def _open_proxy_accounts(rows: list[tuple[PoolAccount, SocialAccount]], account_id: int) -> int:
    """Accounts that still have no set, including the one being assigned."""
    others = 0
    for pool_account, _social in rows:
        if pool_account.id == account_id:
            continue
        if proxy_set_id_list(pool_account):
            continue
        others += 1
    return others + 1


async def assign_proxy_to_new_account(
    session: AsyncSession,
    pool_account: PoolAccount,
    social_account: SocialAccount,
    *,
    preferred_proxy_id: int | None = None,
    lock_preferred: bool = True,
) -> CustomProxy | None:
    """Primary is the proxy chosen at upload. Free proxies fill the rest of the set.

    The set length is the same share ``proxy_set_sizes`` would give this account
    among accounts that do not have a set yet. A dedicated proxy stays first and
    does not block those backups. The set is stored only after the bind succeeds.
    If the socket is still up, the old set and the current address stay.
    """
    proxies = await list_active_proxies(session, pool_account.custom_automation_id)
    roster = await _pool_accounts_for_rebalance(session, pool_account.custom_automation_id)
    reserved: set[int] = set()
    for other, _social in roster:
        if other.id == pool_account.id:
            continue
        reserved.update(proxy_set_id_list(other))
        if other.proxy_id:
            reserved.add(int(other.proxy_id))
    reserved.update(await _factory_reserved_proxy_ids(session, pool_account.custom_automation_id))
    free = [row for row in proxies if not _is_dedicated(row) and row.id not in reserved]
    chosen: CustomProxy | None = None
    if lock_preferred and preferred_proxy_id:
        preferred = next((row for row in proxies if row.id == int(preferred_proxy_id)), None)
        if preferred is not None and preferred.id not in reserved:
            chosen = preferred
    if chosen is None and free:
        chosen = _best_proxy_for_account(free, social_account, {row.id: 0 for row in free})
    if chosen is None:
        return None
    available = len(free) + (0 if any(row.id == chosen.id for row in free) else 1)
    size = proxy_set_sizes(_open_proxy_accounts(roster, pool_account.id), available)[0]
    backups = _rank_proxies(
        [row for row in free if row.id != chosen.id],
        social_account,
        {row.id: 0 for row in free},
    )
    members = [chosen, *backups[: max(0, size - 1)]]
    if not await _bind_released_proxy(pool_account, social_account, chosen):
        return None
    _store_proxy_set(pool_account, [row.id for row in members])
    pool_account.proxy_problem = False
    return chosen


async def load_telethon_proxy(
    session: AsyncSession,
    proxy_id: int | None,
    *,
    automation_id: int | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    if not proxy_id:
        return None, None
    proxy = await session.get(CustomProxy, int(proxy_id))
    if proxy is None or not proxy.is_active:
        return None, None
    if automation_id is not None and int(proxy.custom_automation_id) != int(automation_id):
        return None, None
    return proxy.id, telethon_proxy_dict(connection_payload(proxy))


async def probe_and_fix_proxy(proxy: CustomProxy) -> bool:
    """TCP (and vendor SOCKS port bump) before handing the proxy to Telethon."""
    if await probe_proxy_tcp(proxy.host, int(proxy.port)):
        mark_proxy_ok(proxy)
        return True
    if str(proxy.scheme or "").lower() == "socks5":
        original_port = int(proxy.port)
        bumped = vendor_socks5_port(original_port)
        if bumped and await probe_proxy_tcp(proxy.host, bumped):
            proxy.port = bumped
            proxy.fingerprint = proxy_fingerprint("socks5", proxy.host, bumped, proxy.username)
            proxy.updated_at = _utc_now()
            mark_proxy_ok(proxy)
            logger.info("Connect proxy %s bumped %s -> %s", proxy.id, original_port, bumped)
            return True
    mark_proxy_unhealthy(proxy)
    logger.warning("Connect proxy dead %s:%s", proxy.host, proxy.port)
    return False


def _connect_proxy_dead_message(proxy: CustomProxy) -> str:
    return (
        f"Прокси {proxy.host}:{proxy.port} недоступен (нет соединения). "
        "Выберите другой из пула или вставьте рабочую строку."
    )


async def resolve_connect_proxy(
    session: AsyncSession,
    automation_id: int,
    *,
    proxy_id: int | None = None,
    proxy_line: str | None = None,
    phone: str | None = None,
) -> tuple[int | None, dict[str, Any] | None]:
    explicit = bool((proxy_line or "").strip() or proxy_id)
    occupied = await _foreign_proxy_ids(session, automation_id, phone=phone)
    proxy = await resolve_account_proxy_choice(
        session,
        automation_id,
        proxy_id=proxy_id,
        proxy_line=proxy_line,
        phone=phone,
    )
    if proxy is not None and int(proxy.id) in occupied:
        if explicit:
            raise ProxyChoiceError("Этот прокси уже закреплён за другим аккаунтом")
        proxy = None
    if proxy is None:
        return None, None
    if await probe_and_fix_proxy(proxy):
        return proxy.id, telethon_proxy_dict(connection_payload(proxy))
    if explicit:
        raise ProxyChoiceError(_connect_proxy_dead_message(proxy))
    pool = [
        row
        for row in await list_pool_proxies(session, automation_id)
        if row.id not in occupied and row.id != proxy.id
    ]
    country = await _account_country_for_pick(session, automation_id, phone=phone)
    ranked = sorted(
        pool,
        key=lambda row: (
            0 if is_proxy_healthy(row) else 1,
            *proxy_fit_key(country, getattr(row, "country_code", None)),
            row.id,
        ),
    )
    for row in ranked:
        if await probe_and_fix_proxy(row):
            logger.info(
                "Connect skipped dead %s:%s, using %s:%s",
                proxy.host,
                proxy.port,
                row.host,
                row.port,
            )
            return row.id, telethon_proxy_dict(connection_payload(row))
    raise ProxyChoiceError(
        "Ни один прокси из пула не отвечает. Обновите список или вставьте свой на время входа."
    )


async def replace_proxy_list(
    session: AsyncSession,
    automation: CustomAutomation,
    raw_text: str | None,
    *,
    default_country: str | None = None,
) -> dict[str, Any]:
    text = raw_text if raw_text is not None else ""
    parsed, errors = parse_proxy_list(text)
    if text.strip() and not parsed:
        raise ProxyParseError("Не удалось разобрать ни одного прокси. Проверьте формат строк.")
    if len(parsed) > MAX_PROXIES:
        raise ProxyParseError(f"Слишком много прокси (максимум {MAX_PROXIES}).")
    parsed = await normalize_imported_proxies(parsed, default_country=default_country)

    automation.proxy_list_text = text
    automation.updated_at = _utc_now()
    existing = await session.execute(
        select(CustomProxy).where(CustomProxy.custom_automation_id == automation.id)
    )
    existing_rows = list(existing.scalars().all())
    by_fp = {row.fingerprint: row for row in existing_rows}
    keep_fps = {item["fingerprint"] for item in parsed}
    now = _utc_now()
    kept: list[CustomProxy] = []
    for item in parsed:
        row = by_fp.get(item["fingerprint"])
        password_enc = _encrypt_password(item.get("password"))
        if row:
            row.scheme = item["scheme"]
            row.host = item["host"]
            row.port = item["port"]
            row.username = item["username"]
            row.password_enc = password_enc
            row.country_code = item.get("country_code")
            row.region = item.get("region")
            row.ip_version = item.get("ip_version")
            row.is_active = True
            row.updated_at = now
            kept.append(row)
        else:
            row = CustomProxy(
                custom_automation_id=automation.id,
                scheme=item["scheme"],
                host=item["host"],
                port=item["port"],
                username=item["username"],
                password_enc=password_enc,
                fingerprint=item["fingerprint"],
                country_code=item.get("country_code"),
                region=item.get("region"),
                ip_version=item.get("ip_version"),
                is_dedicated=False,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            kept.append(row)
    await session.flush()
    for row in existing_rows:
        if row.fingerprint not in keep_fps and not _is_dedicated(row):
            await session.delete(row)
    await session.flush()
    stats = await rebalance_proxies(session, automation.id, proxies=kept)
    stats["errors"] = errors
    stats["skipped"] = len(errors)
    return stats


async def proxy_settings_payload(session: AsyncSession, automation: CustomAutomation) -> dict[str, Any]:
    proxies = await list_active_proxies(session, automation.id)
    pool = [row for row in proxies if not _is_dedicated(row)]
    accounts = await _pool_accounts_for_rebalance(session, automation.id)
    counts: dict[int, int] = {row.id: 0 for row in proxies}
    assigned = 0
    for pool_account, _social in accounts:
        if pool_account.proxy_id in counts:
            counts[pool_account.proxy_id] += 1
            assigned += 1
    distribution = [
        {
            "id": row.id,
            "scheme": row.scheme,
            "host": row.host,
            "port": row.port,
            "country_code": getattr(row, "country_code", None),
            "region": getattr(row, "region", None),
            "ip_version": getattr(row, "ip_version", None),
            "account_count": counts.get(row.id, 0),
        }
        for row in pool
    ]
    payload = {
        "proxy_list_text": automation.proxy_list_text or "",
        "proxy_count": len(pool),
        "accounts_with_proxy": assigned,
        "proxy_distribution": distribution,
    }
    payload.update(proxy_purity_stats(accounts_with_proxy=assigned, distribution=distribution))
    return payload


async def account_proxy_picker_payload(session: AsyncSession, automation_id: int) -> dict[str, Any]:
    return {
        "items": [
            {
                "id": row.id,
                "label": proxy_row_label(row),
                "scheme": row.scheme,
                "host": row.host,
                "port": row.port,
                "country_code": getattr(row, "country_code", None),
                "ip_version": getattr(row, "ip_version", None),
            }
            for row in await list_pool_proxies(session, automation_id)
        ]
    }


def is_proxy_healthy(proxy: CustomProxy | None) -> bool:
    if proxy is None or not proxy.is_active:
        return False
    if getattr(proxy, "is_healthy", True):
        return True
    failed = getattr(proxy, "last_failed_at", None)
    if failed is None:
        return True
    then = failed.replace(tzinfo=None) if getattr(failed, "tzinfo", None) else failed
    return (_utc_now() - then) >= _UNHEALTHY_TTL


def mark_proxy_unhealthy(proxy: CustomProxy) -> None:
    now = _utc_now()
    proxy.is_healthy = False
    proxy.fail_count = int(getattr(proxy, "fail_count", 0) or 0) + 1
    proxy.last_failed_at = now
    proxy.updated_at = now


def mark_proxy_ok(proxy: CustomProxy) -> None:
    now = _utc_now()
    proxy.is_healthy = True
    proxy.fail_count = 0
    proxy.last_ok_at = now
    proxy.updated_at = now


async def probe_proxy_tcp(host: str, port: int, timeout: float = 4.0) -> bool:
    """Cheap liveness check. Does not touch Telegram or .session files."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, int(port)), timeout)
    except Exception:
        return False
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass
    return True


async def _rotate_lock_for(account_id: int) -> asyncio.Lock:
    async with _rotate_locks_guard:
        lock = _rotate_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            _rotate_locks[account_id] = lock
        return lock


async def _drop_live_session(account: SocialAccount) -> bool:
    """Disconnect the one live Telethon client before changing its IP.

    False means the socket is still up. The caller must not bind a new exit.
    """
    from ...config import settings
    from .account_session_orchestrator import _hubs
    from .telegram_account_client import live_client_for_path

    closed = True
    rel = (getattr(account, "session_file_path", None) or "").strip()
    if rel:
        path = str(Path(settings.MEDIA_ROOT).resolve() / rel)
        live = live_client_for_path(path)
        if live is not None:
            try:
                closed = await live.drop_alive() and closed
            except Exception:
                logger.debug("drop_alive before proxy rotate failed for %s", account.id, exc_info=True)
                closed = False
    for hub in list(_hubs.values()):
        client = hub.clients.get(account.id)
        if client is None:
            continue
        try:
            if await client.drop_alive():
                hub.clients.pop(account.id, None)
            else:
                closed = False
        except Exception:
            logger.debug("hub drop_alive before proxy rotate failed for %s", account.id, exc_info=True)
            closed = False
    return closed


async def record_proxy_success(session: AsyncSession, account: SocialAccount) -> None:
    payload = getattr(account, "telegram_proxy", None) or {}
    proxy_id = payload.get("proxy_id") if isinstance(payload, dict) else None
    pool = await session.scalar(select(PoolAccount).where(PoolAccount.social_account_id == account.id))
    if proxy_id is None and pool is not None:
        proxy_id = pool.proxy_id
    if not proxy_id:
        return
    proxy = await session.get(CustomProxy, int(proxy_id))
    if proxy is None:
        return
    mark_proxy_ok(proxy)
    if pool is not None:
        owned = set(proxy_set_id_list(pool))
        if not owned or int(proxy.id) in owned:
            pool.proxy_problem = False


async def recover_dead_proxy(session: AsyncSession, account: SocialAccount) -> CustomProxy | None:
    """Mark the current proxy dead and bind the next living proxy from this account's set.

    Does not take a proxy that belongs to another account. Session-safe: drops
    the live MTProto client first, then writes the new proxy.
    """
    lock = await _rotate_lock_for(account.id)
    async with lock:
        last = _last_rotate_at.get(account.id)
        if last and (_utc_now() - last) < _ROTATE_GAP:
            return None
        pool_account = await session.scalar(
            select(PoolAccount).where(
                PoolAccount.social_account_id == account.id,
                PoolAccount.removed_at.is_(None),
            )
        )
        if pool_account is None:
            return None
        current_id = pool_account.proxy_id
        current = await session.get(CustomProxy, int(current_id)) if current_id else None
        if current is not None:
            mark_proxy_unhealthy(current)
        owned_ids = proxy_set_id_list(pool_account)
        if current is not None and _is_dedicated(current) and current.id not in owned_ids:
            owned_ids = [current.id]
        chosen: CustomProxy | None = None
        tried = False
        for proxy_id in owned_ids:
            if current_id is not None and int(proxy_id) == int(current_id):
                continue
            proxy = await session.get(CustomProxy, int(proxy_id))
            if proxy is None or not proxy.is_active:
                continue
            if int(proxy.custom_automation_id) != int(pool_account.custom_automation_id):
                continue
            if _is_dedicated(proxy) and (current is None or proxy.id != current.id):
                continue
            tried = True
            if await probe_proxy_tcp(proxy.host, proxy.port):
                chosen = proxy
                break
            mark_proxy_unhealthy(proxy)
        if chosen is None:
            owned_set = set(owned_ids)
            if current is not None and owned_set and int(current.id) not in owned_set:
                primary = await session.get(CustomProxy, int(owned_ids[0]))
                if primary is not None and await _drop_live_session(account):
                    bind_account_proxy(pool_account, account, primary)
            if tried or current is not None:
                pool_account.proxy_problem = True
            logger.warning("No living proxy in account %s set", account.id)
            return None
        if not await _drop_live_session(account):
            logger.warning("Skip proxy rotate for account %s: the session is still in use", account.id)
            return None
        bind_account_proxy(pool_account, account, chosen)
        mark_proxy_ok(chosen)
        pool_account.proxy_problem = False
        _last_rotate_at[account.id] = _utc_now()
        logger.info(
            "Rotated account %s proxy %s -> %s:%s",
            account.id,
            current_id,
            chosen.host,
            chosen.port,
        )
        return chosen


async def rebind_account_proxy_if_far(
    session: AsyncSession,
    pool_account: PoolAccount | None,
    social_account: SocialAccount,
) -> CustomProxy | None:
    """Move auto-assigned accounts off a far proxy once the phone country is known.

    Never runs after the first Telegram connect — swapping IP on a live
    .session is a freeze / AuthKeyDuplicated trigger.
    """
    if pool_account is None:
        return None
    if getattr(social_account, "last_health_check_at", None) is not None:
        return None
    current = await session.get(CustomProxy, int(pool_account.proxy_id)) if pool_account.proxy_id else None
    if _is_dedicated(current):
        return None
    country = country_from_phone(getattr(social_account, "phone_number", None))
    if not country:
        return None
    owned = set(proxy_set_id_list(pool_account))
    if not owned:
        return None
    rows = []
    for proxy_id in owned:
        row = await session.get(CustomProxy, int(proxy_id))
        if row is None or not row.is_active or _is_dedicated(row):
            continue
        if int(row.custom_automation_id) != int(pool_account.custom_automation_id):
            continue
        if not is_proxy_healthy(row):
            continue
        rows.append(row)
    if not rows:
        return None
    best = _best_proxy_for_account(rows, social_account, {row.id: 0 for row in rows}, country=country)
    current_rank = proxy_fit_key(country, getattr(current, "country_code", None) if current else None)[0]
    best_rank = proxy_fit_key(country, getattr(best, "country_code", None))[0]
    if current is not None and current.id == best.id:
        return None
    if current is not None and current_rank <= best_rank:
        return None
    if not await _drop_live_session(social_account):
        logger.warning(
            "Skip proxy rebind for account %s: the session is still in use",
            social_account.id,
        )
        return None
    bind_account_proxy(pool_account, social_account, best)
    logger.info(
        "Rebound account %s proxy %s -> %s (%s) for country %s",
        social_account.id,
        getattr(current, "id", None),
        best.id,
        best.country_code,
        country,
    )
    return best

