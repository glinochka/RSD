"""YooKassa autopay for paid agent subscriptions."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from yookassa import Configuration, Payment

from ..agent_template_pricing import (
    PAYMENT_KIND_AGENT_MAINTENANCE,
    agent_payment_plan_name,
    calculate_contract_amount_kopecks,
    get_agent_template_pricing,
    get_paid_agent_template_types,
)
from ..alembic.database import async_session_maker
from ..alembic.models import Agent, WebsitePaymentTransaction
from ..config import settings
from ..router_agents.dao import AgentDAO
from ..router_payments.dao import WebsitePaymentTransactionDAO
logger = getLogger(__name__)

AUTOPAY_CHARGE_DAYS_BEFORE = 1


def is_yookassa_autopay_available() -> bool:
    """True when merchant has autopay feature enabled in app config (and YooKassa credentials set)."""
    if not settings.YOOKASSA_AUTOPAY_ENABLED:
        return False
    return bool(settings.YOOKASSA_SHOP_ID.strip() and settings.YOOKASSA_SECRET_KEY.strip())
AUTOPAY_RETRY_COOLDOWN_HOURS = 12

def _configure_yookassa_from_settings() -> None:
    shop_id = settings.YOOKASSA_SHOP_ID.strip()
    secret_key = settings.YOOKASSA_SECRET_KEY.strip()
    if not shop_id or not secret_key:
        raise RuntimeError("YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY are not configured")
    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key


def _payment_attr(payment: Any, key: str, default=None):
    if payment is None:
        return default
    if isinstance(payment, dict):
        return payment.get(key, default)
    return getattr(payment, key, default)


def _payment_method_attr(payment_method: Any, key: str, default=None):
    if payment_method is None:
        return default
    if isinstance(payment_method, dict):
        return payment_method.get(key, default)
    return getattr(payment_method, key, default)


def extract_saved_payment_method_id(payment: Any) -> str | None:
    payment_method = _payment_attr(payment, "payment_method")
    if not _payment_method_attr(payment_method, "saved", False):
        return None
    raw_id = _payment_method_attr(payment_method, "id")
    if not raw_id:
        return None
    return str(raw_id).strip() or None


async def sync_agent_autopay_after_successful_payment(
    agent_dao: AgentDAO,
    agent: Agent,
    payment: Any,
    *,
    autopay_requested: bool,
    duration_months: int,
) -> None:
    """Persist saved payment method when user opted in during checkout."""
    updates: dict[str, Any] = {"autopay_last_error": None}
    if autopay_requested:
        payment_method_id = extract_saved_payment_method_id(payment)
        if payment_method_id:
            updates.update(
                {
                    "autopay_enabled": True,
                    "yookassa_payment_method_id": payment_method_id,
                    "autopay_duration_months": max(1, min(6, int(duration_months or 1))),
                }
            )
        else:
            updates["autopay_last_error"] = (
                "Не удалось сохранить способ оплаты для автопродления. "
                "Повторите оплату с включённым автопродлением."
            )
    await agent_dao.update(agent, updates)


async def _has_recent_autopay_activity(
    website_tx_dao: WebsitePaymentTransactionDAO,
    *,
    agent_id: int,
    since: datetime,
) -> bool:
    query = (
        select(WebsitePaymentTransaction.id)
        .where(
            WebsitePaymentTransaction.agent_id == agent_id,
            WebsitePaymentTransaction.is_autopay_charge.is_(True),
            WebsitePaymentTransaction.created_at >= since,
            WebsitePaymentTransaction.status.in_(("pending", "waiting_for_capture", "succeeded")),
        )
        .limit(1)
    )
    row_id = await website_tx_dao.scalar_or_default(query, None)
    return row_id is not None


def _agent_due_for_autopay_charge(agent: Agent, *, today: date | None = None) -> bool:
    if not agent.autopay_enabled or not agent.yookassa_payment_method_id:
        return False
    paid_until = getattr(agent, "maintenance_paid_until", None)
    if paid_until is None:
        return False
    if isinstance(paid_until, datetime):
        paid_until = paid_until.date()
    ref = today or date.today()
    charge_by = ref + timedelta(days=AUTOPAY_CHARGE_DAYS_BEFORE)
    return paid_until <= charge_by


async def _create_autopay_charge(
    *,
    agent: Agent,
    user_id: int,
    agent_dao: AgentDAO,
    website_tx_dao: WebsitePaymentTransactionDAO,
) -> bool:
    """Charge saved payment method. Returns True if payment succeeded immediately."""
    template_type = (agent.template_type or "qa").strip().lower()
    pricing = get_agent_template_pricing(template_type)
    if not pricing or pricing.monthly_maintenance_rub_min <= 0:
        return False

    duration_months = max(1, min(6, int(getattr(agent, "autopay_duration_months", None) or 1)))
    amount_kopecks = calculate_contract_amount_kopecks(
        pricing.monthly_maintenance_rub_min,
        duration_months,
    )
    plan_name = agent_payment_plan_name(
        payment_kind=PAYMENT_KIND_AGENT_MAINTENANCE,
        template_type=template_type,
    )
    description = (
        f"Автопродление подписки «{pricing.title}» ({duration_months} мес.)"
    )

    _configure_yookassa_from_settings()
    amount_rub = f"{(Decimal(amount_kopecks) / Decimal('100')):.2f}"
    idempotence_key = str(uuid4())

    try:
        payment = await asyncio.to_thread(
            Payment.create,
            {
                "amount": {"value": amount_rub, "currency": "RUB"},
                "capture": True,
                "payment_method_id": agent.yookassa_payment_method_id,
                "description": description,
                "metadata": {
                    "user_id": str(user_id),
                    "agent_id": str(agent.id),
                    "payment_kind": PAYMENT_KIND_AGENT_MAINTENANCE,
                    "template_type": template_type,
                    "duration_months": str(duration_months),
                    "autopay": "1",
                },
            },
            idempotence_key,
        )
    except Exception as exc:
        logger.exception("Autopay charge failed for agent_id=%s", agent.id)
        await agent_dao.update(
            agent,
            {
                "autopay_enabled": False,
                "autopay_last_attempt_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "autopay_last_error": f"Ошибка списания: {str(exc)[:400]}",
            },
        )
        return False

    payment_id = str(_payment_attr(payment, "id", "") or "")
    payment_status = str(_payment_attr(payment, "status", "pending") or "pending")
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    tx_row = await website_tx_dao.add(
        {
            "user_id": user_id,
            "agent_id": agent.id,
            "payment_kind": PAYMENT_KIND_AGENT_MAINTENANCE,
            "plan_name": plan_name,
            "currency": "RUB",
            "total_amount": amount_kopecks,
            "original_total_amount": amount_kopecks,
            "discount_percent": 0,
            "duration_months": duration_months,
            "promo_code": None,
            "yookassa_payment_id": payment_id or f"autopay-{uuid4()}",
            "status": payment_status,
            "is_autopay_charge": True,
            "autopay_requested": False,
        }
    )

    await agent_dao.update(agent, {"autopay_last_attempt_at": now_naive})

    if payment_status == "succeeded":
        base = date.today()
        current_until = getattr(agent, "maintenance_paid_until", None)
        if isinstance(current_until, date) and current_until > base:
            base = current_until
        new_until = base + timedelta(days=30 * duration_months)
        await agent_dao.update(
            agent,
            {
                "maintenance_paid_until": new_until,
                "is_active": True,
                "autopay_last_error": None,
            },
        )
        tx_row.status = "succeeded"
        tx_row.is_processed = True
        tx_row.paid_at = now_naive
        return True

    if payment_status == "canceled":
        cancellation = _payment_attr(payment, "cancellation_details") or {}
        reason = _payment_attr(cancellation, "reason") or "canceled"
        await agent_dao.update(
            agent,
            {
                "autopay_enabled": False,
                "autopay_last_error": f"Автоплатёж отклонён: {reason}",
            },
        )
    return False


async def process_agent_autopay_renewals_once() -> int:
    """
    Charge agents with autopay enabled before subscription expires.
    Returns count of successful immediate renewals.
    """
    if not is_yookassa_autopay_available():
        return 0

    renewed = 0
    cooldown_since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        hours=AUTOPAY_RETRY_COOLDOWN_HOURS
    )
    today = date.today()

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        website_tx_dao = WebsitePaymentTransactionDAO(session)
        async with session.begin():
            query = select(Agent).where(
                Agent.autopay_enabled.is_(True),
                Agent.yookassa_payment_method_id.is_not(None),
                Agent.template_type.in_(get_paid_agent_template_types()),
            )
            candidates = await agent_dao.list_scalars(query)

            for agent in candidates:
                if not _agent_due_for_autopay_charge(agent, today=today):
                    continue
                last_attempt = getattr(agent, "autopay_last_attempt_at", None)
                if last_attempt and last_attempt >= cooldown_since:
                    continue
                if await _has_recent_autopay_activity(
                    website_tx_dao,
                    agent_id=agent.id,
                    since=cooldown_since,
                ):
                    continue

                if await _create_autopay_charge(
                    agent=agent,
                    user_id=agent.user_id,
                    agent_dao=agent_dao,
                    website_tx_dao=website_tx_dao,
                ):
                    renewed += 1

    if renewed:
        logger.info("Agent autopay cron: renewed %s agent subscriptions", renewed)
    return renewed
