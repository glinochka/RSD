"""
Мастер-бот Telegram: регистрация пользователя, агенты, база знаний, тарифы и оплата.
Точка входа для диспетчера — `master_router`.
"""

from .router import master_router

# Подмодули регистрируют хендлеры на master_router при импорте.
from . import (  # noqa: F401
    agent_api_key,
    agent_card,
    agent_creation,
    agent_kb,
    agent_lifecycle,
    agent_prompt,
    agent_welcome,
    agents_list,
    payments,
    start_menu,
)

__all__ = ["master_router"]
