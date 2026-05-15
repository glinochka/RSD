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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    QDRANT_API_KEY:str = ''
    DEEPSEEK_API_KEY: str
    # Chat model for requests that include image_url. deepseek-chat / deepseek-reasoner are text-oriented;
    # multimodal needs a VL id (e.g. deepseek-vl). Name must match current DeepSeek API docs.
    DEEPSEEK_VISION_MODEL: str = "deepseek-vl"
    # Try DeepSeek /chat/completions with OpenAI-style multimodal payloads (content array + image_url,
    # including data:image/...;base64,...). If the gateway/model rejects vision, we fall back to a
    # text-only call with frank instructions for the assistant.
    DEEPSEEK_CHAT_TRY_IMAGE_MULTIMODAL: bool = True
    # Fallback STT when local faster-whisper is disabled or returns empty (optional).
    OPENAI_API_KEY: str = ""
    # Speech-to-text: faster_whisper (local), openai (API), auto = try local then API.
    VOICE_STT_BACKEND: Literal["auto", "faster_whisper", "openai"] = "auto"
    FASTER_WHISPER_MODEL: str = "base"
    FASTER_WHISPER_DEVICE: str = "cpu"
    FASTER_WHISPER_COMPUTE_TYPE: str = "int8"
    # Empty = auto-detect language; e.g. "ru" for Russian-only short voice notes.
    FASTER_WHISPER_LANGUAGE: str = ""
    # STT / vision resource limits (abuse + DoS guardrails).
    VOICE_MAX_BYTES: int = 10 * 1024 * 1024
    IMAGE_MAX_BYTES: int = 10 * 1024 * 1024
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
    # Текст в автоматическом счёте (.docx) для отдела продаж.
    SALES_INVOICE_SUPPLIER_NAME: str = 'ООО «RSD»'
    SALES_INVOICE_SUPPLIER_DETAILS: str = ""
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