import asyncio
from html import escape as html_escape

from fastapi import status

from aiogram import Bot, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.backendAPI import APIcreate, APIdelete, APIread, get_response_status
from keyboards.master_kb import get_main_menu
from states.master import CreateAgentSG

from .formatting import escape_md
from .knowledge_helpers import is_public_http_url
from .router import master_router
from .telegram_helpers import safe_callback_answer, safe_edit_callback_message


@master_router.callback_query(F.data.startswith("edit_kb_"))
async def show_knowledge_base(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])

    all_agent_docs = await APIread.allDocsBy_botID(agent_id)

    response_status = get_response_status(all_agent_docs)
    if response_status == status.HTTP_404_NOT_FOUND:
        await safe_callback_answer(callback, "Ошибка: агент не найден.")
        return

    elif response_status != status.HTTP_200_OK:
        await safe_callback_answer(
            callback,
            "Ошибка сервера при попытке получить список документов агента",
        )
        if callback.message:
            await callback.message.answer(
                "Вернитесь в главное меню и попробуйте еще раз.",
                reply_markup=get_main_menu(),
            )
        return

    builder = InlineKeyboardBuilder()

    if all_agent_docs:
        for doc in all_agent_docs:
            short_name = doc["file_name"][:25] + "..." if len(doc["file_name"]) > 25 else doc["file_name"]
            status_emoji = "⏳" if doc["status"] == "processing" else "✅" if doc["status"] == "ready" else "❌"

            builder.button(
                text=f"🗑 {status_emoji} {short_name}",
                callback_data=f"del_doc_conf_{doc['id']}",
            )
        builder.adjust(1)

    builder.row(types.InlineKeyboardButton(text="➕ Добавить файл", callback_data=f"add_doc_{agent_id}"))
    builder.row(types.InlineKeyboardButton(text="🔗 Добавить ссылку", callback_data=f"add_link_{agent_id}"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад к агенту", callback_data=f"agent_info_{agent_id}"))

    text = (
        "📚 *Управление базой знаний*\n\n"
        "Нажмите на источник, который хотите удалить.\n\n"
        "Легенда:\n"
        "✅ — Успешно загружен в ИИ\n"
        "⏳ — В процессе обработки\n"
        "❌ — Ошибка чтения файла"
    ) if all_agent_docs else "📚 *Управление базой знаний*\n\nВ базе данных этого агента пока нет источников."

    await safe_edit_callback_message(callback, text, reply_markup=builder.as_markup(), parse_mode="Markdown")


@master_router.callback_query(F.data.startswith("del_doc_conf_"))
async def confirm_delete_document(callback: types.CallbackQuery):
    doc_id = int(callback.data.split("_")[3])

    doc_json = await APIread.docBy_ID(doc_id)
    response_status = get_response_status(doc_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer("Документ по id не найден", show_alert=True)
            return
        else:
            await callback.answer("Ошибка сервера при попытке получить документ по id", show_alert=True)
            return

    kb_bot_id = doc_json.get("bot_id")
    if kb_bot_id is None:
        await callback.answer(
            "Не удалось открыть подтверждение: у агента не задан bot_id. Обновите сервер или обратитесь в поддержку.",
            show_alert=True,
        )
        return

    text = (
        f"⚠️ *ВНИМАНИЕ!*\n\nВы действительно хотите навсегда удалить файл `{escape_md(doc_json['file_name'])}`?\n"
        f"Бот больше не сможет использовать его для ответов."
    )

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ ОТМЕНА", callback_data=f"edit_kb_{kb_bot_id}"),
                types.InlineKeyboardButton(text="❌ ДА, УДАЛИТЬ", callback_data=f"del_doc_force_{doc_json['id']}"),
            ]
        ]
    )

    await safe_edit_callback_message(callback, text, reply_markup=kb, parse_mode="Markdown")


@master_router.callback_query(F.data.startswith("del_doc_force_"))
async def force_delete_document(callback: types.CallbackQuery):
    doc_id = int(callback.data.split("_")[3])

    response_data = await APIdelete.documentBy_ID(doc_id)
    response_status = get_response_status(response_data)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer("Документ уже был удален", show_alert=True)

            return
        else:
            await callback.answer("Ошибка сервера при попытке удалить документ", show_alert=True)

            return

    bot_id = response_data.get("bot_id")
    if bot_id is None:
        await callback.answer(
            "Файл удалён, но не удалось вернуться в меню базы знаний (нет bot_id в ответе сервера). Откройте раздел из карточки агента.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Файл успешно удален из базы знаний!", show_alert=True)

    fake_callback = types.CallbackQuery(
        id="0",
        from_user=callback.from_user,
        chat_instance="0",
        message=callback.message,
        data=f"edit_kb_{bot_id}",
    )
    await show_knowledge_base(fake_callback)


@master_router.callback_query(F.data.startswith("add_doc_"))
async def prompt_add_document(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])

    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.adding_extra_docs)

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_kb_{agent_id}")],
        ]
    )

    await safe_edit_callback_message(
        callback,
        "📂 *Добавление нового файла*\n\n"
        "Отправьте мне документ (PDF, TXT, DOCX), который нужно загрузить в базу знаний.\n"
        "Можно отправлять по одному файлу.",
        reply_markup=kb,
        parse_mode="Markdown",
    )


@master_router.callback_query(F.data.startswith("add_link_"))
async def prompt_add_link(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])

    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.adding_extra_links)

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_kb_{agent_id}")],
        ]
    )

    await safe_edit_callback_message(
        callback,
        "🔗 *Добавление публичной ссылки*\n\n"
        "Отправьте URL (http/https), который нужно загрузить в базу знаний.\n"
        "Ссылка обрабатывается один раз и не обновляется автоматически.",
        reply_markup=kb,
        parse_mode="Markdown",
    )


@master_router.message(CreateAgentSG.adding_extra_docs, F.document)
async def process_extra_document(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    agent_id = data.get("edit_agent_id")
    if not agent_id:
        await message.answer("Ошибка: потерян ID агента. Начните сначала.")
        await state.clear()
        return

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

    msg = await message.answer(f"⏳ Проверяю лимиты и анализирую файл `{file_name}`...")

    if response_data["status"] == "limit_error":
        await msg.edit_text(
            f"🚫 *Лимит базы знаний превышен!*\n\n"
            f"Ваш тариф: *{response_data['current_plan']}* (макс. {response_data['limit']} чанков).\n"
            f"Уже использовано: {response_data['current_count']}.\n"
            f"Файл содержит: {response_data['new_chunks_count']}.\n\n"
            f"Удалите старые документы или повысьте тариф в меню.",
            parse_mode="Markdown",
        )
        return

    await msg.edit_text(
        f"✅ Файл `{file_name}` принят и обрабатывается ({response_data['new_chunks_count']} чанков).\n"
        f"Текущий тариф: {response_data.get('current_plan', 'unknown')} "
        f"(лимит: {response_data.get('limit', 'unknown')}, уже занято: {response_data.get('current_count', 'unknown')})."
    )

    await asyncio.sleep(2)
    fake_callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=f"edit_kb_{agent_id}",
    )
    await show_knowledge_base(fake_callback)


@master_router.message(CreateAgentSG.adding_extra_links, F.text)
async def process_extra_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data.get("edit_agent_id")
    if not agent_id:
        await message.answer("Ошибка: потерян ID агента. Начните сначала.")
        await state.clear()
        return

    url_value = (message.text or "").strip()
    if not is_public_http_url(url_value):
        await message.answer("❌ Нужна корректная публичная ссылка в формате http/https.")
        return

    msg = await message.answer("⏳ Проверяю лимиты и анализирую ссылку...")
    response_data = await APIcreate.documentLinkBy_botID(agent_id, url_value)
    response_status = get_response_status(response_data)

    if response_status != status.HTTP_200_OK:
        await msg.edit_text("Ошибка сервера при попытке добавить ссылку.")
        return

    if response_data.get("status") == "limit_error":
        await msg.edit_text(
            f"🚫 <b>Лимит базы знаний превышен!</b>\n\n"
            f"Ваш тариф: <b>{html_escape(str(response_data.get('current_plan', 'unknown')))}</b> "
            f"(макс. {response_data.get('limit', 'unknown')} чанков).\n"
            f"Уже использовано: {response_data.get('current_count', 'unknown')}.\n"
            f"Ссылка добавит: {response_data.get('new_chunks_count', 'unknown')}.\n\n"
            f"Удалите старые источники или повысьте тариф в меню.",
            parse_mode="HTML",
        )
        return

    if response_data.get("status") == "duplicate":
        await msg.edit_text(
            f"ℹ️ Ссылка уже добавлена ранее "
            f"(статус: {html_escape(str(response_data.get('document_status', 'ready')))}).",
            parse_mode="HTML",
        )
    else:
        await msg.edit_text(
            f"✅ Ссылка принята и обрабатывается ({response_data.get('new_chunks_count', 'unknown')} чанков).",
            parse_mode="HTML",
        )

    await asyncio.sleep(2)
    fake_callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=f"edit_kb_{agent_id}",
    )
    await show_knowledge_base(fake_callback)
