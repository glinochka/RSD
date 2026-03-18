from pydantic_settings import BaseSettings
import os
class Settings(BaseSettings):
    NGROK_AUTHTOKEN: str
    ENCRYPTION_KEY: str
    DEEPSEEK_API_KEY: str
    MASTER_BOT_TOKEN: str
    BASE_URL: str
    API_PORT: str

    API_HOST: str

settings = Settings()
if not os.path.exists('/.dockerenv'):
    settings.API_HOST = 'localhost'

