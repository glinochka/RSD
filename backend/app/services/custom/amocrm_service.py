"""AmoCRM integration for transferring leads and syncing statuses."""
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import AmocrmConnection, CustomAutomation, CustomLead
from ...config import settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _base_url(subdomain: str) -> str:
    return f"https://{subdomain}.amocrm.ru/api/v4"


def _headers(connection: AmocrmConnection) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {connection.access_token_hash}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _refresh_token_if_needed(connection: AmocrmConnection) -> bool:
    if not connection.refresh_token_hash:
        return False
    if not settings.AMOCRM_CLIENT_ID or not settings.AMOCRM_CLIENT_SECRET:
        logger.warning("AmoCRM client credentials are not configured, cannot refresh token")
        return False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://{connection.subdomain}.amocrm.ru/oauth2/access_token",
                json={
                    "client_id": settings.AMOCRM_CLIENT_ID,
                    "client_secret": settings.AMOCRM_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": connection.refresh_token_hash,
                    "redirect_uri": settings.AMOCRM_REDIRECT_URI or "https://localhost/amocrm/callback",
                },
            )
            response.raise_for_status()
            data = response.json()
            connection.access_token_hash = data.get("access_token") or connection.access_token_hash
            connection.refresh_token_hash = data.get("refresh_token") or connection.refresh_token_hash
            connection.updated_at = _utc_now()
            return True
    except Exception as exc:
        logger.warning("AmoCRM token refresh failed: %s", exc)
        return False


async def get_connection(session: AsyncSession, automation_id: int) -> AmocrmConnection | None:
    return await session.scalar(
        select(AmocrmConnection).where(
            AmocrmConnection.custom_automation_id == automation_id,
            AmocrmConnection.is_active.is_(True),
        )
    )


async def create_or_update_connection(
    session: AsyncSession,
    automation_id: int,
    *,
    subdomain: str,
    access_token: str,
    refresh_token: str | None = None,
    pipeline_id: str | None = None,
    responsible_user_id: str | None = None,
    lead_status_id: str | None = None,
) -> AmocrmConnection:
    connection = await session.scalar(
        select(AmocrmConnection).where(AmocrmConnection.custom_automation_id == automation_id)
    )
    if not connection:
        connection = AmocrmConnection(
            custom_automation_id=automation_id,
            subdomain=subdomain,
            access_token_hash=access_token,
            refresh_token_hash=refresh_token,
            pipeline_id=pipeline_id,
            responsible_user_id=responsible_user_id,
            lead_status_id=lead_status_id,
            is_active=True,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(connection)
    else:
        connection.subdomain = subdomain
        connection.access_token_hash = access_token
        if refresh_token is not None:
            connection.refresh_token_hash = refresh_token
        if pipeline_id is not None:
            connection.pipeline_id = pipeline_id
        if responsible_user_id is not None:
            connection.responsible_user_id = responsible_user_id
        if lead_status_id is not None:
            connection.lead_status_id = lead_status_id
        connection.is_active = True
        connection.updated_at = _utc_now()
    await session.commit()
    await session.refresh(connection)
    return connection


async def _create_amocrm_contact(
    connection: AmocrmConnection,
    lead: CustomLead,
) -> str | None:
    custom_fields = []
    if lead.contact_type == "phone" and lead.contact_value:
        custom_fields.append({
            "field_code": "PHONE",
            "values": [{"value": lead.contact_value}],
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_base_url(connection.subdomain)}/contacts",
                headers=_headers(connection),
                json=payload,
            )
            if response.status_code == 401:
                refreshed = await _refresh_token_if_needed(connection)
                if refreshed:
                    response = await client.post(
                        f"{_base_url(connection.subdomain)}/contacts",
                        headers=_headers(connection),
                        json=payload,
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_base_url(connection.subdomain)}/leads",
                headers=_headers(connection),
                json=[payload_item],
            )
            if response.status_code == 401:
                refreshed = await _refresh_token_if_needed(connection)
                if refreshed:
                    response = await client.post(
                        f"{_base_url(connection.subdomain)}/leads",
                        headers=_headers(connection),
                        json=[payload_item],
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


async def transfer_lead_to_amocrm(
    session: AsyncSession,
    automation_id: int,
    lead: CustomLead,
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation or not automation.is_amocrm_enabled:
        return {"transferred": False, "reason": "amocrm_disabled"}

    connection = await get_connection(session, automation_id)
    if not connection:
        return {"transferred": False, "reason": "no_connection"}

    contact_id = await _create_amocrm_contact(connection, lead)
    if not contact_id:
        return {"transferred": False, "reason": "contact_failed"}

    lead_id = await _create_amocrm_lead(connection, lead, contact_id)
    if not lead_id:
        return {"transferred": False, "reason": "lead_failed"}

    lead.amocrm_contact_id = contact_id
    lead.amocrm_lead_id = lead_id
    lead.amocrm_pipeline_id = connection.pipeline_id
    lead.amocrm_status_id = connection.lead_status_id
    lead.status = "transferred"
    lead.transferred_at = _utc_now()
    lead.status_history = (lead.status_history or []) + [{"status": "transferred", "changed_at": lead.transferred_at.isoformat()}]
    lead.updated_at = lead.transferred_at
    await session.commit()

    connection.last_sync_at = _utc_now()
    await session.commit()

    return {"transferred": True, "amocrm_lead_id": lead_id, "amocrm_contact_id": contact_id}


def _status_from_amocrm(amocrm_status_id: str | None, amocrm_lead: dict[str, Any] | None = None) -> str | None:
    if amocrm_lead:
        if amocrm_lead.get("is_deleted"):
            return "lost"
        # Historical AmoCRM unchangeable statuses: 142 won, 143 lost.
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

    connection = await get_connection(session, automation_id)
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            params = {}
            for idx, lid in enumerate(lead_ids):
                params[f"filter[id][{idx}]"] = lid
            response = await client.get(
                f"{_base_url(connection.subdomain)}/leads",
                headers=_headers(connection),
                params=params,
            )
            if response.status_code == 401:
                refreshed = await _refresh_token_if_needed(connection)
                if refreshed:
                    response = await client.get(
                        f"{_base_url(connection.subdomain)}/leads",
                        headers=_headers(connection),
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

    if synced:
        await session.commit()

    connection.last_sync_at = _utc_now()
    await session.commit()
    return {"synced": synced}
