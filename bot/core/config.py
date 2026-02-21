from pydantic_settings import BaseSettings
from qdrant_client import AsyncQdrantClient

class Settings(BaseSettings):
    NGROK_AUTHTOKEN: str
    ENCRYPTION_KEY: str
    QDRANT_URL: str
    QDRANT_API_KEY:str = ''
    DEEPSEEK_API_KEY: str
    MASTER_BOT_TOKEN: str
    BASE_URL: str

settings = Settings()

q_client = AsyncQdrantClient(
    url=settings.QDRANT_URL, 
    api_key=settings.QDRANT_API_KEY
)