from fastapi import status

from aiogram import F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.backendAPI import APIread, get_response_status
from keyboards.master_kb import get_main_menu

from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.callback_query(F.data == "my_agents")
async def show_my_agents(callback: types.CallbackQuery):
    tg_id = callback.from_user.id

    all_user_agents = await APIread.allAgentsBy_tgID(tg_id)
    response_status_agents = get_response_status(all_user_agents)

    if response_status_agents != status.HTTP_200_OK:
        await callback.answer(
            "Ошибка сервера при попытке получить всех ваших агентов",
            reply_markup=get_main_menu(),
        )
        return

    if not all_user_agents:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="➕ Создать агента", callback_data="add_agent")],
                [types.InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="start_menu")],
            ]
        )
        await safe_edit_callback_message(
            callback,
            "У вас пока нет созданных ботов.\nСамое время создать первого!",
            reply_markup=kb,
        )
        return

    builder = InlineKeyboardBuilder()
    for agent in all_user_agents:
        status_emoji = "🟢" if agent["is_active"] else "🔴"
        bot_name = f"@{agent['bot_username']}" if agent["bot_username"] else f"Агент #{agent['bot_id']}"
        button_text = f"{status_emoji} {bot_name}"

        builder.button(text=button_text, callback_data=f"agent_info_{agent['bot_id']}")

    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="start_menu"))

    await safe_edit_callback_message(
        callback,
        "🤖 *Ваши агенты:*\nВыберите бота для просмотра подробной информации:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
