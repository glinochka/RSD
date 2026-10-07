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
from ...alembic.models import CustomAutomation, CustomProxy, PoolAccount, SocialAccount
from ...utils.crypto import decrypt_token, encrypt_token


logger = getLogger(__name__)

MAX_PROXIES = 500
_UNHEALTHY_TTL = timedelta(minutes=30)
_ROTATE_GAP = timedelta(seconds=90)
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


async def rebalance_proxies(
    session: AsyncSession,
    automation_id: int,
    *,
    proxies: list[CustomProxy] | None = None,
) -> dict[str, Any]:
    all_active = await list_active_proxies(session, automation_id)
    by_id = {row.id: row for row in all_active}
    shared_source = proxies if proxies is not None else all_active
    shared = [row for row in shared_source if not _is_dedicated(row)]
    accounts = await _pool_accounts_for_rebalance(session, automation_id)
    if not shared:
        assigned = 0
        for pool_account, social in accounts:
            current = by_id.get(pool_account.proxy_id)
            if _is_dedicated(current):
                assigned += 1
                continue
            bind_account_proxy(pool_account, social, None)
        return {"proxy_count": 0, "assigned": assigned}
    assigned = 0
    loads = {row.id: 0 for row in shared}
    for pool_account, social in accounts:
        current = by_id.get(pool_account.proxy_id)
        if _is_dedicated(current):
            assigned += 1
            continue
        chosen = _best_proxy_for_account(shared, social, loads)
        bind_account_proxy(pool_account, social, chosen)
        loads[chosen.id] += 1
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


def _best_proxy_for_account(
    rows: list[CustomProxy],
    account: SocialAccount | None,
    loads: dict[int, int],
    *,
    country: str | None = None,
) -> CustomProxy:
    if country is None:
        country = country_from_phone(getattr(account, "phone_number", None))
    return min(
        rows,
        key=lambda row: (
            *proxy_fit_key(country, getattr(row, "country_code", None)),
            loads.get(row.id, 0),
            row.id,
        ),
    )


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
    rows = [row for row in source if not _is_dedicated(row)]
    if not rows:
        return None
    healthy = [row for row in rows if is_proxy_healthy(row)]
    rows = healthy or rows
    counts = {row.id: 0 for row in rows}
    result = await session.execute(
        select(PoolAccount.proxy_id).where(
            PoolAccount.custom_automation_id == automation_id,
            PoolAccount.removed_at.is_(None),
            PoolAccount.proxy_id.isnot(None),
        )
    )
    for proxy_id in result.scalars().all():
        if proxy_id in counts:
            counts[proxy_id] += 1
    country = await _account_country_for_pick(
        session,
        automation_id,
        account=account,
        phone=phone,
        account_country=account_country,
    )
    return _best_proxy_for_account(rows, account, counts, country=country)


async def assign_proxy_to_new_account(
    session: AsyncSession,
    pool_account: PoolAccount,
    social_account: SocialAccount,
    *,
    preferred_proxy_id: int | None = None,
    lock_preferred: bool = True,
) -> CustomProxy | None:
    proxies = await list_active_proxies(session, pool_account.custom_automation_id)
    chosen: CustomProxy | None = None
    if lock_preferred and preferred_proxy_id:
        chosen = next((row for row in proxies if row.id == int(preferred_proxy_id)), None)
    if chosen is None:
        chosen = await pick_least_loaded_proxy(
            session,
            pool_account.custom_automation_id,
            proxies=proxies,
            account=social_account,
        )
    bind_account_proxy(pool_account, social_account, chosen)
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
    proxy = await resolve_account_proxy_choice(
        session,
        automation_id,
        proxy_id=proxy_id,
        proxy_line=proxy_line,
        phone=phone,
    )
    if proxy is None:
        return None, None
    if await probe_and_fix_proxy(proxy):
        return proxy.id, telethon_proxy_dict(connection_payload(proxy))
    if explicit:
        raise ProxyChoiceError(_connect_proxy_dead_message(proxy))
    pool = [
        row
        for row in await list_pool_proxies(session, automation_id)
        if row.id != proxy.id
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
    return {
        "proxy_list_text": automation.proxy_list_text or "",
        "proxy_count": len(pool),
        "accounts_with_proxy": assigned,
        "proxy_distribution": distribution,
    }


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


def _next_proxy_order(rows: list[CustomProxy], current_id: int | None) -> list[CustomProxy]:
    if not rows:
        return []
    pivot = int(current_id or 0)
    after = [row for row in rows if row.id > pivot]
    before = [row for row in rows if row.id <= pivot]
    return after + before


async def _rotate_lock_for(account_id: int) -> asyncio.Lock:
    async with _rotate_locks_guard:
        lock = _rotate_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            _rotate_locks[account_id] = lock
        return lock


async def _drop_live_session(account: SocialAccount) -> None:
    """Disconnect the one live Telethon client before changing its IP."""
    from ...config import settings
    from .account_session_orchestrator import _hubs
    from .telegram_account_client import live_client_for_path

    rel = (getattr(account, "session_file_path", None) or "").strip()
    if rel:
        path = str(Path(settings.MEDIA_ROOT).resolve() / rel)
        live = live_client_for_path(path)
        if live is not None:
            try:
                await live.drop_alive()
            except Exception:
                logger.debug("drop_alive before proxy rotate failed for %s", account.id, exc_info=True)
    for hub in list(_hubs.values()):
        client = hub.clients.pop(account.id, None)
        if client is None:
            continue
        try:
            await client.drop_alive()
        except Exception:
            logger.debug("hub drop_alive before proxy rotate failed for %s", account.id, exc_info=True)


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


async def recover_dead_proxy(session: AsyncSession, account: SocialAccount) -> CustomProxy | None:
    """Mark the current proxy dead and bind the next living pool proxy.

    Session-safe: drops the live MTProto client first, then writes the new
    proxy. Caller must wait a couple of seconds and keep_alive() the same file.
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
        candidates = [
            row
            for row in await list_active_proxies(session, pool_account.custom_automation_id)
            if not _is_dedicated(row) or (current is not None and row.id == current.id)
        ]
        living = [
            row
            for row in candidates
            if row.id != current_id and is_proxy_healthy(row) and not _is_dedicated(row)
        ]
        chosen: CustomProxy | None = None
        country = country_from_phone(getattr(account, "phone_number", None))
        ranked = sorted(
            living,
            key=lambda row: (
                *proxy_fit_key(country, getattr(row, "country_code", None)),
                0 if row.id > int(current_id or 0) else 1,
                row.id,
            ),
        )
        for proxy in ranked or _next_proxy_order(living, current_id):
            if await probe_proxy_tcp(proxy.host, proxy.port):
                chosen = proxy
                break
            mark_proxy_unhealthy(proxy)
        if chosen is None:
            logger.warning("No living proxy to rotate account %s onto", account.id)
            return None
        await _drop_live_session(account)
        bind_account_proxy(pool_account, account, chosen)
        mark_proxy_ok(chosen)
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
    """Move auto-assigned accounts off a far proxy once the phone country is known."""
    if pool_account is None:
        return None
    current = await session.get(CustomProxy, int(pool_account.proxy_id)) if pool_account.proxy_id else None
    if _is_dedicated(current):
        return None
    country = country_from_phone(getattr(social_account, "phone_number", None))
    if not country:
        return None
    rows = [
        row
        for row in await list_pool_proxies(session, pool_account.custom_automation_id)
        if is_proxy_healthy(row)
    ]
    if not rows:
        return None
    best = _best_proxy_for_account(rows, social_account, {row.id: 0 for row in rows}, country=country)
    current_rank = proxy_fit_key(country, getattr(current, "country_code", None) if current else None)[0]
    best_rank = proxy_fit_key(country, getattr(best, "country_code", None))[0]
    if current is not None and current.id == best.id:
        return None
    if current is not None and current_rank <= best_rank:
        return None
    await _drop_live_session(social_account)
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

