from fastapi import status

from aiogram import F, types

from core.backendAPI import APIcreate, APIread, get_response_status

from .router import master_router
from .telegram_helpers import build_copy_api_key_button, safe_callback_answer, safe_edit_callback_message


async def render_api_key_menu(callback: types.CallbackQuery, agent_id: int):
    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)
    if response_status != status.HTTP_200_OK:
        await safe_callback_answer(
            callback,
            "Не удалось открыть меню API ключа. Попробуйте позже.",
            show_alert=True,
        )
        return

    external_api_key = agent_json.get("external_api_key")
    api_key_button = build_copy_api_key_button(external_api_key)
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                api_key_button,
                types.InlineKeyboardButton(
                    text="♻️ Перевыпустить ключ",
                    callback_data=f"confirm_regen_api_key_{agent_id}",
                ),
            ],
            [types.InlineKeyboardButton(text="⬅️ Назад к агенту", callback_data=f"agent_info_{agent_id}")],
        ]
    )
    text = (
        "🔑 *API ключ агента*\n\n"
        "Вы можете скопировать API ключ вашего агента, чтобы интегрировать его "
        "в свой сервис через API-запросы.\n\n"
        "⚠️ Если вы перевыпустите ключ, старый ключ сразу перестанет работать."
    )
    await safe_edit_callback_message(callback, text, reply_markup=kb, parse_mode="Markdown")


@master_router.callback_query(F.data.startswith("api_menu_"))
async def show_api_menu(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])
    await render_api_key_menu(callback, agent_id)


@master_router.callback_query(F.data == "api_key_unavailable")
async def api_key_unavailable(callback: types.CallbackQuery):
    await safe_callback_answer(
        callback,
        "API ключ временно недоступен. Попробуйте открыть карточку агента еще раз.",
        show_alert=True,
    )


@master_router.callback_query(F.data.startswith("confirm_regen_api_key_"))
async def confirm_regenerate_api_key(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[4])
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Да, перевыпустить", callback_data=f"regen_api_key_{agent_id}"),
                types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"api_menu_{agent_id}"),
            ]
        ]
    )
    await safe_edit_callback_message(
        callback,
        "⚠️ Вы точно хотите перевыпустить ключ?\n\nНынешний API ключ больше не будет активен.",
        reply_markup=kb,
    )


@master_router.callback_query(F.data.startswith("regen_api_key_"))
async def regenerate_api_key(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[3])
    result = await APIcreate.regenerateExternalAgentApiKey(agent_id)
    response_status = get_response_status(result)
    if response_status != status.HTTP_200_OK:
        await safe_callback_answer(
            callback,
            "Не удалось перевыпустить API ключ. Попробуйте позже.",
            show_alert=True,
        )
        return

    await safe_callback_answer(callback, "API ключ перевыпущен", show_alert=True)
    await render_api_key_menu(callback, agent_id)
