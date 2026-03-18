from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, Literal


class NewUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=32, description="Имя пользователя: длина от 3 до 32 символов")
    password: str = Field(..., min_length=6, max_length=30, description="Пароль: длина от 6 до 30 символов")
    # Optional Telegram ID for linking bot later; web registration does not require it.
    telegram_id: Optional[int] = Field(default=None, description="Id пользователя в телеграме (необязательное поле)")

class LoginUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=30, description="Имя пользователя: длина от 3 до 30 символов")
    password: str = Field(..., min_length=6, max_length=30, description="Пароль: длина от 6 до 30 символов")

class User_from_tg(BaseModel):
    name: str = Field(..., min_length=3, max_length=32, description="Имя пользователя: длина от 3 до 32 символов")
    telegram_id: int = Field(..., description="Id пользователя в телеграме")
    
class User_by_agent_or_tgID(BaseModel):
    id: int = Field(..., description="id")

class Update_userSubscription(BaseModel):
    telegram_id: int = Field(..., description="Id пользователя в телеграме")

    subscription_type: Optional[Literal['Free', 'Advanced', 'Pro']] = Field(None, description="Тип подписки ('Free', 'Advanced', 'Pro')")
    subscription_end_date: Optional[date] = Field(None, description="Дата окончания подписки")
