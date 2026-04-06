
from ..alembic.models import Agent, AgentChannelConnection, User
from ..BaseDAO import BaseDAO
from sqlalchemy import String, cast, desc, func, or_, select


class AgentDAO(BaseDAO):
    model = Agent

    async def find_all_by_user_id(self, user_id: int) -> list[Agent]:
        query = select(self.model).where(self.model.user_id == user_id)
        return await self.list_scalars(query)

    async def count_all(self) -> int:
        query = select(func.count(self.model.id))
        return await self.scalar_or_default(query, 0)

    async def count_active(self) -> int:
        query = select(func.count(self.model.id)).where(self.model.is_active.is_(True))
        return await self.scalar_or_default(query, 0)

    async def count_for_admin(self, search_value: str | None = None) -> int:
        query = select(func.count(self.model.id)).join(User, User.id == self.model.user_id)
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.bot_username.ilike(pattern),
                    User.name.ilike(pattern),
                    cast(self.model.bot_id, String).ilike(pattern),
                )
            )
        return await self.scalar_or_default(query, 0)

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search_value: str | None = None,
    ):
        query = (
            select(
                self.model.id,
                self.model.bot_id,
                self.model.bot_username,
                self.model.is_active,
                self.model.registered,
                User.name.label("owner_name"),
                User.subscription_type.label("owner_subscription_type"),
            )
            .join(User, User.id == self.model.user_id)
            .order_by(desc(self.model.registered), desc(self.model.id))
        )
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.bot_username.ilike(pattern),
                    User.name.ilike(pattern),
                    cast(self.model.bot_id, String).ilike(pattern),
                )
            )
        return await self.list_rows(query, page=page, page_size=page_size)


class AgentChannelConnectionDAO(BaseDAO):
    model = AgentChannelConnection
