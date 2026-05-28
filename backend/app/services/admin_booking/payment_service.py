"""Paid booking payments and manual full-refund workflow."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from yookassa import Configuration, Payment, Refund

from ...alembic.database import async_session_maker
from ...alembic.models import AdminBookingPayment, AdminBookingRefundRequest, Agent
from ...utils.crypto import decrypt_booking_payment_secret

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize_payment(row: AdminBookingPayment) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "appointment_id": row.appointment_id,
        "client_external_id": row.client_external_id,
        "yookassa_payment_id": row.yookassa_payment_id,
        "amount_minor": row.amount_minor,
        "amount_rub": round(int(row.amount_minor) / 100, 2),
        "currency": row.currency,
        "status": row.status,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _serialize_refund_request(row: AdminBookingRefundRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "payment_id": row.payment_id,
        "appointment_id": row.appointment_id,
        "client_external_id": row.client_external_id,
        "amount_minor": row.amount_minor,
        "amount_rub": round(int(row.amount_minor) / 100, 2),
        "currency": row.currency,
        "cancel_reason": row.cancel_reason,
        "status": row.status,
        "yookassa_refund_id": row.yookassa_refund_id,
        "error_message": row.error_message,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class AdminBookingPaymentService:
    def __init__(self, session_factory: Callable[[], Any] | async_sessionmaker = async_session_maker):
        self._session_factory = session_factory

    async def _get_agent_yookassa_credentials(self, session: Any, *, agent_id: int) -> tuple[str, str]:
        agent = await session.scalar(select(Agent).where(Agent.id == agent_id))
        if agent is None or not getattr(agent, "encrypted_booking_payment_api_key", None):
            raise RuntimeError("ЮKassa API ключ агента не настроен")
        raw = decrypt_booking_payment_secret(agent.encrypted_booking_payment_api_key)
        if not raw or ":" not in raw:
            raise RuntimeError("ЮKassa API ключ должен быть в формате shop_id:secret_key")
        shop_id, secret_key = raw.split(":", 1)
        shop_id = shop_id.strip()
        secret_key = secret_key.strip()
        if not shop_id or not secret_key:
            raise RuntimeError("ЮKassa API ключ должен быть в формате shop_id:secret_key")
        return shop_id, secret_key

    @staticmethod
    def configure_yookassa(shop_id: str, secret_key: str) -> None:
        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

    async def find_by_idempotency_key(self, idempotency_key: str) -> AdminBookingPayment | None:
        async with self._session_factory() as session:
            return await session.scalar(
                select(AdminBookingPayment).where(
                    AdminBookingPayment.idempotency_key == idempotency_key,
                )
            )

    async def save_pending_payment(
        self,
        *,
        agent_id: int,
        client_external_id: str,
        idempotency_key: str,
        yookassa_payment_id: str,
        amount_minor: int,
        booking_payload: dict[str, Any],
    ) -> AdminBookingPayment:
        now = _utc_now_naive()
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(AdminBookingPayment).where(
                        AdminBookingPayment.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    if existing.yookassa_payment_id != yookassa_payment_id:
                        existing.yookassa_payment_id = yookassa_payment_id
                        existing.updated_at = now
                    return existing
                row = AdminBookingPayment(
                    agent_id=agent_id,
                    client_external_id=client_external_id.strip(),
                    yookassa_payment_id=yookassa_payment_id,
                    amount_minor=int(amount_minor),
                    currency="RUB",
                    status="pending",
                    idempotency_key=idempotency_key,
                    booking_payload_json=json.dumps(booking_payload, ensure_ascii=False),
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return row

    async def get_pending_payment_context(
        self,
        *,
        agent_id: int,
        yookassa_payment_id: str,
        client_external_id: str,
    ) -> tuple[AdminBookingPayment, dict[str, Any]]:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(AdminBookingPayment).where(
                    AdminBookingPayment.agent_id == agent_id,
                    AdminBookingPayment.yookassa_payment_id == yookassa_payment_id,
                )
            )
            if row is None:
                raise RuntimeError("Платеж не найден. Запросите новую ссылку на оплату.")
            if row.client_external_id != client_external_id.strip():
                raise RuntimeError("Платеж принадлежит другому клиенту")
            payload: dict[str, Any] = {}
            if row.booking_payload_json:
                try:
                    parsed = json.loads(row.booking_payload_json)
                    if isinstance(parsed, dict):
                        payload = parsed
                except Exception:
                    payload = {}
            return row, payload

    async def mark_payment_paid(
        self,
        *,
        payment_id: int,
        appointment_id: int,
    ) -> AdminBookingPayment:
        now = _utc_now_naive()
        async with self._session_factory() as session:
            async with session.begin():
                row = await session.scalar(
                    select(AdminBookingPayment).where(AdminBookingPayment.id == payment_id)
                )
                if row is None:
                    raise RuntimeError("Платеж не найден")
                row.status = "paid"
                row.appointment_id = appointment_id
                row.paid_at = now
                row.updated_at = now
                await session.flush()
                await session.refresh(row)
                return row

    async def get_paid_payment_for_appointment(
        self,
        *,
        agent_id: int,
        appointment_id: int,
    ) -> AdminBookingPayment | None:
        async with self._session_factory() as session:
            return await session.scalar(
                select(AdminBookingPayment).where(
                    AdminBookingPayment.agent_id == agent_id,
                    AdminBookingPayment.appointment_id == appointment_id,
                    AdminBookingPayment.status == "paid",
                )
            )

    async def create_refund_request_for_payment(
        self,
        *,
        payment: AdminBookingPayment,
        appointment_id: int | None,
        cancel_reason: str | None,
    ) -> dict[str, Any]:
        now = _utc_now_naive()
        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.scalar(
                    select(AdminBookingRefundRequest).where(
                        AdminBookingRefundRequest.payment_id == payment.id,
                    )
                )
                if existing is not None:
                    return _serialize_refund_request(existing)
                row = AdminBookingRefundRequest(
                    agent_id=payment.agent_id,
                    payment_id=payment.id,
                    appointment_id=appointment_id,
                    client_external_id=payment.client_external_id,
                    amount_minor=payment.amount_minor,
                    currency=payment.currency,
                    cancel_reason=(cancel_reason or "").strip() or None,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                await session.flush()
                await session.refresh(row)
                return _serialize_refund_request(row)

    async def list_refund_requests(
        self,
        *,
        agent_id: int,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            conditions = [AdminBookingRefundRequest.agent_id == agent_id]
            if status:
                conditions.append(AdminBookingRefundRequest.status == status.strip().lower())
            rows = (
                await session.execute(
                    select(AdminBookingRefundRequest)
                    .where(*conditions)
                    .order_by(AdminBookingRefundRequest.created_at.desc())
                    .limit(max(1, min(limit, 500)))
                )
            ).scalars().all()
            return [_serialize_refund_request(row) for row in rows]

    async def approve_refund_request(
        self,
        *,
        agent_id: int,
        refund_request_id: int,
        reviewed_by_user_id: int,
    ) -> dict[str, Any]:
        now = _utc_now_naive()
        async with self._session_factory() as session:
            async with session.begin():
                refund_row = await session.scalar(
                    select(AdminBookingRefundRequest).where(
                        AdminBookingRefundRequest.id == refund_request_id,
                        AdminBookingRefundRequest.agent_id == agent_id,
                    )
                )
                if refund_row is None:
                    raise ValueError("Refund request not found")
                if refund_row.status == "refunded":
                    return _serialize_refund_request(refund_row)
                if refund_row.status != "pending":
                    raise ValueError(f"Refund request cannot be approved in status '{refund_row.status}'")

                payment = await session.scalar(
                    select(AdminBookingPayment).where(AdminBookingPayment.id == refund_row.payment_id)
                )
                if payment is None:
                    raise ValueError("Payment not found for refund request")
                if payment.status not in ("paid",):
                    raise ValueError(f"Payment status '{payment.status}' is not refundable")

                shop_id, secret_key = await self._get_agent_yookassa_credentials(session, agent_id=agent_id)
                self.configure_yookassa(shop_id, secret_key)

                amount_rub = f"{int(refund_row.amount_minor) / 100:.2f}"
                idempotence_key = f"booking-refund:{refund_row.id}"
                try:
                    refund = Refund.create(
                        {
                            "payment_id": payment.yookassa_payment_id,
                            "amount": {"value": amount_rub, "currency": refund_row.currency or "RUB"},
                            "description": f"Возврат за отмену записи #{refund_row.appointment_id or '—'}",
                        },
                        idempotence_key,
                    )
                except Exception as exc:
                    refund_row.status = "failed"
                    refund_row.error_message = str(exc)[:2000]
                    refund_row.reviewed_by_user_id = reviewed_by_user_id
                    refund_row.reviewed_at = now
                    refund_row.updated_at = now
                    await session.flush()
                    raise RuntimeError(f"Не удалось создать возврат в ЮKassa: {exc}") from exc

                refund_status = str(getattr(refund, "status", "") or "").strip().lower()
                refund_id = str(getattr(refund, "id", "") or "").strip()
                refund_row.yookassa_refund_id = refund_id or None
                refund_row.reviewed_by_user_id = reviewed_by_user_id
                refund_row.reviewed_at = now
                refund_row.updated_at = now

                if refund_status in ("succeeded", "pending", "waiting_for_capture"):
                    refund_row.status = "refunded"
                    payment.status = "refunded"
                    payment.updated_at = now
                else:
                    refund_row.status = "failed"
                    refund_row.error_message = f"Unexpected refund status: {refund_status or 'unknown'}"

                await session.flush()
                await session.refresh(refund_row)
                return _serialize_refund_request(refund_row)

    async def reject_refund_request(
        self,
        *,
        agent_id: int,
        refund_request_id: int,
        reviewed_by_user_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now_naive()
        async with self._session_factory() as session:
            async with session.begin():
                refund_row = await session.scalar(
                    select(AdminBookingRefundRequest).where(
                        AdminBookingRefundRequest.id == refund_request_id,
                        AdminBookingRefundRequest.agent_id == agent_id,
                    )
                )
                if refund_row is None:
                    raise ValueError("Refund request not found")
                if refund_row.status != "pending":
                    raise ValueError(f"Refund request cannot be rejected in status '{refund_row.status}'")
                refund_row.status = "rejected"
                refund_row.error_message = (reason or "").strip() or None
                refund_row.reviewed_by_user_id = reviewed_by_user_id
                refund_row.reviewed_at = now
                refund_row.updated_at = now
                await session.flush()
                await session.refresh(refund_row)
                return _serialize_refund_request(refund_row)

    async def verify_yookassa_payment_succeeded(
        self,
        *,
        agent_id: int,
        yookassa_payment_id: str,
    ) -> str:
        async with self._session_factory() as session:
            shop_id, secret_key = await self._get_agent_yookassa_credentials(session, agent_id=agent_id)
        self.configure_yookassa(shop_id, secret_key)
        payment = Payment.find_one(yookassa_payment_id)
        return str(getattr(payment, "status", "") or "").strip().lower()


_payment_service: AdminBookingPaymentService | None = None


def get_admin_booking_payment_service() -> AdminBookingPaymentService:
    global _payment_service
    if _payment_service is None:
        _payment_service = AdminBookingPaymentService()
    return _payment_service
