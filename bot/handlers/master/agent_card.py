from fastapi import status

from aiogram import F, types

from core.backendAPI import APIread, get_response_status

from .formatting import escape_md
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


async def render_agent_info(callback: types.CallbackQuery, agent_id: int):
    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer("Агент по bot id не найден")
            return
        else:
            await callback.answer("Ошибка сервера при попытке получить агента по bot id")
            return

    welcome_display = agent_json["welcome_message"] if agent_json["welcome_message"] else "❌ Не установлено"

    bot_name = escape_md(agent_json["bot_username"]) if agent_json["bot_username"] else "Бот"
    status_text = "✅ Активен" if agent_json["is_active"] else "❌ Отключен"
    toggle_label = "🔴 Отключить" if agent_json["is_active"] else "🟢 Включить"
    text = (
        f"🤖 *Управление агентом*\n\n"
        f"ID: `{agent_id}`\n"
        f"🔗 *Бот:* @{bot_name}\n"
        f"📊 *Статус:* {status_text}\n"
        f"👋 *Приветствие:* {welcome_display}\n\n"
        f"🧠 *Промпт:* \n_{escape_md(agent_json['system_prompt'][:200])}..._"
    )

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="📝 Изменить промпт", callback_data=f"edit_prompt_{agent_id}"),
                types.InlineKeyboardButton(text="👋 Изменить приветствие", callback_data=f"edit_welcome_{agent_id}"),
            ],
            [types.InlineKeyboardButton(text="🔑 API ключ", callback_data=f"api_menu_{agent_id}")],
            [types.InlineKeyboardButton(text="📚 Редактировать базу знаний", callback_data=f"edit_kb_{agent_id}")],
            [
                types.InlineKeyboardButton(text=toggle_label, callback_data=f"toggle_agent_{agent_id}"),
                types.InlineKeyboardButton(text="🗑 Удалить бота", callback_data=f"confirm_delete_{agent_id}"),
            ],
            [types.InlineKeyboardButton(text="⬅️ К списку агентов", callback_data="my_agents")],
        ]
    )

    await safe_edit_callback_message(callback, text, reply_markup=kb, parse_mode="Markdown")


@master_router.callback_query(F.data.startswith("agent_info_"))
async def show_agent_info(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])
    await render_agent_info(callback, agent_id)
