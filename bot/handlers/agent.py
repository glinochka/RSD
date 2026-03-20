from aiogram import Router, types
from services.ai_service import get_answer
from core.backendAPI import APIread, get_response_status
agent_router = Router()

@agent_router.message()
async def handle_agent_message(message: types.Message, agent_config: dict):
    """
    Универсальный обработчик. 
    agent_config прилетел сюда из Middleware.
    """
    query = message.text
    # Обратите внимание: в agent_config должны быть данные из вашей модели Agent
    agent_id = int(agent_config["bot_id"])
    system_prompt = agent_config["system_prompt"]
    welcome_message = agent_config.get("welcome_message") # Получаем приветствие

    # 1. ПРОВЕРКА НА /START
    if query == "/start":
        if welcome_message:
            await message.answer(welcome_message)
        else:
            await message.answer("Здравствуйте! Чем я могу вам помочь?")
        return # Важно: прерываем выполнение функции, чтобы не идти в LLM

    # 2. Поиск по базе знаний (только по этому агенту!)
    # Если это не старт, работаем в обычном режиме
    context = await APIread.contextBy_botID(agent_id, query)
    
    get_response_status(context)
    # 3. Генерация ответа через LLM с динамическим промптом
    answer = await get_answer(query, context, system_prompt)
    
    await message.answer(answer)