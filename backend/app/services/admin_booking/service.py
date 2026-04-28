"""Unified booking domain service for crm_admin template."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AgentCrmConnection
from ...utils.crypto import decrypt_crm_credentials
from ..crm import build_provider
from .providers import BookingProvider, CrmBookingProvider, LocalBookingProvider

CRM_MODES = {"disabled", "optional", "required"}
BOOKING_BACKENDS = {"local", "crm", "auto"}


def _parse_template_config(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


@dataclass
class BookingProviderResolution:
    provider_name: str
    provider: BookingProvider
    crm_connected: bool


class AdminBookingService:
    """Domain service that routes booking operations to the selected provider."""

    def __init__(self, session_factory: Callable[[], Any] | async_sessionmaker = async_session_maker):
        self._session_factory = session_factory
        self._local_provider = LocalBookingProvider(session_factory=session_factory)

    async def resolve_provider(self, *, agent_id: int) -> BookingProviderResolution:
        async with self._session_factory() as session:
            agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
            if agent is None:
                raise ValueError("Agent not found")
            template_type = str(agent.template_type or "").strip().lower()
            if template_type != "crm_admin":
                return BookingProviderResolution(
                    provider_name="local",
                    provider=self._local_provider,
                    crm_connected=False,
                )

            cfg = _parse_template_config(agent.template_config)
            crm_mode = str(cfg.get("crm_mode") or "optional").strip().lower()
            booking_backend = str(cfg.get("booking_backend") or "auto").strip().lower()
            crm_provider_name = str(cfg.get("crm_provider") or "amocrm").strip().lower()

            if crm_mode not in CRM_MODES:
                crm_mode = "optional"
            if booking_backend not in BOOKING_BACKENDS:
                booking_backend = "auto"

            crm_connection = await session.scalar(
                select(AgentCrmConnection).where(
                    AgentCrmConnection.agent_id == agent_id,
                    AgentCrmConnection.provider == crm_provider_name,
                    AgentCrmConnection.is_active.is_(True),
                )
            )
            crm_provider = await self._build_crm_provider(connection=crm_connection)
            has_crm = crm_provider is not None

            if crm_mode == "disabled":
                return BookingProviderResolution(
                    provider_name="local",
                    provider=self._local_provider,
                    crm_connected=False,
                )

            if crm_mode == "required" and not has_crm:
                raise RuntimeError("CRM connection is required for this administrator template")

            if booking_backend == "local":
                return BookingProviderResolution(
                    provider_name="local",
                    provider=self._local_provider,
                    crm_connected=has_crm,
                )
            if booking_backend == "crm":
                if has_crm and crm_provider is not None:
                    return BookingProviderResolution(
                        provider_name="crm",
                        provider=CrmBookingProvider(local_provider=self._local_provider, crm_provider=crm_provider),
                        crm_connected=True,
                    )
                if crm_mode == "required":
                    raise RuntimeError("CRM booking backend is required but no active CRM connection found")
                return BookingProviderResolution(
                    provider_name="local",
                    provider=self._local_provider,
                    crm_connected=False,
                )

            # booking_backend = auto
            if has_crm and crm_provider is not None:
                return BookingProviderResolution(
                    provider_name="crm",
                    provider=CrmBookingProvider(local_provider=self._local_provider, crm_provider=crm_provider),
                    crm_connected=True,
                )
            return BookingProviderResolution(
                provider_name="local",
                provider=self._local_provider,
                crm_connected=False,
            )

    async def list_staff(
        self,
        *,
        agent_id: int,
        role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.list_staff(agent_id=agent_id, role=role, active_only=active_only)

    async def create_staff(
        self,
        *,
        agent_id: int,
        role: str,
        full_name: str,
        specializations: list[str] | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.create_staff(
            agent_id=agent_id,
            role=role,
            full_name=full_name,
            specializations=specializations,
            is_active=is_active,
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.update_staff(
            agent_id=agent_id,
            staff_id=staff_id,
            full_name=full_name,
            specializations=specializations,
            is_active=is_active,
        )

    async def delete_staff(self, *, agent_id: int, staff_id: int) -> None:
        resolution = await self.resolve_provider(agent_id=agent_id)
        await resolution.provider.delete_staff(agent_id=agent_id, staff_id=staff_id)

    async def list_resources(
        self,
        *,
        agent_id: int,
        resource_type: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.list_resources(
            agent_id=agent_id,
            resource_type=resource_type,
            active_only=active_only,
        )

    async def create_resource(
        self,
        *,
        agent_id: int,
        resource_type: str,
        title: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.create_resource(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.update_resource(
            agent_id=agent_id,
            resource_id=resource_id,
            title=title,
            is_active=is_active,
        )

    async def delete_resource(self, *, agent_id: int, resource_id: int) -> None:
        resolution = await self.resolve_provider(agent_id=agent_id)
        await resolution.provider.delete_resource(agent_id=agent_id, resource_id=resource_id)

    async def list_services(
        self,
        *,
        agent_id: int,
        target_role: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.list_services(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.create_service(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.update_service(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        await resolution.provider.delete_service(agent_id=agent_id, service_id=service_id)

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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.create_schedule_slot(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.list_available_slots(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.create_appointment(
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
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.reschedule_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
            starts_at=starts_at,
            ends_at=ends_at,
            staff_id=staff_id,
            resource_id=resource_id,
        )

    async def cancel_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.cancel_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
            reason=reason,
        )

    async def confirm_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
    ) -> dict[str, Any]:
        resolution = await self.resolve_provider(agent_id=agent_id)
        return await resolution.provider.confirm_appointment(
            agent_id=agent_id,
            appointment_id=appointment_id,
        )

    async def _build_crm_provider(self, *, connection: AgentCrmConnection | None):
        if connection is None or not connection.encrypted_credentials:
            return None
        try:
            decrypted_payload, _ = decrypt_crm_credentials(connection.encrypted_credentials)
            payload = json.loads(decrypted_payload)
            if not isinstance(payload, dict):
                return None
            base_url = str(payload.get("base_url") or "").strip()
            access_token = str(payload.get("access_token") or "").strip()
            if not base_url or not access_token:
                return None
            return build_provider(connection.provider, base_url=base_url, access_token=access_token)
        except Exception:
            return None


_admin_booking_service: AdminBookingService | None = None


def get_admin_booking_service() -> AdminBookingService:
    global _admin_booking_service
    if _admin_booking_service is None:
        _admin_booking_service = AdminBookingService()
    return _admin_booking_service
