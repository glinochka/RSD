from pydantic import BaseModel, Field, model_validator
from typing import Optional


class AgentLookup(BaseModel):
    agent_id: Optional[int] = Field(None, gt=0, description="Внутренний id агента")
    bot_id: Optional[int] = Field(None, description="Legacy id (Telegram id канала)")

    @model_validator(mode="after")
    def validate_lookup(self):
        if self.agent_id is None and self.bot_id is None:
            raise ValueError("Either agent_id or bot_id is required")
        return self


class UpdateAgent(AgentLookup):
    name: Optional[str]  = Field(None, min_length=3, max_length=100, description="Имя агента: длина от 3 до 30 символов")
    system_prompt: Optional[str] = Field(None, description="Промпт")
    welcome_message: Optional[str] = Field(None, min_length=3, description="Начальное сообщение бота: длина от 3 символов")
    template_type: Optional[str] = Field(
        None,
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )

class NewAgent_byUserWith_tgID(BaseModel):
    tg_id: int = Field(..., description="tg id")
    bot_id: int = Field(..., description="bot id from telegram")
    bot_username: str = Field(..., min_length=3, max_length=100, description="Имя агента: длина от 3 до 30 символов")
    encrypted_token: str = Field(..., min_length=3, max_length=65535, description="Зашифрованный токен бота")

    system_prompt: Optional[str] = Field(None,description="Промпт")
    welcome_message: Optional[str] = Field(None,min_length=3, description="Начальное сообщение бота: длина от 3 символов")
    template_type: str = Field(
        default="qa",
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )


class Agent_by_botID(AgentLookup):
    pass

class User_by_agent_or_tgID(BaseModel):
    id: int = Field(..., description="id")


class NewAgent_byToken(BaseModel):
    bot_token: str = Field(..., min_length=10, max_length=500, description="API token from BotFather")
    system_prompt: str = Field(..., min_length=1, description="System prompt for agent")
    template_type: str = Field(
        default="qa",
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )


class NewAgent_byUserbotSession(BaseModel):
    api_id: int = Field(..., gt=0, description="Telegram API ID from my.telegram.org")
    api_hash: str = Field(..., min_length=16, max_length=128, description="Telegram API hash")
    session_string: str = Field(..., min_length=10, max_length=65535, description="Telethon StringSession")
    system_prompt: str = Field(..., min_length=1, description="System prompt for agent")
    template_type: str = Field(
        default="qa",
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )


class CreateEmptyAgent(BaseModel):
    system_prompt: Optional[str] = Field(default="Ты — полезный ассистент.", min_length=1, description="System prompt for agent")
    template_type: str = Field(
        default="qa",
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )


class AgentChannelsByBotId(AgentLookup):
    pass


class AddTelegramBotChannel(AgentLookup):
    bot_token: str = Field(..., min_length=10, max_length=500, description="API token from BotFather")
    make_primary: bool = Field(default=False, description="Сделать канал основным")


class AddTelegramUserbotChannel(AgentLookup):
    api_id: int = Field(..., gt=0, description="Telegram API ID from my.telegram.org")
    api_hash: str = Field(..., min_length=16, max_length=128, description="Telegram API hash")
    session_string: str = Field(..., min_length=10, max_length=65535, description="Telethon StringSession")
    make_primary: bool = Field(default=False, description="Сделать канал основным")


class AddWhatsAppBusinessApiChannel(AgentLookup):
    phone_number_id: str = Field(
        ...,
        min_length=3,
        max_length=128,
        description="Phone Number ID из Meta WhatsApp Business API",
    )
    access_token: str = Field(
        ...,
        min_length=10,
        max_length=4096,
        description="Постоянный access token для WhatsApp Business API",
    )
    business_account_id: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=128,
        description="Опциональный WhatsApp Business Account ID",
    )
    verify_token: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=255,
        description="Опциональный verify token для webhook-валидации",
    )
    make_primary: bool = Field(default=False, description="Сделать канал основным")


class AddWhatsAppUserbotChannel(AgentLookup):
    phone_number: str = Field(
        ...,
        min_length=5,
        max_length=32,
        description="Номер WhatsApp аккаунта в международном формате",
    )
    session_string: str = Field(
        ...,
        min_length=10,
        max_length=65535,
        description="Сериализованная сессия WhatsApp userbot",
    )
    client_label: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Опциональное имя клиента/устройства",
    )
    make_primary: bool = Field(default=False, description="Сделать канал основным")


class DeleteAgentChannel(AgentLookup):
    connection_id: int = Field(..., gt=0, description="Id подключения канала")


class UserbotRequestCode(BaseModel):
    api_id: int = Field(..., gt=0, description="Telegram API ID from my.telegram.org")
    api_hash: str = Field(..., min_length=16, max_length=128, description="Telegram API hash")
    phone_number: str = Field(..., min_length=5, max_length=32, description="Telegram phone number")


class UserbotVerifyCode(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=4096, description="Temporary auth token")
    code: str = Field(..., min_length=3, max_length=12, description="Telegram code from message")
    password: Optional[str] = Field(None, min_length=1, max_length=128, description="Telegram 2FA password")


class WhatsAppUserbotRequestCode(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=32, description="WhatsApp phone number")


class WhatsAppUserbotVerifyCode(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=4096, description="Temporary auth token")
    code: Optional[str] = Field(None, min_length=1, max_length=64, description="Verification code from WhatsApp flow")


class WhatsAppUserbotAuthStatus(BaseModel):
    auth_token: str = Field(..., min_length=20, max_length=4096, description="Temporary auth token")


class AgentAIAction(AgentLookup):
    pass


class ExternalAgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Запрос для агента")
    external_user_id: Optional[str] = Field(
        None,
        max_length=128,
        description="ID пользователя/чата во внешней системе (обязателен для отображения в дашборде)",
    )
    chat_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Алиас для external_user_id (инициализация id чата на стороне интегратора)",
    )
    external_user_name: Optional[str] = Field(
        None,
        max_length=128,
        description="Опциональное имя пользователя во внешней системе",
    )


class AgentAnalyticsMessageLog(AgentLookup):
    role: str = Field(..., pattern="^(user|agent|operator)$", description="Роль сообщения")
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
    telegram_peer_access_hash: Optional[int] = Field(
        default=None,
        description="Telegram access_hash для InputPeerUser (userbot), если известен",
    )
    tool_name: Optional[str] = Field(default=None, max_length=64, description="Название CRM tool/fallback")
    tool_args_hash: Optional[str] = Field(default=None, max_length=64, description="SHA-256 хеш аргументов tool")
    tool_status: Optional[str] = Field(default=None, max_length=24, description="Статус tool-вызова")
    latency_ms: Optional[int] = Field(default=None, ge=0, description="Latency tool-вызова в миллисекундах")
    crm_provider: Optional[str] = Field(default=None, max_length=32, description="CRM провайдер (amocrm/bitrix24)")


class AgentFreezeUserPayload(AgentLookup):
    user_external_id: str = Field(..., max_length=128, description="Внешний id пользователя (Telegram user id)")
    frozen: bool = Field(default=True, description="True — заморозить, False — снять")


class AgentTelegramSendToUserPayload(AgentLookup):
    user_external_id: str = Field(..., max_length=128, description="Telegram user id получателя")
    preferred_channel: Optional[str] = Field(
        default=None,
        pattern="^(telegram|telegram_userbot)$",
        description="Предпочитаемый telegram-канал доставки",
    )
    message: str = Field(..., min_length=1, max_length=4096, description="Текст сообщения от владельца")


class AgentTelegramBroadcastPayload(AgentLookup):
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


class AgentWhatsappUserbotSendToUserPayload(AgentLookup):
    user_external_id: str = Field(
        ...,
        max_length=128,
        description="Получатель: номер (цифры) или полный JID WhatsApp",
    )
    message: str = Field(..., min_length=1, max_length=4096, description="Текст сообщения от владельца")


class AgentWhatsappUserbotBroadcastPayload(AgentLookup):
    message: str = Field(..., min_length=1, max_length=4096, description="Текст рассылки от владельца")
    skip_frozen: bool = Field(
        default=True,
        description="Не отправлять пользователям со статусом «заморожен»",
    )
    max_recipients: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Максимум получателей за один запрос",
    )


class InternalProcessMessageRequest(BaseModel):
    bot_id: int = Field(..., gt=0, description="ID публичного канала/агента")
    query: str = Field(..., min_length=1, max_length=4000, description="Сообщение пользователя")
    user_external_id: str = Field(..., min_length=1, max_length=128, description="Внешний ID пользователя")
    channel: str = Field(
        ...,
        pattern="^(telegram|telegram_userbot|whatsapp_userbot)$",
        description="Канал сообщения",
    )
    system_prompt: Optional[str] = Field(default="", description="Системный промпт агента")
    welcome_message: Optional[str] = Field(default=None, description="Welcome message для /start")
    user_display_name: Optional[str] = Field(default=None, max_length=128, description="Отображаемое имя")
    telegram_peer_access_hash: Optional[int] = Field(
        default=None,
        description="Telegram access_hash для userbot-сценария",
    )


class AgentCrmConnectPayload(AgentLookup):
    provider: str = Field(
        ...,
        pattern="^(amocrm|bitrix24)$",
        description="CRM провайдер (amocrm или bitrix24)",
    )
    account_base_url: str = Field(
        ...,
        min_length=10,
        max_length=255,
        description="Базовый URL аккаунта CRM (например https://example.amocrm.ru)",
    )
    access_token: str = Field(
        ...,
        min_length=20,
        max_length=4096,
        description="OAuth access token CRM",
    )


class AgentCrmHealthPayload(AgentLookup):
    provider: Optional[str] = Field(
        default=None,
        pattern="^(amocrm|bitrix24)$",
        description="Опционально: конкретный CRM провайдер",
    )


class AgentCrmValidatePayload(BaseModel):
    provider: str = Field(
        ...,
        pattern="^(amocrm|bitrix24)$",
        description="CRM провайдер (amocrm или bitrix24)",
    )
    account_base_url: str = Field(
        ...,
        min_length=10,
        max_length=255,
        description="Базовый URL аккаунта CRM (например https://example.amocrm.ru)",
    )
    access_token: str = Field(
        ...,
        min_length=20,
        max_length=4096,
        description="OAuth access token CRM",
    )


class AgentCrmRotateSecretPayload(AgentLookup):
    provider: Optional[str] = Field(
        default=None,
        pattern="^(amocrm|bitrix24)$",
        description="Опционально: конкретный CRM провайдер для ротации",
    )

