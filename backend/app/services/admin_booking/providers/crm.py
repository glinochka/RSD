"""CRM-aware booking provider.

Source of truth for booking data remains local DB tables, while this provider
adds best-effort CRM side effects for appointment lifecycle events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ...crm.providers.base import CRMProvider
from .base import BookingProvider
from .local import LocalBookingProvider


class CrmBookingProvider(BookingProvider):
    provider_name = "crm"

    def __init__(self, *, local_provider: LocalBookingProvider, crm_provider: CRMProvider):
        self._local = local_provider
        self._crm = crm_provider

    async def list_staff(
        self,
        *,
        agent_id: int,
        role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        return await self._local.list_staff(agent_id=agent_id, role=role, active_only=active_only)

    async def create_staff(
        self,
        *,
        agent_id: int,
        role: str,
        full_name: str,
        specializations: list[str] | None = None,
        is_active: bool = True,
        auto_create_resource: bool = False,
        resource_type: str = "workplace",
    ) -> dict[str, Any]:
        return await self._local.create_staff(
            agent_id=agent_id,
            role=role,
            full_name=full_name,
            specializations=specializations,
            is_active=is_active,
            auto_create_resource=auto_create_resource,
            resource_type=resource_type,
        )

    async def update_staff(
        self,
        *,
        agent_id: int,
        staff_id: int,
        full_name: str | None = None,
        specializations: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        return await self._local.update_staff(
            agent_id=agent_id,
            staff_id=staff_id,
            full_name=full_name,
            specializations=specializations,
            is_active=is_active,
        )

    async def delete_staff(self, *, agent_id: int, staff_id: int) -> None:
        await self._local.delete_staff(agent_id=agent_id, staff_id=staff_id)

    async def list_resources(
        self,
        *,
        agent_id: int,
        resource_type: str | None = None,
        active_only: bool = True,
        exclude_linked: bool = False,
    ) -> list[dict[str, Any]]:
        return await self._local.list_resources(
            agent_id=agent_id,
            resource_type=resource_type,
            active_only=active_only,
            exclude_linked=exclude_linked,
        )

    async def create_resource(
        self,
        *,
        agent_id: int,
        resource_type: str,
        title: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        return await self._local.create_resource(
            agent_id=agent_id,
            resource_type=resource_type,
            title=title,
            is_active=is_active,
        )

    async def update_resource(
        self,
        *,
        agent_id: int,
        resource_id: int,
        title: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        return await self._local.update_resource(
            agent_id=agent_id,
            resource_id=resource_id,
            title=title,
            is_active=is_active,
        )

    async def delete_resource(self, *, agent_id: int, resource_id: int) -> None:
        await self._local.delete_resource(agent_id=agent_id, resource_id=resource_id)

    async def list_services(
        self,
        *,
        agent_id: int,
        target_role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        return await self._local.list_services(
            agent_id=agent_id,
            target_role=target_role,
            active_only=active_only,
        )

    async def create_service(
        self,
        *,
        agent_id: int,
        target_role: str,
        staff_id: int | None = None,
        title: str,
        duration_minutes: int,
        price_minor: int = 0,
        resource_type_filters: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        return await self._local.create_service(
            agent_id=agent_id,
            target_role=target_role,
            staff_id=staff_id,
            title=title,
            duration_minutes=duration_minutes,
            price_minor=price_minor,
            resource_type_filters=resource_type_filters,
            is_active=is_active,
        )

    async def update_service(
        self,
        *,
        agent_id: int,
        service_id: int,
        staff_id: int | None = None,
        title: str | None = None,
        duration_minutes: int | None = None,
        price_minor: int | None = None,
        resource_type_filters: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        return await self._local.update_service(
            agent_id=agent_id,
            service_id=service_id,
            staff_id=staff_id,
            title=title,
            duration_minutes=duration_minutes,
            price_minor=price_minor,
            resource_type_filters=resource_type_filters,
            is_active=is_active,
        )

    async def delete_service(self, *, agent_id: int, service_id: int) -> None:
        await self._local.delete_service(agent_id=agent_id, service_id=service_id)

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
        return await self._local.create_schedule_slot(
            agent_id=agent_id,
            starts_at=starts_at,
            ends_at=ends_at,
            staff_id=staff_id,
            resource_id=resource_id,
            slot_kind=slot_kind,
            is_active=is_active,
        )

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
        return await self._local.list_available_slots(
            agent_id=agent_id,
            starts_at=starts_at,
            ends_at=ends_at,
            staff_id=staff_id,
            resource_id=resource_id,
            service_id=service_id,
        )

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
        appointment = await self._local.create_appointment(
            agent_id=agent_id,
            client_external_id=client_external_id,
            starts_at=starts_at,
            ends_at=ends_at,
            staff_id=staff_id,
            resource_id=resource_id,
            service_id=service_id,
            client_name=client_name,
            source_channel=source_channel,
            notes=notes,
        )
        await self._sync_crm_event(event="created", appointment=appointment)
        return appointment

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
        appointment = await self._local.reschedule_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
            starts_at=starts_at,
            ends_at=ends_at,
            staff_id=staff_id,
            resource_id=resource_id,
        )
        await self._sync_crm_event(event="rescheduled", appointment=appointment)
        return appointment

    async def cancel_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        del reason
        appointment = await self._local.delete_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
        )
        await self._sync_crm_event(event="deleted", appointment=appointment)
        return appointment

    async def confirm_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
    ) -> dict[str, Any]:
        appointment = await self._local.confirm_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
        )
        await self._sync_crm_event(event="confirmed", appointment=appointment)
        return appointment

    async def find_next_available_slot(
        self,
        *,
        agent_id: int,
        duration_minutes: int = 30,
        staff_id: int | None = None,
        resource_id: int | None = None,
        service_id: int | None = None,
        earliest_starts_at: datetime,
        search_days_ahead: int = 7,
    ) -> dict[str, Any]:
        return await self._local.find_next_available_slot(
            agent_id=agent_id,
            duration_minutes=duration_minutes,
            staff_id=staff_id,
            resource_id=resource_id,
            service_id=service_id,
            earliest_starts_at=earliest_starts_at,
            search_days_ahead=search_days_ahead,
        )

    async def delete_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
    ) -> dict[str, Any]:
        appointment = await self._local.delete_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
        )
        await self._sync_crm_event(event="deleted", appointment=appointment)
        return appointment

    async def _sync_crm_event(self, *, event: str, appointment: dict[str, Any]) -> None:
        title = f"Booking {event}: client={appointment.get('client_name') or appointment.get('client_external_id')}"
        try:
            await self._crm.create_lead(name=title[:120], price=None)
        except Exception:
            # CRM mirroring is optional and must not break the local booking flow.
            return
