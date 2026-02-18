from pydantic import BaseModel, Field
from datetime import date




class NewUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=30, description="Имя пользователя: длина от 3 до 30 символов")
    password: str = Field(..., min_length=6, max_length=30, description="Пароль: длина от 6 до 30 символов")
    registered: date = Field(default_factory=date.today, description="Дата регистрации")


class LoginUser(BaseModel):
    name: str = Field(..., min_length=3, max_length=30, description="Имя пользователя: длина от 3 до 30 символов")
    password: str = Field(..., min_length=6, max_length=30, description="Пароль: длина от 6 до 30 символов")
    


    