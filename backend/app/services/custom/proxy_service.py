"""Parse, store and evenly assign SOCKS/HTTP proxies to /custom accounts."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from logging import getLogger
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomAutomation, CustomProxy, PoolAccount, SocialAccount
from ...utils.crypto import decrypt_token, encrypt_token


logger = getLogger(__name__)

MAX_PROXIES = 500
_ALLOWED_SCHEMES = {"socks5": "socks5", "socks4": "socks4", "http": "http", "https": "http", "socks5h": "socks5"}
_HOST_PORT_RE = re.compile(r"^(?P<host>[^:\s]+):(?P<port>\d+)$")
_USER_AT_RE = re.compile(
    r"^(?P<username>[^:@\s]+):(?P<password>[^@]*?)@(?P<host>[^:\s]+):(?P<port>\d+)$"
)


class ProxyParseError(ValueError):
    """Raised when a pasted proxy list cannot be applied."""


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


def proxy_fingerprint(scheme: str, host: str, port: int, username: str | None) -> str:
    raw = f"{scheme}|{host.lower()}|{port}|{(username or '').lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_proxy_line(raw: str) -> dict[str, Any]:
    line = (raw or "").strip()
    if not line or line.startswith("#"):
        raise ValueError("empty")
    if line.lower().startswith(("socks", "http")) and "://" in line:
        parsed = urlparse(line)
        scheme = _normalize_scheme(parsed.scheme)
        host = _parse_host(parsed.hostname)
        port = _parse_port(parsed.port)
        username = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None
    elif "@" in line and "://" not in line:
        match = _USER_AT_RE.match(line)
        if not match:
            raise ValueError("Ожидается user:pass@host:port")
        scheme = "socks5"
        host = _parse_host(match.group("host"))
        port = _parse_port(match.group("port"))
        username = match.group("username")
        password = match.group("password") or None
    else:
        parts = line.split(":")
        if len(parts) == 2:
            scheme = "socks5"
            host = _parse_host(parts[0])
            port = _parse_port(parts[1])
            username = None
            password = None
        elif len(parts) >= 4:
            scheme = "socks5"
            host = _parse_host(parts[0])
            port = _parse_port(parts[1])
            username = parts[2] or None
            password = ":".join(parts[3:]) or None
        else:
            match = _HOST_PORT_RE.match(line)
            if not match:
                raise ValueError("Ожидается host:port или host:port:user:pass")
            scheme = "socks5"
            host = _parse_host(match.group("host"))
            port = _parse_port(match.group("port"))
            username = None
            password = None
    username = (username or "").strip() or None
    password = password if password else None
    return {
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "fingerprint": proxy_fingerprint(scheme, host, port, username),
    }


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


async def count_active_proxies(session: AsyncSession, automation_id: int) -> int:
    return len(await list_active_proxies(session, automation_id))


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
    rows = proxies if proxies is not None else await list_active_proxies(session, automation_id)
    accounts = await _pool_accounts_for_rebalance(session, automation_id)
    if not rows:
        for pool_account, social in accounts:
            bind_account_proxy(pool_account, social, None)
        return {"proxy_count": 0, "assigned": 0}
    for index, (pool_account, social) in enumerate(accounts):
        bind_account_proxy(pool_account, social, rows[index % len(rows)])
    return {"proxy_count": len(rows), "assigned": len(accounts)}


async def pick_least_loaded_proxy(
    session: AsyncSession,
    automation_id: int,
    *,
    proxies: list[CustomProxy] | None = None,
) -> CustomProxy | None:
    rows = proxies if proxies is not None else await list_active_proxies(session, automation_id)
    if not rows:
        return None
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
    return min(rows, key=lambda row: (counts.get(row.id, 0), row.id))


async def assign_proxy_to_new_account(
    session: AsyncSession,
    pool_account: PoolAccount,
    social_account: SocialAccount,
    *,
    preferred_proxy_id: int | None = None,
) -> CustomProxy | None:
    proxies = await list_active_proxies(session, pool_account.custom_automation_id)
    chosen: CustomProxy | None = None
    if preferred_proxy_id:
        chosen = next((row for row in proxies if row.id == int(preferred_proxy_id)), None)
    if chosen is None:
        chosen = await pick_least_loaded_proxy(
            session,
            pool_account.custom_automation_id,
            proxies=proxies,
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


async def resolve_connect_proxy(
    session: AsyncSession,
    automation_id: int,
) -> tuple[int | None, dict[str, Any] | None]:
    proxy = await pick_least_loaded_proxy(session, automation_id)
    if proxy is None:
        return None, None
    return proxy.id, telethon_proxy_dict(connection_payload(proxy))


async def replace_proxy_list(
    session: AsyncSession,
    automation: CustomAutomation,
    raw_text: str | None,
) -> dict[str, Any]:
    text = raw_text if raw_text is not None else ""
    parsed, errors = parse_proxy_list(text)
    if text.strip() and not parsed:
        raise ProxyParseError("Не удалось разобрать ни одного прокси. Проверьте формат строк.")
    if len(parsed) > MAX_PROXIES:
        raise ProxyParseError(f"Слишком много прокси (максимум {MAX_PROXIES}).")

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
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            kept.append(row)
    await session.flush()
    for row in existing_rows:
        if row.fingerprint not in keep_fps:
            await session.delete(row)
    await session.flush()
    stats = await rebalance_proxies(session, automation.id, proxies=kept)
    stats["errors"] = errors
    stats["skipped"] = len(errors)
    return stats


async def proxy_settings_payload(session: AsyncSession, automation: CustomAutomation) -> dict[str, Any]:
    proxies = await list_active_proxies(session, automation.id)
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
            "account_count": counts.get(row.id, 0),
        }
        for row in proxies
    ]
    return {
        "proxy_list_text": automation.proxy_list_text or "",
        "proxy_count": len(proxies),
        "accounts_with_proxy": assigned,
        "proxy_distribution": distribution,
    }
