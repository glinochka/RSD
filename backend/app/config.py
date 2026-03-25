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
    QDRANT_API_KEY:str = ''
    DEEPSEEK_API_KEY: str

    QDRANT_URL: str
    DB_HOST: str
    INTERNAL_API_KEY: str = ""

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

def get_auth_data():
    return {"secret_key": settings.SECRET_KEY, "algorithm": settings.ALGORITHM}