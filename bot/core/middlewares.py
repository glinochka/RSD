from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


# Эта Middleware достает настройки агента.
# Проверки подписки/фриза и шаблонный runtime выполняются на backend.
class AgentContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        agent_config = {
            "bot_id": data['bot_id'],
            "system_prompt": data['system_prompt'],
            "welcome_message": data['welcome_message'],
            "process_start_with_llm": bool(data.get("process_start_with_llm", False)),
        }
        # Always inject agent config so handler signature stays valid
        # even when owner lookup/subscription check fails.
        data["agent_config"] = agent_config
        return await handler(event, data)