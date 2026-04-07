from sqlalchemy import desc, func, or_, select

from ..BaseDAO import BaseDAO
from ..alembic.models import (
    PaymentTransaction,
    PromoCode,
    TurnkeyAgentRequest,
    WebsitePaymentTransaction,
)


class PaymentTransactionDAO(BaseDAO):
    model = PaymentTransaction

    async def exists_by_telegram_charge_id(self, telegram_payment_charge_id: str) -> bool:
        query = (
            select(self.model.id)
            .where(self.model.telegram_payment_charge_id == telegram_payment_charge_id)
            .limit(1)
        )
        return (await self._session.scalar(query)) is not None

    async def count_all(self) -> int:
        query = select(func.count(self.model.id))
        return await self.scalar_or_default(query, 0)


class WebsitePaymentTransactionDAO(BaseDAO):
    model = WebsitePaymentTransaction

    async def find_for_update_by_payment_id(
        self,
        yookassa_payment_id: str,
        user_id: int | None = None,
    ) -> WebsitePaymentTransaction | None:
        query = select(self.model).where(self.model.yookassa_payment_id == yookassa_payment_id)
        if user_id is not None:
            query = query.where(self.model.user_id == user_id)
        query = query.with_for_update()
        return await self._session.scalar(query)


class PromoCodeDAO(BaseDAO):
    model = PromoCode

    async def find_by_code_case_insensitive(self, normalized_code: str) -> PromoCode | None:
        query = select(self.model).where(func.upper(self.model.code) == normalized_code)
        return await self._session.scalar(query)

    async def list_all_desc(self) -> list[PromoCode]:
        query = select(self.model).order_by(self.model.created_at.desc(), self.model.id.desc())
        return await self.list_scalars(query)


class TurnkeyAgentRequestDAO(BaseDAO):
    model = TurnkeyAgentRequest

    async def count_for_admin(self, search_value: str | None = None) -> int:
        query = select(func.count(self.model.id))
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.phone_number.ilike(pattern),
                    self.model.email.ilike(pattern),
                    self.model.requested_agent.ilike(pattern),
                    self.model.purpose.ilike(pattern),
                )
            )
        return await self.scalar_or_default(query, 0)

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search_value: str | None = None,
    ) -> list[TurnkeyAgentRequest]:
        query = (
            select(self.model)
            .order_by(desc(self.model.created_at), desc(self.model.id))
        )
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.phone_number.ilike(pattern),
                    self.model.email.ilike(pattern),
                    self.model.requested_agent.ilike(pattern),
                    self.model.purpose.ilike(pattern),
                )
            )
        return await self.list_scalars(query, page=page, page_size=page_size)

