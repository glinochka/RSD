from fastapi import status

from aiogram import F, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext

from core.backendAPI import APIcreate, APIread, get_response_status
from keyboards.master_kb import get_main_menu

from .account_linking import respond_to_telegram_link_code
from .formatting import build_start_menu_text, escape_md
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    user_json = await APIread.userBy_tgID(message.from_user.id)

    response_status = get_response_status(user_json)
    if response_status == status.HTTP_404_NOT_FOUND:
        await APIcreate.userBy_tgID(message.from_user.username, message.from_user.id)

    elif response_status != status.HTTP_200_OK:
        await message.answer(
            "Ошибка сервера при попытке Вас зарегестрировать",
            reply_markup=get_main_menu(),
        )
        return

    await message.answer(
        build_start_menu_text(message.from_user.first_name),
        reply_markup=get_main_menu(),
    )


@master_router.message(StateFilter(None), F.text.regexp(r"^\d{6}$"))
async def link_website_account_by_code(message: types.Message):
    raw_code = (message.text or "").strip()
    await respond_to_telegram_link_code(message, raw_code)


@master_router.callback_query(F.data == "start_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await safe_edit_callback_message(
        callback,
        build_start_menu_text(callback.from_user.first_name),
        reply_markup=get_main_menu(),
    )
    await callback.answer()


@master_router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    tg_id = callback.from_user.id

    all_user_agents = await APIread.allAgentsBy_tgID(tg_id)

    response_status = get_response_status(all_user_agents)
    if response_status == status.HTTP_404_NOT_FOUND:
        await callback.answer("Ошибка: пользователь не найден.")
        return

    elif response_status != status.HTTP_200_OK:
        await callback.answer(
            "Ошибка сервера при попытке получить всех ваших агентов",
            reply_markup=get_main_menu(),
        )
        return

    if all_user_agents:
        agents_names = [agent.get("bot_username") for agent in all_user_agents]
    else:
        agents_names = []

    if len(agents_names) > 5:
        agents_names = agents_names[:5]

    agents_list_str = "\n".join([f"• @{escape_md(name)}" for name in agents_names if name]) if agents_names else "У вас пока нет агентов."

    profile_text = (
        "👤 *Мой профиль*\n\n"
        f"🆔 Ваш ID: `{tg_id}`\n"
        f"🤖 Создано агентов: {len(all_user_agents)}\n\n"
        "*Ваши последние боты:*\n"
        f"{agents_list_str}\n\n"
        "💡 Здесь можно управлять подпиской."
    )

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="start_menu")],
        ]
    )

    try:
        await callback.message.edit_text(profile_text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Ошибка парсинга Markdown: {e}")
        await callback.message.edit_text(profile_text.replace("*", "").replace("`", ""), reply_markup=kb)


@master_router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await safe_edit_callback_message(
        callback,
        "👋 Привет! Я Мастер-бот для создания AI-агентов.\n\n"
        "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний.",
        reply_markup=get_main_menu(),
    )
