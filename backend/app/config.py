from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os

class Settings(BaseSettings):
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    SECRET_KEY: str
    ALGORITHM: str

    @property
    def DB_HOST(self) -> str:
        return "postgres" if os.path.exists('/.dockerenv') else "localhost"

    model_config = SettingsConfigDict(
        env_file= Path(__file__).parent.parent.parent / '.env',  
        env_file_encoding='utf-8',
        extra='ignore'  
    )


settings = Settings()

def get_db_url():
    return (f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@"
            f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")

def get_auth_data():
    return {"secret_key": settings.SECRET_KEY, "algorithm": settings.ALGORITHM}