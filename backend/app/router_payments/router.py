from datetime import datetime, timedelta, timezone
from logging import getLogger
import asyncio
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select
from yookassa import Configuration, Payment
from yookassa.domain.notification.webhook_notification import WebhookNotificationFactory
from yookassa.domain.notification.webhook_notification_types import WebhookNotificationEventType
from yookassa.domain.exceptions import NotFoundError
from ..alembic.database import async_session_maker
from ..alembic.models import PaymentTransaction, PromoCode, TurnkeyAgentRequest, WebsitePaymentTransaction
from ..config import settings
from ..router_users.dao import UserDAO
from ..subscription_plans import (
    get_all_subscription_plans,
    get_subscription_plan,
)
from ..utils.internal_auth import verify_internal_key
from ..utils.JWT import get_user_from_access_token
from .schemas import (
    CreateTurnkeyAgentRequest,
    CreateYooKassaPayment,
    ProcessTelegramPayment,
    YooKassaPaymentStatusResponse,
)

logger = getLogger(__name__)
router = APIRouter(prefix="/api/payments")
http_bearer = HTTPBearer(auto_error=False)


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


def _calculate_new_end_date(current_end_date) -> datetime:
    now_utc = datetime.now(timezone.utc)
    base_date = now_utc
    if current_end_date:
        if current_end_date.tzinfo is None:
            current_end = current_end_date.replace(tzinfo=timezone.utc)
        else:
            current_end = current_end_date.astimezone(timezone.utc)
        if current_end > now_utc:
            base_date = current_end
    return (base_date + timedelta(days=30)).replace(tzinfo=None)


def _normalize_promo_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


async def _apply_yookassa_payment_to_subscription(
    user_dao: UserDAO,
    tx: WebsitePaymentTransaction,
    payment_status: str,
) -> None:
    """Update stored status and extend subscription once when payment succeeds."""
    tx.status = payment_status
    if payment_status != "succeeded" or tx.is_processed:
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

    new_end_date = _calculate_new_end_date(user.subscription_end_date)
    await user_dao.update(
        user,
        {
            "subscription_type": tx.plan_name,
            "subscription_end_date": new_end_date,
        },
    )
    tx.is_processed = True
    tx.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/plans")
async def get_subscription_plans():
    return JSONResponse(
        content={"plans": get_all_subscription_plans()},
        status_code=status.HTTP_200_OK,
    )


@router.post("/turnkey-requests")
async def create_turnkey_request(payload: CreateTurnkeyAgentRequest):
    async with async_session_maker() as session:
        async with session.begin():
            session.add(
                TurnkeyAgentRequest(
                    phone_number=payload.phone_number,
                    email=payload.email,
                    requested_agent=payload.requested_agent,
                    purpose=payload.purpose,
                )
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
    now_utc = datetime.now(timezone.utc)

    try:
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            async with session.begin():
                existing_tx = await session.scalar(
                    select(PaymentTransaction.id).where(
                        PaymentTransaction.telegram_payment_charge_id == payload.telegram_payment_charge_id
                    )
                )
                if existing_tx:
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
                session.add(
                    PaymentTransaction(
                        telegram_id=payload.telegram_id,
                        plan_name=payload.plan_name,
                        currency=payload.currency,
                        total_amount=payload.total_amount,
                        telegram_payment_charge_id=payload.telegram_payment_charge_id,
                        provider_payment_charge_id=payload.provider_payment_charge_id,
                        invoice_payload=payload.invoice_payload,
                    )
                )
                await session.flush()

                base_date = now_utc
                if user.subscription_end_date:
                    current_end = user.subscription_end_date
                    if current_end.tzinfo is None:
                        current_end = current_end.replace(tzinfo=timezone.utc)
                    else:
                        current_end = current_end.astimezone(timezone.utc)
                    if current_end > now_utc:
                        base_date = current_end

                selected_plan = get_subscription_plan(payload.plan_name)
                if not selected_plan or not selected_plan.get("is_paid"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid paid plan",
                    )

                new_end_date = (base_date + timedelta(days=30)).replace(tzinfo=None)
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

    original_amount_kopecks = int(selected_plan.get("price_rub_month", 0) or 0) * 100
    normalized_promo = _normalize_promo_code(payload.promo_code)
    applied_discount_percent = 0
    applied_promo_code = None

    if normalized_promo:
        async with async_session_maker() as session:
            promo = await session.scalar(
                select(PromoCode).where(func.upper(PromoCode.code) == normalized_promo)
            )
        if not promo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promo code not found",
            )
        applied_discount_percent = int(promo.discount_percent or 0)
        applied_promo_code = promo.code

    discount_kopecks = (original_amount_kopecks * applied_discount_percent) // 100
    amount_kopecks = max(0, original_amount_kopecks - discount_kopecks)

    # 100% promo flow: activate subscription without external payment gateway.
    if amount_kopecks == 0:
        async with async_session_maker() as session:
            user_dao = UserDAO(session)
            async with session.begin():
                user = await user_dao.find_one_by_filter(id=current_user.id)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )

                new_end_date = _calculate_new_end_date(user.subscription_end_date)
                await user_dao.update(
                    user,
                    {
                        "subscription_type": payload.plan_name,
                        "subscription_end_date": new_end_date,
                    },
                )
                session.add(
                    WebsitePaymentTransaction(
                        user_id=current_user.id,
                        plan_name=payload.plan_name,
                        currency="RUB",
                        total_amount=0,
                        original_total_amount=original_amount_kopecks,
                        discount_percent=applied_discount_percent,
                        promo_code=applied_promo_code,
                        yookassa_payment_id=f"promo-{uuid4()}",
                        status="succeeded",
                        is_processed=True,
                        paid_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )

        return JSONResponse(
            content={
                "payment_id": None,
                "status": "succeeded",
                "confirmation_url": None,
                "plan_name": payload.plan_name,
                "promo_code": applied_promo_code,
                "discount_percent": applied_discount_percent,
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
                "description": f"Подписка {selected_plan.get('title', payload.plan_name)} на 30 дней",
                "metadata": {
                    "user_id": str(current_user.id),
                    "plan_name": payload.plan_name,
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
        async with session.begin():
            session.add(
                WebsitePaymentTransaction(
                    user_id=current_user.id,
                    plan_name=payload.plan_name,
                    currency="RUB",
                    total_amount=amount_kopecks,
                    original_total_amount=original_amount_kopecks,
                    discount_percent=applied_discount_percent,
                    promo_code=applied_promo_code,
                    yookassa_payment_id=payment_id,
                    status=payment_status,
                )
            )

    return JSONResponse(
        content={
            "payment_id": payment_id,
            "status": payment_status,
            "confirmation_url": confirmation_url,
            "plan_name": payload.plan_name,
            "promo_code": applied_promo_code,
            "discount_percent": applied_discount_percent,
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
        async with session.begin():
            tx = await session.scalar(
                select(WebsitePaymentTransaction)
                .where(
                    WebsitePaymentTransaction.yookassa_payment_id == payment_id,
                    WebsitePaymentTransaction.user_id == current_user.id,
                )
                .with_for_update(),
            )
            if not tx:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found",
                )

            await _apply_yookassa_payment_to_subscription(user_dao, tx, payment_status)

            user = await user_dao.find_one_by_filter(id=current_user.id)
            return YooKassaPaymentStatusResponse(
                payment_id=payment_id,
                status=payment_status,
                plan_name=tx.plan_name,
                subscription_type=user.subscription_type if user else None,
                subscription_end_date=user.subscription_end_date.isoformat()
                if user and user.subscription_end_date
                else None,
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

    _configure_yookassa()
    try:
        payment = await asyncio.to_thread(Payment.find_one, payment_id)
    except Exception:
        logger.exception("YooKassa webhook: Payment.find_one failed for %s", payment_id)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    verified_status = str(getattr(payment, "status", "pending"))

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        async with session.begin():
            tx = await session.scalar(
                select(WebsitePaymentTransaction)
                .where(WebsitePaymentTransaction.yookassa_payment_id == payment_id)
                .with_for_update(),
            )
            if not tx:
                logger.info("YooKassa webhook: no local website tx for payment_id=%s", payment_id)
            else:
                await _apply_yookassa_payment_to_subscription(user_dao, tx, verified_status)

    return Response(status_code=status.HTTP_200_OK)

