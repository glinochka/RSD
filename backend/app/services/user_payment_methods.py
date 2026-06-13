"""User saved payment methods (YooKassa) for autopay."""

from __future__ import annotations

from datetime import datetime, timezone
from logging import getLogger
from typing import Any

from sqlalchemy import select, update

from ..alembic.models import Agent, UserPaymentMethod
from .agent_autopay import extract_saved_payment_method_id

logger = getLogger(__name__)


def _payment_attr(payment: Any, key: str, default=None):
    if payment is None:
        return default
    if isinstance(payment, dict):
        return payment.get(key, default)
    return getattr(payment, key, default)


def extract_card_label_from_payment(payment: Any) -> tuple[str | None, str | None]:
    payment_method = _payment_attr(payment, "payment_method")
    if payment_method is None:
        return None, None
    card = _payment_attr(payment_method, "card")
    if card is None:
        pm_type = _payment_attr(payment_method, "type")
        if pm_type:
            return str(pm_type), None
        return None, None
    last4 = _payment_attr(card, "last4")
    card_type = _payment_attr(card, "card_type") or _payment_attr(payment_method, "type")
    return (
        str(card_type) if card_type else None,
        str(last4) if last4 else None,
    )


def format_payment_method_title(*, card_type: str | None, card_last4: str | None, method_id: str) -> str:
    if card_last4:
        brand = (card_type or "Карта").replace("_", " ").title()
        return f"{brand} •••• {card_last4}"
    if card_type:
        return card_type.replace("_", " ").title()
    return f"Способ оплаты {method_id[-6:]}"


async def upsert_user_payment_method_from_payment(
    session,
    *,
    user_id: int,
    payment: Any,
) -> UserPaymentMethod | None:
    method_id = extract_saved_payment_method_id(payment)
    if not method_id:
        return None
    card_type, card_last4 = extract_card_label_from_payment(payment)
    existing = await session.scalar(
        select(UserPaymentMethod).where(
            UserPaymentMethod.user_id == user_id,
            UserPaymentMethod.yookassa_payment_method_id == method_id,
        )
    )
    if existing:
        existing.card_type = card_type or existing.card_type
        existing.card_last4 = card_last4 or existing.card_last4
        return existing
    row = UserPaymentMethod(
        user_id=user_id,
        yookassa_payment_method_id=method_id,
        card_type=card_type,
        card_last4=card_last4,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(row)
    await session.flush()
    return row


async def detach_payment_method_from_user_agents(
    session,
    *,
    user_id: int,
    yookassa_payment_method_id: str,
) -> int:
    """Disable autopay on agents that used this payment method. Returns updated agent count."""
    result = await session.execute(
        update(Agent)
        .where(
            Agent.user_id == user_id,
            Agent.yookassa_payment_method_id == yookassa_payment_method_id,
        )
        .values(
            autopay_enabled=False,
            yookassa_payment_method_id=None,
            autopay_last_error=None,
        )
    )
    return int(result.rowcount or 0)


async def disable_all_user_autopay(session, *, user_id: int) -> int:
    result = await session.execute(
        update(Agent)
        .where(Agent.user_id == user_id, Agent.autopay_enabled.is_(True))
        .values(
            autopay_enabled=False,
            yookassa_payment_method_id=None,
            autopay_last_error="Нет сохранённых способов оплаты — автопродление отключено.",
        )
    )
    return int(result.rowcount or 0)


def serialize_payment_method(row: UserPaymentMethod) -> dict[str, Any]:
    method_id = row.yookassa_payment_method_id
    return {
        "id": row.id,
        "yookassa_payment_method_id": method_id,
        "card_type": row.card_type,
        "card_last4": row.card_last4,
        "title": format_payment_method_title(
            card_type=row.card_type,
            card_last4=row.card_last4,
            method_id=method_id,
        ),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
