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
