"""Local Postgres-backed booking provider for admin template."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import json
from typing import Any, Callable

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ....alembic.database import async_session_maker
from ....alembic.models import (
    AdminAppointment,
    AdminClientProfile,
    AdminResource,
    AdminScheduleSlot,
    AdminService,
    AdminStaff,
    AdminWaitlistEntry,
    Agent,
)
from .base import BookingProvider

ACTIVE_APPOINTMENT_STATUSES = {"pending_confirmation", "booked", "confirmed", "in_progress"}


@asynccontextmanager
async def _maybe_begin(session):
    if session.in_transaction():
        yield
        return
    async with session.begin():
        yield


def _normalize_string(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _ensure_window(starts_at: datetime, ends_at: datetime) -> None:
    if ends_at <= starts_at:
        raise ValueError("Invalid time window: ends_at must be greater than starts_at")


def _json_list_load(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _json_list_dump(values: list[str] | None) -> str | None:
    normalized = [str(item).strip() for item in (values or []) if str(item).strip()]
    if not normalized:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def _json_object_load(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _serialize_staff(row: AdminStaff) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "role": row.role,
        "full_name": row.full_name,
        "specializations": _json_list_load(row.specializations_json),
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_resource(row: AdminResource) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "resource_type": row.resource_type,
        "title": row.title,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_service(row: AdminService) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "target_role": row.target_role,
        "title": row.title,
        "duration_minutes": int(row.duration_minutes),
        "price_minor": int(row.price_minor or 0),
        "resource_type_filters": _json_list_load(row.resource_type_filters_json),
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_schedule_slot(row: AdminScheduleSlot) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "staff_id": row.staff_id,
        "resource_id": row.resource_id,
        "slot_kind": row.slot_kind,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "ends_at": row.ends_at.isoformat() if row.ends_at else None,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_appointment(row: AdminAppointment) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "staff_id": row.staff_id,
        "resource_id": row.resource_id,
        "service_id": row.service_id,
        "client_external_id": row.client_external_id,
        "client_name": row.client_name,
        "source_channel": row.source_channel,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "ends_at": row.ends_at.isoformat() if row.ends_at else None,
        "status": row.status,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class LocalBookingProvider(BookingProvider):
    provider_name = "local"

    def __init__(self, session_factory: Callable[[], Any] | async_sessionmaker = async_session_maker):
        self._session_factory = session_factory

    async def list_staff(
        self,
        *,
        agent_id: int,
        role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            query = select(AdminStaff).where(AdminStaff.agent_id == agent_id)
            if role:
                query = query.where(AdminStaff.role == role.strip().lower())
            if active_only:
                query = query.where(AdminStaff.is_active.is_(True))
            rows = (await session.execute(query.order_by(AdminStaff.id.asc()))).scalars().all()
            return [_serialize_staff(row) for row in rows]

    async def create_staff(
        self,
        *,
        agent_id: int,
        role: str,
        full_name: str,
        specializations: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        normalized_role = _normalize_string(role)
        normalized_name = _normalize_string(full_name)
        if not normalized_role or not normalized_name:
            raise ValueError("role and full_name are required")

        row = AdminStaff(
            agent_id=agent_id,
            role=normalized_role.lower(),
            full_name=normalized_name,
            specializations_json=_json_list_dump(specializations),
            is_active=bool(is_active),
        )
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return _serialize_staff(row)

    async def update_staff(
        self,
        *,
        agent_id: int,
        staff_id: int,
        full_name: str | None = None,
        specializations: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminStaff).where(
                        AdminStaff.id == staff_id,
                        AdminStaff.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Staff not found")

                if full_name is not None:
                    normalized_name = _normalize_string(full_name)
                    if not normalized_name:
                        raise ValueError("full_name cannot be empty")
                    row.full_name = normalized_name
                if specializations is not None:
                    row.specializations_json = _json_list_dump(specializations)
                if is_active is not None:
                    row.is_active = bool(is_active)
                await session.flush()
                await session.refresh(row)
                return _serialize_staff(row)

    async def delete_staff(self, *, agent_id: int, staff_id: int) -> None:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminStaff).where(
                        AdminStaff.id == staff_id,
                        AdminStaff.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Staff not found")
                await session.delete(row)

    async def list_resources(
        self,
        *,
        agent_id: int,
        resource_type: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            query = select(AdminResource).where(AdminResource.agent_id == agent_id)
            if resource_type:
                query = query.where(AdminResource.resource_type == resource_type.strip().lower())
            if active_only:
                query = query.where(AdminResource.is_active.is_(True))
            rows = (await session.execute(query.order_by(AdminResource.id.asc()))).scalars().all()
            return [_serialize_resource(row) for row in rows]

    async def create_resource(
        self,
        *,
        agent_id: int,
        resource_type: str,
        title: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        normalized_type = _normalize_string(resource_type)
        normalized_title = _normalize_string(title)
        if not normalized_type or not normalized_title:
            raise ValueError("resource_type and title are required")

        row = AdminResource(
            agent_id=agent_id,
            resource_type=normalized_type.lower(),
            title=normalized_title,
            is_active=bool(is_active),
        )
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return _serialize_resource(row)

    async def update_resource(
        self,
        *,
        agent_id: int,
        resource_id: int,
        title: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminResource).where(
                        AdminResource.id == resource_id,
                        AdminResource.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Resource not found")
                if title is not None:
                    normalized_title = _normalize_string(title)
                    if not normalized_title:
                        raise ValueError("title cannot be empty")
                    row.title = normalized_title
                if is_active is not None:
                    row.is_active = bool(is_active)
                await session.flush()
                await session.refresh(row)
                return _serialize_resource(row)

    async def delete_resource(self, *, agent_id: int, resource_id: int) -> None:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminResource).where(
                        AdminResource.id == resource_id,
                        AdminResource.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Resource not found")
                await session.delete(row)

    async def list_services(
        self,
        *,
        agent_id: int,
        target_role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            query = select(AdminService).where(AdminService.agent_id == agent_id)
            if target_role:
                query = query.where(AdminService.target_role == target_role.strip().lower())
            if active_only:
                query = query.where(AdminService.is_active.is_(True))
            rows = (await session.execute(query.order_by(AdminService.id.asc()))).scalars().all()
            return [_serialize_service(row) for row in rows]

    async def create_service(
        self,
        *,
        agent_id: int,
        target_role: str,
        title: str,
        duration_minutes: int,
        price_minor: int = 0,
        resource_type_filters: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        normalized_role = _normalize_string(target_role)
        normalized_title = _normalize_string(title)
        if not normalized_role or not normalized_title:
            raise ValueError("target_role and title are required")
        if int(duration_minutes) <= 0:
            raise ValueError("duration_minutes must be positive")
        if int(price_minor) < 0:
            raise ValueError("price_minor cannot be negative")

        row = AdminService(
            agent_id=agent_id,
            target_role=normalized_role.lower(),
            title=normalized_title,
            duration_minutes=int(duration_minutes),
            price_minor=int(price_minor),
            resource_type_filters_json=_json_list_dump(resource_type_filters),
            is_active=bool(is_active),
        )
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return _serialize_service(row)

    async def update_service(
        self,
        *,
        agent_id: int,
        service_id: int,
        title: str | None = None,
        duration_minutes: int | None = None,
        price_minor: int | None = None,
        resource_type_filters: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminService).where(
                        AdminService.id == service_id,
                        AdminService.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Service not found")

                if title is not None:
                    normalized_title = _normalize_string(title)
                    if not normalized_title:
                        raise ValueError("title cannot be empty")
                    row.title = normalized_title
                if duration_minutes is not None:
                    if int(duration_minutes) <= 0:
                        raise ValueError("duration_minutes must be positive")
                    row.duration_minutes = int(duration_minutes)
                if price_minor is not None:
                    if int(price_minor) < 0:
                        raise ValueError("price_minor cannot be negative")
                    row.price_minor = int(price_minor)
                if resource_type_filters is not None:
                    row.resource_type_filters_json = _json_list_dump(resource_type_filters)
                if is_active is not None:
                    row.is_active = bool(is_active)
                await session.flush()
                await session.refresh(row)
                return _serialize_service(row)

    async def delete_service(self, *, agent_id: int, service_id: int) -> None:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminService).where(
                        AdminService.id == service_id,
                        AdminService.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Service not found")
                await session.delete(row)

    async def create_schedule_slot(
        self,
        *,
        agent_id: int,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None = None,
        resource_id: int | None = None,
        slot_kind: str = "work",
        is_active: bool = True,
    ) -> dict[str, Any]:
        _ensure_window(starts_at, ends_at)
        if staff_id is None and resource_id is None:
            raise ValueError("Either staff_id or resource_id must be provided")

        async with self._session_factory() as session:
            async with _maybe_begin(session):
                await self._validate_staff_resource_ownership(
                    session,
                    agent_id=agent_id,
                    staff_id=staff_id,
                    resource_id=resource_id,
                )
                await self._assert_no_schedule_overlap(
                    session,
                    agent_id=agent_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    staff_id=staff_id,
                    resource_id=resource_id,
                )
                row = AdminScheduleSlot(
                    agent_id=agent_id,
                    staff_id=staff_id,
                    resource_id=resource_id,
                    slot_kind=_normalize_string(slot_kind) or "work",
                    starts_at=starts_at,
                    ends_at=ends_at,
                    is_active=bool(is_active),
                )
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return _serialize_schedule_slot(row)

    async def list_available_slots(
        self,
        *,
        agent_id: int,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None = None,
        resource_id: int | None = None,
        service_id: int | None = None,
    ) -> list[dict[str, Any]]:
        _ensure_window(starts_at, ends_at)
        async with self._session_factory() as session:
            conditions = [
                AdminScheduleSlot.agent_id == agent_id,
                AdminScheduleSlot.is_active.is_(True),
                AdminScheduleSlot.starts_at < ends_at,
                AdminScheduleSlot.ends_at > starts_at,
            ]
            if staff_id is not None:
                conditions.append(AdminScheduleSlot.staff_id == staff_id)
            if resource_id is not None:
                conditions.append(AdminScheduleSlot.resource_id == resource_id)

            if service_id is not None:
                service_row = await session.scalar(
                    select(AdminService).where(
                        AdminService.id == service_id,
                        AdminService.agent_id == agent_id,
                        AdminService.is_active.is_(True),
                    )
                )
                if service_row is None:
                    raise ValueError("Service not found")
                service_resource_filters = _json_list_load(service_row.resource_type_filters_json)
                if service_resource_filters:
                    resource_rows = (
                        await session.execute(
                            select(AdminResource.id).where(
                                AdminResource.agent_id == agent_id,
                                AdminResource.resource_type.in_(service_resource_filters),
                            )
                        )
                    ).scalars().all()
                    if resource_rows:
                        conditions.append(
                            or_(
                                AdminScheduleSlot.resource_id.is_(None),
                                AdminScheduleSlot.resource_id.in_(resource_rows),
                            )
                        )
                if service_row.target_role:
                    staff_rows = (
                        await session.execute(
                            select(AdminStaff.id).where(
                                AdminStaff.agent_id == agent_id,
                                AdminStaff.role == service_row.target_role,
                                AdminStaff.is_active.is_(True),
                            )
                        )
                    ).scalars().all()
                    if staff_rows:
                        conditions.append(
                            or_(
                                AdminScheduleSlot.staff_id.is_(None),
                                AdminScheduleSlot.staff_id.in_(staff_rows),
                            )
                        )

            slots = (
                await session.execute(
                    select(AdminScheduleSlot)
                    .where(*conditions)
                    .order_by(AdminScheduleSlot.starts_at.asc())
                )
            ).scalars().all()
            available: list[dict[str, Any]] = []
            for slot in slots:
                occupied = await self._has_appointment_overlap(
                    session,
                    agent_id=agent_id,
                    starts_at=slot.starts_at,
                    ends_at=slot.ends_at,
                    staff_id=slot.staff_id if staff_id is None else staff_id,
                    resource_id=slot.resource_id if resource_id is None else resource_id,
                )
                if not occupied:
                    available.append(_serialize_schedule_slot(slot))
            return available

    async def create_appointment(
        self,
        *,
        agent_id: int,
        client_external_id: str,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None = None,
        resource_id: int | None = None,
        service_id: int | None = None,
        client_name: str | None = None,
        source_channel: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        _ensure_window(starts_at, ends_at)
        normalized_client = _normalize_string(client_external_id)
        if not normalized_client:
            raise ValueError("client_external_id is required")
        if staff_id is None and resource_id is None:
            raise ValueError("Either staff_id or resource_id must be provided")

        async with self._session_factory() as session:
            async with _maybe_begin(session):
                agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
                cfg = _json_object_load(getattr(agent, "template_config", None))
                await self._validate_staff_resource_ownership(
                    session,
                    agent_id=agent_id,
                    staff_id=staff_id,
                    resource_id=resource_id,
                )
                if service_id is not None:
                    service_row = await session.scalar(
                        select(AdminService).where(
                            AdminService.id == service_id,
                            AdminService.agent_id == agent_id,
                        )
                    )
                    if service_row is None:
                        raise ValueError("Service not found")
                else:
                    service_row = None

                manual_confirmation_enabled = bool(cfg.get("manual_confirmation_enabled"))
                manual_confirmation_duration = int(cfg.get("manual_confirmation_duration_minutes") or 120)
                manual_confirmation_price = int(cfg.get("manual_confirmation_price_minor") or 15000)
                appointment_status = "booked"
                if (
                    manual_confirmation_enabled
                    and service_row is not None
                    and (
                        int(service_row.duration_minutes or 0) >= max(1, manual_confirmation_duration)
                        or int(service_row.price_minor or 0) >= max(0, manual_confirmation_price)
                    )
                ):
                    appointment_status = "pending_confirmation"

                await self._assert_no_appointment_overlap(
                    session,
                    agent_id=agent_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    staff_id=staff_id,
                    resource_id=resource_id,
                )
                row = AdminAppointment(
                    agent_id=agent_id,
                    staff_id=staff_id,
                    resource_id=resource_id,
                    service_id=service_id,
                    client_external_id=normalized_client,
                    client_name=_normalize_string(client_name),
                    source_channel=_normalize_string(source_channel),
                    starts_at=starts_at,
                    ends_at=ends_at,
                    status=appointment_status,
                    notes=_normalize_string(notes),
                )
                session.add(row)
                await session.flush()
                await self._upsert_client_profile(
                    session,
                    agent_id=agent_id,
                    client_external_id=normalized_client,
                    client_name=_normalize_string(client_name),
                    event={
                        "event": "appointment_created",
                        "appointment_id": row.id,
                        "starts_at": row.starts_at.isoformat(),
                        "ends_at": row.ends_at.isoformat(),
                        "service_id": service_id,
                        "status": appointment_status,
                    },
                )
                await session.refresh(row)
                return _serialize_appointment(row)

    async def reschedule_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None = None,
        resource_id: int | None = None,
    ) -> dict[str, Any]:
        _ensure_window(starts_at, ends_at)
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminAppointment).where(
                        AdminAppointment.id == appointment_id,
                        AdminAppointment.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Appointment not found")
                if row.status in {"cancelled", "completed"}:
                    raise ValueError("Cannot reschedule finished appointment")

                prev_starts_at = row.starts_at
                prev_ends_at = row.ends_at
                prev_staff_id = row.staff_id
                prev_resource_id = row.resource_id
                prev_service_id = row.service_id
                next_staff_id = row.staff_id if staff_id is None else staff_id
                next_resource_id = row.resource_id if resource_id is None else resource_id
                if next_staff_id is None and next_resource_id is None:
                    raise ValueError("Either staff_id or resource_id must be provided")
                await self._validate_staff_resource_ownership(
                    session,
                    agent_id=agent_id,
                    staff_id=next_staff_id,
                    resource_id=next_resource_id,
                )
                await self._assert_no_appointment_overlap(
                    session,
                    agent_id=agent_id,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    staff_id=next_staff_id,
                    resource_id=next_resource_id,
                    exclude_appointment_id=row.id,
                )

                row.staff_id = next_staff_id
                row.resource_id = next_resource_id
                row.starts_at = starts_at
                row.ends_at = ends_at
                row.status = "pending_confirmation" if row.status == "pending_confirmation" else "booked"
                await session.flush()
                await self._try_waitlist_auto_book(
                    session,
                    agent_id=agent_id,
                    freed_starts_at=prev_starts_at,
                    freed_ends_at=prev_ends_at,
                    staff_id=prev_staff_id,
                    resource_id=prev_resource_id,
                    service_id=prev_service_id,
                )
                await session.refresh(row)
                return _serialize_appointment(row)

    async def cancel_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminAppointment).where(
                        AdminAppointment.id == appointment_id,
                        AdminAppointment.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Appointment not found")

                row.status = "cancelled"
                normalized_reason = _normalize_string(reason)
                if normalized_reason:
                    previous_notes = _normalize_string(row.notes) or ""
                    suffix = f"cancel_reason: {normalized_reason}"
                    row.notes = f"{previous_notes}\n{suffix}".strip()
                await session.flush()
                await self._try_waitlist_auto_book(
                    session,
                    agent_id=agent_id,
                    freed_starts_at=row.starts_at,
                    freed_ends_at=row.ends_at,
                    staff_id=row.staff_id,
                    resource_id=row.resource_id,
                    service_id=row.service_id,
                )
                await session.refresh(row)
                return _serialize_appointment(row)

    async def confirm_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            async with _maybe_begin(session):
                row = await session.scalar(
                    select(AdminAppointment).where(
                        AdminAppointment.id == appointment_id,
                        AdminAppointment.agent_id == agent_id,
                    )
                )
                if row is None:
                    raise ValueError("Appointment not found")
                if row.status in {"cancelled", "completed", "no_show"}:
                    raise ValueError("Cannot confirm finished appointment")
                row.status = "confirmed"
                await session.flush()
                await session.refresh(row)
                return _serialize_appointment(row)

    async def _upsert_client_profile(
        self,
        session: Any,
        *,
        agent_id: int,
        client_external_id: str,
        client_name: str | None,
        event: dict[str, Any] | None = None,
    ) -> None:
        profile = await session.scalar(
            select(AdminClientProfile).where(
                AdminClientProfile.agent_id == agent_id,
                AdminClientProfile.client_external_id == client_external_id,
            )
        )
        if profile is None:
            profile = AdminClientProfile(
                agent_id=agent_id,
                client_external_id=client_external_id,
                client_name=client_name,
                tags_json=None,
                preferences_json=None,
                history_json=None,
                last_visit_at=datetime.utcnow(),
            )
            session.add(profile)
            await session.flush()
        if client_name:
            profile.client_name = client_name
        profile.last_visit_at = datetime.utcnow()
        history = _json_list_load(profile.history_json)
        if event:
            history.append(json.dumps(event, ensure_ascii=False))
        history = history[-50:]
        profile.history_json = _json_list_dump(history)

    async def _try_waitlist_auto_book(
        self,
        session: Any,
        *,
        agent_id: int,
        freed_starts_at: datetime,
        freed_ends_at: datetime,
        staff_id: int | None,
        resource_id: int | None,
        service_id: int | None,
    ) -> None:
        if freed_ends_at <= freed_starts_at:
            return
        entries = (
            await session.execute(
                select(AdminWaitlistEntry)
                .where(
                    AdminWaitlistEntry.agent_id == agent_id,
                    AdminWaitlistEntry.status == "waiting",
                )
                .order_by(AdminWaitlistEntry.created_at.asc())
            )
        ).scalars().all()
        for entry in entries:
            if entry.desired_staff_id is not None and entry.desired_staff_id != staff_id:
                continue
            if entry.desired_resource_id is not None and entry.desired_resource_id != resource_id:
                continue
            if entry.service_id is not None and service_id is not None and entry.service_id != service_id:
                continue
            if entry.earliest_starts_at is not None and freed_starts_at < entry.earliest_starts_at:
                continue
            if entry.latest_ends_at is not None and freed_ends_at > entry.latest_ends_at:
                continue
            await self._assert_no_appointment_overlap(
                session,
                agent_id=agent_id,
                starts_at=freed_starts_at,
                ends_at=freed_ends_at,
                staff_id=staff_id,
                resource_id=resource_id,
            )
            auto_appointment = AdminAppointment(
                agent_id=agent_id,
                staff_id=staff_id,
                resource_id=resource_id,
                service_id=entry.service_id or service_id,
                client_external_id=entry.client_external_id,
                client_name=_normalize_string(entry.client_name),
                source_channel="waitlist_auto",
                starts_at=freed_starts_at,
                ends_at=freed_ends_at,
                status="booked",
                notes="created_from_waitlist_auto_match",
            )
            session.add(auto_appointment)
            await session.flush()
            entry.status = "matched"
            entry.matched_appointment_id = auto_appointment.id
            await self._upsert_client_profile(
                session,
                agent_id=agent_id,
                client_external_id=entry.client_external_id,
                client_name=_normalize_string(entry.client_name),
                event={
                    "event": "waitlist_auto_match",
                    "appointment_id": auto_appointment.id,
                    "starts_at": auto_appointment.starts_at.isoformat(),
                    "ends_at": auto_appointment.ends_at.isoformat(),
                },
            )
            break

    async def _validate_staff_resource_ownership(
        self,
        session: Any,
        *,
        agent_id: int,
        staff_id: int | None,
        resource_id: int | None,
    ) -> None:
        if staff_id is not None:
            staff_row = await session.scalar(
                select(AdminStaff).where(
                    AdminStaff.id == staff_id,
                    AdminStaff.agent_id == agent_id,
                )
            )
            if staff_row is None:
                raise ValueError("Staff not found")
        if resource_id is not None:
            resource_row = await session.scalar(
                select(AdminResource).where(
                    AdminResource.id == resource_id,
                    AdminResource.agent_id == agent_id,
                )
            )
            if resource_row is None:
                raise ValueError("Resource not found")

    async def _assert_no_schedule_overlap(
        self,
        session: Any,
        *,
        agent_id: int,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None,
        resource_id: int | None,
    ) -> None:
        if staff_id is not None:
            conflict = await session.scalar(
                select(AdminScheduleSlot.id).where(
                    AdminScheduleSlot.agent_id == agent_id,
                    AdminScheduleSlot.staff_id == staff_id,
                    AdminScheduleSlot.is_active.is_(True),
                    AdminScheduleSlot.starts_at < ends_at,
                    AdminScheduleSlot.ends_at > starts_at,
                )
            )
            if conflict:
                raise ValueError("Schedule slot overlaps with existing staff slot")
        if resource_id is not None:
            conflict = await session.scalar(
                select(AdminScheduleSlot.id).where(
                    AdminScheduleSlot.agent_id == agent_id,
                    AdminScheduleSlot.resource_id == resource_id,
                    AdminScheduleSlot.is_active.is_(True),
                    AdminScheduleSlot.starts_at < ends_at,
                    AdminScheduleSlot.ends_at > starts_at,
                )
            )
            if conflict:
                raise ValueError("Schedule slot overlaps with existing resource slot")

    async def _has_appointment_overlap(
        self,
        session: Any,
        *,
        agent_id: int,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None,
        resource_id: int | None,
    ) -> bool:
        conditions = [
            AdminAppointment.agent_id == agent_id,
            AdminAppointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            AdminAppointment.starts_at < ends_at,
            AdminAppointment.ends_at > starts_at,
        ]
        if staff_id is not None:
            conditions.append(AdminAppointment.staff_id == staff_id)
        if resource_id is not None:
            conditions.append(AdminAppointment.resource_id == resource_id)
        if staff_id is None and resource_id is None:
            return False
        conflict = await session.scalar(select(AdminAppointment.id).where(and_(*conditions)))
        return conflict is not None

    async def _assert_no_appointment_overlap(
        self,
        session: Any,
        *,
        agent_id: int,
        starts_at: datetime,
        ends_at: datetime,
        staff_id: int | None,
        resource_id: int | None,
        exclude_appointment_id: int | None = None,
    ) -> None:
        if staff_id is not None:
            conditions = [
                AdminAppointment.agent_id == agent_id,
                AdminAppointment.staff_id == staff_id,
                AdminAppointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
                AdminAppointment.starts_at < ends_at,
                AdminAppointment.ends_at > starts_at,
            ]
            if exclude_appointment_id is not None:
                conditions.append(AdminAppointment.id != exclude_appointment_id)
            staff_conflict = await session.scalar(select(AdminAppointment.id).where(and_(*conditions)))
            if staff_conflict is not None:
                raise ValueError("Appointment overlaps with another staff booking")

        if resource_id is not None:
            conditions = [
                AdminAppointment.agent_id == agent_id,
                AdminAppointment.resource_id == resource_id,
                AdminAppointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
                AdminAppointment.starts_at < ends_at,
                AdminAppointment.ends_at > starts_at,
            ]
            if exclude_appointment_id is not None:
                conditions.append(AdminAppointment.id != exclude_appointment_id)
            resource_conflict = await session.scalar(select(AdminAppointment.id).where(and_(*conditions)))
            if resource_conflict is not None:
                raise ValueError("Appointment overlaps with another resource booking")
