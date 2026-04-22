import re
from html import escape as html_escape

from fastapi import status

from aiogram import Bot, F, types
from aiogram.fsm.context import FSMContext

from core.backendAPI import APIcreate, APIread, APIupdate, get_response_status
from core.config import settings
from core.crypto import encrypt_token
from keyboards.master_kb import get_main_menu
from states.master import CreateAgentSG

from .account_linking import respond_to_telegram_link_code
from .formatting import escape_md
from .knowledge_helpers import handle_link_upload_result, is_public_http_url, text_is_not_command
from .plans import get_plans_from_backend
from .router import master_router
from .telegram_helpers import safe_edit_callback_message


@master_router.callback_query(F.data == "add_agent")
async def start_add_agent(callback: types.CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    user_json = await APIread.userBy_tgID(tg_id)

    response_status_user = get_response_status(user_json)

    if response_status_user == status.HTTP_404_NOT_FOUND:
        await callback.answer("Ошибка: пользователь не найден.")
        return

    elif response_status_user != status.HTTP_200_OK:
        await callback.answer(
            "Ошибка сервера при попытке получить пользователя",
            reply_markup=get_main_menu(),
        )
        return

    all_user_agents = await APIread.allAgentsBy_tgID(tg_id)
    response_status_agents = get_response_status(all_user_agents)

    if response_status_agents != status.HTTP_200_OK:
        await callback.answer(
            "Ошибка сервера при попытке получить всех ваших агентов",
            reply_markup=get_main_menu(),
        )
        return

    agents_count = len(all_user_agents)
    plans = await get_plans_from_backend()
    plans_by_code = {p.get("code"): p for p in plans if p.get("code")}
    current_plan_code = user_json.get("subscription_type") or "Free"
    current_plan = plans_by_code.get(current_plan_code) or plans_by_code.get("Free") or {}
    current_limit = int(current_plan.get("max_active_agents") or 1)

    if agents_count >= current_limit:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="💎 Повысить тариф", callback_data="tariffs_menu")],
                [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")],
            ]
        )

        await safe_edit_callback_message(
            callback,
            f"🚫 *Лимит достигнут*\n\n"
            f"На вашем тарифе (*{user_json['subscription_type']}*) можно создать не более {current_limit} агентов.\n"
            f"У вас уже создано: {agents_count}.\n\n"
            f"Чтобы создавать больше ботов, пожалуйста, обновите тарифную подписку.",
            reply_markup=kb,
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await state.set_state(CreateAgentSG.waiting_token)
    await safe_edit_callback_message(
        callback,
        "🤖 *Создание нового агента*\n\n"
        "Для начала работы мне нужен API токен вашего бота.\n"
        "Получить его можно у @BotFather.",
        parse_mode="Markdown",
    )
    await callback.answer()


@master_router.message(CreateAgentSG.waiting_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    if re.fullmatch(r"\d{6}", token):
        response_status = await respond_to_telegram_link_code(message, token)
        if response_status == status.HTTP_200_OK:
            await state.clear()
        return

    temp_bot = None
    try:
        temp_bot = Bot(token=token)
        bot_info = await temp_bot.get_me()

        existing_agent_json = await APIread.agentBy_botID(bot_info.id)
        response_status = get_response_status(existing_agent_json)

        if response_status == status.HTTP_200_OK:
            return await message.answer(
                f"❌ Этот бот (ID: {bot_info.id}) уже зарегистрирован в системе под юзернеймом @{escape_md(bot_info.username)}.\n"
                "Один и тот же бот не может быть добавлен дважды."
            )
        elif response_status != status.HTTP_404_NOT_FOUND:
            return await message.answer("Ошибка сервера при попытке получить агента по bot id")

        tg_id = message.from_user.id

        response = await APIcreate.agentBy_UserWith_tgID(
            bot_id=bot_info.id,
            encrypted_token=encrypt_token(token),
            bot_username=bot_info.username,
            tg_id=tg_id,
        )
        get_response_status(response)

        await temp_bot.set_webhook(
            url=f"{settings.BASE_URL}/webhook/{bot_info.id}",
            drop_pending_updates=True,
        )

        await state.update_data(agent_id=bot_info.id)
        await message.answer(
            f"✅ Бот @{escape_md(bot_info.username)} успешно подключен!\nТеперь напиши системный промпт:"
        )
        await state.set_state(CreateAgentSG.waiting_prompt)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()


@master_router.message(CreateAgentSG.waiting_prompt)
async def process_prompt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data["agent_id"]
    new_prompt = message.text
    update_response = await APIupdate.agentPromptBy_botID(new_prompt, agent_id)
    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        await message.answer(
            "Ошибка сервера при попытке обновить промпт вашего агента",
            reply_markup=get_main_menu(),
        )
        return

    await message.answer(
        "Отправь файлы (.pdf, .docx, .txt) или публичные ссылки (http/https).\n"
        "Когда закончишь, нажми /start."
    )
    await state.set_state(CreateAgentSG.waiting_docs)


@master_router.message(CreateAgentSG.waiting_docs, F.document)
async def handle_docs(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    agent_id = data["agent_id"]
    file_name = message.document.file_name

    file = await bot.get_file(message.document.file_id)
    bytes_data = (await bot.download_file(file.file_path)).read()
    file_name = message.document.file_name

    response_data = await APIcreate.documentBy_botID(agent_id, file_name, bytes_data)
    response_status = get_response_status(response_data)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await message.answer("Ресурс на сервере не найден", show_alert=True)
            await state.clear()
            return
        else:
            await message.answer("Ошибка сервера при попытке добавить документ", show_alert=True)
            await state.clear()
            return

    if response_data["status"] == "limit_error":
        await message.answer(
            f"🚫 <b>Лимит базы знаний превышен!</b>\n\n"
            f"Ваш тариф: <b>{html_escape(str(response_data['current_plan']))}</b> "
            f"(макс. {response_data['limit']} чанков).\n"
            f"Уже использовано: {response_data['current_count']}.\n"
            f"Файл содержит: {response_data['new_chunks_count']}.\n\n"
            f"Удалите старые документы или повысьте тариф в меню.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"✅ Файл <b>{html_escape(file_name or '')}</b> принят и обрабатывается "
        f"({response_data['new_chunks_count']} чанков).",
        parse_mode="HTML",
    )


@master_router.message(CreateAgentSG.waiting_docs, F.text, F.func(text_is_not_command))
async def handle_link_during_agent_creation(message: types.Message, state: FSMContext):
    url_value = (message.text or "").strip()
    if not is_public_http_url(url_value):
        await message.answer("❌ Нужна корректная публичная ссылка в формате http/https.")
        return

    data = await state.get_data()
    agent_id = data.get("agent_id")
    if not agent_id:
        await message.answer("Ошибка: потерян ID агента. Начните заново через /start.")
        await state.clear()
        return

    response_data = await APIcreate.documentLinkBy_botID(agent_id, url_value)
    response_status = get_response_status(response_data)

    if response_status != status.HTTP_200_OK:
        await message.answer("Ошибка сервера при попытке добавить ссылку.")
        return

    await handle_link_upload_result(message, response_data, source_label="Ссылка")
