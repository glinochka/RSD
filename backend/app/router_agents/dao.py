
from ..alembic.models import Agent, AgentDocument
from ..BaseDAO import BaseDAO


class AgentDAO(BaseDAO):
    model = Agent

class AgentDocumentDAO(BaseDAO):
    model = AgentDocument