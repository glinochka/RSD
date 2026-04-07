from ..alembic.models import AgentDocument, ReindexJob
from ..BaseDAO import BaseDAO
from sqlalchemy import func, select


class DocumentDAO(BaseDAO):
    model = AgentDocument

    async def find_by_agent_and_content_hash(
        self,
        agent_id: int,
        content_hash: str,
        embedding_profile_key: str | None = None,
    ) -> AgentDocument | None:
        query = select(self.model).where(
            self.model.agent_id == agent_id,
            self.model.content_hash == content_hash,
        )
        if embedding_profile_key:
            query = query.where(self.model.embedding_profile_key == embedding_profile_key)
        return await self._session.scalar(query)

    async def count_all(self) -> int:
        query = select(func.count(self.model.id))
        return await self.scalar_or_default(query, 0)

    async def count_ready_for_reindex(self, agent_pk: int, target_profile_key: str) -> int:
        query = select(func.count(self.model.id)).where(
            self.model.agent_id == agent_pk,
            self.model.status == "ready",
            self.model.embedding_profile_key != target_profile_key,
        )
        return await self.scalar_or_default(query, 0)

    async def list_ready_for_reindex_batch(
        self,
        *,
        agent_pk: int,
        target_profile_key: str,
        cursor: int,
        limit: int,
    ) -> list[AgentDocument]:
        query = (
            select(self.model)
            .where(
                self.model.agent_id == agent_pk,
                self.model.status == "ready",
                self.model.embedding_profile_key != target_profile_key,
                self.model.id > cursor,
            )
            .order_by(self.model.id.asc())
            .limit(limit)
        )
        return await self.list_scalars(query)


class ReindexJobDAO(BaseDAO):
    model = ReindexJob

    async def claim_next_pending(self) -> ReindexJob | None:
        query = (
            select(self.model)
            .where(self.model.status.in_(["queued", "retrying"]))
            .order_by(self.model.created_at.asc(), self.model.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        return await self._session.scalar(query)

    async def list_by_agent(self, agent_pk: int) -> list[ReindexJob]:
        query = (
            select(self.model)
            .where(self.model.agent_id == agent_pk)
            .order_by(self.model.created_at.desc(), self.model.id.desc())
        )
        return await self.list_scalars(query)
