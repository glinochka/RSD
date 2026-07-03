from sqlalchemy import func, select

from ..alembic.models import ProjectDocument
from ..BaseDAO import BaseDAO


class ProjectDocumentDAO(BaseDAO):
    model = ProjectDocument

    async def find_by_project_and_content_hash(
        self,
        project_id: int,
        content_hash: str,
        embedding_profile_key: str | None = None,
    ) -> ProjectDocument | None:
        query = select(self.model).where(
            self.model.project_id == project_id,
            self.model.content_hash == content_hash,
        )
        if embedding_profile_key:
            query = query.where(self.model.embedding_profile_key == embedding_profile_key)
        return await self._session.scalar(query)

    async def count_by_project(self, project_id: int) -> int:
        query = select(func.count(self.model.id)).where(
            self.model.project_id == project_id,
        )
        return await self.scalar_or_default(query, 0)
