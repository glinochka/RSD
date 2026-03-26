from datetime import datetime, timedelta, timezone
from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from ..alembic.database import async_session_maker
from ..alembic.models import PaymentTransaction
from ..router_users.dao import UserDAO
from ..utils.internal_auth import verify_internal_key
from .schemas import ProcessTelegramPayment

logger = getLogger(__name__)
router = APIRouter(prefix="/api/payments")


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

