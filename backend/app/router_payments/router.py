from datetime import date, datetime, timedelta, timezone
from typing import Any
from logging import getLogger
import asyncio
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from yookassa import Configuration, Payment
from yookassa.domain.notification.webhook_notification import WebhookNotificationFactory
from yookassa.domain.notification.webhook_notification_types import WebhookNotificationEventType
from yookassa.domain.exceptions import NotFoundError
from ..alembic.database import async_session_maker
from ..agent_template_pricing import (
    AGENT_DURATION_DISCOUNT_BY_MONTHS,
    PAYMENT_KIND_AGENT_ACTIVATION,
    PAYMENT_KIND_AGENT_MAINTENANCE,
    PAYMENT_KIND_SUBSCRIPTION,
    agent_payment_plan_name,
    build_agent_billing_state,
    calculate_contract_amount_kopecks,
    get_agent_template_pricing,
    is_activation_paid,
    list_public_agent_template_pricing,
    parse_agent_payment_plan_name,
    user_has_free_agent_activation,
)
from ..alembic.models import AdminBookingPayment, Agent, UserPaymentMethod, WebsitePaymentTransaction
from ..router_agents.dao import AgentDAO
from ..config import settings
from ..router_users.dao import UserDAO
from ..subscription_plans import (
    get_all_subscription_plans,
    get_subscription_plan,
)
from ..utils.internal_auth import verify_internal_key
from ..utils.JWT import get_user_from_access_token
from ..utils.rate_limit import rate_limit
from .schemas import (
    CreateAgentBillingPayment,
    CreateTurnkeyAgentRequest,
    CreateYooKassaPayment,
    ProcessTelegramPayment,
    YooKassaPaymentStatusResponse,
)
from ..router_referrals.dao import PartnerPromoCodeDAO
from ..services.agent_autopay import is_yookassa_autopay_available, sync_agent_autopay_after_successful_payment
from ..services.user_payment_methods import (
    detach_payment_method_from_user_agents,
    disable_all_user_autopay,
    serialize_payment_method,
    upsert_user_payment_method_from_payment,
)
from ..services.referral import attach_referrer_by_partner_id, record_referral_commission_for_transaction
from .dao import (
    PaymentTransactionDAO,
    PromoCodeDAO,
    TurnkeyAgentRequestDAO,
    WebsitePaymentTransactionDAO,
)

logger = getLogger(__name__)
router = APIRouter(prefix="/api/payments")
http_bearer = HTTPBearer(auto_error=False)
DURATION_DISCOUNT_BY_MONTHS = {
    1: 0,
    3: 15,
    6: 25,
}


async def get_current_user_required(
    http_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
):
    if not http_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = http_credentials.credentials
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            return await get_user_from_access_token(token, user_dao)


def _configure_yookassa() -> None:
    shop_id = settings.YOOKASSA_SHOP_ID.strip()
    secret_key = settings.YOOKASSA_SECRET_KEY.strip()
    if not shop_id or not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY are not configured",
        )
    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key


def _resolve_confirmation_url(payment: Payment) -> str | None:
    confirmation = getattr(payment, "confirmation", None)
    if confirmation is None:
        return None
    if isinstance(confirmation, dict):
        return confirmation.get("confirmation_url")
    return getattr(confirmation, "confirmation_url", None)


def _calculate_new_end_date(current_end_date: date | datetime | None, duration_months: int = 1) -> datetime:
    """Extend subscription from now or from current end. Handles DB values as date or datetime."""
    now_utc = datetime.now(timezone.utc)
    base_date = now_utc
    if current_end_date is not None:
        if isinstance(current_end_date, datetime):
            if current_end_date.tzinfo is None:
                current_end = current_end_date.replace(tzinfo=timezone.utc)
            else:
                current_end = current_end_date.astimezone(timezone.utc)
        else:
            current_end = datetime.combine(
                current_end_date, datetime.min.time(), tzinfo=timezone.utc
            )
        if current_end > now_utc:
            base_date = current_end
    return (base_date + timedelta(days=30 * duration_months)).replace(tzinfo=None)


def _normalize_promo_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


async def _resolve_checkout_promo(
    session,
    normalized_promo: str,
) -> tuple[int, str | None, int | None, int]:
    """Returns (discount_percent, promo_code, partner_user_id, partner_promo_discount_percent)."""
    partner_promo_dao = PartnerPromoCodeDAO(session)
    partner_promo = await partner_promo_dao.find_active_by_code_case_insensitive(normalized_promo)
    if partner_promo:
        discount = int(partner_promo.discount_percent or 0)
        return discount, partner_promo.code, partner_promo.partner_user_id, discount

    promo_dao = PromoCodeDAO(session)
    admin_promo = await promo_dao.find_by_code_case_insensitive(normalized_promo)
    if admin_promo:
        return int(admin_promo.discount_percent or 0), admin_promo.code, None, 0

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Promo code not found",
    )


async def _apply_agent_billing_payment(
    agent_dao: AgentDAO,
    tx: WebsitePaymentTransaction,
) -> None:
    parsed = parse_agent_payment_plan_name(tx.plan_name)
    if not parsed or not tx.agent_id:
        logger.error("Website payment %s: invalid agent billing payload", tx.yookassa_payment_id)
        return
    payment_kind, template_type = parsed
    agent = await agent_dao.find_one_by_filter(id=tx.agent_id, user_id=tx.user_id)
    if not agent:
        logger.error(
            "Website payment %s: agent_id=%s not found for user_id=%s",
            tx.yookassa_payment_id,
            tx.agent_id,
            tx.user_id,
        )
        return
    if (agent.template_type or "qa").strip().lower() != template_type:
        logger.error(
            "Website payment %s: template mismatch agent=%s payment=%s",
            tx.yookassa_payment_id,
            agent.template_type,
            template_type,
        )
        return

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    if payment_kind == PAYMENT_KIND_AGENT_ACTIVATION:
        await agent_dao.update(agent, {"activation_paid_at": now_naive})
        return
    if payment_kind == PAYMENT_KIND_AGENT_MAINTENANCE:
        duration_months = max(1, int(getattr(tx, "duration_months", None) or 1))
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
            },
        )


async def _apply_yookassa_payment_to_subscription(
    user_dao: UserDAO,
    agent_dao: AgentDAO,
    tx: WebsitePaymentTransaction,
    payment_status: str,
    *,
    yookassa_payment: Any | None = None,
) -> None:
    """Update stored status and extend subscription or agent billing once when payment succeeds."""
    tx.status = payment_status

    if payment_status == "canceled" and getattr(tx, "is_autopay_charge", False) and tx.agent_id:
        agent = await agent_dao.find_one_by_filter(id=tx.agent_id)
        if agent:
            await agent_dao.update(
                agent,
                {
                    "autopay_enabled": False,
                    "autopay_last_error": "Автоплатёж отклонён. Продлите подписку вручную.",
                },
            )
        return

    if payment_status != "succeeded" or tx.is_processed:
        return

    payment_kind = (getattr(tx, "payment_kind", None) or PAYMENT_KIND_SUBSCRIPTION).strip()
    if payment_kind in (PAYMENT_KIND_AGENT_ACTIVATION, PAYMENT_KIND_AGENT_MAINTENANCE):
        await _apply_agent_billing_payment(agent_dao, tx)
        tx.is_processed = True
        tx.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if tx.agent_id and payment_kind == PAYMENT_KIND_AGENT_MAINTENANCE:
            agent = await agent_dao.find_one_by_filter(id=tx.agent_id, user_id=tx.user_id)
            if agent and yookassa_payment is not None:
                autopay_requested = bool(getattr(tx, "autopay_requested", False))
                await sync_agent_autopay_after_successful_payment(
                    agent_dao,
                    agent,
                    yookassa_payment,
                    autopay_requested=autopay_requested,
                    duration_months=int(getattr(tx, "duration_months", None) or 1),
                )
                if autopay_requested:
                    await upsert_user_payment_method_from_payment(
                        user_dao._session,
                        user_id=tx.user_id,
                        payment=yookassa_payment,
                    )
        await record_referral_commission_for_transaction(
            user_dao._session,
            user_dao,
            tx,
        )
        return

    user = await user_dao.find_one_by_filter(id=tx.user_id)
    if not user:
        logger.error(
            "Website payment %s: user_id %s not found",
            tx.yookassa_payment_id,
            tx.user_id,
        )
        return

    selected_plan = get_subscription_plan(tx.plan_name)
    if not selected_plan or not selected_plan.get("is_paid"):
        logger.error(
            "Website payment %s: invalid plan %s",
            tx.yookassa_payment_id,
            tx.plan_name,
        )
        return

    duration_months = int(getattr(tx, "duration_months", 1) or 1)
    new_end_date = _calculate_new_end_date(user.subscription_end_date, duration_months=duration_months)
    await user_dao.update(
        user,
        {
            "subscription_type": tx.plan_name,
            "subscription_end_date": new_end_date,
        },
    )
    tx.is_processed = True
    tx.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await record_referral_commission_for_transaction(
        user_dao._session,
        user_dao,
        tx,
    )


@router.get("/plans")
async def get_subscription_plans():
    return JSONResponse(
        content={"plans": get_all_subscription_plans()},
        status_code=status.HTTP_200_OK,
    )


@router.get("/agent-templates")
async def list_agent_template_pricing():
    return JSONResponse(
        content={
            "templates": list_public_agent_template_pricing(),
            "policy_notes": [
                "ИИ консультант — бесплатно.",
                "ИИ Администратор — 990 ₽/мес, ИИ МОП — 1 990 ₽/мес.",
                "Первые 3 дня после создания платного агента — бесплатный пробный период.",
                "Оплата на 1, 3 или 6 месяцев; при длительном сроке действует скидка.",
                "Токены LLM включены — расходы на модели покрывает платформа.",
            ],
        },
        status_code=status.HTTP_200_OK,
    )


def _agent_billing_amount_kopecks(
    *,
    payment_kind: str,
    template_type: str,
    duration_months: int = 1,
    promo_discount_percent: int = 0,
) -> tuple[int, str, int]:
    pricing = get_agent_template_pricing(template_type)
    if not pricing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown agent template")
    if payment_kind == PAYMENT_KIND_AGENT_ACTIVATION:
        if pricing.setup_rub_min <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Activation payment is not required for this template",
            )
        original_kopecks = pricing.setup_rub_min * 100
        promo_discount_kopecks = (original_kopecks * promo_discount_percent) // 100
        amount_kopecks = max(0, original_kopecks - promo_discount_kopecks)
        return amount_kopecks, f"Запуск агента «{pricing.title}»", original_kopecks
    if payment_kind == PAYMENT_KIND_AGENT_MAINTENANCE:
        if pricing.monthly_maintenance_rub_min <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Monthly maintenance is not billed for this template",
            )
        original_kopecks = calculate_contract_amount_kopecks(
            pricing.monthly_maintenance_rub_min,
            duration_months,
        )
        promo_discount_kopecks = (original_kopecks * promo_discount_percent) // 100
        amount_kopecks = max(0, original_kopecks - promo_discount_kopecks)
        duration_label = f"{duration_months} мес."
        return (
            amount_kopecks,
            f"Подписка на агента «{pricing.title}» ({duration_label})",
            original_kopecks,
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment kind")


@router.post("/yookassa/agent-billing/create")
async def create_yookassa_agent_billing_payment(
    payload: CreateAgentBillingPayment,
    current_user=Depends(get_current_user_required),
):
    duration_months = int(payload.duration_months or 1)
    autopay_requested = bool(payload.enable_autopay) and payload.payment_kind == PAYMENT_KIND_AGENT_MAINTENANCE
    enable_autopay = autopay_requested and is_yookassa_autopay_available()
    autopay_warning = None
    if autopay_requested and not enable_autopay:
        autopay_warning = (
            "Автопродление сейчас недоступно: подключите рекуррентные платежи в ЮKassa "
            "и укажите YOOKASSA_AUTOPAY_ENABLED=true. Оплата пройдёт без сохранения карты."
        )
    normalized_promo = _normalize_promo_code(payload.promo_code)
    applied_discount_percent = 0
    applied_promo_code = None
    partner_user_id = None
    partner_promo_discount_percent = 0

    async with async_session_maker() as session:
        agent_dao = AgentDAO(session)
        async with session.begin():
            agent = await agent_dao.find_one_by_filter(id=payload.agent_id, user_id=current_user.id)
            if not agent:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

            template_type = (agent.template_type or "qa").strip().lower()
            if payload.payment_kind == PAYMENT_KIND_AGENT_ACTIVATION:
                if user_has_free_agent_activation(current_user):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Оплата активации не требуется для этого аккаунта",
                    )
                if is_activation_paid(agent, user=current_user):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Activation payment already completed",
                    )
            if normalized_promo:
                (
                    applied_discount_percent,
                    applied_promo_code,
                    partner_user_id,
                    partner_promo_discount_percent,
                ) = await _resolve_checkout_promo(session, normalized_promo)
                if partner_user_id:
                    user_dao = UserDAO(session)
                    buyer = await user_dao.find_one_by_filter(id=current_user.id)
                    if buyer:
                        await attach_referrer_by_partner_id(user_dao, buyer, partner_user_id)

    amount_kopecks, description, original_amount_kopecks = _agent_billing_amount_kopecks(
        payment_kind=payload.payment_kind,
        template_type=template_type,
        duration_months=duration_months,
        promo_discount_percent=applied_discount_percent,
    )
    plan_name = agent_payment_plan_name(
        payment_kind=payload.payment_kind,
        template_type=template_type,
    )
    duration_discount_percent = AGENT_DURATION_DISCOUNT_BY_MONTHS.get(duration_months, 0)

    if amount_kopecks == 0:
        async with async_session_maker() as session:
            agent_dao = AgentDAO(session)
            website_tx_dao = WebsitePaymentTransactionDAO(session)
            async with session.begin():
                tx_row = await website_tx_dao.add(
                    {
                        "user_id": current_user.id,
                        "agent_id": payload.agent_id,
                        "payment_kind": payload.payment_kind,
                        "plan_name": plan_name,
                        "currency": "RUB",
                        "total_amount": 0,
                        "original_total_amount": original_amount_kopecks,
                        "discount_percent": applied_discount_percent,
                        "duration_months": duration_months,
                        "promo_code": applied_promo_code,
                        "partner_user_id": partner_user_id,
                        "partner_promo_discount_percent": partner_promo_discount_percent,
                        "yookassa_payment_id": f"promo-{uuid4()}",
                        "status": "succeeded",
                        "is_processed": True,
                        "paid_at": datetime.now(timezone.utc).replace(tzinfo=None),
                        "autopay_requested": autopay_requested,
                    }
                )
                await session.flush()
                await _apply_agent_billing_payment(agent_dao, tx_row)
                if autopay_requested and enable_autopay:
                    agent = await agent_dao.find_one_by_filter(
                        id=payload.agent_id,
                        user_id=current_user.id,
                    )
                    if agent:
                        await agent_dao.update(
                            agent,
                            {
                                "autopay_enabled": True,
                                "autopay_duration_months": duration_months,
                                "autopay_last_error": None,
                            },
                        )
                await record_referral_commission_for_transaction(session, UserDAO(session), tx_row)
        return JSONResponse(
            content={
                "payment_id": None,
                "status": "succeeded",
                "confirmation_url": None,
                "plan_name": plan_name,
                "payment_kind": payload.payment_kind,
                "agent_id": payload.agent_id,
                "amount_kopecks": 0,
                "template_type": template_type,
                "promo_code": applied_promo_code,
                "discount_percent": applied_discount_percent,
                "duration_discount_percent": duration_discount_percent,
                "duration_months": duration_months,
                "contract_activated": True,
                "autopay_warning": autopay_warning,
            },
            status_code=status.HTTP_200_OK,
        )

    return_url = (payload.return_url or settings.YOOKASSA_RETURN_URL or "").strip()
    if not return_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="return_url is required (or set YOOKASSA_RETURN_URL)",
        )

    _configure_yookassa()
    amount_rub = f"{(Decimal(amount_kopecks) / Decimal('100')):.2f}"
    idempotence_key = str(uuid4())

    payment_payload: dict[str, Any] = {
        "amount": {"value": amount_rub, "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": description,
        "metadata": {
            "user_id": str(current_user.id),
            "agent_id": str(payload.agent_id),
            "payment_kind": payload.payment_kind,
            "template_type": template_type,
            "duration_months": str(duration_months),
            "enable_autopay": "1" if enable_autopay else "0",
        },
    }
    if enable_autopay:
        payment_payload["save_payment_method"] = True

    try:
        payment = await asyncio.to_thread(
            Payment.create,
            payment_payload,
            idempotence_key,
        )
    except Exception as e:
        if enable_autopay and payment_payload.pop("save_payment_method", None):
            logger.warning(
                "YooKassa rejected save_payment_method, retrying without autopay: %s",
                e,
            )
            enable_autopay = False
            autopay_requested = False
            autopay_warning = (
                "Автопродление недоступно в ЮKassa — оплата создана без сохранения карты. "
                "Подключите рекуррентные платежи в личном кабинете."
            )
            try:
                payment = await asyncio.to_thread(
                    Payment.create,
                    payment_payload,
                    idempotence_key,
                )
            except Exception as retry_exc:
                logger.exception("YooKassa agent billing payment creation failed")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"YooKassa payment creation failed: {retry_exc}",
                ) from retry_exc
        else:
            logger.exception("YooKassa agent billing payment creation failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"YooKassa payment creation failed: {e}",
            ) from e

    confirmation_url = _resolve_confirmation_url(payment)
    payment_id = str(getattr(payment, "id", ""))
    payment_status = str(getattr(payment, "status", "pending"))
    if not payment_id or not confirmation_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YooKassa returned invalid payment payload",
        )

    async with async_session_maker() as session:
        website_tx_dao = WebsitePaymentTransactionDAO(session)
        async with session.begin():
            await website_tx_dao.add(
                {
                    "user_id": current_user.id,
                    "agent_id": payload.agent_id,
                    "payment_kind": payload.payment_kind,
                    "plan_name": plan_name,
                    "currency": "RUB",
                    "total_amount": amount_kopecks,
                    "original_total_amount": original_amount_kopecks,
                    "discount_percent": applied_discount_percent,
                    "duration_months": duration_months,
                    "promo_code": applied_promo_code,
                    "partner_user_id": partner_user_id,
                    "partner_promo_discount_percent": partner_promo_discount_percent,
                    "yookassa_payment_id": payment_id,
                    "status": payment_status,
                    "autopay_requested": autopay_requested,
                }
            )

    return JSONResponse(
        content={
            "payment_id": payment_id,
            "status": payment_status,
            "confirmation_url": confirmation_url,
            "plan_name": plan_name,
            "payment_kind": payload.payment_kind,
            "agent_id": payload.agent_id,
            "amount_kopecks": amount_kopecks,
            "template_type": template_type,
            "promo_code": applied_promo_code,
            "discount_percent": applied_discount_percent,
            "duration_discount_percent": duration_discount_percent,
            "duration_months": duration_months,
            "enable_autopay": enable_autopay,
            "autopay_warning": autopay_warning,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/payment-methods")
async def list_user_payment_methods(
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        async with session.begin():
            rows = list(
                await session.scalars(
                    select(UserPaymentMethod)
                    .where(UserPaymentMethod.user_id == current_user.id)
                    .order_by(UserPaymentMethod.created_at.desc())
                )
            )
            known_ids = {row.yookassa_payment_method_id for row in rows}
            agent_rows = list(
                await session.scalars(
                    select(Agent).where(
                        Agent.user_id == current_user.id,
                        Agent.yookassa_payment_method_id.is_not(None),
                    )
                )
            )
            for agent in agent_rows:
                method_id = (agent.yookassa_payment_method_id or "").strip()
                if not method_id or method_id in known_ids:
                    continue
                backfill = UserPaymentMethod(
                    user_id=current_user.id,
                    yookassa_payment_method_id=method_id,
                    card_type=None,
                    card_last4=None,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                session.add(backfill)
                rows.append(backfill)
                known_ids.add(method_id)
            await session.flush()
    return JSONResponse(
        content={"items": [serialize_payment_method(row) for row in rows]},
        status_code=status.HTTP_200_OK,
    )


@router.delete("/payment-methods/{method_id}")
async def delete_user_payment_method(
    method_id: int,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        async with session.begin():
            row = await session.scalar(
                select(UserPaymentMethod).where(
                    UserPaymentMethod.id == method_id,
                    UserPaymentMethod.user_id == current_user.id,
                )
            )
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment method not found")
            yookassa_id = row.yookassa_payment_method_id
            await session.delete(row)
            await detach_payment_method_from_user_agents(
                session,
                user_id=current_user.id,
                yookassa_payment_method_id=yookassa_id,
            )
            remaining = await session.scalar(
                select(UserPaymentMethod.id).where(UserPaymentMethod.user_id == current_user.id).limit(1)
            )
            agents_disabled = 0
            if not remaining:
                agents_disabled = await disable_all_user_autopay(session, user_id=current_user.id)
    return JSONResponse(
        content={
            "detail": "Payment method removed",
            "autopay_disabled_agents": agents_disabled,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/turnkey-requests", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, scope="turnkey_requests"))])
async def create_turnkey_request(payload: CreateTurnkeyAgentRequest):
    async with async_session_maker() as session:
        turnkey_request_dao = TurnkeyAgentRequestDAO(session)
        async with session.begin():
            await turnkey_request_dao.add(
                {
                    "phone_number": payload.phone_number,
                    "email": payload.email,
                    "requested_agent": payload.requested_agent,
                    "purpose": payload.purpose,
                }
            )
    return JSONResponse(
        content={"detail": "Request created"},
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/process_successful")
async def process_successful_payment(
    payload: ProcessTelegramPayment,
    _internal=Depends(verify_internal_key),
):
    """
    Idempotent payment processing.
    Guarantees that the same telegram_payment_charge_id cannot be processed twice.
    """
    try:
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            payment_tx_dao = PaymentTransactionDAO(session)
            async with session.begin():
                if await payment_tx_dao.exists_by_telegram_charge_id(payload.telegram_payment_charge_id):
                    user = await user_dao.find_one_by_filter(telegram_id=payload.telegram_id)
                    if not user:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found",
                        )
                    return JSONResponse(
                        content={
                            "status": "duplicate",
                            "subscription_type": user.subscription_type,
                            "subscription_end_date": user.subscription_end_date.isoformat()
                            if user.subscription_end_date
                            else None,
                        },
                        status_code=status.HTTP_200_OK,
                    )

                user = await user_dao.find_one_by_filter(telegram_id=payload.telegram_id)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                # Reserve unique charge id early to avoid concurrent double processing.
                await payment_tx_dao.add(
                    {
                        "telegram_id": payload.telegram_id,
                        "plan_name": payload.plan_name,
                        "currency": payload.currency,
                        "total_amount": payload.total_amount,
                        "telegram_payment_charge_id": payload.telegram_payment_charge_id,
                        "provider_payment_charge_id": payload.provider_payment_charge_id,
                        "invoice_payload": payload.invoice_payload,
                    }
                )
                await session.flush()

                selected_plan = get_subscription_plan(payload.plan_name)
                if not selected_plan or not selected_plan.get("is_paid"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid paid plan",
                    )

                new_end_date = _calculate_new_end_date(user.subscription_end_date)
                await user_dao.update(
                    user,
                    {
                        "subscription_type": payload.plan_name,
                        "subscription_end_date": new_end_date,
                    },
                )

                return JSONResponse(
                    content={
                        "status": "processed",
                        "subscription_type": payload.plan_name,
                        "subscription_end_date": new_end_date.isoformat(),
                    },
                    status_code=status.HTTP_200_OK,
                )
    except IntegrityError:
        logger.warning(
            "Duplicate telegram_payment_charge_id skipped: %s",
            payload.telegram_payment_charge_id,
        )
        return JSONResponse(
            content={"status": "duplicate"},
            status_code=status.HTTP_200_OK,
        )


@router.post("/yookassa/create")
async def create_yookassa_payment(
    payload: CreateYooKassaPayment,
    current_user=Depends(get_current_user_required),
):
    selected_plan = get_subscription_plan(payload.plan_name)
    if not selected_plan or not selected_plan.get("is_paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid paid plan",
        )

    duration_months = int(payload.duration_months or 1)
    duration_discount_percent = DURATION_DISCOUNT_BY_MONTHS.get(duration_months, 0)
    original_amount_kopecks = int(selected_plan.get("price_rub_month", 0) or 0) * 100 * duration_months
    normalized_promo = _normalize_promo_code(payload.promo_code)
    applied_discount_percent = 0
    applied_promo_code = None
    partner_user_id = None
    partner_promo_discount_percent = 0

    if normalized_promo:
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            async with session.begin():
                (
                    applied_discount_percent,
                    applied_promo_code,
                    partner_user_id,
                    partner_promo_discount_percent,
                ) = await _resolve_checkout_promo(session, normalized_promo)
                if partner_user_id:
                    buyer = await user_dao.find_one_by_filter(id=current_user.id)
                    if buyer:
                        await attach_referrer_by_partner_id(user_dao, buyer, partner_user_id)

    duration_discount_kopecks = (original_amount_kopecks * duration_discount_percent) // 100
    amount_after_duration_discount = max(0, original_amount_kopecks - duration_discount_kopecks)
    promo_discount_kopecks = (amount_after_duration_discount * applied_discount_percent) // 100
    amount_kopecks = max(0, amount_after_duration_discount - promo_discount_kopecks)

    # 100% promo flow: activate subscription without external payment gateway.
    if amount_kopecks == 0:
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            website_tx_dao = WebsitePaymentTransactionDAO(session)
            async with session.begin():
                user = await user_dao.find_one_by_filter(id=current_user.id)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )
                if partner_user_id:
                    await attach_referrer_by_partner_id(user_dao, user, partner_user_id)

                new_end_date = _calculate_new_end_date(
                    user.subscription_end_date,
                    duration_months=duration_months,
                )
                await user_dao.update(
                    user,
                    {
                        "subscription_type": payload.plan_name,
                        "subscription_end_date": new_end_date,
                    },
                )
                tx_row = await website_tx_dao.add(
                    {
                        "user_id": current_user.id,
                        "plan_name": payload.plan_name,
                        "currency": "RUB",
                        "total_amount": 0,
                        "original_total_amount": original_amount_kopecks,
                        "discount_percent": applied_discount_percent,
                        "duration_months": duration_months,
                        "promo_code": applied_promo_code,
                        "partner_user_id": partner_user_id,
                        "partner_promo_discount_percent": partner_promo_discount_percent,
                        "yookassa_payment_id": f"promo-{uuid4()}",
                        "status": "succeeded",
                        "is_processed": True,
                        "paid_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    }
                )
                await session.flush()
                await record_referral_commission_for_transaction(session, user_dao, tx_row)

        return JSONResponse(
            content={
                "payment_id": None,
                "status": "succeeded",
                "confirmation_url": None,
                "plan_name": payload.plan_name,
                "promo_code": applied_promo_code,
                "discount_percent": applied_discount_percent,
                "duration_discount_percent": duration_discount_percent,
                "duration_months": duration_months,
                "amount_kopecks": 0,
                "subscription_activated": True,
            },
            status_code=status.HTTP_200_OK,
        )

    return_url = (payload.return_url or settings.YOOKASSA_RETURN_URL or "").strip()
    if not return_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="return_url is required (or set YOOKASSA_RETURN_URL)",
        )

    _configure_yookassa()

    amount_rub = f"{(Decimal(amount_kopecks) / Decimal('100')):.2f}"
    idempotence_key = str(uuid4())

    try:
        payment = await asyncio.to_thread(
            Payment.create,
            {
                "amount": {"value": amount_rub, "currency": "RUB"},
                "capture": True,
                "confirmation": {"type": "redirect", "return_url": return_url},
                "description": (
                    f"Подписка {selected_plan.get('title', payload.plan_name)} "
                    f"на {duration_months} мес."
                ),
                "metadata": {
                    "user_id": str(current_user.id),
                    "plan_name": payload.plan_name,
                    "duration_months": str(duration_months),
                    "duration_discount_percent": str(duration_discount_percent),
                    "promo_code": applied_promo_code or "",
                    "discount_percent": str(applied_discount_percent),
                },
            },
            idempotence_key,
        )
    except Exception as e:
        logger.exception("YooKassa payment creation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"YooKassa payment creation failed: {e}",
        )

    confirmation_url = _resolve_confirmation_url(payment)
    payment_id = str(getattr(payment, "id", ""))
    payment_status = str(getattr(payment, "status", "pending"))
    if not payment_id or not confirmation_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YooKassa returned invalid payment payload",
        )

    async with async_session_maker() as session:
        website_tx_dao = WebsitePaymentTransactionDAO(session)
        async with session.begin():
            await website_tx_dao.add(
                {
                    "user_id": current_user.id,
                    "plan_name": payload.plan_name,
                    "currency": "RUB",
                    "total_amount": amount_kopecks,
                    "original_total_amount": original_amount_kopecks,
                    "discount_percent": applied_discount_percent,
                    "duration_months": duration_months,
                    "promo_code": applied_promo_code,
                    "partner_user_id": partner_user_id,
                    "partner_promo_discount_percent": partner_promo_discount_percent,
                    "yookassa_payment_id": payment_id,
                    "status": payment_status,
                }
            )

    return JSONResponse(
        content={
            "payment_id": payment_id,
            "status": payment_status,
            "confirmation_url": confirmation_url,
            "plan_name": payload.plan_name,
            "promo_code": applied_promo_code,
            "discount_percent": applied_discount_percent,
            "duration_discount_percent": duration_discount_percent,
            "duration_months": duration_months,
            "amount_kopecks": amount_kopecks,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/yookassa/status", response_model=YooKassaPaymentStatusResponse)
async def get_yookassa_payment_status(
    payment_id: str = Query(..., min_length=1),
    current_user=Depends(get_current_user_required),
):
    _configure_yookassa()

    try:
        payment = await asyncio.to_thread(Payment.find_one, payment_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    except Exception as e:
        logger.exception("YooKassa payment status check failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"YooKassa payment status check failed: {e}")

    payment_status = str(getattr(payment, "status", "pending"))

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        website_tx_dao = WebsitePaymentTransactionDAO(session)
        async with session.begin():
            tx = await website_tx_dao.find_for_update_by_payment_id(
                yookassa_payment_id=payment_id,
                user_id=current_user.id,
            )
            if not tx:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found",
                )

            await _apply_yookassa_payment_to_subscription(
                user_dao,
                agent_dao,
                tx,
                payment_status,
                yookassa_payment=payment,
            )

            user = await user_dao.find_one_by_filter(id=current_user.id)
            agent_billing: dict[str, Any] | None = None
            if tx.agent_id:
                agent = await agent_dao.find_one_by_filter(id=tx.agent_id, user_id=current_user.id)
                if agent:
                    agent_billing = build_agent_billing_state(agent, user=user)
            return YooKassaPaymentStatusResponse(
                payment_id=payment_id,
                status=payment_status,
                plan_name=tx.plan_name,
                subscription_type=user.subscription_type if user else None,
                subscription_end_date=user.subscription_end_date.isoformat()
                if user and user.subscription_end_date
                else None,
                agent_id=tx.agent_id,
                payment_kind=getattr(tx, "payment_kind", None),
                agent_billing=agent_billing,
            )


@router.post("/yookassa/webhook")
async def yookassa_webhook(request: Request):
    """
    HTTP-уведомления ЮKassa. Должен отвечать 200 OK (тело ответа игнорируется).
    Статус платежа подтверждается через API (Payment.find_one), как в документации.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("YooKassa webhook: invalid JSON body")
        return Response(status_code=status.HTTP_200_OK)

    if not isinstance(body, dict):
        return Response(status_code=status.HTTP_200_OK)

    try:
        notification = WebhookNotificationFactory().create(body)
    except Exception as e:
        logger.warning("YooKassa webhook: notification parse failed: %s", e)
        return Response(status_code=status.HTTP_200_OK)

    event = getattr(notification, "event", None)

    if event == WebhookNotificationEventType.REFUND_SUCCEEDED:
        logger.info("YooKassa webhook: refund.succeeded received (subscription not changed)")
        return Response(status_code=status.HTTP_200_OK)

    if event not in (
        WebhookNotificationEventType.PAYMENT_SUCCEEDED,
        WebhookNotificationEventType.PAYMENT_WAITING_FOR_CAPTURE,
        WebhookNotificationEventType.PAYMENT_CANCELED,
    ):
        return Response(status_code=status.HTTP_200_OK)

    payment_obj = getattr(notification, "object", None)
    payment_id = str(getattr(payment_obj, "id", "") or "")
    if not payment_id:
        return Response(status_code=status.HTTP_200_OK)

    notification_status = str(getattr(payment_obj, "status", "") or "").strip().lower()

    async with async_session_maker() as session:
        booking_payment_id = await session.scalar(
            select(AdminBookingPayment.id).where(
                AdminBookingPayment.yookassa_payment_id == payment_id,
            )
        )
    if booking_payment_id is not None:
        from ..services.admin_booking.payment_fulfillment import process_admin_booking_yookassa_webhook

        if event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
            await process_admin_booking_yookassa_webhook(
                yookassa_payment_id=payment_id,
                verified_status=notification_status or "succeeded",
            )
        logger.info(
            "YooKassa webhook: admin_booking payment_id=%s event=%s status=%s",
            payment_id,
            event,
            notification_status,
        )
        return Response(status_code=status.HTTP_200_OK)

    _configure_yookassa()
    try:
        payment = await asyncio.to_thread(Payment.find_one, payment_id)
    except Exception:
        logger.exception("YooKassa webhook: Payment.find_one failed for %s", payment_id)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    verified_status = str(getattr(payment, "status", "pending"))

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        website_tx_dao = WebsitePaymentTransactionDAO(session)
        async with session.begin():
            tx = await website_tx_dao.find_for_update_by_payment_id(
                yookassa_payment_id=payment_id
            )
            if not tx:
                logger.info("YooKassa webhook: no local website tx for payment_id=%s", payment_id)
            else:
                await _apply_yookassa_payment_to_subscription(
                    user_dao,
                    agent_dao,
                    tx,
                    verified_status,
                    yookassa_payment=payment,
                )

    return Response(status_code=status.HTTP_200_OK)

