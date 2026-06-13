import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.admin_booking.payment_fulfillment import (
    _build_client_thank_you_message,
    fulfill_admin_booking_payment,
)


def test_build_client_thank_you_message():
    msg = _build_client_thank_you_message(
        appointment={"starts_at": "2026-06-04T13:00:00"},
        booking_payload={"starts_at": "2026-06-04T13:00:00"},
        service_title="Рукав",
    )
    assert "Спасибо" in msg
    assert "Рукав" in msg
    assert "04.06.2026" in msg


@pytest.mark.asyncio
async def test_fulfill_creates_appointment_when_paid(monkeypatch):
    payment_row = MagicMock()
    payment_row.id = 1
    payment_row.agent_id = 17
    payment_row.client_external_id = "12345"
    payment_row.appointment_id = None
    payment_row.yookassa_payment_id = "pay-abc"
    payment_row.booking_payload_json = json.dumps(
        {
            "starts_at": "2026-06-04T13:00:00",
            "ends_at": "2026-06-04T13:30:00",
            "staff_id": 23,
            "service_id": 20,
            "client_name": "Пётр",
            "source_channel": "telegram",
        },
        ensure_ascii=False,
    )

    class _SessionCtx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def scalar(self, query):
            return payment_row

    monkeypatch.setattr(
        "app.services.admin_booking.payment_fulfillment.async_session_maker",
        lambda: _SessionCtx(),
    )

    payment_svc = MagicMock()

    async def _get_context(**kwargs):
        return payment_row, json.loads(payment_row.booking_payload_json)

    async def _mark_paid(**kwargs):
        payment_row.appointment_id = 99

    payment_svc.get_pending_payment_context = _get_context
    payment_svc.mark_payment_paid = _mark_paid
    payment_svc.verify_yookassa_payment_succeeded = AsyncMock(return_value="succeeded")

    booking_svc = MagicMock()
    booking_svc.create_appointment = AsyncMock(
        return_value={
            "id": 99,
            "starts_at": "2026-06-04T13:00:00",
            "ends_at": "2026-06-04T13:30:00",
        }
    )

    async def _service_title(agent_id, service_id):
        return "Рукав"

    monkeypatch.setattr(
        "app.services.admin_booking.payment_fulfillment.get_admin_booking_payment_service",
        lambda: payment_svc,
    )
    monkeypatch.setattr(
        "app.services.admin_booking.payment_fulfillment.get_admin_booking_service",
        lambda: booking_svc,
    )
    monkeypatch.setattr(
        "app.services.admin_booking.payment_fulfillment._resolve_service_title",
        _service_title,
    )

    result = await fulfill_admin_booking_payment(
        yookassa_payment_id="pay-abc",
        verified_status="succeeded",
    )

    assert result is not None
    assert result.fulfilled is True
    assert result.appointment["id"] == 99
    assert "Спасибо" in (result.client_message or "")
    booking_svc.create_appointment.assert_awaited_once()
