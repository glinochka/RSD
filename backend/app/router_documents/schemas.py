from pydantic import BaseModel, Field

class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")

