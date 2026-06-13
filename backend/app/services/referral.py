"""Referral / partner program: attribution, promo codes, commissions."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from logging import getLogger

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..alembic.models import PartnerPromoCode, ReferralCommission, User, WebsitePaymentTransaction
from ..router_users.dao import UserDAO

logger = getLogger(__name__)

PARTNER_BASE_COMMISSION_PERCENT = 50
MAX_PARTNER_PROMO_DISCOUNT_PERCENT = 50
REFERRAL_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REFERRAL_CODE_LENGTH = 8


def normalize_referral_code(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.strip().upper() if ch.isalnum())
    return cleaned or None


def normalize_promo_code(value: str | None) -> str | None:
    return normalize_referral_code(value)


def generate_referral_code() -> str:
    return "".join(secrets.choice(REFERRAL_CODE_ALPHABET) for _ in range(REFERRAL_CODE_LENGTH))


def compute_partner_commission_percent(partner_promo_discount_percent: int) -> int:
    discount = min(MAX_PARTNER_PROMO_DISCOUNT_PERCENT, max(0, int(partner_promo_discount_percent or 0)))
    return max(0, PARTNER_BASE_COMMISSION_PERCENT - discount)


def compute_commission_kopecks(*, gross_kopecks: int, commission_percent: int) -> int:
    if gross_kopecks <= 0 or commission_percent <= 0:
        return 0
    return (int(gross_kopecks) * int(commission_percent)) // 100


async def ensure_user_referral_code(user_dao: UserDAO, user: User) -> str:
    existing = normalize_referral_code(getattr(user, "referral_code", None))
    if existing:
        return existing

    for _ in range(12):
        candidate = generate_referral_code()
        conflict = await user_dao.find_one_by_filter(referral_code=candidate)
        if conflict and conflict.id != user.id:
            continue
        await user_dao.update(user, {"referral_code": candidate})
        return candidate

    raise RuntimeError("Failed to allocate referral code")


async def resolve_referrer_user_id(
    user_dao: UserDAO,
    referral_code: str | None,
    *,
    exclude_user_id: int | None = None,
) -> int | None:
    normalized = normalize_referral_code(referral_code)
    if not normalized:
        return None

    partner = await user_dao.find_one_by_filter(referral_code=normalized)
    if not partner:
        return None
    if exclude_user_id is not None and partner.id == exclude_user_id:
        return None
    return partner.id


async def attach_referrer_by_partner_id(
    user_dao: UserDAO,
    user: User,
    partner_user_id: int | None,
) -> bool:
    """Bind user to a single partner (first touch). Returns True if newly attached."""
    if not partner_user_id or partner_user_id == user.id:
        return False
    if getattr(user, "referred_by_user_id", None):
        return False

    await user_dao.update(user, {"referred_by_user_id": partner_user_id})
    await ensure_user_referral_code(user_dao, user)
    return True


async def attach_referrer_on_signup(
    user_dao: UserDAO,
    user: User,
    referral_code: str | None,
) -> bool:
    referrer_id = await resolve_referrer_user_id(
        user_dao,
        referral_code,
        exclude_user_id=user.id,
    )
    return await attach_referrer_by_partner_id(user_dao, user, referrer_id)


async def record_referral_commission_for_transaction(
    session: AsyncSession,
    user_dao: UserDAO,
    tx: WebsitePaymentTransaction,
) -> ReferralCommission | None:
    """Create commission row once per successful website payment."""
    existing = await session.scalar(
        select(ReferralCommission.id).where(
            ReferralCommission.website_payment_transaction_id == tx.id
        )
    )
    if existing is not None:
        return None

    buyer = await user_dao.find_one_by_filter(id=tx.user_id)
    if not buyer:
        return None

    await attach_referrer_by_partner_id(
        user_dao,
        buyer,
        getattr(tx, "partner_user_id", None),
    )
    buyer = await user_dao.find_one_by_filter(id=tx.user_id)
    if not buyer:
        return None

    tx_partner_id = getattr(tx, "partner_user_id", None)
    partner_discount = int(getattr(tx, "partner_promo_discount_percent", 0) or 0)
    assigned_partner_id = getattr(buyer, "referred_by_user_id", None)

    partner_user_id = assigned_partner_id or tx_partner_id
    if not partner_user_id or partner_user_id == buyer.id:
        return None

    promo_matches_assigned_partner = (
        tx_partner_id is not None and tx_partner_id == partner_user_id
    )
    if promo_matches_assigned_partner and partner_discount > 0:
        commission_percent = compute_partner_commission_percent(partner_discount)
        gross_kopecks = int(tx.original_total_amount or tx.total_amount or 0)
        promo_code = tx.promo_code
    else:
        commission_percent = PARTNER_BASE_COMMISSION_PERCENT
        gross_kopecks = int(tx.total_amount or 0)
        promo_code = tx.promo_code if promo_matches_assigned_partner else None

    commission_kopecks = compute_commission_kopecks(
        gross_kopecks=gross_kopecks,
        commission_percent=commission_percent,
    )
    if commission_kopecks <= 0:
        return None

    row = ReferralCommission(
        partner_user_id=partner_user_id,
        buyer_user_id=buyer.id,
        website_payment_transaction_id=tx.id,
        gross_amount_kopecks=gross_kopecks,
        commission_percent=commission_percent,
        commission_amount_kopecks=commission_kopecks,
        promo_code=promo_code,
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        logger.warning(
            "Duplicate referral commission skipped for payment tx id=%s",
            tx.id,
        )
        return None
    return row


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def default_stats_period_start(days: int = 30) -> datetime:
    return _utc_now_naive() - timedelta(days=days)
