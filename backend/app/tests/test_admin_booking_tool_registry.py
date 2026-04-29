import pytest

from app.services.admin_booking.tool_registry import AdminBookingToolRegistry


@pytest.mark.asyncio
async def test_admin_booking_tool_registry_idempotency_replay(monkeypatch):
    calls = {"list_staff": 0}

    class _FakeService:
        async def list_staff(self, *, agent_id, role, active_only):
            calls["list_staff"] += 1
            return [{"id": 1, "name": "Alex", "role": role or "master", "is_active": active_only}]

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        confirmation_policy="confirm_risky",
        user_message="покажи сотрудников",
        allowed_tools=["list_staff"],
    )
    raw_args = '{"role":"master","active_only":true}'

    first = await registry.execute_tool("list_staff", raw_args)
    second = await registry.execute_tool("list_staff", raw_args)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["idempotent_replay"] is True
    assert first["idempotency_key"] == second["idempotency_key"]
    assert calls["list_staff"] == 1


@pytest.mark.asyncio
async def test_admin_booking_tool_registry_does_not_require_confirmation(monkeypatch):
    class _FakeService:
        async def create_appointment(self, **kwargs):
            return {"id": 101, "status": "booked"}

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        confirmation_policy="always_confirm",
        user_message="создай запись",
        allowed_tools=["create_appointment"],
    )

    result = await registry.execute_tool(
        "create_appointment",
        '{"starts_at":"2026-04-27T10:00:00","ends_at":"2026-04-27T11:00:00","staff_id":1}',
    )
    assert result["ok"] is True
    assert result["tool_status"] == "success"


@pytest.mark.asyncio
async def test_admin_booking_tool_registry_supports_list_and_confirm_tools(monkeypatch):
    class _FakeService:
        async def list_appointments(self, **kwargs):
            return [{"id": 77, "status": "booked", "client_external_id": kwargs.get("client_external_id")}]

        async def confirm_appointment(self, **kwargs):
            return {"id": kwargs["appointment_id"], "status": "confirmed"}

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        confirmation_policy="confirm_risky",
        user_message="подтверди и покажи запись клиента",
        allowed_tools=["list_appointments", "confirm_appointment"],
    )

    list_result = await registry.execute_tool(
        "list_appointments",
        '{"client_external_id":"client-1","status":"booked"}',
    )
    confirm_result = await registry.execute_tool(
        "confirm_appointment",
        '{"appointment_id":77}',
    )

    assert list_result["ok"] is True
    assert list_result["result"][0]["id"] == 77
    assert confirm_result["ok"] is True
    assert confirm_result["result"]["status"] == "confirmed"
