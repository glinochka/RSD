"""Custom outbound/inbound webhooks stored in module_settings.integrations."""
from __future__ import annotations

import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...alembic.models import CustomAutomation, CustomLead, LeadStatus
from ...config import settings

logger = logging.getLogger(__name__)

EVENTS = ("lead.created", "lead.qualified", "lead.transferred", "lead.lost")
DIRECTIONS = ("outbound", "inbound")
LEAD_FIELDS = (
    "lead_id",
    "contact_value",
    "contact_type",
    "full_name",
    "company",
    "position",
    "status",
    "source",
    "automation_id",
    "automation_name",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _secrets_match(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def public_inbound_url(automation_id: int, route_id: str, secret: str | None) -> str:
    base = (settings.BASE_URL or "").rstrip("/")
    if not base or not secret or not route_id:
        return ""
    return f"{base}/api/custom/webhooks/integrations/{automation_id}/{route_id}/{secret}"


def _blob(automation: CustomAutomation) -> dict[str, Any]:
    return dict(automation.module_settings or {})


def _routes_raw(automation: CustomAutomation) -> list[dict[str, Any]]:
    integ = dict((_blob(automation).get("integrations") or {}))
    items = integ.get("routes") or []
    return [dict(item) for item in items if isinstance(item, dict)]


def _save_routes(automation: CustomAutomation, routes: list[dict[str, Any]]) -> None:
    blob = _blob(automation)
    integ = dict(blob.get("integrations") or {})
    integ["routes"] = routes
    blob["integrations"] = integ
    automation.module_settings = blob
    flag_modified(automation, "module_settings")
    automation.updated_at = _utc_now()


def _clean_mappings(raw: Any) -> list[dict[str, str]]:
    items = []
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip()
        target = str(row.get("target") or "").strip()
        if source and target:
            items.append({"source": source[:120], "target": target[:120]})
    return items[:40]


def serialize_route(route: dict[str, Any], automation_id: int) -> dict[str, Any]:
    direction = route.get("direction") if route.get("direction") in DIRECTIONS else "outbound"
    event = route.get("event") if route.get("event") in EVENTS else "lead.transferred"
    secret = str(route.get("secret") or "")
    route_id = str(route.get("id") or "")
    inbound_url = public_inbound_url(automation_id, route_id, secret) if direction == "inbound" else None
    return {
        "id": route_id,
        "name": str(route.get("name") or "Маршрут")[:80],
        "enabled": bool(route.get("enabled", True)),
        "direction": direction,
        "event": event,
        "method": "POST",
        "url": str(route.get("url") or "") or None,
        "secret_header": str(route.get("secret_header") or "X-Webhook-Secret")[:80],
        "secret": secret or None,
        "mappings": _clean_mappings(route.get("mappings")),
        "inbound_url": inbound_url,
    }


def list_routes(automation: CustomAutomation) -> list[dict[str, Any]]:
    return [serialize_route(item, automation.id) for item in _routes_raw(automation)]


def upsert_route(automation: CustomAutomation, payload: dict[str, Any]) -> dict[str, Any]:
    direction = str(payload.get("direction") or "outbound").strip()
    if direction not in DIRECTIONS:
        raise ValueError("Направление: outbound или inbound")
    event = str(payload.get("event") or "lead.transferred").strip()
    if event not in EVENTS:
        raise ValueError("Неизвестное событие")
    name = str(payload.get("name") or "").strip() or "Маршрут"
    url = str(payload.get("url") or "").strip()
    if direction == "outbound":
        if not url.startswith(("http://", "https://")):
            raise ValueError("Нужен URL с http:// или https://")
    routes = _routes_raw(automation)
    route_id = str(payload.get("id") or "").strip()
    current = next((item for item in routes if str(item.get("id")) == route_id), None) if route_id else None
    secret = str(payload.get("secret") or "").strip()
    if not secret:
        secret = str((current or {}).get("secret") or "") or secrets.token_urlsafe(24)
    if not route_id:
        route_id = secrets.token_urlsafe(8)
        current = None
    record = {
        "id": route_id,
        "name": name[:80],
        "enabled": bool(payload.get("enabled", True)),
        "direction": direction,
        "event": event,
        "method": "POST",
        "url": url if direction == "outbound" else "",
        "secret_header": str(payload.get("secret_header") or "X-Webhook-Secret").strip()[:80] or "X-Webhook-Secret",
        "secret": secret,
        "mappings": _clean_mappings(payload.get("mappings")),
    }
    if current:
        routes = [record if str(item.get("id")) == route_id else item for item in routes]
    else:
        routes.append(record)
    _save_routes(automation, routes)
    return serialize_route(record, automation.id)


def delete_route(automation: CustomAutomation, route_id: str) -> bool:
    routes = _routes_raw(automation)
    next_routes = [item for item in routes if str(item.get("id")) != str(route_id)]
    if len(next_routes) == len(routes):
        return False
    _save_routes(automation, next_routes)
    return True


def lead_fields(lead: CustomLead, automation: CustomAutomation) -> dict[str, Any]:
    return {
        "lead_id": lead.id,
        "contact_value": lead.contact_value,
        "contact_type": lead.contact_type,
        "full_name": lead.full_name,
        "company": lead.company,
        "position": lead.position,
        "status": lead.status,
        "source": lead.source,
        "automation_id": automation.id,
        "automation_name": automation.name,
    }


def _get_path(data: Any, path: str) -> Any:
    current = data
    for part in str(path or "").split("."):
        key = part.strip()
        if not key:
            return None
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = [part.strip() for part in str(path or "").split(".") if part.strip()]
    if not parts:
        return
    cursor = data
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[part] = nxt
        cursor = nxt
    cursor[parts[-1]] = value


def _mapped_payload(fields: dict[str, Any], mappings: list[dict[str, str]]) -> dict[str, Any]:
    if not mappings:
        return dict(fields)
    payload: dict[str, Any] = {}
    for row in mappings:
        _set_path(payload, row["target"], fields.get(row["source"]))
    return payload


def _inbound_mapped(body: dict[str, Any], mappings: list[dict[str, str]]) -> dict[str, Any]:
    if not mappings:
        return dict(body)
    payload: dict[str, Any] = {}
    for row in mappings:
        payload[row["target"]] = _get_path(body, row["source"])
    return payload


async def dispatch_event(
    session: AsyncSession,
    automation: CustomAutomation | None,
    event: str,
    lead: CustomLead,
) -> None:
    del session
    if not automation or event not in EVENTS:
        return
    fields = lead_fields(lead, automation)
    for route in _routes_raw(automation):
        if not route.get("enabled", True):
            continue
        if route.get("direction") != "outbound":
            continue
        if route.get("event") != event:
            continue
        url = str(route.get("url") or "").strip()
        if not url:
            continue
        body = _mapped_payload(fields, _clean_mappings(route.get("mappings")))
        headers = {"Content-Type": "application/json"}
        secret = str(route.get("secret") or "")
        header_name = str(route.get("secret_header") or "X-Webhook-Secret")
        if secret:
            headers[header_name] = secret
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
        except Exception as exc:
            logger.warning("Integration webhook %s failed for lead %s: %s", route.get("id"), lead.id, exc)


async def ingest_inbound(
    session: AsyncSession,
    automation_id: int,
    route_id: str,
    secret: str,
    payload: Any,
    header_secret: str | None = None,
) -> dict[str, Any]:
    automation = await session.get(CustomAutomation, automation_id)
    if not automation:
        raise ValueError("not_found")
    route = next((item for item in _routes_raw(automation) if str(item.get("id")) == str(route_id)), None)
    if not route or route.get("direction") != "inbound" or not route.get("enabled", True):
        raise ValueError("not_found")
    expected = str(route.get("secret") or "")
    path_ok = _secrets_match(expected, (secret or "").strip())
    header_ok = _secrets_match(expected, (header_secret or "").strip())
    if not path_ok and not header_ok:
        raise ValueError("forbidden")
    body = payload if isinstance(payload, dict) else {}
    mapped = _inbound_mapped(body, _clean_mappings(route.get("mappings")))
    contact_value = str(
        mapped.get("contact_value")
        or body.get("contact_value")
        or body.get("phone")
        or body.get("email")
        or body.get("contact")
        or ""
    ).strip()
    if not contact_value:
        raise ValueError("contact_required")
    contact_type = str(mapped.get("contact_type") or body.get("contact_type") or "unknown").strip() or "unknown"
    lead = CustomLead(
        custom_automation_id=automation_id,
        source=f"webhook:{route.get('name') or route_id}",
        contact_type=contact_type[:32],
        contact_value=contact_value[:255],
        full_name=(str(mapped.get("full_name") or body.get("full_name") or body.get("name") or "") or None),
        company=(str(mapped.get("company") or body.get("company") or "") or None),
        position=(str(mapped.get("position") or body.get("position") or "") or None),
        dmp_raw_data=body,
        status=LeadStatus.NEW.value,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    await dispatch_event(session, automation, "lead.created", lead)
    return {"created": True, "lead_id": lead.id}
