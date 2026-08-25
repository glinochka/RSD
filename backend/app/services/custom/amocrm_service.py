"""AmoCRM integration: OAuth, lead transfer, status sync."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AmocrmConnection, CustomAutomation, CustomLead
from ...config import settings
from ...utils import crypto as token_crypto

logger = logging.getLogger(__name__)

AMOCRM_OAUTH_SCOPE = "custom_amocrm_oauth"
AMOCRM_OAUTH_STATE_TTL_SECONDS = 600
_REFRESH_SKEW = timedelta(minutes=5)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _base_url(subdomain: str) -> str:
    return f"https://{subdomain}.amocrm.ru/api/v4"


def _encrypt(value: str | None) -> str | None:
    if not value:
        return value
    return token_crypto.encrypt_token(value)


def _decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return token_crypto.decrypt_token(value) or ""
    except Exception:
        return value


def get_redirect_uri() -> str:
    return (settings.AMOCRM_REDIRECT_URI or "").strip()


def _oauth_client_id(connection: AmocrmConnection) -> str:
    return (connection.client_id or settings.AMOCRM_CLIENT_ID or "").strip()


def _oauth_client_secret(connection: AmocrmConnection) -> str:
    if connection.client_secret_enc:
        return _decrypt(connection.client_secret_enc)
    return (settings.AMOCRM_CLIENT_SECRET or "").strip()


def _access_token(connection: AmocrmConnection) -> str:
    return _decrypt(connection.access_token_hash)


def _refresh_token(connection: AmocrmConnection) -> str:
    return _decrypt(connection.refresh_token_hash)


def _headers(connection: AmocrmConnection) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_access_token(connection)}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def connection_is_connected(connection: AmocrmConnection | None) -> bool:
    if not connection or not connection.is_active:
        return False
    return bool(_access_token(connection))


def serialize_connection(connection: AmocrmConnection | None) -> dict[str, Any]:
    return {
        "id": connection.id if connection else None,
        "custom_automation_id": connection.custom_automation_id if connection else None,
        "subdomain": connection.subdomain if connection else None,
        "client_id": connection.client_id if connection else None,
        "has_credentials": bool(connection and connection.client_id and connection.client_secret_enc),
        "client_secret_set": bool(connection and connection.client_secret_enc),
        "connected": connection_is_connected(connection),
        "pipeline_id": connection.pipeline_id if connection else None,
        "responsible_user_id": connection.responsible_user_id if connection else None,
        "lead_status_id": connection.lead_status_id if connection else None,
        "is_active": bool(connection.is_active) if connection else False,
        "last_sync_at": connection.last_sync_at if connection else None,
        "created_at": connection.created_at if connection else None,
        "updated_at": connection.updated_at if connection else None,
        "redirect_uri": get_redirect_uri(),
    }


def create_oauth_state(*, automation_id: int, return_url: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "scope": AMOCRM_OAUTH_SCOPE,
        "automation_id": int(automation_id),
        "return_url": return_url,
        "exp": now + timedelta(seconds=AMOCRM_OAUTH_STATE_TTL_SECONDS),
        "iat": now,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_oauth_state(state_token: str) -> dict[str, Any]:
    try:
        data = jwt.decode(state_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Недействительный или просроченный OAuth state") from exc
    if data.get("scope") != AMOCRM_OAUTH_SCOPE:
        raise ValueError("Некорректный OAuth state")
    if not isinstance(data.get("automation_id"), int):
        raise ValueError("OAuth state без automation_id")
    return data


def safe_return_url(return_url: str | None, automation_id: int) -> str:
    fallback = f"{(settings.BASE_URL or '').rstrip('/')}/custom/automations/{automation_id}/settings"
    expected_path = f"/custom/automations/{automation_id}/settings"
    if not return_url:
        return fallback
    parsed = urlparse(return_url.strip())
    if parsed.scheme not in {"http", "https"}:
        return fallback
    if expected_path not in (parsed.path or ""):
        return fallback
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _subdomain_from_referer(referer: str | None, fallback: str) -> str:
    if not referer:
        return fallback
    host = urlparse(referer if "://" in referer else f"https://{referer}").hostname or ""
    if host.endswith(".amocrm.ru") or host.endswith(".kommo.com"):
        return host.split(".")[0]
    return fallback


def build_oauth_authorization_url(client_id: str, state: str) -> str:
    query = urlencode({"client_id": client_id, "state": state, "mode": "popup"})
    return f"https://www.amocrm.ru/oauth?{query}"


async def get_connection(session: AsyncSession, automation_id: int) -> AmocrmConnection | None:
    return await session.scalar(
        select(AmocrmConnection).where(
            AmocrmConnection.custom_automation_id == automation_id,
        )
    )


async def get_active_connection(session: AsyncSession, automation_id: int) -> AmocrmConnection | None:
    connection = await get_connection(session, automation_id)
    if connection_is_connected(connection):
        return connection
    return None


async def save_credentials(
    session: AsyncSession,
    automation_id: int,
    *,
    subdomain: str,
    client_id: str,
    client_secret: str | None = None,
) -> AmocrmConnection:
    subdomain = (subdomain or "").strip()
    client_id = (client_id or "").strip()
    if not subdomain or not client_id:
        raise ValueError("Нужны поддомен и client_id")

    connection = await get_connection(session, automation_id)
    if not connection:
        if not (client_secret or "").strip():
            raise ValueError("Нужен client_secret")
        connection = AmocrmConnection(
            custom_automation_id=automation_id,
            subdomain=subdomain,
            client_id=client_id,
            client_secret_enc=_encrypt(client_secret.strip()),
            access_token_hash=None,
            refresh_token_hash=None,
            is_active=False,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(connection)
    else:
        connection.subdomain = subdomain
        connection.client_id = client_id
        if (client_secret or "").strip():
            connection.client_secret_enc = _encrypt(client_secret.strip())
        connection.updated_at = _utc_now()
    await session.commit()
    await session.refresh(connection)
    return connection


async def update_pipeline_config(
    session: AsyncSession,
    automation_id: int,
    *,
    pipeline_id: str | None = None,
    responsible_user_id: str | None = None,
    lead_status_id: str | None = None,
) -> AmocrmConnection:
    connection = await get_connection(session, automation_id)
    if not connection:
        raise ValueError("Сначала сохраните client_id и client_secret")
    if pipeline_id is not None:
        connection.pipeline_id = pipeline_id or None
    if responsible_user_id is not None:
        connection.responsible_user_id = responsible_user_id or None
    if lead_status_id is not None:
        connection.lead_status_id = lead_status_id or None
    connection.updated_at = _utc_now()
    await session.commit()
    await session.refresh(connection)
    return connection


async def deactivate_connection(session: AsyncSession, automation_id: int) -> None:
    connection = await get_connection(session, automation_id)
    if not connection:
        return
    connection.is_active = False
    connection.access_token_hash = None
    connection.refresh_token_hash = None
    connection.expires_at = None
    connection.updated_at = _utc_now()
    await session.commit()


def _apply_token_payload(connection: AmocrmConnection, data: dict[str, Any]) -> None:
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if access:
        connection.access_token_hash = _encrypt(str(access))
    if refresh:
        connection.refresh_token_hash = _encrypt(str(refresh))
    expires_in = data.get("expires_in")
    try:
        seconds = int(expires_in) if expires_in is not None else 86400
    except (TypeError, ValueError):
        seconds = 86400
    connection.expires_at = _utc_now() + timedelta(seconds=max(seconds, 60))
    connection.is_active = True
    connection.updated_at = _utc_now()


async def _refresh_and_persist(session: AsyncSession, connection: AmocrmConnection) -> bool:
    refresh = _refresh_token(connection)
    client_id = _oauth_client_id(connection)
    client_secret = _oauth_client_secret(connection)
    redirect_uri = get_redirect_uri()
    if not refresh or not client_id or not client_secret:
        logger.warning("AmoCRM refresh skipped: missing credentials for automation %s", connection.custom_automation_id)
        return False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://{connection.subdomain}.amocrm.ru/oauth2/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "redirect_uri": redirect_uri or "https://localhost/amocrm/callback",
                },
            )
            response.raise_for_status()
            data = response.json()
        _apply_token_payload(connection, data)
        await session.commit()
        await session.refresh(connection)
        return True
    except Exception as exc:
        logger.warning("AmoCRM token refresh failed: %s", exc)
        return False


def _token_expired(connection: AmocrmConnection) -> bool:
    if not connection.expires_at:
        return False
    return connection.expires_at <= (_utc_now() + _REFRESH_SKEW)


async def _ensure_fresh_token(session: AsyncSession, connection: AmocrmConnection) -> None:
    if _token_expired(connection):
        await _refresh_and_persist(session, connection)


async def exchange_authorization_code(
    session: AsyncSession,
    automation_id: int,
    *,
    code: str,
    referer: str | None = None,
) -> AmocrmConnection:
    connection = await get_connection(session, automation_id)
    if not connection:
        raise ValueError("Сначала сохраните client_id и client_secret")
    client_id = _oauth_client_id(connection)
    client_secret = _oauth_client_secret(connection)
    redirect_uri = get_redirect_uri()
    if not client_id or not client_secret:
        raise ValueError("Нет client_id / client_secret")
    if not redirect_uri:
        raise ValueError("AMOCRM_REDIRECT_URI не задан")

    subdomain = _subdomain_from_referer(referer, connection.subdomain)
    connection.subdomain = subdomain
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://{subdomain}.amocrm.ru/oauth2/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise ValueError(f"Не удалось обменять код AmoCRM: {exc}") from exc

    _apply_token_payload(connection, data)
    await session.commit()
    await session.refresh(connection)
    return connection


async def _amocrm_request(
    session: AsyncSession,
    connection: AmocrmConnection,
    method: str,
    url: str,
    *,
    json_body: Any = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    await _ensure_fresh_token(session, connection)
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method,
            url,
            headers=_headers(connection),
            json=json_body,
            params=params,
        )
        if response.status_code == 401:
            refreshed = await _refresh_and_persist(session, connection)
            if refreshed:
                response = await client.request(
                    method,
                    url,
                    headers=_headers(connection),
                    json=json_body,
                    params=params,
                )
        return response


async def _create_amocrm_contact(
    session: AsyncSession,
    connection: AmocrmConnection,
    lead: CustomLead,
) -> str | None:
    custom_fields = []
    raw = lead.dmp_raw_data if isinstance(lead.dmp_raw_data, dict) else {}
    phone = None
    if lead.contact_type == "phone" and lead.contact_value:
        phone = lead.contact_value
    else:
        phone = raw.get("phone") or raw.get("phone_number") or raw.get("tel")
    if phone:
        custom_fields.append({
            "field_code": "PHONE",
            "values": [{"value": str(phone)}],
        })
    if lead.contact_type == "email" and lead.contact_value:
        custom_fields.append({
            "field_code": "EMAIL",
            "values": [{"value": lead.contact_value}],
        })

    payload = [
        {
            "name": lead.full_name or lead.contact_value or "Lead from RSD",
            "custom_fields_values": custom_fields,
        }
    ]

    try:
        response = await _amocrm_request(
            session,
            connection,
            "POST",
            f"{_base_url(connection.subdomain)}/contacts",
            json_body=payload,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return str(data[0].get("id"))
        if isinstance(data, dict) and data.get("_embedded"):
            contacts = data["_embedded"].get("contacts", [])
            if contacts:
                return str(contacts[0].get("id"))
    except Exception as exc:
        logger.warning("AmoCRM create contact failed for lead %s: %s", lead.id, exc)
    return None


async def _create_amocrm_lead(
    session: AsyncSession,
    connection: AmocrmConnection,
    lead: CustomLead,
    contact_id: str,
) -> str | None:
    payload_item: dict[str, Any] = {
        "name": f"Lead {lead.id} — {lead.contact_value}",
        "contacts_id": [{"id": int(contact_id)}],
    }
    if connection.responsible_user_id:
        payload_item["responsible_user_id"] = int(connection.responsible_user_id)
    if connection.pipeline_id:
        payload_item["pipeline_id"] = int(connection.pipeline_id)
    if connection.lead_status_id:
        payload_item["status_id"] = int(connection.lead_status_id)

    try:
        response = await _amocrm_request(
            session,
            connection,
            "POST",
            f"{_base_url(connection.subdomain)}/leads",
            json_body=[payload_item],
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return str(data[0].get("id"))
        if isinstance(data, dict) and data.get("_embedded"):
            leads = data["_embedded"].get("leads", [])
            if leads:
                return str(leads[0].get("id"))
    except Exception as exc:
        logger.warning("AmoCRM create lead failed for lead %s: %s", lead.id, exc)
    return None


async def _add_amocrm_note(
    session: AsyncSession,
    connection: AmocrmConnection,
    amocrm_lead_id: str,
    text: str,
) -> None:
    payload = [
        {
            "note_type": "common",
            "params": {"text": (text or "")[:10000]},
        }
    ]
    try:
        response = await _amocrm_request(
            session,
            connection,
            "POST",
            f"{_base_url(connection.subdomain)}/leads/{amocrm_lead_id}/notes",
            json_body=payload,
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning("AmoCRM note failed for amo lead %s: %s", amocrm_lead_id, exc)


async def transfer_lead_to_amocrm(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation or not automation.is_amocrm_enabled:
        return {"transferred": False, "reason": "amocrm_disabled"}

    connection = await get_active_connection(session, automation_id)
    if not connection:
        return {"transferred": False, "reason": "no_connection"}

    contact_id = await _create_amocrm_contact(session, connection, lead)
    if not contact_id:
        return {"transferred": False, "reason": "contact_failed"}

    lead_id = await _create_amocrm_lead(session, connection, lead, contact_id)
    if not lead_id:
        return {"transferred": False, "reason": "lead_failed"}

    try:
        from .lead_delivery_service import build_lead_handoff_text

        note = await build_lead_handoff_text(session, lead, automation)
        if note:
            await _add_amocrm_note(session, connection, lead_id, note)
    except Exception as exc:
        logger.warning("AmoCRM comment skipped for lead %s: %s", lead.id, exc)

    lead.amocrm_contact_id = contact_id
    lead.amocrm_lead_id = lead_id
    lead.amocrm_pipeline_id = connection.pipeline_id
    lead.amocrm_status_id = connection.lead_status_id
    lead.status = "transferred"
    lead.transferred_at = _utc_now()
    lead.status_history = (lead.status_history or []) + [{"status": "transferred", "changed_at": lead.transferred_at.isoformat()}]
    lead.updated_at = lead.transferred_at
    connection.last_sync_at = _utc_now()
    await session.commit()

    return {"transferred": True, "amocrm_lead_id": lead_id, "amocrm_contact_id": contact_id}


def _status_from_amocrm(amocrm_status_id: str | None, amocrm_lead: dict[str, Any] | None = None) -> str | None:
    if amocrm_lead:
        if amocrm_lead.get("is_deleted"):
            return "lost"
        status_id = str(amocrm_lead.get("status_id") or amocrm_status_id or "")
        if status_id == "142":
            return "converted"
        if status_id == "143":
            return "lost"
        if amocrm_lead.get("closed_at") and status_id == "142":
            return "converted"
    return None


async def run_amocrm_sync_for_automation(automation_id: int) -> dict[str, Any]:
    from ...alembic.database import async_session_maker

    async with async_session_maker() as session:
        return await sync_lead_statuses(session, automation_id)


async def sync_lead_statuses(
    session: AsyncSession,
    automation_id: int,
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation or not automation.is_amocrm_enabled:
        return {"synced": 0, "reason": "amocrm_disabled"}

    connection = await get_active_connection(session, automation_id)
    if not connection:
        return {"synced": 0, "reason": "no_connection"}

    result = await session.execute(
        select(CustomLead).where(
            CustomLead.custom_automation_id == automation_id,
            CustomLead.amocrm_lead_id.is_not(None),
        )
    )
    leads = result.scalars().all()
    if not leads:
        return {"synced": 0}

    lead_ids = [lead.amocrm_lead_id for lead in leads if lead.amocrm_lead_id]
    try:
        params = {}
        for idx, lid in enumerate(lead_ids):
            params[f"filter[id][{idx}]"] = lid
        response = await _amocrm_request(
            session,
            connection,
            "GET",
            f"{_base_url(connection.subdomain)}/leads",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning("AmoCRM sync failed for automation %s: %s", automation_id, exc)
        return {"synced": 0, "reason": "api_error"}

    items = []
    if isinstance(data, dict) and data.get("_embedded"):
        items = data["_embedded"].get("leads", [])
    elif isinstance(data, list):
        items = data

    status_map = {str(item.get("id")): item for item in items}
    synced = 0
    for lead in leads:
        amocrm_lead = status_map.get(str(lead.amocrm_lead_id))
        if not amocrm_lead:
            continue
        new_status_id = str(amocrm_lead.get("status_id") or "")
        if new_status_id and new_status_id != lead.amocrm_status_id:
            lead.amocrm_status_id = new_status_id
            mapped = _status_from_amocrm(new_status_id, amocrm_lead)
            if mapped and lead.status != mapped:
                lead.status = mapped
                lead.status_history = (lead.status_history or []) + [{"status": mapped, "changed_at": _utc_now().isoformat()}]
            lead.updated_at = _utc_now()
            synced += 1

    connection.last_sync_at = _utc_now()
    await session.commit()
    return {"synced": synced}
