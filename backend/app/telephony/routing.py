"""DTMF extension and DID routing (refactor stage 7)."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.database import async_session_maker
from ..alembic.models import AgentChannelConnection, TelephonySipRoute
from ..telephony.credentials import (
    TELEPHONY_CHANNEL_PROVIDER,
    TelephonyCredentialsV1,
    parse_telephony_credentials,
)
from ..utils.crypto import decrypt_token
from .redis_keys import route_did_key, route_dtmf_key
from .redis_store import (
    delete_route_did,
    delete_route_dtmf,
    get_route_did,
    get_route_dtmf,
    get_route_dtmf_owner,
    redis_enabled,
    set_route_did,
    set_route_dtmf,
    set_route_dtmf_owner,
)

logger = logging.getLogger(__name__)

_EXTENSION_RE = re.compile(r"^\d{4}$")
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def normalize_e164(value: str) -> str | None:
    raw = (value or "").strip().replace(" ", "")
    if not raw:
        return None
    if not raw.startswith("+"):
        if raw.startswith("8") and len(raw) == 11:
            raw = "+7" + raw[1:]
        else:
            raw = f"+{raw}"
    if not _E164_RE.match(raw):
        return None
    return raw


def normalize_extension(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if not _EXTENSION_RE.match(raw):
        return None
    return raw


def normalize_inbound_numbers(numbers: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in numbers or []:
        norm = normalize_e164(str(item))
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def dedicated_did_numbers(creds: TelephonyCredentialsV1) -> list[str]:
    """DIDs that map this connection without DTMF."""
    numbers: list[str] = []
    primary = normalize_e164(creds.phone_number_e164)
    if primary and not creds.routing_extension:
        numbers.append(primary)
    numbers.extend(normalize_inbound_numbers(creds.inbound_numbers))
    seen: set[str] = set()
    unique: list[str] = []
    for num in numbers:
        if num not in seen:
            seen.add(num)
            unique.append(num)
    return unique


def pool_line_e164(creds: TelephonyCredentialsV1) -> str | None:
    """Shared inbound number when agents use DTMF extensions."""
    if not creds.routing_extension:
        return None
    return normalize_e164(creds.phone_number_e164)


def _normalize_sip_header(value: str | None) -> str:
    return (value or "").strip().lower()


def _sip_header_matches(header: str, pattern: str | None) -> bool:
    if not pattern or not str(pattern).strip():
        return True
    pat = _normalize_sip_header(pattern)
    if pat == "*":
        return True
    return pat in header or header.endswith(pat)


async def resolve_connection_by_sip_headers(
    *,
    sip_from: str | None,
    sip_to: str | None,
    fallback_connection_id: int,
) -> int | None:
    """Match SIP From/To against telephony_sip_routes (variant 7C)."""
    from_hdr = _normalize_sip_header(sip_from)
    to_hdr = _normalize_sip_header(sip_to)
    if not from_hdr and not to_hdr:
        return None

    async with async_session_maker() as session:
        rows = await session.scalars(
            select(TelephonySipRoute).where(TelephonySipRoute.is_active.is_(True))
        )
        for row in rows:
            if _sip_header_matches(from_hdr, row.match_from) and _sip_header_matches(to_hdr, row.match_to):
                conn_id = int(row.connection_id)
                if conn_id > 0:
                    return conn_id
    return None


async def resolve_connection_by_called_number(
    called_e164: str,
    *,
    fallback_connection_id: int,
) -> tuple[int, str]:
    """Return (connection_id, routed_by) where routed_by is 'did' or 'webhook'."""
    called = normalize_e164(called_e164)
    if not called:
        return fallback_connection_id, "webhook"
    if not redis_enabled():
        return fallback_connection_id, "webhook"
    routed = await get_route_did(called)
    if routed is not None and routed > 0:
        return routed, "did"
    return fallback_connection_id, "webhook"


async def resolve_agent_by_extension(extension: str) -> int | None:
    ext = normalize_extension(extension)
    if not ext or not redis_enabled():
        return None
    return await get_route_dtmf(ext)


async def find_extension_owner(extension: str) -> int | None:
    ext = normalize_extension(extension)
    if not ext or not redis_enabled():
        return None
    return await get_route_dtmf_owner(ext)


async def assert_extension_available(
    extension: str,
    *,
    connection_id: int,
) -> None:
    from fastapi import HTTPException, status

    ext = normalize_extension(extension)
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Добавочный номер должен состоять из 4 цифр",
        )
    owner = await find_extension_owner(ext)
    if owner is not None and int(owner) != int(connection_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Добавочный {ext} уже занят другим агентом",
        )


async def assert_did_available(e164: str, *, connection_id: int) -> None:
    from fastapi import HTTPException, status

    norm = normalize_e164(e164)
    if not norm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Некорректный номер DID: {e164!r}",
        )
    if not redis_enabled():
        return
    owner = await get_route_did(norm)
    if owner is not None and int(owner) != int(connection_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Номер {norm} уже привязан к другому агенту",
        )


async def sync_channel_routes(
    *,
    connection_id: int,
    agent_id: int,
    creds: TelephonyCredentialsV1,
    previous: TelephonyCredentialsV1 | None = None,
) -> None:
    if not redis_enabled():
        return
    if previous is not None:
        await clear_channel_routes(previous, connection_id=connection_id)

    ext = normalize_extension(creds.routing_extension)
    if ext:
        await assert_extension_available(ext, connection_id=connection_id)
        await set_route_dtmf(ext, int(agent_id))
        await set_route_dtmf_owner(ext, int(connection_id))

    for e164 in dedicated_did_numbers(creds):
        await assert_did_available(e164, connection_id=connection_id)
        await set_route_did(e164, int(connection_id))

    pool = pool_line_e164(creds)
    if pool:
        logger.info(
            "telephony routing pool line %s connection_id=%s extension=%s",
            pool,
            connection_id,
            ext,
        )


async def clear_channel_routes(
    creds: TelephonyCredentialsV1,
    *,
    connection_id: int | None = None,
) -> None:
    if not redis_enabled():
        return
    ext = normalize_extension(creds.routing_extension)
    if ext:
        owner = await get_route_dtmf_owner(ext)
        if connection_id is None or owner is None or int(owner) == int(connection_id):
            await delete_route_dtmf(ext)
    for e164 in dedicated_did_numbers(creds):
        await delete_route_did(e164)


async def scan_extension_conflict_in_db(
    session: AsyncSession,
    extension: str,
    *,
    exclude_connection_id: int | None = None,
) -> int | None:
    """Fallback uniqueness check when Redis is empty."""
    ext = normalize_extension(extension)
    if not ext:
        return None
    rows = await session.scalars(
        select(AgentChannelConnection).where(
            AgentChannelConnection.provider == TELEPHONY_CHANNEL_PROVIDER,
            AgentChannelConnection.is_active.is_(True),
        )
    )
    for row in rows:
        if exclude_connection_id is not None and int(row.id) == int(exclude_connection_id):
            continue
        if not row.encrypted_credentials:
            continue
        try:
            creds = parse_telephony_credentials(decrypt_token(row.encrypted_credentials))
        except Exception:
            continue
        if normalize_extension(creds.routing_extension) == ext:
            return int(row.id)
    return None


def telephony_routing_public_fields(creds: TelephonyCredentialsV1) -> dict[str, Any]:
    from .platform_config import format_dial_with_extension

    pool = pool_line_e164(creds) or normalize_e164(creds.phone_number_e164)
    ext = normalize_extension(creds.routing_extension)
    return {
        "routing_extension": ext,
        "inbound_numbers": [],
        "pool_line_e164": pool,
        "dedicated_dids": [],
        "routing_mode": "dtmf_extension",
        "dial_hint": format_dial_with_extension(pool or "", ext),
    }


def routing_summary_for_call(
    *,
    routed_by: str,
    called_e164: str,
    routing_extension: str | None = None,
) -> dict[str, Any]:
    return {
        "routed_by": routed_by,
        "called_e164": normalize_e164(called_e164) or called_e164,
        "routing_extension": routing_extension,
    }
