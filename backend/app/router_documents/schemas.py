from pydantic import BaseModel, Field

class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")

class Context_by_botID(BaseModel):
    agent_id: int = Field(..., description="id бота")
    query: str = Field(..., description="запрос для qdrant")

