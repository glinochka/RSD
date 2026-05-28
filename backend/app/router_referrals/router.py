from logging import getLogger

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError

from ..alembic.database import async_session_maker
from ..router_payments.dao import PromoCodeDAO
from ..router_users.dao import UserDAO
from ..services.referral import (
    PARTNER_BASE_COMMISSION_PERCENT,
    compute_partner_commission_percent,
    default_stats_period_start,
    ensure_user_referral_code,
)
from ..utils.JWT import get_user_from_access_token
from .dao import PartnerPromoCodeDAO, ReferralCommissionDAO
from .schemas import PartnerPromoCodeCreateRequest, PartnerPromoCodePatchRequest

logger = getLogger(__name__)

router = APIRouter(prefix="/api/referrals")
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


def _serialize_partner_promo(item) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "discount_percent": int(item.discount_percent or 0),
        "partner_commission_percent": compute_partner_commission_percent(item.discount_percent),
        "is_active": bool(item.is_active),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_commission(item) -> dict:
    return {
        "id": item.id,
        "buyer_user_id": item.buyer_user_id,
        "gross_amount_kopecks": item.gross_amount_kopecks,
        "commission_percent": item.commission_percent,
        "commission_amount_kopecks": item.commission_amount_kopecks,
        "promo_code": item.promo_code,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/partner/dashboard")
async def partner_dashboard(current_user=Depends(get_current_user_required)):
    period_start = default_stats_period_start(30)
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        promo_dao = PartnerPromoCodeDAO(session)
        commission_dao = ReferralCommissionDAO(session)
        async with session.begin():
            user = await user_dao.find_one_by_filter(id=current_user.id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

            referral_code = await ensure_user_referral_code(user_dao, user)
            referrals_total = await commission_dao.count_referrals_for_partner(user.id)
            commission_total_kopecks = await commission_dao.sum_commission_for_partner(user.id)
            commission_period_kopecks = await commission_dao.sum_commission_for_partner(
                user.id,
                since=period_start,
            )
            payments_period_kopecks = await commission_dao.sum_payments_for_referrals(
                user.id,
                since=period_start,
            )
            promo_codes = await promo_dao.list_for_partner(user.id)
            recent_commissions = await commission_dao.list_recent_for_partner(user.id, limit=15)
            timeseries_rows = await commission_dao.timeseries_for_partner(user.id, since=period_start)

    timeseries = [
        {
            "date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]),
            "commission_kopecks": int(row[1] or 0),
            "payments_count": int(row[2] or 0),
        }
        for row in timeseries_rows
    ]

    return JSONResponse(
        content={
            "referral_code": referral_code,
            "base_commission_percent": PARTNER_BASE_COMMISSION_PERCENT,
            "max_promo_discount_percent": 50,
            "stats": {
                "referrals_total": referrals_total,
                "commission_total_kopecks": commission_total_kopecks,
                "commission_period_kopecks": commission_period_kopecks,
                "payments_period_kopecks": payments_period_kopecks,
                "period_days": 30,
            },
            "promo_codes": [_serialize_partner_promo(row) for row in promo_codes],
            "recent_commissions": [_serialize_commission(row) for row in recent_commissions],
            "timeseries": timeseries,
        },
        status_code=status.HTTP_200_OK,
    )


@router.post("/partner/promo-codes")
async def create_partner_promo_code(
    payload: PartnerPromoCodeCreateRequest,
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        promo_dao = PartnerPromoCodeDAO(session)
        async with session.begin():
            owner = await user_dao.find_one_by_filter(id=current_user.id)
            if not owner:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            await ensure_user_referral_code(user_dao, owner)
            admin_promo_dao = PromoCodeDAO(session)
            if await promo_dao.find_by_code_case_insensitive(payload.code):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Промокод уже используется",
                )
            if await admin_promo_dao.find_by_code_case_insensitive(payload.code):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Промокод уже используется",
                )
            try:
                item = await promo_dao.add(
                    {
                        "partner_user_id": current_user.id,
                        "code": payload.code,
                        "discount_percent": payload.discount_percent,
                        "is_active": True,
                    }
                )
            except IntegrityError:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Промокод уже существует",
                )

    return JSONResponse(
        content={"item": _serialize_partner_promo(item)},
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/partner/promo-codes/{promo_code_id}")
async def patch_partner_promo_code(
    payload: PartnerPromoCodePatchRequest,
    promo_code_id: int = Path(..., ge=1),
    current_user=Depends(get_current_user_required),
):
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    async with async_session_maker() as session:
        promo_dao = PartnerPromoCodeDAO(session)
        async with session.begin():
            item = await promo_dao.find_one_by_filter(id=promo_code_id, partner_user_id=current_user.id)
            if not item:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
            await promo_dao.update(item, update_data)

    return JSONResponse(
        content={"item": _serialize_partner_promo(item)},
        status_code=status.HTTP_200_OK,
    )


@router.delete("/partner/promo-codes/{promo_code_id}")
async def delete_partner_promo_code(
    promo_code_id: int = Path(..., ge=1),
    current_user=Depends(get_current_user_required),
):
    async with async_session_maker() as session:
        promo_dao = PartnerPromoCodeDAO(session)
        async with session.begin():
            item = await promo_dao.find_one_by_filter(id=promo_code_id, partner_user_id=current_user.id)
            if not item:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Промокод не найден")
            await promo_dao.delete(item)

    return JSONResponse(content={"detail": "Промокод удалён"}, status_code=status.HTTP_200_OK)
