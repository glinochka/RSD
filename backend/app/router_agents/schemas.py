from pydantic import BaseModel, Field
from typing import Optional

class UpdateAgent(BaseModel):
    name: Optional[str]  = Field(None, min_length=3, max_length=100, description="Имя агента: длина от 3 до 30 символов")
    bot_id: int = Field(..., description="Id бота")
    system_prompt: Optional[str] = Field(None, description="Промпт")
    welcome_message: Optional[str] = Field(None, min_length=3, description="Начальное сообщение бота: длина от 3 символов")

class NewAgent_byUserWith_tgID(BaseModel):
    tg_id: int = Field(..., description="tg id")
    bot_id: int = Field(..., description="bot id from telegram")
    bot_username: str = Field(..., min_length=3, max_length=100, description="Имя агента: длина от 3 до 30 символов")
    encrypted_token: str = Field(..., min_length=3, max_length=500, description="Зашифрованный токен бота")

    system_prompt: Optional[str] = Field(None,description="Промпт")
    welcome_message: Optional[str] = Field(None,min_length=3, description="Начальное сообщение бота: длина от 3 символов")


class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")

class User_by_agent_or_tgID(BaseModel):
    id: int = Field(..., description="id")


class NewAgent_byToken(BaseModel):
    bot_token: str = Field(..., min_length=10, max_length=500, description="API token from BotFather")
    system_prompt: str = Field(..., min_length=1, description="System prompt for agent")


class AgentAIAction(BaseModel):
    bot_id: int = Field(..., description="id бота")

