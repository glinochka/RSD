"""Booking provider abstraction for admin template runtime."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BookingProvider(ABC):
    provider_name: str

    @abstractmethod
    async def list_staff(
        self,
        *,
        agent_id: int,
        role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def create_staff(
        self,
        *,
        agent_id: int,
        role: str,
        full_name: str,
        specializations: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def update_staff(
        self,
        *,
        agent_id: int,
        staff_id: int,
        full_name: str | None = None,
        specializations: list[str] | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def delete_staff(self, *, agent_id: int, staff_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_resources(
        self,
        *,
        agent_id: int,
        resource_type: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def create_resource(
        self,
        *,
        agent_id: int,
        resource_type: str,
        title: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def update_resource(
        self,
        *,
        agent_id: int,
        resource_id: int,
        title: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def delete_resource(self, *, agent_id: int, resource_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_services(
        self,
        *,
        agent_id: int,
        target_role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    async def delete_service(self, *, agent_id: int, service_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    async def cancel_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def confirm_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
    ) -> dict[str, Any]:
        raise NotImplementedError
