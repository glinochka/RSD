from pydantic_settings import BaseSettings
import os
class Settings(BaseSettings):
    ENCRYPTION_KEY: str
    DEEPSEEK_API_KEY: str
    MASTER_BOT_TOKEN: str
    BOT_PAYMENT_TOKEN: str = ""
    BASE_URL: str
    API_PORT: str

    API_HOST: str
    INTERNAL_API_KEY: str = ""
    USERBOT_POLL_INTERVAL_SECONDS: int = 30
    TELEGRAM_PROXY_TYPE: str = "none"
    TELEGRAM_PROXY_HOST: str = ""
    TELEGRAM_PROXY_PORT: int = 0
    TELEGRAM_PROXY_USERNAME: str = ""
    TELEGRAM_PROXY_PASSWORD: str = ""

settings = Settings()
if not os.path.exists('/.dockerenv'):
    settings.API_HOST = 'localhost'

