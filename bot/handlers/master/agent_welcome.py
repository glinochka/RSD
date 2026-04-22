from fastapi import status

from aiogram import F, types
from aiogram.fsm.context import FSMContext

from core.backendAPI import APIread, APIupdate, get_response_status
from keyboards.master_kb import get_main_menu
from services.ai_service import generate_welcome_with_ai
from states.master import CreateAgentSG

from .agent_card import render_agent_info
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.callback_query(F.data.startswith("edit_welcome_"))
async def start_edit_welcome(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])
    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.editing_welcome)
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✨ Сгенерировать с ИИ", callback_data=f"gen_welcome_{agent_id}")],
        ]
    )
    await safe_edit_callback_message(
        callback,
        "Введите новое приветственное сообщение или сгенерируйте его с помощью ИИ, которое пользователь увидит при команде /start:",
        reply_markup=kb,
    )
    await callback.answer()


@master_router.message(CreateAgentSG.editing_welcome)
async def process_welcome_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data.get("edit_agent_id")
    welcome_message = message.text

    update_response = await APIupdate.agentWelcomeBy_botID(welcome_message, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        if response_status_agents == status.HTTP_404_NOT_FOUND:
            await message.answer(
                "Агент с таким bot id не найден",
                reply_markup=get_main_menu(),
            )
        else:
            await message.answer(
                "Ошибка сервера при попытке обновить welcome message вашего агента",
                reply_markup=get_main_menu(),
            )
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Приветствие сохранено!")


@master_router.callback_query(F.data.startswith("gen_welcome_"))
async def generate_welcome_callback(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])

    await safe_edit_callback_message(
        callback,
        "⏳ *DeepSeek анализирует промпт и генерирует приветствие...*",
        parse_mode="Markdown",
    )

    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer("Агент по bot id не найден")
            return
        else:
            await callback.answer("Ошибка сервера при попытке получить агента по bot id")
            return

    generated_text = await generate_welcome_with_ai(agent_json["system_prompt"])
    update_response = await APIupdate.agentWelcomeBy_botID(generated_text, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        if response_status_agents == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                "Агент с таким bot id не найден",
                reply_markup=get_main_menu(),
            )
        else:
            await callback.answer(
                "Ошибка сервера при попытке обновить welcome message вашего агента",
                reply_markup=get_main_menu(),
            )
        await state.clear()
        return

    await state.clear()

    await callback.answer("✅ Приветствие сгенерировано и сохранено", show_alert=True)
    await render_agent_info(callback, agent_id)
