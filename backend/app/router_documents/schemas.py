from pydantic import BaseModel, Field
#from typing import Optional

class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")


