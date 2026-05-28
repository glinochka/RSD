from datetime import datetime

from sqlalchemy import desc, func, select

from ..BaseDAO import BaseDAO
from ..alembic.models import PartnerPromoCode, ReferralCommission, User


class PartnerPromoCodeDAO(BaseDAO):
    model = PartnerPromoCode

    async def find_by_code_case_insensitive(self, normalized_code: str) -> PartnerPromoCode | None:
        query = select(self.model).where(func.upper(self.model.code) == normalized_code)
        return await self._session.scalar(query)

    async def find_active_by_code_case_insensitive(self, normalized_code: str) -> PartnerPromoCode | None:
        query = (
            select(self.model)
            .where(func.upper(self.model.code) == normalized_code)
            .where(self.model.is_active.is_(True))
        )
        return await self._session.scalar(query)

    async def list_for_partner(self, partner_user_id: int) -> list[PartnerPromoCode]:
        query = (
            select(self.model)
            .where(self.model.partner_user_id == partner_user_id)
            .order_by(desc(self.model.created_at), desc(self.model.id))
        )
        return await self.list_scalars(query)

    async def find_owned_by_code(
        self,
        partner_user_id: int,
        normalized_code: str,
    ) -> PartnerPromoCode | None:
        query = (
            select(self.model)
            .where(self.model.partner_user_id == partner_user_id)
            .where(func.upper(self.model.code) == normalized_code)
        )
        return await self._session.scalar(query)


class ReferralCommissionDAO(BaseDAO):
    model = ReferralCommission

    async def count_referrals_for_partner(self, partner_user_id: int) -> int:
        query = select(func.count(User.id)).where(User.referred_by_user_id == partner_user_id)
        return await self.scalar_or_default(query, 0)

    async def sum_commission_for_partner(
        self,
        partner_user_id: int,
        *,
        since: datetime | None = None,
    ) -> int:
        query = select(func.coalesce(func.sum(self.model.commission_amount_kopecks), 0)).where(
            self.model.partner_user_id == partner_user_id
        )
        if since is not None:
            query = query.where(self.model.created_at >= since)
        return int(await self.scalar_or_default(query, 0))

    async def sum_payments_for_referrals(
        self,
        partner_user_id: int,
        *,
        since: datetime | None = None,
    ) -> int:
        query = (
            select(func.coalesce(func.sum(self.model.gross_amount_kopecks), 0))
            .where(self.model.partner_user_id == partner_user_id)
        )
        if since is not None:
            query = query.where(self.model.created_at >= since)
        return int(await self.scalar_or_default(query, 0))

    async def list_recent_for_partner(
        self,
        partner_user_id: int,
        *,
        limit: int = 20,
    ) -> list[ReferralCommission]:
        query = (
            select(self.model)
            .where(self.model.partner_user_id == partner_user_id)
            .order_by(desc(self.model.created_at), desc(self.model.id))
            .limit(limit)
        )
        return await self.list_scalars(query)

    async def timeseries_for_partner(
        self,
        partner_user_id: int,
        *,
        since: datetime,
    ) -> list[tuple]:
        day_expr = func.date(self.model.created_at)
        query = (
            select(
                day_expr,
                func.coalesce(func.sum(self.model.commission_amount_kopecks), 0),
                func.count(self.model.id),
            )
            .where(self.model.partner_user_id == partner_user_id)
            .where(self.model.created_at >= since)
            .group_by(day_expr)
            .order_by(day_expr)
        )
        return await self.list_rows(query)
