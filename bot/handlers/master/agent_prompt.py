from fastapi import status

from aiogram import F, types
from aiogram.fsm.context import FSMContext

from core.backendAPI import APIread, APIupdate, get_response_status
from keyboards.master_kb import get_main_menu
from services.ai_service import improve_prompt_with_ai
from states.master import CreateAgentSG

from .agent_card import render_agent_info, show_agent_info
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.callback_query(F.data.startswith("edit_prompt_"))
async def start_edit_prompt(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])
    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.editing_prompt)

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✨ Улучшить текущий через ИИ", callback_data=f"ai_improve_prompt_{agent_id}")],
        ]
    )

    await safe_edit_callback_message(
        callback,
        "📝 *Редактирование системного промпта*\n\n"
        "Введите новую инструкцию для бота. Опишите, как он должен себя вести и на какие вопросы отвечать.\n\n"
        "💡 *Совет:* Чем подробнее инструкция, тем лучше результат.",
        reply_markup=kb,
        parse_mode="Markdown",
    )
    await callback.answer()


@master_router.callback_query(F.data.startswith("ai_improve_prompt_"))
async def process_ai_improve_prompt(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[3])

    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer("Агент по bot id не найден")
            return
        else:
            await callback.answer("Ошибка сервера при попытке получить агента по bot id")
            return

    if not agent_json["system_prompt"]:
        await callback.answer("❌ Сначала введите хотя бы краткое описание роли!", show_alert=True)
        return

    await safe_edit_callback_message(
        callback,
        "*LLM модель обрабатывает промпт...*",
        parse_mode="Markdown",
    )

    new_prompt = await improve_prompt_with_ai(agent_json["system_prompt"])
    update_response = await APIupdate.agentPromptBy_botID(new_prompt, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        await callback.answer(
            "Ошибка сервера при попытке обновить промпт вашего агента",
            reply_markup=get_main_menu(),
        )
        return

    await state.clear()

    await callback.answer("✅ Промпт улучшен и сохранен", show_alert=True)
    await render_agent_info(callback, agent_id)


@master_router.message(CreateAgentSG.editing_prompt)
async def process_new_prompt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data.get("edit_agent_id")

    if not agent_id:
        await message.answer("Ошибка: ID агента потерян. Попробуй заново через меню.")
        await state.clear()
        return

    update_response = await APIupdate.agentPromptBy_botID(message.text, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        await message.answer(
            "Ошибка сервера при попытке обновить промпт вашего агента",
            reply_markup=get_main_menu(),
        )
        await state.clear()
        return

    await state.clear()

    fake_callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=f"agent_info_{agent_id}",
    )

    await message.answer("✅ Системный промпт успешно обновлен!")
    await show_agent_info(fake_callback)
