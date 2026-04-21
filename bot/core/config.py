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
    WHATSAPP_USERBOT_BRIDGE_URL: str = ""
    WHATSAPP_USERBOT_BRIDGE_API_KEY: str = ""
    WHATSAPP_USERBOT_BRIDGE_TIMEOUT_SECONDS: float = 60.0
    WHATSAPP_USERBOT_POLL_INTERVAL_SECONDS: int = 5

settings = Settings()
if not os.path.exists('/.dockerenv'):
    settings.API_HOST = 'localhost'

