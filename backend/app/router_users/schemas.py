from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class NewUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=32, description="Имя пользователя: длина от 3 до 32 символов")
    password: str = Field(..., min_length=6, max_length=30, description="Пароль: длина от 6 до 30 символов")
    # Optional Telegram ID for linking bot later; web registration does not require it.
    telegram_id: Optional[int] = Field(default=None, description="Id пользователя в телеграме (необязательное поле)")

class LoginUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=30, description="Имя пользователя: длина от 3 до 30 символов")
    password: str = Field(..., min_length=6, max_length=30, description="Пароль: длина от 6 до 30 символов")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=32, max_length=1024, description="Refresh token")


class AuthTokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"

class User_from_tg(BaseModel):
    name: str = Field(..., min_length=3, max_length=32, description="Имя пользователя: длина от 3 до 32 символов")
    telegram_id: int = Field(..., description="Id пользователя в телеграме")
    
class User_by_agent_or_tgID(BaseModel):
    id: int = Field(..., description="id")

class Update_userSubscription(BaseModel):
    telegram_id: int = Field(..., description="Id пользователя в телеграме")

    subscription_type: Optional[Literal['Free', 'Advanced', 'Pro']] = Field(None, description="Тип подписки ('Free', 'Advanced', 'Pro')")
    subscription_end_date: Optional[datetime] = Field(None, description="Дата окончания подписки")


class TelegramLinkStartResponse(BaseModel):
    code: str = Field(..., description="Одноразовый код для привязки Telegram")
    expires_at: datetime = Field(..., description="UTC время истечения кода")
    expires_in_seconds: int = Field(..., description="Оставшееся время жизни кода")


class TelegramLinkStartRequest(BaseModel):
    telegram_username: str = Field(
        ...,
        min_length=4,
        max_length=33,
        pattern=r"^@[A-Za-z0-9_]{3,32}$",
        description="Username Telegram в формате @username",
    )


class TelegramLinkConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, description="Одноразовый 6-значный код из сайта")
    telegram_id: int = Field(..., description="Telegram ID пользователя")


class UserMeResponse(BaseModel):
    id: int
    name: str
    telegram_id: Optional[int] = None
    is_telegram_linked: bool
