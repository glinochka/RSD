from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import joinedload

from ..alembic.models import ApplicationErrorLog, User
from ..BaseDAO import BaseDAO


class ApplicationErrorLogDAO(BaseDAO):
    model = ApplicationErrorLog

    async def count_for_admin(
        self,
        *,
        search_value: str | None = None,
        level: str | None = None,
        source: str | None = None,
        is_resolved: bool | None = None,
    ) -> int:
        query = select(func.count(self.model.id))
        query = self._apply_admin_filters(query, search_value, level, source, is_resolved)
        return await self.scalar_or_default(query, 0)

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search_value: str | None = None,
        level: str | None = None,
        source: str | None = None,
        is_resolved: bool | None = None,
    ) -> list[ApplicationErrorLog]:
        query = (
            select(self.model)
            .options(joinedload(self.model.user))
            .order_by(desc(self.model.created_at), desc(self.model.id))
        )
        query = self._apply_admin_filters(query, search_value, level, source, is_resolved)
        return await self.list_scalars(query, page=page, page_size=page_size)

    async def get_by_id(self, log_id: int) -> ApplicationErrorLog | None:
        query = (
            select(self.model)
            .options(joinedload(self.model.user))
            .where(self.model.id == log_id)
        )
        return await self._session.scalar(query)

    @staticmethod
    def _apply_admin_filters(
        query,
        search_value: str | None,
        level: str | None,
        source: str | None,
        is_resolved: bool | None,
    ):
        if level:
            query = query.where(ApplicationErrorLog.level == level)
        if source:
            query = query.where(ApplicationErrorLog.source == source)
        if is_resolved is not None:
            query = query.where(ApplicationErrorLog.is_resolved.is_(is_resolved))

        if search_value:
            pattern = f"%{search_value}%"
            query = query.outerjoin(User, User.id == ApplicationErrorLog.user_id).where(
                or_(
                    ApplicationErrorLog.scenario.ilike(pattern),
                    ApplicationErrorLog.message.ilike(pattern),
                    ApplicationErrorLog.error_type.ilike(pattern),
                    ApplicationErrorLog.traceback.ilike(pattern),
                    User.name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        return query
