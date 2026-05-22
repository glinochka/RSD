from datetime import timedelta
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal
import os

class Settings(BaseSettings):
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    SECRET_KEY: str
    USER_JWT_SECRET_KEY: str = ""
    ADMIN_JWT_SECRET_KEY: str = ""
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Внутренний портал отдела продаж (отдельный JWT, как у пользователей — тот же SECRET в get_auth_data).
    SALES_STAFF_TOKEN_EXPIRE_HOURS: int = 24
    # Дневная выдача контактов из общего пула (если у сотрудника daily_contacts_quota = 0).
    SALES_TRAINEE_DAILY_QUOTA: int = 30
    SALES_MOP_DAILY_QUOTA: int = 50
    # Календарный день для архива и лимитов выдачи контактов (IANA timezone).
    SALES_DAY_TIMEZONE: str = "Europe/Moscow"
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    QDRANT_API_KEY:str = ''
    DEEPSEEK_API_KEY: str
    # Fallback STT when local faster-whisper is disabled or returns empty (optional).
    OPENAI_API_KEY: str = ""
    # Speech-to-text: faster_whisper (local), openai (API), auto = try local then API.
    VOICE_STT_BACKEND: Literal["auto", "faster_whisper", "openai"] = "auto"
    FASTER_WHISPER_MODEL: str = "base"
    FASTER_WHISPER_DEVICE: str = "cpu"
    FASTER_WHISPER_COMPUTE_TYPE: str = "int8"
    # Empty = auto-detect language; e.g. "ru" for Russian-only short voice notes.
    FASTER_WHISPER_LANGUAGE: str = ""
    # STT resource limits (abuse + DoS guardrails).
    VOICE_MAX_BYTES: int = 10 * 1024 * 1024
    VOICE_TRANSCRIPTION_TIMEOUT_SECONDS: float = 120.0
    KLING_API_KEY: str = ""
    KLING_API_BASE_URL: str = "https://api.klingai.com"
    KLING_TIMEOUT_SECONDS: float = 30.0
    KLING_MAX_RETRIES: int = 3
    YOUTUBE_OAUTH_CLIENT_ID: str = ""
    YOUTUBE_OAUTH_CLIENT_SECRET: str = ""
    YOUTUBE_OAUTH_REDIRECT_URI: str = ""
    YOUTUBE_OAUTH_SCOPES: str = "https://www.googleapis.com/auth/youtube.upload"
    YOUTUBE_TIMEOUT_SECONDS: float = 45.0
    YOUTUBE_MAX_RETRIES: int = 3
    CONTENT_FACTORY_ENABLED: bool = False
    CONTENT_FACTORY_POLL_INTERVAL_SECONDS: int = 20
    CONTENT_FACTORY_RENDER_POLL_INTERVAL_SECONDS: int = 6
    CONTENT_FACTORY_RENDER_MAX_POLLS: int = 60

    ARTICLE_PUBLISHER_ENABLED: bool = False
    ARTICLE_PUBLISHER_POLL_INTERVAL_SECONDS: int = 300
    ARTICLE_PUBLISHER_IMAGES_DIR: str = ""

    QDRANT_URL: str
    DB_HOST: str
    INTERNAL_API_KEY: str = ""
    INTERNAL_REQUEST_SIGNING_SECRET: str = ""
    INTERNAL_REQUEST_SIGNATURE_TTL_SECONDS: int = 300
    ALLOW_INSECURE_INTERNAL_API: bool = False
    CORS_ALLOWED_ORIGINS: str = ""
    # Public base URL (domain) used by Telegram webhooks.
    # Bot container uses this as well to reach `/webhook/{bot_id}`.
    BASE_URL: str | None = None
    ADMIN_WEB_LOGIN: str = ""
    ADMIN_WEB_PASSWORD_HASH: str = ""

    @field_validator("ADMIN_WEB_PASSWORD_HASH", mode="before")
    @classmethod
    def unescape_compose_dollars_in_admin_hash(cls, v: object) -> object:
        # Docker Compose interpolates `$name` in env values; bcrypt hashes look like `$2b$12$...`.
        # Store `$$` for a literal `$` in `.env`, then collapse here (also works when Compose
        # already collapsed `$$` → `$` before injecting into the container).
        if isinstance(v, str) and "$$" in v:
            return v.replace("$$", "$")
        return v

    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str | None = None
    MASTER_BOT_TOKEN: str = ""
    # Шаблон наименования услуги в чеке «Мой налог» ({org_name}, {contact_id}).
    SALES_INVOICE_SERVICE_NAME_TEMPLATE: str = "Услуги RSD для {org_name}"
    SALES_INVOICE_DEFAULT_AMOUNT_RUB: str = "10000.00"
    # Интеграция «Мой налог» (самозанятый), lknpd.nalog.ru.
    # Вариант A: MOY_NALOG_REFRESH_TOKEN (+ MOY_NALOG_INN) — без пароля в .env.
    # Вариант B: MOY_NALOG_INN + MOY_NALOG_PASSWORD (первый вход; дальше — session file).
    MOY_NALOG_INN: str = ""
    MOY_NALOG_PASSWORD: str = ""
    MOY_NALOG_REFRESH_TOKEN: str = ""
    MOY_NALOG_ACCESS_TOKEN: str = ""
    MOY_NALOG_SESSION_FILE: str = "data/moy_nalog_session.json"
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_ALLOWED_HD: str = ""
    MAILOPOST_API_URL: str = "https://api.mailopost.ru/v1"
    MAILOPOST_API_TOKEN: str = ""
    MAILOPOST_FROM_EMAIL: str = ""
    MAILOPOST_FROM_NAME: str = ""
    MAILOPOST_SEND_TIMEOUT_SECONDS: float = 10.0
    # Пауза между письмами в админских рассылках (подтверждённые пользователи, точечные группы), сек.
    MAILOPOST_BROADCAST_INTERVAL_SECONDS: int = 900
    # Пауза между автоматическими напоминаниям (onboarding), сек. (30 мин).
    MAILOPOST_REMINDER_BATCH_INTERVAL_SECONDS: int = 1800
    WHATSAPP_USERBOT_BRIDGE_URL: str = ""
    WHATSAPP_USERBOT_BRIDGE_API_KEY: str = ""
    WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS: float = 60.0
    USERBOT_POLL_INTERVAL_SECONDS: int = 30
    MAX_BOT_POLL_INTERVAL_SECONDS: int = 15
    MAX_BOT_UPDATES_TIMEOUT_SECONDS: int = 30
    MAX_BOT_RECONNECT_DELAY_SECONDS: int = 5
    MAX_USERBOT_POLL_INTERVAL_SECONDS: int = 30
    MAX_USERBOT_RECONNECT_DELAY_SECONDS: int = 5
    WHATSAPP_USERBOT_POLL_INTERVAL_SECONDS: int = 5
    WA_USERBOT_SESSION_SECRET: str = ""
    TELEPHONY_ENABLED: bool = False
    TELEPHONY_INTERNAL_API_KEY: str = ""
    TELEPHONY_MAX_TURN_SECONDS: int = 30
    TELEPHONY_MAX_CALL_MINUTES: int = 15
    TELEPHONY_MAX_TURNS: int = 15
    TELEPHONY_TTS_PROVIDER: Literal["voximplant", "yandex", "openai"] = "voximplant"
    YANDEX_SPEECHKIT_API_KEY: str = ""
    TELEPHONY_TTS_TIMEOUT_SECONDS: float = 20.0
    TELEPHONY_WEBHOOK_BASE_URL: str = ""
    TELEPHONY_WEBHOOK_SIGNATURE_TTL_SECONDS: int = 300
    TELEPHONY_WEBHOOK_RATE_LIMIT_PER_CONNECTION: int = 120
    TELEPHONY_WEBHOOK_RATE_LIMIT_PER_IP: int = 240
    TELEPHONY_WEBHOOK_RATE_WINDOW_SECONDS: int = 60
    TELEPHONY_TURNS_RETENTION_DAYS: int = 90
    # crm_admin + KB (Qdrant) + tool calls often exceed 8s on informational questions.
    TELEPHONY_LLM_TIMEOUT_SECONDS: float = 25.0
    TELEPHONY_LLM_RETRY_TIMEOUT_SECONDS: float = 15.0
    TELEPHONY_PREVIEW_LLM_TIMEOUT_SECONDS: float = 60.0
    TELEPHONY_TURN_LATENCY_ALERT_P95_MS: int = 10000
    # Stage 5: latency / streaming pipeline
    TELEPHONY_STREAMING_ENABLED: bool = True
    TELEPHONY_ENDPOINT_SILENCE_MS: int = 600
    TELEPHONY_CRM_FILLER_THRESHOLD_MS: int = 1500
    TELEPHONY_DEDICATED_POOL_ENABLED: bool = True
    TELEPHONY_DEDICATED_POOL_SIZE: int = 8
    TELEPHONY_WORKER_PORT: int = 8001
    # Stage 6: human-like dialogue
    TELEPHONY_BARGE_IN_ENABLED: bool = True
    TELEPHONY_BACKCHANNEL_MIN_MS: int = 5000
    TELEPHONY_SSML_ENABLED: bool = True
    REDIS_URL: str = ""
    VOXIMPLANT_API_BASE_URL: str = "https://api.voximplant.com/platform_api"
    TELEPHONY_VOXIMPLANT_API_TIMEOUT_SECONDS: float = 15.0
    CRM_CREDENTIALS_ENCRYPTION_KEY: str = ""
    CRM_CREDENTIALS_ENCRYPTION_KEY_PREVIOUS: str = ""
    EMBEDDING_THREADS: int = 1
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_PARALLEL: int = 1
    EMBEDDING_MAX_CONCURRENT_DOCUMENTS: int = 1
    EMBEDDING_PROFILE_KEY: str = "bge_m3_v1"
    EMBEDDING_SCHEMA_VERSION: int = 1
    EMBEDDING_CHUNK_SIZE: int = 1000
    EMBEDDING_CHUNK_OVERLAP: int = 100
    # If set, load the SentenceTransformer from this directory (no Hub download). For air-gapped / offline deploys.
    EMBEDDING_LOCAL_MODEL_PATH: str = ""
    model_config = SettingsConfigDict(
        env_file= Path(__file__).parent.parent.parent / '.env',  
        env_file_encoding='utf-8',
        extra='ignore'  
    )

settings = Settings()
 
if not os.path.exists('/.dockerenv'):
    settings.DB_HOST = "localhost"
    settings.QDRANT_URL = "http://localhost:6333"


def get_db_url():
    return (f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@"
            f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")


def get_auth_data(token_kind: Literal["user", "admin", "sales_staff"] = "user"):
    if token_kind == "admin":
        secret_key = settings.ADMIN_JWT_SECRET_KEY.strip()
        if not secret_key:
            raise RuntimeError("ADMIN_JWT_SECRET_KEY is not configured")
    else:
        secret_key = settings.USER_JWT_SECRET_KEY.strip()
        if not secret_key:
            raise RuntimeError("USER_JWT_SECRET_KEY is not configured")

    return {"secret_key": secret_key, "algorithm": settings.ALGORITHM}


def sales_staff_token_expire_delta() -> timedelta:
    hours = max(1, int(settings.SALES_STAFF_TOKEN_EXPIRE_HOURS))
    return timedelta(hours=hours)