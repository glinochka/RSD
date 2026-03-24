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
        agent_id = data.get("agent_id")
        
        if agent_id:
            agent_json = await APIread.agentBy_botID(agent_id)
            owner_json = await APIread.userBy_agentID(agent_id)
            if not owner_json.get('error_code'):
                # ПРОВЕРКА СТАТУСА ПОДПИСКИ
                # Если дата окончания подписки установлена и она меньше текущего времени (подписка истекла)
                subscription_end_raw = owner_json.get('subscription_end_date')
                if subscription_end_raw:
                    subscription_end_date = datetime.fromisoformat(subscription_end_raw)
                else:
                    subscription_end_date = None

                if subscription_end_date and subscription_end_date < datetime.now(timezone.utc):
                    
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
                data["agent_config"] = {
                    # middleware/handlers treat this `id` as Telegram bot_id
                    "id": agent_json['bot_id'],
                    "system_prompt": agent_json['system_prompt'],
                    "is_active": agent_json['is_active'],
                    "welcome_message": agent_json['welcome_message']
                }
            else:
                print('Http ошибка при получении информации о пользавателе')
    
        # Передаем управление в следующий хендлер (handlers/agent.py)
        return await handler(event, data)