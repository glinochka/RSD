import json
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.alembic.models import Agent, AgentCrmConnection, User
from app.services.admin_booking.service import AdminBookingService


class _FakeCRMProvider:
    provider_name = "amocrm"

    async def validate_connection(self):
        return None

    async def find_contact(self, *, query: str):
        return {}

    async def create_contact(self, *, name: str, phone: str | None = None, email: str | None = None):
        return {}

    async def find_lead(self, *, query: str):
        return {}

    async def create_lead(self, *, name: str, price: int | None = None):
        return {"id": 1}

    async def update_lead(self, *, lead_id: int, fields: dict):
        return {}

    async def add_note(self, *, entity_type: str, entity_id: int, text: str):
        return {}

    async def create_task(
        self,
        *,
        text: str,
        complete_till_unix: int,
        entity_type: str,
        entity_id: int,
        responsible_user_id: int | None = None,
    ):
        return {}

    async def assign_owner(self, *, entity_type: str, entity_id: int, responsible_user_id: int):
        return {}


@pytest_asyncio.fixture()
async def booking_session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _create_user_and_agent(
    session_factory,
    *,
    template_type: str = "crm_admin",
    template_config: dict | None = None,
) -> Agent:
    async with session_factory() as session:
        async with session.begin():
            user = User(
                name="booking_user",
                password="pwd",
                telegram_id=int(datetime.utcnow().timestamp()),
                subscription_type="Free",
            )
            session.add(user)
            await session.flush()

            agent = Agent(
                user_id=user.id,
                bot_username="booking_agent",
                encrypted_token=f"enc_{datetime.utcnow().timestamp()}",
                bot_id=int(datetime.utcnow().timestamp() * 10),
                template_type=template_type,
                template_config=json.dumps(template_config or {}, ensure_ascii=False),
                system_prompt="test",
                is_active=True,
            )
            session.add(agent)
            await session.flush()
            await session.refresh(agent)
            return agent


async def _create_crm_connection(session_factory, *, agent_id: int, provider: str = "amocrm") -> None:
    async with session_factory() as session:
        async with session.begin():
            session.add(
                AgentCrmConnection(
                    agent_id=agent_id,
                    provider=provider,
                    external_id=f"ext_{agent_id}",
                    encrypted_credentials="crmv1:mock",
                    is_active=True,
                )
            )


@pytest.mark.asyncio
async def test_resolve_provider_fallbacks_to_local_without_crm(booking_session_factory):
    agent = await _create_user_and_agent(
        booking_session_factory,
        template_config={
            "crm_mode": "optional",
            "booking_backend": "crm",
            "crm_provider": "amocrm",
        },
    )
    service = AdminBookingService(session_factory=booking_session_factory)
    resolution = await service.resolve_provider(agent_id=agent.id)
    assert resolution.provider_name == "local"
    assert resolution.crm_connected is False


@pytest.mark.asyncio
async def test_resolve_provider_uses_crm_when_connected(booking_session_factory, monkeypatch):
    agent = await _create_user_and_agent(
        booking_session_factory,
        template_config={
            "crm_mode": "optional",
            "booking_backend": "auto",
            "crm_provider": "amocrm",
        },
    )
    await _create_crm_connection(booking_session_factory, agent_id=agent.id)
    monkeypatch.setattr(
        "app.services.admin_booking.service.decrypt_crm_credentials",
        lambda _: (json.dumps({"base_url": "https://example.crm", "access_token": "token"}), False),
    )
    monkeypatch.setattr(
        "app.services.admin_booking.service.build_provider",
        lambda *_args, **_kwargs: _FakeCRMProvider(),
    )

    service = AdminBookingService(session_factory=booking_session_factory)
    resolution = await service.resolve_provider(agent_id=agent.id)
    assert resolution.provider_name == "crm"
    assert resolution.crm_connected is True


@pytest.mark.asyncio
async def test_resolve_provider_requires_crm_connection(booking_session_factory):
    agent = await _create_user_and_agent(
        booking_session_factory,
        template_config={
            "crm_mode": "required",
            "booking_backend": "auto",
            "crm_provider": "amocrm",
        },
    )
    service = AdminBookingService(session_factory=booking_session_factory)
    with pytest.raises(RuntimeError, match="CRM connection is required"):
        await service.resolve_provider(agent_id=agent.id)


@pytest.mark.asyncio
async def test_local_booking_lifecycle_create_reschedule_cancel(booking_session_factory):
    agent = await _create_user_and_agent(
        booking_session_factory,
        template_config={
            "crm_mode": "disabled",
            "booking_backend": "local",
            "domain_type": "beauty_salon",
        },
    )
    service = AdminBookingService(session_factory=booking_session_factory)
    now = datetime.utcnow().replace(microsecond=0)
    later = now + timedelta(hours=1)
    later2 = now + timedelta(hours=2)

    staff = await service.create_staff(
        agent_id=agent.id,
        role="master",
        full_name="Anna Master",
        specializations=["haircut", "coloring"],
    )
    resource = await service.create_resource(agent_id=agent.id, resource_type="chair", title="Chair 1")
    svc = await service.create_service(
        agent_id=agent.id,
        target_role="master",
        title="Haircut",
        duration_minutes=60,
        resource_type_filters=["chair"],
    )
    await service.create_schedule_slot(
        agent_id=agent.id,
        staff_id=staff["id"],
        resource_id=resource["id"],
        starts_at=now,
        ends_at=later,
    )
    available_before = await service.list_available_slots(
        agent_id=agent.id,
        starts_at=now,
        ends_at=later2,
        service_id=svc["id"],
    )
    assert len(available_before) == 1

    appointment = await service.create_appointment(
        agent_id=agent.id,
        client_external_id="client-1",
        client_name="Client One",
        staff_id=staff["id"],
        resource_id=resource["id"],
        service_id=svc["id"],
        starts_at=now,
        ends_at=later,
    )
    appointments = await service.list_appointments(
        agent_id=agent.id,
        client_external_id="client-1",
        status="booked",
    )
    assert len(appointments) == 1
    assert appointments[0]["id"] == appointment["id"]

    with pytest.raises(ValueError, match="overlaps"):
        await service.create_appointment(
            agent_id=agent.id,
            client_external_id="client-2",
            staff_id=staff["id"],
            resource_id=resource["id"],
            service_id=svc["id"],
            starts_at=now + timedelta(minutes=15),
            ends_at=later,
        )

    rescheduled = await service.reschedule_appointment(
        agent_id=agent.id,
        appointment_id=appointment["id"],
        starts_at=later,
        ends_at=later2,
    )
    assert rescheduled["starts_at"] == later.isoformat()
    confirmed = await service.confirm_appointment(
        agent_id=agent.id,
        appointment_id=appointment["id"],
    )
    assert confirmed["status"] == "confirmed"

    cancelled = await service.cancel_appointment(
        agent_id=agent.id,
        appointment_id=appointment["id"],
        reason="client requested",
    )
    cancelled_appt = cancelled["appointment"]
    assert cancelled_appt["status"] == "cancelled"
    assert "cancel_reason" in str(cancelled_appt.get("notes") or "")
