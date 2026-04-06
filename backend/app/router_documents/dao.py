from ..alembic.models import AgentDocument
from ..BaseDAO import BaseDAO
from sqlalchemy import func, select


class DocumentDAO(BaseDAO):
    model = AgentDocument

    async def find_by_agent_and_content_hash(self, agent_id: int, content_hash: str) -> AgentDocument | None:
        query = select(self.model).where(
            self.model.agent_id == agent_id,
            self.model.content_hash == content_hash,
        )
        return await self._session.scalar(query)

    async def count_all(self) -> int:
        query = select(func.count(self.model.id))
        return await self.scalar_or_default(query, 0)
