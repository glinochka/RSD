from aiogram import Router, types
from fastapi import status
from services.ai_service import get_answer
from core.backendAPI import APIread, APIcreate, get_response_status
agent_router = Router()

@agent_router.message()
async def handle_agent_message(message: types.Message, agent_config: dict):
    """
    Универсальный обработчик. 
    agent_config прилетел сюда из Middleware.
    """
    query = message.text
    if query is None or not str(query).strip():
        await message.answer("Напишите, пожалуйста, текстовое сообщение.")
        return

    query = str(query).strip()
    # Обратите внимание: в agent_config должны быть данные из вашей модели Agent
    agent_id = int(agent_config["bot_id"])
    system_prompt = agent_config["system_prompt"]
    welcome_message = agent_config.get("welcome_message") # Получаем приветствие
    from_user = message.from_user
    user_external_id = str(from_user.id) if from_user and from_user.id else None
    if from_user:
        user_display_name = (from_user.full_name or from_user.username or "").strip() or None
    else:
        user_display_name = None

    if user_external_id:
        frozen_check = await APIread.agentFrozenCheck(agent_id, user_external_id)
        if get_response_status(frozen_check) == status.HTTP_200_OK and frozen_check.get("frozen"):
            await message.answer(
                "Доступ к этому боту для вас временно ограничен владельцем. "
                "Если вы считаете, что это ошибка, свяжитесь с поддержкой."
            )
            return

    # 1. ПРОВЕРКА НА /START
    if query == "/start":
        if welcome_message:
            await message.answer(welcome_message)
        else:
            await message.answer("Здравствуйте! Чем я могу вам помочь?")
        return # Важно: прерываем выполнение функции, чтобы не идти в LLM

    # 2. Поиск по базе знаний (только по этому агенту!)
    # Если это не старт, работаем в обычном режиме
    try:
        await APIcreate.logAgentAnalyticsMessage(
            bot_id=agent_id,
            role="user",
            message_text=query,
            user_external_id=user_external_id,
            user_display_name=user_display_name,
            channel="telegram",
        )
    except Exception:
        # Аналитика не должна ломать пользовательский диалог.
        pass

    context = await APIread.contextBy_botID(agent_id, query)
    
    get_response_status(context)
    # 3. Генерация ответа через LLM с динамическим промптом
    answer = await get_answer(query, context, system_prompt)

    try:
        await APIcreate.logAgentAnalyticsMessage(
            bot_id=agent_id,
            role="agent",
            message_text=answer,
            user_external_id=user_external_id,
            user_display_name=user_display_name,
            channel="telegram",
        )
    except Exception:
        pass
    
    await message.answer(answer)