from ..alembic.models import TelegramLinkChallenge, User, UserErrorReport
from ..BaseDAO import BaseDAO
from sqlalchemy import String, cast, desc, func, or_, select
from sqlalchemy.orm import joinedload


class UserDAO(BaseDAO):
    model = User

    async def find_telegram_user_by_normalized_name(self, normalized_name: str) -> User | None:
        query = select(self.model).where(
            func.lower(self.model.name) == normalized_name,
            self.model.telegram_id.is_not(None),
        )
        return await self._session.scalar(query)

    async def count_for_admin(self, search_value: str | None = None) -> int:
        query = select(func.count(self.model.id))
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.name.ilike(pattern),
                    self.model.email.ilike(pattern),
                    cast(self.model.telegram_id, String).ilike(pattern),
                )
            )
        return await self.scalar_or_default(query, 0)

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search_value: str | None = None,
    ) -> list[User]:
        query = (
            select(self.model)
            .order_by(desc(self.model.registered), desc(self.model.id))
        )
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.name.ilike(pattern),
                    self.model.email.ilike(pattern),
                    cast(self.model.telegram_id, String).ilike(pattern),
                )
            )
        return await self.list_scalars(query, page=page, page_size=page_size)

    async def count_by_subscription_type(self, subscription_type: str) -> int:
        query = select(func.count(self.model.id)).where(self.model.subscription_type == subscription_type)
        return await self.scalar_or_default(query, 0)

    async def count_paid_users(self) -> int:
        query = select(func.count(self.model.id)).where(self.model.subscription_type != "Free")
        return await self.scalar_or_default(query, 0)

class TelegramLinkChallengeDAO(BaseDAO):
    model = TelegramLinkChallenge

    async def find_pending_by_code_and_target(
        self,
        code_hash: str,
        target_telegram_id: int,
    ) -> TelegramLinkChallenge | None:
        query = (
            select(self.model)
            .where(
                self.model.code_hash == code_hash,
                self.model.status == "pending",
                self.model.target_telegram_id == target_telegram_id,
            )
            .order_by(desc(self.model.id))
            .limit(1)
        )
        return await self._session.scalar(query)

    async def find_latest_pending_by_target_telegram_id(
        self,
        target_telegram_id: int,
    ) -> TelegramLinkChallenge | None:
        query = (
            select(self.model)
            .where(
                self.model.target_telegram_id == target_telegram_id,
                self.model.status == "pending",
            )
            .order_by(desc(self.model.id))
            .limit(1)
        )
        return await self._session.scalar(query)

    async def find_pending_by_user_id(self, user_id: int) -> list[TelegramLinkChallenge]:
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == "pending",
        )
        result = await self._session.scalars(query)
        return result.all()

    async def find_pending_by_user_id_except(
        self,
        user_id: int,
        challenge_id: int,
    ) -> list[TelegramLinkChallenge]:
        query = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == "pending",
            self.model.id != challenge_id,
        )
        result = await self._session.scalars(query)
        return result.all()


class UserErrorReportDAO(BaseDAO):
    model = UserErrorReport

    async def count_for_admin(self, search_value: str | None = None) -> int:
        query = select(func.count(self.model.id))
        if search_value:
            pattern = f"%{search_value}%"
            query = (
                select(func.count(self.model.id))
                .select_from(self.model)
                .join(User, User.id == self.model.user_id)
                .where(
                    or_(
                        self.model.description.ilike(pattern),
                        User.name.ilike(pattern),
                        User.email.ilike(pattern),
                    )
                )
            )
        return await self.scalar_or_default(query, 0)

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search_value: str | None = None,
    ) -> list[UserErrorReport]:
        query = (
            select(self.model)
            .options(joinedload(self.model.user))
            .order_by(desc(self.model.created_at), desc(self.model.id))
        )
        if search_value:
            pattern = f"%{search_value}%"
            query = query.join(User).where(
                or_(
                    self.model.description.ilike(pattern),
                    User.name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        return await self.list_scalars(query, page=page, page_size=page_size)
