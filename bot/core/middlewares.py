from typing import Any, Awaitable, Callable, Dict
from datetime import datetime, timezone
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from core.backendAPI import APIread


# Эта Middleware достает настройки агента и ПРОВЕРЯЕТ ПОДПИСКУ
class AgentContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        agent_id = data["bot_id"]
        agent_config = {
            "bot_id": data['bot_id'],
            "system_prompt": data['system_prompt'],
            "welcome_message": data['welcome_message']
        }
        # Always inject agent config so handler signature stays valid
        # even when owner lookup/subscription check fails.
        data["agent_config"] = agent_config
        if agent_id:
            owner_json = await APIread.userBy_agentID(agent_id)
            if not owner_json.get('error_code'):
                # ПРОВЕРКА СТАТУСА ПОДПИСКИ
                # Если дата окончания подписки установлена и она меньше текущего времени (подписка истекла)
                subscription_end_raw = owner_json.get('subscription_end_date')
                # For Free/неактивных тарифов поле может быть `None`.
                # В этом случае считаем подписку валидной и пропускаем обработку.
                if not subscription_end_raw:
                    return await handler(event, data)

                subscription_end_date = datetime.fromisoformat(subscription_end_raw)
                date_now = datetime.now(timezone.utc).replace(tzinfo=None)
                if subscription_end_date < date_now:
                    
                    # Если это обычное текстовое сообщение, отвечаем заглушкой
                    if isinstance(event, Message):
                        await event.answer(
                            "⚠️ Извините, но этот бот временно недоступен.\n"
                            "Владельцу бота необходимо проверить статус своей подписки."
                        )
                    
                    # ВАЖНО: Прерываем выполнение!
                    # Мы НЕ вызываем await handler(event, data), 
                    # поэтому код не пойдет в handlers/agent.py и не потратит токены LLM.
                    return
                
                # Если с подпиской всё в порядке, собираем конфиг и пускаем запрос дальше
            else:
                print('Http ошибка при получении информации о пользавателе')
    
        # Передаем управление в следующий хендлер (handlers/agent.py)
        return await handler(event, data)