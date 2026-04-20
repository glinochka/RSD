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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    QDRANT_API_KEY:str = ''
    DEEPSEEK_API_KEY: str

    QDRANT_URL: str
    DB_HOST: str
    INTERNAL_API_KEY: str = ""
    ALLOW_INSECURE_INTERNAL_API: bool = False
    CORS_ALLOWED_ORIGINS: str = ""
    # Public base URL (domain) used by Telegram webhooks.
    # Bot container uses this as well to reach `/webhook/{bot_id}`.
    BASE_URL: str | None = None
    ADMIN_WEB_LOGIN: str = ""
    ADMIN_WEB_PASSWORD_HASH: str = ""
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str | None = None
    MASTER_BOT_TOKEN: str = ""
    MAILOPOST_API_URL: str = "https://api.mailopost.ru/v1"
    MAILOPOST_API_TOKEN: str = ""
    MAILOPOST_FROM_EMAIL: str = ""
    MAILOPOST_FROM_NAME: str = ""
    MAILOPOST_SEND_TIMEOUT_SECONDS: float = 10.0
    EMBEDDING_THREADS: int = 1
    EMBEDDING_BATCH_SIZE: int = 16
    EMBEDDING_PARALLEL: int = 1
    EMBEDDING_MAX_CONCURRENT_DOCUMENTS: int = 1
    EMBEDDING_PROFILE_KEY: str = "bge_m3_v1"
    EMBEDDING_SCHEMA_VERSION: int = 1
    EMBEDDING_CHUNK_SIZE: int = 1000
    EMBEDDING_CHUNK_OVERLAP: int = 100
    TELEGRAM_PROXY_TYPE: str = "none"
    TELEGRAM_PROXY_HOST: str = ""
    TELEGRAM_PROXY_PORT: int = 0
    TELEGRAM_PROXY_USERNAME: str = ""
    TELEGRAM_PROXY_PASSWORD: str = ""
    TELEGRAM_CONNECT_TIMEOUT_SECONDS: float = 30.0

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


def get_auth_data(token_kind: Literal["user", "admin"] = "user"):
    if token_kind == "admin":
        secret_key = settings.ADMIN_JWT_SECRET_KEY.strip()
        if not secret_key:
            raise RuntimeError("ADMIN_JWT_SECRET_KEY is not configured")
    else:
        secret_key = settings.USER_JWT_SECRET_KEY.strip()
        if not secret_key:
            raise RuntimeError("USER_JWT_SECRET_KEY is not configured")

    return {"secret_key": secret_key, "algorithm": settings.ALGORITHM}