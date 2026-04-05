from pydantic import BaseModel, Field

class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")


class PublicLinkSource(BaseModel):
    bot_id: int = Field(..., description="id бота")
    url: str = Field(..., description="Публичная ссылка (http/https)")

