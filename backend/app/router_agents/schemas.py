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
    template_type: str = Field(
        default="qa",
        pattern="^(qa|function_calling|lead_generation|content_factory)$",
        description="Тип шаблона агента",
    )


class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")

class User_by_agent_or_tgID(BaseModel):
    id: int = Field(..., description="id")


class NewAgent_byToken(BaseModel):
    bot_token: str = Field(..., min_length=10, max_length=500, description="API token from BotFather")
    system_prompt: str = Field(..., min_length=1, description="System prompt for agent")
    template_type: str = Field(
        default="qa",
        pattern="^(qa|function_calling|lead_generation|content_factory)$",
        description="Тип шаблона агента",
    )


class AgentAIAction(BaseModel):
    bot_id: int = Field(..., description="id бота")


class ExternalAgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Запрос для агента")
    external_user_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Опциональный ID пользователя во внешней системе",
    )
    external_user_name: Optional[str] = Field(
        None,
        max_length=128,
        description="Опциональное имя пользователя во внешней системе",
    )


class AgentAnalyticsMessageLog(BaseModel):
    bot_id: int = Field(..., description="Id бота")
    role: str = Field(..., pattern="^(user|agent)$", description="Роль сообщения")
    channel: str = Field(
        default="telegram",
        pattern="^(telegram|external_api|web|dashboard|telegram_userbot|whatsapp_userbot|whatsapp_business_api|instagram|tiktok|pinterest)$",
        description="Канал сообщения",
    )
    user_external_id: Optional[str] = Field(
        None,
        max_length=128,
        description="ID пользователя во внешнем канале (например, Telegram user id)",
    )
    user_display_name: Optional[str] = Field(
        None,
        max_length=128,
        description="Отображаемое имя пользователя",
    )
    message_text: str = Field(..., min_length=1, max_length=8000, description="Текст сообщения")


class AgentFreezeUserPayload(BaseModel):
    bot_id: int = Field(..., description="Id бота в Telegram")
    user_external_id: str = Field(..., max_length=128, description="Внешний id пользователя (Telegram user id)")
    frozen: bool = Field(default=True, description="True — заморозить, False — снять")


class AgentTelegramSendToUserPayload(BaseModel):
    bot_id: int = Field(..., description="Id бота в Telegram")
    user_external_id: str = Field(..., max_length=128, description="Telegram user id получателя")
    message: str = Field(..., min_length=1, max_length=4096, description="Текст сообщения от владельца")


class AgentTelegramBroadcastPayload(BaseModel):
    bot_id: int = Field(..., description="Id бота в Telegram")
    message: str = Field(..., min_length=1, max_length=4096, description="Текст рассылки от владельца")
    skip_frozen: bool = Field(
        default=True,
        description="Не отправлять пользователям со статусом «заморожен»",
    )
    max_recipients: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Максимум получателей за один запрос (остальные можно добить повтором)",
    )

