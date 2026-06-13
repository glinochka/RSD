from datetime import datetime, timedelta

import pytest
from yookassa.domain.exceptions import ApiError

from app.services.admin_booking.tool_registry import AdminBookingToolRegistry


@pytest.mark.asyncio
async def test_admin_booking_tool_registry_idempotency_replay(monkeypatch):
    from app.services.admin_booking.tool_registry import _IDEMPOTENCY_CACHE

    _IDEMPOTENCY_CACHE.clear()
    calls = {"create_appointment": 0}
    future_day = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    class _FakeService:
        async def create_appointment(self, **kwargs):
            calls["create_appointment"] += 1
            return {"id": 101, "status": "booked", **kwargs}

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        confirmation_policy="confirm_risky",
        user_message="создай запись",
        allowed_tools=["create_appointment"],
    )
    raw_args = (
        f'{{"starts_at":"{future_day}T10:00:00","ends_at":"{future_day}T11:00:00","staff_id":1}}'
    )

    first = await registry.execute_tool("create_appointment", raw_args)
    second = await registry.execute_tool("create_appointment", raw_args)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["idempotent_replay"] is True
    assert first["idempotency_key"] == second["idempotency_key"]
    assert calls["create_appointment"] == 1


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

    future_day = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    result = await registry.execute_tool(
        "create_appointment",
        f'{{"starts_at":"{future_day}T10:00:00","ends_at":"{future_day}T11:00:00","staff_id":1}}',
    )
    assert result["ok"] is True
    assert result["tool_status"] == "success"


@pytest.mark.asyncio
async def test_admin_booking_tool_registry_supports_list_and_cancel_tools(monkeypatch):
    class _FakeService:
        async def list_appointments(self, **kwargs):
            return [{"id": 77, "status": "booked", "client_external_id": kwargs.get("client_external_id")}]

        async def cancel_appointment(self, **kwargs):
            return {
                "deleted": True,
                "appointment": {"id": kwargs["appointment_id"]},
                "refund_request": None,
            }

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        user_message="отмени и покажи запись клиента",
        allowed_tools=["list_appointments", "cancel_appointment"],
    )

    list_result = await registry.execute_tool(
        "list_appointments",
        '{"client_external_id":"client-1","status":"booked"}',
    )
    cancel_result = await registry.execute_tool(
        "cancel_appointment",
        '{"appointment_id":77}',
    )

    assert list_result["ok"] is True
    assert list_result["result"][0]["id"] == 77
    assert cancel_result["ok"] is True
    assert cancel_result["result"]["deleted"] is True


@pytest.mark.asyncio
async def test_admin_booking_tool_registry_find_next_available_tool(monkeypatch):
    from datetime import datetime
    
    future_day = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    slot_day = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    class _FakeService:
        async def list_staff(self, **kwargs):
            return [{"id": 1, "name": "Alex", "is_active": True}]

        async def find_next_available_slot(self, **kwargs):
            return {
                "available": True,
                "starts_at": f"{slot_day}T09:00:00",
                "ends_at": f"{slot_day}T09:30:00",
                "staff_id": 1,
                "duration_minutes": 30,
            }

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        confirmation_policy="never_confirm",
        user_message="найди свободное время",
        allowed_tools=["find_next_available"],
    )

    result = await registry.execute_tool(
        "find_next_available",
        f'{{"duration_minutes":30,"staff_id":1,"earliest_starts_at":"{future_day}T08:00:00"}}',
    )
    assert result["ok"] is True
    assert result["tool_status"] == "success"
    assert result["result"]["available"] is True
    assert f"{slot_day}T09:00:00" in result["result"]["starts_at"]


@pytest.mark.asyncio
async def test_check_availability_past_date_returns_hint_not_busy(monkeypatch):
    past_day = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    class _FakeService:
        async def list_staff(self, **kwargs):
            return [{"id": 23, "full_name": "Anna"}]

        async def list_available_slots(self, **kwargs):
            raise AssertionError("list_available_slots must not run for a past day")

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        user_message="запиши на прошлый день",
        allowed_tools=["check_availability"],
    )
    result = await registry.execute_tool(
        "check_availability",
        f'{{"starts_at":"{past_day}T00:00:00","ends_at":"{past_day}T23:59:59","staff_id":23}}',
    )

    assert result["ok"] is True
    assert result["result"]["date_status"] == "past"
    assert result["result"]["available_slots"] == []
    assert "прошёл" in result["result"]["hint"].lower()


@pytest.mark.asyncio
async def test_create_appointment_rejects_staff_id_as_service_id(monkeypatch):
    future_day = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    class _FakeService:
        async def list_services(self, **kwargs):
            return [
                {"id": 5, "title": "Рукав", "staff_id": 23, "duration_minutes": 30, "price_minor": 5000000},
            ]

        async def list_staff(self, **kwargs):
            return [{"id": 23, "full_name": "Анна"}]

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        user_message="запиши",
        paid_booking_enabled=True,
        yookassa_api_key="123456:live_test_secret_key",
        allowed_tools=["create_appointment"],
    )

    with pytest.raises(RuntimeError, match="service_id совпадает с staff_id"):
        await registry.execute_tool(
            "create_appointment",
            f'{{"starts_at":"{future_day}T13:00:00","ends_at":"{future_day}T13:30:00",'
            f'"staff_id":23,"service_id":23,"client_name":"Пётр"}}',
        )


@pytest.mark.asyncio
async def test_create_appointment_yookassa_invalid_credentials_message(monkeypatch):
    future_day = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    class _FakeService:
        async def list_services(self, **kwargs):
            return [
                {"id": 5, "title": "Рукав", "staff_id": 23, "duration_minutes": 30, "price_minor": 5000000},
            ]

        async def list_staff(self, **kwargs):
            return [{"id": 23, "full_name": "Анна"}]

    class _FakePayment:
        @staticmethod
        def create(*args, **kwargs):
            raise ApiError(
                {
                    "type": "error",
                    "code": "invalid_credentials",
                    "description": "Incorrect password format",
                }
            )

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )
    monkeypatch.setattr("app.services.admin_booking.tool_registry.Payment", _FakePayment)
    class _FakePaySvc:
        async def find_by_idempotency_key(self, *args, **kwargs):
            return None

        async def save_pending_payment(self, *args, **kwargs):
            return None

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_payment_service",
        lambda: _FakePaySvc(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        user_message="запиши",
        paid_booking_enabled=True,
        yookassa_api_key="123456:live_test_secret_key",
        allowed_tools=["create_appointment"],
    )

    with pytest.raises(RuntimeError, match="Ошибка авторизации ЮKassa"):
        await registry.execute_tool(
            "create_appointment",
            f'{{"starts_at":"{future_day}T13:00:00","ends_at":"{future_day}T13:30:00",'
            f'"staff_id":23,"service_id":5,"client_name":"Пётр"}}',
        )


@pytest.mark.asyncio
async def test_list_services_strips_price_minor_from_llm_payload(monkeypatch):
    class _FakeService:
        async def list_services(self, **kwargs):
            return [
                {
                    "id": 20,
                    "title": "Рукав",
                    "price_minor": 10000,
                    "price_rub": 100.0,
                    "duration_minutes": 30,
                }
            ]

    monkeypatch.setattr(
        "app.services.admin_booking.tool_registry.get_admin_booking_service",
        lambda: _FakeService(),
    )

    registry = AdminBookingToolRegistry(
        agent_id=17,
        user_external_id="u-5",
        source_channel="telegram",
        user_message="сколько стоит рукав",
        allowed_tools=["list_services"],
    )
    payload = await registry.execute_tool("list_services", '{"active_only":true}')

    assert payload["ok"] is True
    item = payload["result"][0]
    assert item["price_rub"] == 100.0
    assert "price_minor" not in item
