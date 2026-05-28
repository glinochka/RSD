from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Literal, Optional

from ..prompts.system_prompts import DEFAULT_AGENT_SYSTEM_PROMPT


class ContentFactoryTemplateConfig(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255, description="Название компании")
    company_activity: str = Field(..., min_length=1, max_length=2000, description="Описание деятельности")
    brand_tone: Optional[str] = Field(default=None, max_length=500, description="Тон коммуникации бренда")
    content_language: str = Field(default="ru", pattern="^[a-z]{2,16}(?:-[a-z]{2,16})?$", description="Язык контента")
    daily_posting_enabled: bool = Field(default=True, description="Включена ли ежедневная публикация")
    daily_post_time: str = Field(default="10:00", pattern="^([01]\\d|2[0-3]):([0-5]\\d)$", description="Время публикации HH:MM")
    timezone: str = Field(default="UTC", min_length=1, max_length=64, description="IANA timezone (например UTC/Europe-Moscow)")
    video_duration_seconds: int = Field(default=8, ge=1, le=8, description="Длительность видео в секундах (MVP <= 8)")
    kling_model: str = Field(default="kling-v1", min_length=1, max_length=128, description="Модель Kling для генерации")

    @model_validator(mode="after")
    def validate_timezone(self):
        value = (self.timezone or "").strip()
        if not value:
            raise ValueError("timezone must not be empty")
        allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_+-/"
        if any(ch not in allowed for ch in value):
            raise ValueError("timezone format is invalid")
        return self


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
    process_start_with_llm: Optional[bool] = Field(
        default=None,
        description="Если true, /start обрабатывается через LLM как обычное сообщение",
    )
    external_webhook_url: Optional[str] = Field(
        None,
        max_length=1024,
        description="Webhook URL для исходящих сообщений в external_api-чатах",
    )
    template_type: Optional[str] = Field(
        None,
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict | ContentFactoryTemplateConfig] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )
    yookassa_api_key: Optional[str] = Field(
        default=None,
        max_length=4096,
        description="API-ключ платежей для платной брони (формат shop_id:secret_key). Пустая строка очищает ключ.",
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
    template_config: Optional[dict | ContentFactoryTemplateConfig] = Field(
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
    template_config: Optional[dict | ContentFactoryTemplateConfig] = Field(
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
    template_config: Optional[dict | ContentFactoryTemplateConfig] = Field(
        default=None,
        description="Конфигурация шаблона (JSON)",
    )


class CreateEmptyAgent(BaseModel):
    system_prompt: Optional[str] = Field(
        default=DEFAULT_AGENT_SYSTEM_PROMPT,
        min_length=1,
        description="System prompt for agent",
    )
    template_type: str = Field(
        default="qa",
        pattern="^(qa|crm_admin|function_calling|lead_generation|content_factory|sales_manager)$",
        description="Тип шаблона агента",
    )
    template_config: Optional[dict | ContentFactoryTemplateConfig] = Field(
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


class AddMaxBotChannel(AgentLookup):
    bot_token: str = Field(
        ...,
        min_length=10,
        max_length=65535,
        description="Токен чат-бота MAX (из платформы MAX для партнеров)",
    )
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


class AddMaxUserbotChannel(AgentLookup):
    max_token: str = Field(
        ...,
        min_length=10,
        max_length=65535,
        description="Токен авторизации MAX (из localStorage __oneme_auth.token)",
    )
    make_primary: bool = Field(default=False, description="Сделать канал основным")


class TelephonyChannelCredentialsInput(BaseModel):
    """Per-agent telephony settings (platform Voximplant/DID — только в .env)."""

    routing_extension: str = Field(
        ...,
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$",
        description="Добавочный (4 цифры) после общего входящего номера",
    )
    voice_id: str = Field(default="default", min_length=1, max_length=64)
    language: str = Field(default="ru-RU", min_length=2, max_length=16)
    record_calls: bool = Field(default=True)
    disclaimer_played: bool = Field(default=True)


class UpdateTelephonyRouting(AgentLookup):
    routing_extension: str = Field(
        ...,
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$",
        description="Новый добавочный (4 цифры)",
    )


class ValidateTelephonyChannelInput(BaseModel):
    """Опционально проверить занятость добавочного до подключения канала."""

    routing_extension: str | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$",
    )


class AddTelephonyChannel(AgentLookup, TelephonyChannelCredentialsInput):
    make_primary: bool = Field(default=False, description="Сделать канал основным")


class ValidateTelephonyChannel(ValidateTelephonyChannelInput):
    pass


class DeleteAgentChannel(AgentLookup):
    connection_id: int = Field(..., gt=0, description="Id подключения канала")


class YouTubeOAuthStartPayload(AgentLookup):
    redirect_uri: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=1024,
        description="Опционально: redirect URI для OAuth callback",
    )


class YouTubeOAuthCallbackPayload(BaseModel):
    code: str = Field(..., min_length=8, max_length=4096, description="Authorization code from Google OAuth")
    state: str = Field(..., min_length=16, max_length=4096, description="Signed OAuth state")


class YouTubeHealthPayload(AgentLookup):
    pass


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
        pattern="^(telegram|external_api|web|dashboard|telegram_userbot|max_bot|max_userbot|whatsapp_userbot|whatsapp_business_api|instagram|tiktok|pinterest)$",
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


class AgentExternalApiSendToUserPayload(AgentLookup):
    user_external_id: str = Field(
        ...,
        max_length=128,
        description="ID пользователя/чата во внешней системе",
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


class AgentMaxUserbotSendToUserPayload(AgentLookup):
    user_external_id: str = Field(
        ...,
        max_length=128,
        description="ID пользователя в MAX (для привязки в аналитике чата)",
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
    query: str = Field(default="", max_length=4000, description="Текст сообщения пользователя")
    user_external_id: str = Field(..., min_length=1, max_length=128, description="Внешний ID пользователя")
    channel: str = Field(
        ...,
        pattern="^(telegram|telegram_userbot|max_bot|max_userbot|whatsapp_userbot)$",
        description="Канал сообщения",
    )
    system_prompt: Optional[str] = Field(default="", description="Системный промпт агента")
    welcome_message: Optional[str] = Field(default=None, description="Welcome message для /start")
    process_start_with_llm: bool = Field(
        default=False,
        description="Если true, команда /start передается в LLM-пайплайн",
    )
    user_display_name: Optional[str] = Field(default=None, max_length=128, description="Отображаемое имя")
    telegram_peer_access_hash: Optional[int] = Field(
        default=None,
        description="Telegram access_hash для userbot-сценария",
    )
    voice_base64: Optional[str] = Field(
        default=None,
        max_length=15_000_000,
        description="Аудио в Base64; см. VOICE_MAX_BYTES на сервере",
    )
    voice_mime_type: Optional[str] = Field(default="audio/ogg", max_length=128)

    @model_validator(mode="after")
    def validate_any_content(self):
        q = (self.query or "").strip()
        voice = (self.voice_base64 or "").strip()
        if not q and not voice:
            raise ValueError("Укажите query или voice_base64.")
        return self


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


class HttpIntegrationAuthPayload(BaseModel):
    type: Literal["none", "bearer", "header", "basic"] = Field(
        default="none",
        description="Способ авторизации ко внешнему HTTP API",
    )
    token: Optional[str] = Field(default=None, max_length=8192, description="Bearer token")
    header_name: Optional[str] = Field(default=None, max_length=256)
    header_value: Optional[str] = Field(default=None, max_length=8192)
    username: Optional[str] = Field(default=None, max_length=256)
    password: Optional[str] = Field(default=None, max_length=8192)


class HttpIntegrationToolPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=2000)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: str = Field(..., min_length=1, max_length=512)
    requires_confirmation: Optional[bool] = None
    parameters: dict[str, Any] = Field(
        ...,
        description="Параметры вызова в формате JSON Schema с корнем type=object",
    )


class HttpIntegrationConnectPayload(AgentLookup):
    integration_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Slug интеграции (латиница / цифры / дефис / подчёркивание)",
    )
    base_url: str = Field(..., min_length=8, max_length=2048)
    timeout_seconds: float = Field(default=25.0, ge=3.0, le=120.0)
    default_headers: dict[str, str] = Field(default_factory=dict)
    auth: HttpIntegrationAuthPayload = Field(default_factory=HttpIntegrationAuthPayload)
    tools: list[HttpIntegrationToolPayload] = Field(..., min_length=1, max_length=16)


class HttpIntegrationDeactivatePayload(AgentLookup):
    integration_id: int = Field(..., gt=0, description="ID строки интеграции (agent_http_integrations.id)")


class AdminTemplateStaffCreatePayload(AgentLookup):
    role: str = Field(..., pattern="^(master|doctor)$", description="Роль сотрудника")
    full_name: str = Field(..., min_length=1, max_length=128, description="ФИО сотрудника")
    specializations: list[str] = Field(default_factory=list, description="Список специализаций")
    is_active: bool = Field(default=True, description="Активен ли сотрудник")


class AdminTemplateStaffUpdatePayload(AgentLookup):
    staff_id: int = Field(..., gt=0, description="ID сотрудника")
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=128, description="ФИО сотрудника")
    specializations: Optional[list[str]] = Field(default=None, description="Список специализаций")
    is_active: Optional[bool] = Field(default=None, description="Активность сотрудника")


class AdminTemplateStaffDeletePayload(AgentLookup):
    staff_id: int = Field(..., gt=0, description="ID сотрудника")


class AdminTemplateResourceCreatePayload(AgentLookup):
    resource_type: str = Field(..., pattern="^(chair|room|equipment)$", description="Тип ресурса")
    title: str = Field(..., min_length=1, max_length=128, description="Название ресурса")
    is_active: bool = Field(default=True, description="Активен ли ресурс")


class AdminTemplateResourceUpdatePayload(AgentLookup):
    resource_id: int = Field(..., gt=0, description="ID ресурса")
    title: Optional[str] = Field(default=None, min_length=1, max_length=128, description="Название ресурса")
    is_active: Optional[bool] = Field(default=None, description="Активность ресурса")


class AdminTemplateResourceDeletePayload(AgentLookup):
    resource_id: int = Field(..., gt=0, description="ID ресурса")


class AdminTemplateServiceCreatePayload(AgentLookup):
    target_role: str = Field(..., pattern="^(master|doctor)$", description="Целевая роль исполнителя")
    staff_id: Optional[int] = Field(default=None, gt=0, description="ID конкретного сотрудника-исполнителя")
    title: str = Field(..., min_length=1, max_length=128, description="Название услуги")
    duration_minutes: int = Field(..., ge=1, le=24 * 60, description="Длительность услуги в минутах")
    price_minor: int = Field(default=0, ge=0, description="Стоимость в minor units")
    resource_type_filters: list[str] = Field(default_factory=list, description="Ограничение по типам ресурсов")
    is_active: bool = Field(default=True, description="Активна ли услуга")


class AdminTemplateServiceUpdatePayload(AgentLookup):
    service_id: int = Field(..., gt=0, description="ID услуги")
    staff_id: Optional[int] = Field(default=None, gt=0, description="ID конкретного сотрудника-исполнителя")
    title: Optional[str] = Field(default=None, min_length=1, max_length=128, description="Название услуги")
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=24 * 60, description="Длительность услуги")
    price_minor: Optional[int] = Field(default=None, ge=0, description="Стоимость в minor units")
    resource_type_filters: Optional[list[str]] = Field(default=None, description="Ограничение по типам ресурсов")
    is_active: Optional[bool] = Field(default=None, description="Активность услуги")


class AdminTemplateServiceDeletePayload(AgentLookup):
    service_id: int = Field(..., gt=0, description="ID услуги")


class AdminTemplateScheduleCreatePayload(AgentLookup):
    starts_at: str = Field(..., min_length=16, max_length=40, description="Начало слота ISO datetime")
    ends_at: str = Field(..., min_length=16, max_length=40, description="Конец слота ISO datetime")
    staff_id: Optional[int] = Field(default=None, gt=0, description="ID сотрудника")
    resource_id: Optional[int] = Field(default=None, gt=0, description="ID ресурса")
    slot_kind: str = Field(default="work", min_length=1, max_length=24, description="Тип слота")
    is_active: bool = Field(default=True, description="Активность слота")


class AdminTemplateScheduleDeletePayload(AgentLookup):
    schedule_slot_id: int = Field(..., gt=0, description="ID слота расписания")


class AdminTemplateAppointmentCreatePayload(AgentLookup):
    client_external_id: str = Field(..., min_length=1, max_length=128, description="ID клиента во внешнем канале")
    starts_at: str = Field(..., min_length=16, max_length=40, description="Начало записи ISO datetime")
    ends_at: str = Field(..., min_length=16, max_length=40, description="Конец записи ISO datetime")
    staff_id: Optional[int] = Field(default=None, gt=0, description="ID сотрудника")
    resource_id: Optional[int] = Field(default=None, gt=0, description="ID ресурса")
    service_id: Optional[int] = Field(default=None, gt=0, description="ID услуги")
    client_name: Optional[str] = Field(default=None, max_length=128, description="Имя клиента")
    source_channel: Optional[str] = Field(default=None, max_length=32, description="Источник записи")
    notes: Optional[str] = Field(default=None, max_length=4000, description="Заметка")


class AdminTemplateAppointmentReschedulePayload(AgentLookup):
    appointment_id: int = Field(..., gt=0, description="ID записи")
    starts_at: str = Field(..., min_length=16, max_length=40, description="Новое начало записи ISO datetime")
    ends_at: str = Field(..., min_length=16, max_length=40, description="Новый конец записи ISO datetime")
    staff_id: Optional[int] = Field(default=None, gt=0, description="ID сотрудника")
    resource_id: Optional[int] = Field(default=None, gt=0, description="ID ресурса")


class AdminTemplateAppointmentCancelPayload(AgentLookup):
    appointment_id: int = Field(..., gt=0, description="ID записи")
    reason: Optional[str] = Field(default=None, max_length=1000, description="Причина отмены")


class AdminTemplateAppointmentConfirmPayload(AgentLookup):
    appointment_id: int = Field(..., gt=0, description="ID записи")


class AdminTemplateAppointmentDeletePayload(AgentLookup):
    appointment_id: int = Field(..., gt=0, description="ID записи")
    reason: Optional[str] = Field(default=None, max_length=1000, description="Причина отмены")


class AdminTemplateRefundRequestActionPayload(AgentLookup):
    refund_request_id: int = Field(..., gt=0, description="ID заявки на возврат")
    reason: Optional[str] = Field(default=None, max_length=1000, description="Комментарий при отклонении")


class AdminTemplateWaitlistCreatePayload(AgentLookup):
    client_external_id: str = Field(..., min_length=1, max_length=128)
    client_name: Optional[str] = Field(default=None, max_length=128)
    service_id: Optional[int] = Field(default=None, gt=0)
    desired_staff_id: Optional[int] = Field(default=None, gt=0)
    desired_resource_id: Optional[int] = Field(default=None, gt=0)
    earliest_starts_at: Optional[str] = Field(default=None, min_length=16, max_length=40)
    latest_ends_at: Optional[str] = Field(default=None, min_length=16, max_length=40)
    notes: Optional[str] = Field(default=None, max_length=2000)


class AdminTemplateWaitlistUpdatePayload(AgentLookup):
    waitlist_id: int = Field(..., gt=0)
    status: Optional[str] = Field(default=None, pattern="^(waiting|matched|cancelled)$")
    notes: Optional[str] = Field(default=None, max_length=2000)


class AdminTemplateWaitlistDeletePayload(AgentLookup):
    waitlist_id: int = Field(..., gt=0)


class AdminTemplateClientProfileUpdatePayload(AgentLookup):
    client_external_id: str = Field(..., min_length=1, max_length=128)
    client_name: Optional[str] = Field(default=None, max_length=128)
    tags: Optional[list[str]] = Field(default=None)
    preferences: Optional[dict] = Field(default=None)
    history_note: Optional[str] = Field(default=None, max_length=2000)


class AdminTemplateQuickReplyCreatePayload(AgentLookup):
    title: str = Field(..., min_length=1, max_length=128)
    body: str = Field(..., min_length=1, max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    is_active: bool = Field(default=True)


class AdminTemplateQuickReplyUpdatePayload(AgentLookup):
    quick_reply_id: int = Field(..., gt=0)
    title: Optional[str] = Field(default=None, min_length=1, max_length=128)
    body: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = Field(default=None)


class AdminTemplateQuickReplyDeletePayload(AgentLookup):
    quick_reply_id: int = Field(..., gt=0)


class AdminTemplateRemindersRunPayload(AgentLookup):
    now_iso: Optional[str] = Field(default=None, min_length=16, max_length=40)
    channel: Optional[str] = Field(default=None, max_length=32)


class TelephonyPreviewStartPayload(AgentLookup):
    pass


class TelephonyPreviewHistoryItem(BaseModel):
    role: str = Field(..., min_length=1, max_length=16)
    text: str = Field(..., min_length=1, max_length=8000)


class TelephonyPreviewTurnPayload(AgentLookup):
    call_db_id: Optional[int] = Field(default=None, gt=0, description="ID сессии с телефонией")
    preview_session_id: Optional[str] = Field(default=None, max_length=128)
    dialog_state: Optional[str] = Field(default=None, max_length=32)
    turn_history: Optional[list[TelephonyPreviewHistoryItem]] = Field(default=None, max_length=32)
    user_transcript: Optional[str] = Field(default=None, max_length=8000)
    audio_base64: Optional[str] = Field(default=None, description="Аудио реплики (base64)")
    audio_mime_type: Optional[str] = Field(default="audio/webm", max_length=64)

    @model_validator(mode="after")
    def validate_session_ref(self):
        if self.call_db_id is None and not (self.preview_session_id or "").strip():
            raise ValueError("Either call_db_id or preview_session_id is required")
        return self


class TelephonyPreviewEndPayload(AgentLookup):
    call_db_id: Optional[int] = Field(default=None, gt=0)
    preview_session_id: Optional[str] = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_session_ref(self):
        if self.call_db_id is None and not (self.preview_session_id or "").strip():
            raise ValueError("Either call_db_id or preview_session_id is required")
        return self


class TelephonyPreviewSpeakPayload(AgentLookup):
    text: str = Field(..., min_length=1, max_length=4000)

