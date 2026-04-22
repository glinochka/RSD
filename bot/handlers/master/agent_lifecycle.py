from fastapi import status

from aiogram import Bot, F, types

from core.backendAPI import APIdelete, APIread, APIupdate, get_response_status
from core.config import settings
from core.crypto import decrypt_token

from .agent_card import render_agent_info
from .agents_list import show_my_agents
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.callback_query(F.data.startswith("toggle_agent_"))
async def toggle_agent(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])

    agent_json = await APIupdate.agentToggle_status(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer("Агент по bot id не найден")
            return
        else:
            await callback.answer("Ошибка сервера при попытке получить агента по bot id")
            return

    new_status = agent_json["is_active"]

    try:
        temp_bot = Bot(token=decrypt_token(agent_json["encrypted_token"]))

        if new_status:
            webhook_url = f"{settings.BASE_URL}/webhook/{agent_id}"
            await temp_bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
            )

        else:
            await temp_bot.delete_webhook()

        await temp_bot.session.close()
    except Exception as e:
        print(f"Ошибка вебхука при переключении: {e}")

    await callback.answer(f"Статус изменен: {'Включен' if new_status else 'Отключен'}")
    await render_agent_info(callback, agent_id)


@master_router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: types.CallbackQuery):
    agent_id = callback.data.split("_")[2]

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="❌ ДА, УДАЛИТЬ", callback_data=f"delete_force_{agent_id}"),
                types.InlineKeyboardButton(text="✅ ОТМЕНА", callback_data=f"agent_info_{agent_id}"),
            ]
        ]
    )

    await safe_edit_callback_message(
        callback,
        "⚠️ *ВНИМАНИЕ!*\nВы уверены, что хотите удалить этого агента? Все данные и привязка бота будут стерты.",
        reply_markup=kb,
        parse_mode="Markdown",
    )


@master_router.callback_query(F.data.startswith("delete_force_"))
async def delete_agent(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])
    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)
    if response_status == status.HTTP_200_OK:
        try:
            temp_bot = Bot(token=decrypt_token(agent_json["encrypted_token"]))
            await temp_bot.delete_webhook()
            await temp_bot.session.close()
        except Exception:
            await callback.answer("Ошибка при отключении веб хука")

        del_response = await APIdelete.agentBy_botID(agent_id)
        del_response_status = get_response_status(del_response)

        if del_response_status != status.HTTP_200_OK and del_response_status != status.HTTP_404_NOT_FOUND:
            await callback.answer("Произошла ошибка на сервере при удалении.", show_alert=True)
            await show_my_agents(callback)

        await callback.answer("Агент полностью удален.", show_alert=True)
        await show_my_agents(callback)

    elif response_status == status.HTTP_404_NOT_FOUND:
        await callback.answer("Агент уже был удален.")
    else:
        await callback.answer("Ошибка на сервере при попытке получить агента по bot id.")
