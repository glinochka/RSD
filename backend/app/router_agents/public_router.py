"""Public agent endpoints for website builder (stage 5)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..alembic.database import async_session_maker
from ..alembic.models import Agent
from ..services.admin_booking import get_admin_booking_service
from ..services.agent_public_data import (
    agent_has_published_website,
    get_agent_public_data,
    is_admin_booking_agent,
)
from ..services.website_public_forms import submit_website_lead
from ..utils.rate_limit import rate_limit
from .public_schemas import (
    AgentPublicDataResponse,
    PublicBookingCreateRequest,
    PublicBookingCreateResponse,
    PublicBookingSlotsResponse,
    PublicWebsiteLeadRequest,
    PublicWebsiteLeadResponse,
)

router = APIRouter(prefix="/api/v1/agents")

logger = logging.getLogger(__name__)

_PUBLIC_RATE = Depends(rate_limit(max_requests=100, window_seconds=60, scope="agents_public"))


def _parse_iso_datetime(raw_value: str, *, field_name: str) -> datetime:
    value = str(raw_value or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} is required",
        )
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be ISO datetime",
        ) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@router.get("/{agent_id}/public-data", response_model=AgentPublicDataResponse)
async def get_agent_public_data_endpoint(
    agent_id: int,
    embed: Annotated[bool, Query(description="Include widget API key if agent has published website")] = False,
    _: None = _PUBLIC_RATE,
):
    """Public agent profile: services, contacts, optional widget key for embed."""
    include_key = embed and await agent_has_published_website(agent_id)
    data = await get_agent_public_data(agent_id, include_widget_key=include_key)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return data


@router.get("/{agent_id}/booking/slots", response_model=PublicBookingSlotsResponse)
async def list_public_booking_slots(
    agent_id: int,
    service_id: Annotated[int, Query(gt=0)],
    date: Annotated[str, Query(description="Date YYYY-MM-DD")],
    _: None = _PUBLIC_RATE,
):
    """Available time slots for a service on a given day."""
    async with async_session_maker() as session:
        agent = await session.get(Agent, agent_id)
        if not agent or not agent.is_active or not is_admin_booking_agent(agent):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        day = datetime.strptime(date.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date must be YYYY-MM-DD",
        ) from exc

    start_dt = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(days=1)

    items = await get_admin_booking_service().list_available_slots(
        agent_id=agent_id,
        starts_at=start_dt.replace(tzinfo=None),
        ends_at=end_dt.replace(tzinfo=None),
        service_id=service_id,
    )
    return PublicBookingSlotsResponse(items=items)


@router.post("/{agent_id}/booking/appointments", response_model=PublicBookingCreateResponse)
async def create_public_booking(
    agent_id: int,
    request: PublicBookingCreateRequest,
    _: None = _PUBLIC_RATE,
):
    """Create appointment from public website booking form."""
    async with async_session_maker() as session:
        agent = await session.get(Agent, agent_id)
        if not agent or not agent.is_active or not is_admin_booking_agent(agent):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    start_dt = _parse_iso_datetime(request.starts_at, field_name="starts_at")
    end_dt = _parse_iso_datetime(request.ends_at, field_name="ends_at")
    if end_dt <= start_dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ends_at must be greater than starts_at",
        )

    client_external_id = f"web_{uuid.uuid4().hex[:16]}"
    notes_parts = []
    if request.client_phone:
        notes_parts.append(f"Телефон: {request.client_phone}")
    if request.notes:
        notes_parts.append(request.notes)

    try:
        row = await get_admin_booking_service().create_appointment(
            agent_id=agent_id,
            client_external_id=client_external_id,
            starts_at=start_dt,
            ends_at=end_dt,
            service_id=request.service_id,
            staff_id=request.staff_id,
            client_name=request.client_name,
            source_channel="website",
            notes="\n".join(notes_parts) if notes_parts else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось создать запись. Выберите другое время.",
        ) from e

    return PublicBookingCreateResponse(
        id=row["id"],
        status=row.get("status", "pending"),
        starts_at=row.get("starts_at"),
        ends_at=row.get("ends_at"),
    )


@router.post("/{agent_id}/website/leads", response_model=PublicWebsiteLeadResponse)
async def create_website_lead(
    agent_id: int,
    request: PublicWebsiteLeadRequest,
    _: None = _PUBLIC_RATE,
):
    """Create a lead/application from a public landing page form."""
    if not await agent_has_published_website(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        row = await submit_website_lead(
            agent_id=agent_id,
            client_name=request.client_name,
            fields=request.fields,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception:
        logger.exception("website lead submission failed agent_id=%s", agent_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось отправить заявку. Попробуйте позже.",
        )

    return PublicWebsiteLeadResponse(
        id=row["id"],
        status=row.get("status", "new"),
    )
