"""Partner balance and payout request rules."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..router_referrals.dao import PartnerPayoutRequestDAO, ReferralCommissionDAO

MIN_PAYOUT_KOPECKS = 10_000  # 100 ₽
MIN_PAYOUT_RUB = MIN_PAYOUT_KOPECKS // 100

PAYOUT_STATUS_PENDING = "pending"
PAYOUT_STATUS_APPROVED = "approved"
PAYOUT_STATUS_PAID = "paid"
PAYOUT_STATUS_REJECTED = "rejected"

ACTIVE_PAYOUT_STATUSES = (PAYOUT_STATUS_PENDING, PAYOUT_STATUS_APPROVED)


async def get_partner_balance_kopecks(session: AsyncSession, partner_user_id: int) -> dict:
    commission_dao = ReferralCommissionDAO(session)
    payout_dao = PartnerPayoutRequestDAO(session)

    earned_kopecks = await commission_dao.sum_commission_for_partner(partner_user_id)
    reserved_kopecks = await payout_dao.sum_amount_by_statuses(
        partner_user_id,
        ACTIVE_PAYOUT_STATUSES,
    )
    withdrawn_kopecks = await payout_dao.sum_amount_by_statuses(
        partner_user_id,
        (PAYOUT_STATUS_PAID,),
    )
    available_kopecks = max(0, earned_kopecks - reserved_kopecks - withdrawn_kopecks)

    return {
        "earned_kopecks": earned_kopecks,
        "reserved_kopecks": reserved_kopecks,
        "withdrawn_kopecks": withdrawn_kopecks,
        "available_kopecks": available_kopecks,
        "min_payout_kopecks": MIN_PAYOUT_KOPECKS,
        "min_payout_rub": MIN_PAYOUT_RUB,
    }
