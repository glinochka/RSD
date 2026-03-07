from ..alembic.models import AgentDocument
from ..BaseDAO import BaseDAO


class DocumentDAO(BaseDAO):
    model = AgentDocument
