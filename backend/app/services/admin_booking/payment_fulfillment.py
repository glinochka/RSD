"""Подтверждение платной брони после успешной оплаты ЮKassa."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from yookassa import Payment

from ...alembic.database import async_session_maker
from ...alembic.models import AdminBookingPayment, AdminService
from .payment_service import get_admin_booking_payment_service
from .service import get_admin_booking_service
from .tool_registry import _parse_iso_datetime

logger = logging.getLogger(__name__)

BOOKING_CONFIRMED_MESSAGE = (
    "Спасибо! Оплата получена, запись подтверждена. "
    "Ждём вас {when} — {service}{staff_part}."
)


@dataclass(frozen=True)
class BookingFulfillmentResult:
    fulfilled: bool
    already_booked: bool
    agent_id: int | None = None
    client_external_id: str | None = None
    source_channel: str | None = None
    appointment: dict[str, Any] | None = None
    client_message: str | None = None
    yookassa_payment_id: str | None = None


def _format_appointment_when(starts_at_raw: str | None) -> str:
    if not starts_at_raw:
        return "в назначенное время"
    try:
        dt = _parse_iso_datetime(str(starts_at_raw))
        return f"{dt.day:02d}.{dt.month:02d}.{dt.year} в {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return str(starts_at_raw)[:16].replace("T", " ")


def _build_client_thank_you_message(
    *,
    appointment: dict[str, Any],
    booking_payload: dict[str, Any],
    service_title: str | None = None,
    staff_name: str | None = None,
) -> str:
    service = (service_title or "").strip() or "услуга"
    staff_part = f", мастер {staff_name}" if (staff_name or "").strip() else ""
    when = _format_appointment_when(
        str(appointment.get("starts_at") or booking_payload.get("starts_at") or "")
    )
    return BOOKING_CONFIRMED_MESSAGE.format(when=when, service=service, staff_part=staff_part)


async def _resolve_service_title(agent_id: int, service_id: Any) -> str | None:
    if service_id is None:
        return None
    try:
        sid = int(service_id)
    except (TypeError, ValueError):
        return None
    async with async_session_maker() as session:
        row = await session.scalar(
            select(AdminService.title).where(
                AdminService.id == sid,
                AdminService.agent_id == agent_id,
            )
        )
        return str(row).strip() if row else None


async def fulfill_admin_booking_payment(
    *,
    yookassa_payment_id: str,
    verified_status: str | None = None,
) -> BookingFulfillmentResult | None:
    """
  Находит локальный платёж бронирования и при status=succeeded создаёт запись.
  Возвращает None, если payment_id не относится к admin_booking.
    """
    payment_id = (yookassa_payment_id or "").strip()
    if not payment_id:
        return None

    payment_svc = get_admin_booking_payment_service()
    booking_svc = get_admin_booking_service()

    async with async_session_maker() as session:
        db_payment = await session.scalar(
            select(AdminBookingPayment).where(
                AdminBookingPayment.yookassa_payment_id == payment_id,
            )
        )
        if db_payment is None:
            return None

        agent_id = int(db_payment.agent_id)
        client_external_id = str(db_payment.client_external_id or "").strip()

        if db_payment.appointment_id:
            payload: dict[str, Any] = {}
            if db_payment.booking_payload_json:
                try:
                    parsed = json.loads(db_payment.booking_payload_json)
                    if isinstance(parsed, dict):
                        payload = parsed
                except Exception:
                    payload = {}
            service_title = await _resolve_service_title(agent_id, payload.get("service_id"))
            return BookingFulfillmentResult(
                fulfilled=False,
                already_booked=True,
                agent_id=agent_id,
                client_external_id=client_external_id,
                source_channel=str(payload.get("source_channel") or "telegram"),
                appointment={"id": int(db_payment.appointment_id), **payload},
                yookassa_payment_id=payment_id,
                client_message=_build_client_thank_you_message(
                    appointment=payload,
                    booking_payload=payload,
                    service_title=service_title,
                ),
            )

        status = (verified_status or "").strip().lower()
        if not status:
            status = await payment_svc.verify_yookassa_payment_succeeded(
                agent_id=agent_id,
                yookassa_payment_id=payment_id,
            )

        if status != "succeeded":
            return BookingFulfillmentResult(
                fulfilled=False,
                already_booked=False,
                agent_id=agent_id,
                client_external_id=client_external_id,
                yookassa_payment_id=payment_id,
            )

    try:
        db_payment, booking_payload = await payment_svc.get_pending_payment_context(
            agent_id=agent_id,
            yookassa_payment_id=payment_id,
            client_external_id=client_external_id,
        )
    except Exception as exc:
        logger.warning("fulfill_admin_booking_payment: %s", exc)
        return BookingFulfillmentResult(
            fulfilled=False,
            already_booked=False,
            agent_id=agent_id,
            client_external_id=client_external_id,
            yookassa_payment_id=payment_id,
        )

    if db_payment.appointment_id:
        service_title = await _resolve_service_title(agent_id, booking_payload.get("service_id"))
        return BookingFulfillmentResult(
            fulfilled=False,
            already_booked=True,
            agent_id=agent_id,
            client_external_id=client_external_id,
            source_channel=str(booking_payload.get("source_channel") or "telegram"),
            appointment={"id": int(db_payment.appointment_id), **booking_payload},
            yookassa_payment_id=payment_id,
            client_message=_build_client_thank_you_message(
                appointment=booking_payload,
                booking_payload=booking_payload,
                service_title=service_title,
            ),
        )

    def _optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    try:
        appointment = await booking_svc.create_appointment(
            agent_id=agent_id,
            client_external_id=client_external_id,
            starts_at=_parse_iso_datetime(str(booking_payload.get("starts_at") or "")),
            ends_at=_parse_iso_datetime(str(booking_payload.get("ends_at") or "")),
            staff_id=_optional_int(booking_payload.get("staff_id")),
            resource_id=_optional_int(booking_payload.get("resource_id")),
            service_id=_optional_int(booking_payload.get("service_id")),
            client_name=booking_payload.get("client_name"),
            source_channel=str(booking_payload.get("source_channel") or "telegram"),
            notes=booking_payload.get("notes"),
        )
    except Exception:
        logger.exception(
            "fulfill_admin_booking_payment: create_appointment failed payment_id=%s agent_id=%s",
            payment_id,
            agent_id,
        )
        return BookingFulfillmentResult(
            fulfilled=False,
            already_booked=False,
            agent_id=agent_id,
            client_external_id=client_external_id,
            yookassa_payment_id=payment_id,
        )

    await payment_svc.mark_payment_paid(
        payment_id=int(db_payment.id),
        appointment_id=int(appointment["id"]),
    )

    service_title = await _resolve_service_title(agent_id, booking_payload.get("service_id"))
    source_channel = str(booking_payload.get("source_channel") or "telegram")
    client_message = _build_client_thank_you_message(
        appointment=appointment,
        booking_payload=booking_payload,
        service_title=service_title,
    )

    return BookingFulfillmentResult(
        fulfilled=True,
        already_booked=False,
        agent_id=agent_id,
        client_external_id=client_external_id,
        source_channel=source_channel,
        appointment=appointment,
        yookassa_payment_id=payment_id,
        client_message=client_message,
    )


async def sync_pending_payments_for_client(
    *,
    agent_id: int,
    client_external_id: str,
) -> BookingFulfillmentResult | None:
    """Проверяет незавершённые платежи клиента (если webhook не дошёл)."""
    uid = (client_external_id or "").strip()
    if not uid:
        return None

    async with async_session_maker() as session:
        rows = (
            await session.execute(
                select(AdminBookingPayment)
                .where(
                    AdminBookingPayment.agent_id == agent_id,
                    AdminBookingPayment.client_external_id == uid,
                    AdminBookingPayment.status == "pending",
                )
                .order_by(AdminBookingPayment.created_at.desc())
                .limit(5)
            )
        ).scalars().all()

    last_new: BookingFulfillmentResult | None = None
    for row in rows:
        result = await fulfill_admin_booking_payment(
            yookassa_payment_id=str(row.yookassa_payment_id),
        )
        if result is None:
            continue
        if result.fulfilled:
            last_new = result
        elif result.already_booked and result.client_message:
            last_new = result

    return last_new


async def process_admin_booking_yookassa_webhook(
    *,
    yookassa_payment_id: str,
    verified_status: str,
) -> BookingFulfillmentResult | None:
    """Обработка webhook ЮKassa для платежей бронирования (отдельный магазин агента)."""
    if verified_status != "succeeded":
        return await fulfill_admin_booking_payment(
            yookassa_payment_id=yookassa_payment_id,
            verified_status=verified_status,
        )
    result = await fulfill_admin_booking_payment(
        yookassa_payment_id=yookassa_payment_id,
        verified_status=verified_status,
    )
    if result is None:
        return None
    if result.fulfilled and result.client_message:
        from .client_notify import notify_booking_payment_confirmed

        try:
            await notify_booking_payment_confirmed(result)
        except Exception:
            logger.exception(
                "Failed to notify client after booking payment %s",
                yookassa_payment_id,
            )
    return result
