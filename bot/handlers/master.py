import os
import asyncio
from fastapi import status
from aiogram import Router, F, Bot, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from aiogram.filters import StateFilter
from core.backendAPI import APIread, APIcreate, APIupdate, APIdelete, get_response_status
from core.config import settings
from core.crypto import encrypt_token

from states.master import CreateAgentSG
from keyboards.master_kb import get_main_menu
from aiogram.utils.keyboard import InlineKeyboardBuilder
from core.crypto import decrypt_token  

from services.ai_service import generate_welcome_with_ai
from services.ai_service import improve_prompt_with_ai

from datetime import datetime, timedelta, timezone

from keyboards.master_kb import get_main_menu, get_tariffs_keyboard

master_router = Router()

# --- Вспомогательная функция для безопасности Markdown ---
def escape_md(text: str) -> str:
    """Экранирует нижнее подчеркивание для стандартного Markdown."""
    if not text:
        return ""
    return text.replace("_", "\\_")

# --- ГЛАВНОЕ МЕНЮ ---

@master_router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Логика регистрации пользователя
    await state.clear()

    user_json = await APIread.userBy_tgID(message.from_user.id)
    
    response_status = get_response_status(user_json)
    if response_status == status.HTTP_404_NOT_FOUND:

        await APIcreate.userBy_tgID(message.from_user.username, message.from_user.id)
        
    elif response_status != status.HTTP_200_OK: 
        await message.answer(
                    f"Ошибка сервера при попытке Вас зарегестрировать",
                    reply_markup=get_main_menu())
        return 

    await message.answer(
        f"Привет, {message.from_user.first_name}! Это конструктор AI-агентов.\n\n"
        "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний.",
        reply_markup=get_main_menu()
    )

@master_router.callback_query(F.data == "start_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.delete()
    await cmd_start(callback.message)


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
            f"Ошибка сервера при попытке получить всех ваших агентов",
            reply_markup=get_main_menu()
        )
        return 
    
    if all_user_agents:
        agents_names = [agent.get('bot_username') for agent in all_user_agents]
    else:
        agents_names = []

    if len(agents_names) > 5:
        agents_names = agents_names[:5]

    # Экранируем юзернеймы ботов, чтобы подчеркивания не ломали Markdown
    agents_list_str = "\n".join([f"• @{escape_md(name)}" for name in agents_names if name]) \
        if agents_names else "У вас пока нет агентов."
    
    profile_text = (
        "👤 *Мой профиль*\n\n"
        f"🆔 Ваш ID: `{tg_id}`\n"
        f"🤖 Создано агентов: {len(all_user_agents)}\n\n"
        "*Ваши последние боты:*\n"
        f"{agents_list_str}\n\n"
        "💡 Здесь можно управлять подпиской."
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="start_menu")]
    ])

    try:
        await callback.message.edit_text(profile_text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        # Если Markdown всё равно упадет, отправляем чистым текстом
        print(f"❌ Ошибка парсинга Markdown: {e}")
        await callback.message.edit_text(profile_text.replace("*", "").replace("`", ""), reply_markup=kb)

# --- СОЗДАНИЕ АГЕНТА ---

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
            f"Ошибка сервера при попытке получить пользователя",
            reply_markup=get_main_menu()
            )
        return 


    all_user_agents = await APIread.allAgentsBy_tgID(tg_id)
    response_status_agents = get_response_status(all_user_agents)

    if response_status_agents != status.HTTP_200_OK: 
        await callback.answer(
            f"Ошибка сервера при попытке получить всех ваших агентов",
            reply_markup=get_main_menu()
        )
        return 

    agents_count = len(all_user_agents)
    #  Определяем лимиты согласно ТЗ
    # Базовый (Free) — 1, Продвинутый — 5, Pro — 20
    limits = {
        "Free": 1,
        "Advanced": 5,
        "Pro": 20
    }
    
    current_limit = limits.get(user_json['subscription_type'], 1)

    #  Проверяем превышение лимита
    if agents_count >= current_limit:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💎 Повысить тариф", callback_data="tariffs_menu")],
            [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
        ])
        
        await callback.message.edit_text(
            f"🚫 *Лимит достигнут*\n\n"
            f"На вашем тарифе (*{user_json['subscription_type']}*) можно создать не более {current_limit} агентов.\n"
            f"У вас уже создано: {agents_count}.\n\n"
            f"Чтобы создавать больше ботов, пожалуйста, обновите тарифную подписку.",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    #  Если лимит не превышен, запускаем стандартный процесс создания
    await state.set_state(CreateAgentSG.waiting_token)
    await callback.message.answer(
        "🤖 *Создание нового агента*\n\n"
        "Для начала работы мне нужен API токен вашего бота.\n"
        "Получить его можно у @BotFather.",
        parse_mode="Markdown"
    )
    await callback.answer()

@master_router.message(CreateAgentSG.waiting_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    try:
        temp_bot = Bot(token=token)
        bot_info = await temp_bot.get_me()
        
        # --- ПРОВЕРКА ПО УНИКАЛЬНОМУ ID БОТА ---
        # Это защитит от смены username
        existing_agent_json = await APIread.agentBy_botID(bot_info.id)
        response_status = get_response_status(existing_agent_json)

        if response_status == status.HTTP_200_OK:
            await temp_bot.session.close()
            return await message.answer(
                f"❌ Этот бот (ID: {bot_info.id}) уже зарегистрирован в системе под юзернеймом @{escape_md(bot_info.username)}.\n"
                "Один и тот же бот не может быть добавлен дважды."
            )
        elif response_status != status.HTTP_404_NOT_FOUND:
            return await message.answer(
                f"Ошибка сервера при попытке получить агента по bot id"
            )
        # ---------------------------------------


        tg_id = message.from_user.id

        response = await APIcreate.agentBy_UserWith_tgID(bot_id = bot_info.id,
                                              encrypted_token = encrypt_token(token),
                                              bot_username = bot_info.username,
                                              tg_id = tg_id)
        #для просмотра возможных ошибок
        get_response_status(response)

        # Ставим вебхук с очисткой очереди
        await temp_bot.set_webhook(
            url=f"{os.getenv('BASE_URL')}/webhook/{bot_info.id}",
            drop_pending_updates=True
        )
        await temp_bot.session.close()

        await state.update_data(agent_id = bot_info.id)
        await message.answer(f"✅ Бот @{escape_md(bot_info.username)} успешно подключен!\nТеперь напиши системный промпт:")
        await state.set_state(CreateAgentSG.waiting_prompt)

    except Exception as e:
        if 'temp_bot' in locals(): await temp_bot.session.close()
        await message.answer(f"❌ Ошибка: {e}")

@master_router.message(CreateAgentSG.waiting_prompt)
async def process_prompt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data['agent_id']
    newPrompt = message.text
    update_response = await APIupdate.agentPromptBy_botID(newPrompt, agent_id)
    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK: 
        await message.answer(
            f"Ошибка сервера при попытке обновить промпт вашего агента",
            reply_markup=get_main_menu()
        )
        return 

    await message.answer("Отправь файлы (.pdf, .docx, .txt). Когда закончишь, нажми /start")
    await state.set_state(CreateAgentSG.waiting_docs)

@master_router.message(CreateAgentSG.waiting_docs, F.document)
async def handle_docs(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    agent_id = data['agent_id']
    file_name = message.document.file_name
    
    file = await bot.get_file(message.document.file_id)
    bytes_data = (await bot.download_file(file.file_path)).read() 
    file_name = message.document.file_name

    response_data = await APIcreate.documentBy_botID(agent_id, file_name, bytes_data)
    response_status = get_response_status(response_data)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await message.answer(
                f"Ресурс на сервере не найден", show_alert=True
            )
            await state.clear()
            return 
        else:
            await message.answer(
                f"Ошибка сервера при попытке добавить документ", show_alert=True
            )
            await state.clear()
            return 
        
    if response_data['status'] == 'limit_error':

        await message.answer(
            f"🚫 *Лимит базы знаний превышен!*\n\n"
            f"Ваш тариф: *{response_data['current_plan']}* (макс. {response_data['limit']} чанков).\n"
            f"Уже использовано: {response_data['current_count']}.\n"
            f"Файл содержит: {response_data['new_chunks_count']}.\n\n"
            f"Удалите старые документы или повысьте тариф в меню.",
            parse_mode="Markdown"
        )
        return


    await message.answer(
        f"✅ Файл '_{escape_md(file_name)}_' принят и обрабатывается ({response_data['new_chunks_count']} чанков).",
        parse_mode="Markdown"
    )

# --- МОИ АГЕНТЫ (СПИСОК) ---

@master_router.callback_query(F.data == "my_agents")
async def show_my_agents(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    
    # Достаем всех агентов этого пользователя
    all_user_agents = await APIread.allAgentsBy_tgID(tg_id)
    response_status_agents = get_response_status(all_user_agents)

    if response_status_agents != status.HTTP_200_OK: 
        await callback.answer(
            f"Ошибка сервера при попытке получить всех ваших агентов",
            reply_markup=get_main_menu()
        )
        return

    # Если агентов нет
    if not all_user_agents:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Создать агента", callback_data="add_agent")],
            [types.InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="start_menu")]
        ])
        await callback.message.edit_text(" У вас пока нет созданных ботов.\nСамое время создать первого!", reply_markup=kb)
        return

    # Если агенты есть, собираем клавиатуру через Builder
    builder = InlineKeyboardBuilder()
    for agent in all_user_agents:
        
        status_emoji = "🟢" if agent['is_active'] else "🔴"
        bot_name = f"@{agent['bot_username']}" if agent['bot_username'] else f"Агент #{agent['bot_id']}"
        button_text = f"{status_emoji} {bot_name}"
        
        builder.button(text=button_text, callback_data=f"agent_info_{agent['bot_id']}")
    
    # Делаем по 1 кнопке в ряд
    builder.adjust(1)
    # Добавляем кнопку возврата в конце
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="start_menu"))

    await callback.message.edit_text(
        "🤖 *Ваши агенты:*\nВыберите бота для просмотра подробной информации:", 
        reply_markup=builder.as_markup(), 
        parse_mode="Markdown"
    )

# --- ИНФОРМАЦИЯ О КОНКРЕТНОМ АГЕНТЕ ---

@master_router.callback_query(F.data.startswith("agent_info_"))
async def show_agent_info(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])

    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Агент по bot id не найден"
            )
            return 
        else:
            await callback.answer(
                f"Ошибка сервера при попытке получить агента по bot id"
            )
            return 

    

    welcome_display = agent_json['welcome_message'] if agent_json['welcome_message'] else "❌ Не установлено"

    bot_name = escape_md(agent_json['bot_username']) if agent_json['bot_username'] else "Бот"
    status_text = "✅ Активен" if agent_json['is_active'] else "❌ Отключен"
    toggle_label = "🔴 Отключить" if agent_json['is_active'] else "🟢 Включить"
    
    text = (
        f"🤖 *Управление агентом*\n\n"
        f"ID: `{agent_id}`\n"
        f"🔗 *Бот:* @{bot_name}\n"
        f"📊 *Статус:* {status_text}\n"
        f"👋 *Приветствие:* {welcome_display}\n\n"
        f"🧠 *Промпт:* \n_{escape_md(agent_json['system_prompt'][:200])}..._"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
       [
        types.InlineKeyboardButton(text="📝 Изменить промпт", callback_data=f"edit_prompt_{agent_id}"),
        types.InlineKeyboardButton(text="👋 Изменить приветствие", callback_data=f"edit_welcome_{agent_id}")
        ],
        [types.InlineKeyboardButton(text="📚 Редактировать базу знаний", callback_data=f"edit_kb_{agent_id}")],
        [
            types.InlineKeyboardButton(text=toggle_label, callback_data=f"toggle_agent_{agent_id}"),
            types.InlineKeyboardButton(text="🗑 Удалить бота", callback_data=f"confirm_delete_{agent_id}")
        ],
        [types.InlineKeyboardButton(text="⬅️ К списку агентов", callback_data="my_agents")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

# --- ПЕРЕКЛЮЧЕНИЕ СТАТУСА ---

@master_router.callback_query(F.data.startswith("toggle_agent_"))
async def toggle_agent(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])

    agent_json = await APIupdate.agentToggle_status(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Агент по bot id не найден"
            )
            return 
        else:
            await callback.answer(
                f"Ошибка сервера при попытке получить агента по bot id"
            )
            return 

    new_status = not agent_json['is_active']

    try:
        from core.crypto import decrypt_token
        temp_bot = Bot(token=decrypt_token(agent_json['encrypted_token']))
        
        if new_status:
            # Добавляем drop_pending_updates=True, чтобы удалить старые сообщения
            webhook_url = f"{settings.BASE_URL}/webhook/{agent_id}"
            await temp_bot.set_webhook(
                url=webhook_url, 
                drop_pending_updates=True  # Игнорировать всё, что прислали, пока бот был выключен
            )
        else:
            # При отключении просто удаляем вебхук
            await temp_bot.delete_webhook()
            
        await temp_bot.session.close()
    except Exception as e:
        print(f"Ошибка вебхука при переключении: {e}")

    await callback.answer(f"Статус изменен: {'Отключен' if new_status else 'Включен'}")
    await show_agent_info(callback)

# --- УДАЛЕНИЕ АГЕНТА ---

@master_router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: types.CallbackQuery):
    agent_id = callback.data.split("_")[2]
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="❌ ДА, УДАЛИТЬ", callback_data=f"delete_force_{agent_id}"),
            types.InlineKeyboardButton(text="✅ ОТМЕНА", callback_data=f"agent_info_{agent_id}")
        ]
    ])
    
    await callback.message.edit_text(
        "⚠️ *ВНИМАНИЕ!*\nВы уверены, что хотите удалить этого агента? Все данные и привязка бота будут стерты.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@master_router.callback_query(F.data.startswith("delete_force_"))
async def delete_agent(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])
    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)
    if response_status == status.HTTP_200_OK:
        try:
            # 1. Отключаем вебхук перед удалением
            temp_bot = Bot(token = decrypt_token(agent_json['encrypted_token']))
            await temp_bot.delete_webhook()
            await temp_bot.session.close()
        except:
            await callback.answer("Ошибка при отключении веб хука")

        del_response = await APIdelete.agentBy_botID(agent_id)
        del_response_status = get_response_status(del_response)
        
        if del_response_status != status.HTTP_200_OK and del_response_status != status.HTTP_404_NOT_FOUND:
            await callback.answer("Произошла ошибка на сервере при удалении.", show_alert=True)
            await show_my_agents(callback)

        await callback.answer("Агент полностью удален.", show_alert=True)
        await show_my_agents(callback) # Возвращаемся к списку
        
    elif response_status == status.HTTP_404_NOT_FOUND :
        await callback.answer("Агент уже был удален.")
    else:
        await callback.answer("Ошибка на сервере при попытке получить агента по bot id.")


# --- РЕДАКТИРОВАНИЕ ПРОМПТА ---

@master_router.callback_query(F.data.startswith("edit_prompt_"))
async def start_edit_prompt(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])
    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.editing_prompt)
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✨ Улучшить текущий через ИИ", callback_data=f"ai_improve_prompt_{agent_id}")]
    ])
    
    await callback.message.answer(
        "📝 *Редактирование системного промпта*\n\n"
        "Введите новую инструкцию для бота. Опишите, как он должен себя вести и на какие вопросы отвечать.\n\n"
        "💡 *Совет:* Чем подробнее инструкция, тем лучше результат.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@master_router.callback_query(F.data.startswith("ai_improve_prompt_"))
async def process_ai_improve_prompt(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[3])
    
    # 1. Получаем текущий промпт агента
    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Агент по bot id не найден"
            )
            return 
        else:
            await callback.answer(
                f"Ошибка сервера при попытке получить агента по bot id"
            )
            return 
        
    if not agent_json['system_prompt']:
        await callback.answer("❌ Сначала введите хотя бы краткое описание роли!", show_alert=True)
        return

    # Визуальный фидбек пользователю
    await callback.message.edit_text(
        "*LLM модель обрабатывает промпт...*", 
        parse_mode="Markdown"
    )
    
    # 2. Генерируем улучшение через сервис
    
    new_prompt = await improve_prompt_with_ai(agent_json['system_prompt'])
    
    # 3. Сохраняем новый промпт в базу данных
    update_response = await APIupdate.agentPromptBy_botID(new_prompt, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK: 
        await callback.answer(
            f"Ошибка сервера при попытке обновить промпт вашего агента",
            reply_markup=get_main_menu()
        )
        return 
    
    # Сбрасываем состояние FSM, так как редактирование завершено
    await state.clear()
    
    # Экранируем текст для безопасного отображения в Markdown
    # Это предотвратит ошибку "can't parse entities", если ИИ выдаст много спецсимволов
    safe_new_prompt = escape_md(new_prompt)
    
    # 4. Отправляем красивое сообщение с результатом (как при приветствии)
    await callback.message.answer(
        f"✅ ИИ модель придумала отличный промпт :\n\n_{safe_new_prompt}_",
        parse_mode="Markdown"
    )
    
    # 5. Возвращаем пользователя к карточке управления агентом
    from handlers.master import show_agent_info
    fake_callback = types.CallbackQuery(
        id="0", 
        from_user=callback.from_user, 
        chat_instance="0",
        message=callback.message, 
        data=f"agent_info_{agent_id}"
    )
    await show_agent_info(fake_callback)

@master_router.message(CreateAgentSG.editing_prompt)
async def process_new_prompt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data.get('edit_agent_id')
    
    if not agent_id:
        await message.answer("Ошибка: ID агента потерян. Попробуй заново через меню.")
        await state.clear()
        return

    # Обновляем промпт в базе
    update_response = await APIupdate.agentPromptBy_botID(message.text, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK: 
        await message.answer(
            f"Ошибка сервера при попытке обновить промпт вашего агента",
            reply_markup=get_main_menu()
        )
        await state.clear()
        return 
    
    
    await state.clear()
    
    # Сразу показываем обновленную карточку агента
    # Для этого имитируем callback
    fake_callback = types.CallbackQuery(
        id="0",
        from_user=message.from_user,
        chat_instance="0",
        message=message,
        data=f"agent_info_{agent_id}"
    )
    
    await message.answer("✅ Системный промпт успешно обновлен!")
    await show_agent_info(fake_callback)

# --- УПРАВЛЕНИЕ БАЗОЙ ЗНАНИЙ (ДОКУМЕНТЫ) ---

@master_router.callback_query(F.data.startswith("edit_kb_"))
async def show_knowledge_base(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])

    # Получаем все документы агента
    all_agent_docs = await APIread.allDocsBy_botID(agent_id)

    response_status = get_response_status(all_agent_docs)
    if response_status == status.HTTP_404_NOT_FOUND:
        await callback.answer("Ошибка: агент не найден.")
        return
    
    elif response_status != status.HTTP_200_OK: 
        await callback.answer(
            f"Ошибка сервера при попытке получить всех ваших документов агентов",
            reply_markup=get_main_menu()
        )
        return 


    builder = InlineKeyboardBuilder()

    if all_agent_docs:
        for doc in all_agent_docs:
            # Обрезаем имя файла, если оно слишком длинное (Telegram лимит на кнопки)
            short_name = doc['file_name'][:25] + "..." if len(doc['file_name']) > 25 else doc['file_name']
            # Индикаторы статуса
            status_emoji = "⏳" if doc['status'] == "processing" else "✅" if doc['status'] == "ready" else "❌"
            
            builder.button(
                text=f"🗑 {status_emoji} {short_name}",
                callback_data=f"del_doc_conf_{doc['id']}"
            )
        builder.adjust(1) # По одной кнопке в ряд
    
    # Кнопки навигации
   
    builder.row(types.InlineKeyboardButton(text="➕ Добавить файл", callback_data=f"add_doc_{agent_id}"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад к агенту", callback_data=f"agent_info_{agent_id}"))

    text = (
        "📚 *Управление базой знаний*\n\n"
        "Нажмите на файл, который хотите удалить.\n\n"
        "Легенда:\n"
        "✅ — Успешно загружен в ИИ\n"
        "⏳ — В процессе обработки\n"
        "❌ — Ошибка чтения файла"
    ) if all_agent_docs else "📚 *Управление базой знаний*\n\nВ базе данных этого агента пока нет файлов."

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")


# --- ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ДОКУМЕНТА ---

@master_router.callback_query(F.data.startswith("del_doc_conf_"))
async def confirm_delete_document(callback: types.CallbackQuery):
    # callback_data имеет вид "del_doc_conf_15", id под индексом 3
    doc_id = int(callback.data.split("_")[3])

    doc_json = await APIread.docBy_ID(doc_id)
    response_status = get_response_status(doc_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Документ по id не найден", show_alert=True
            )
            return 
        else:
            await callback.answer(
                f"Ошибка сервера при попытке получить документ по id", show_alert=True
            )
            return 
        

    text = f"⚠️ *ВНИМАНИЕ!*\n\nВы действительно хотите навсегда удалить файл `{escape_md(doc_json['file_name'])}`?\nБот больше не сможет использовать его для ответов."

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ ОТМЕНА", callback_data=f"edit_kb_{doc_json['agent_id']}"),
            types.InlineKeyboardButton(text="❌ ДА, УДАЛИТЬ", callback_data=f"del_doc_force_{doc_json['id']}")
        ]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# --- ФАКТИЧЕСКОЕ УДАЛЕНИЕ ДОКУМЕНТА ---

@master_router.callback_query(F.data.startswith("del_doc_force_"))
async def force_delete_document(callback: types.CallbackQuery):
    doc_id = int(callback.data.split("_")[3])


    response_data = await APIdelete.documentBy_ID(doc_id)
    response_status = get_response_status(response_data)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Документ уже был удален", show_alert=True
            )

            return 
        else:
            await callback.answer(
                f"Ошибка сервера при попытке удалить документ", show_alert=True
            )

            return 

    agent_id = response_data['agent_id']

    await callback.answer("✅ Файл успешно удален из базы знаний!", show_alert=True)


    # Возвращаемся обратно в меню базы знаний (генерируем фейковый callback)
    fake_callback = types.CallbackQuery(
        id="0", from_user=callback.from_user, chat_instance="0",
        message=callback.message, data=f"edit_kb_{agent_id}"
    )
    await show_knowledge_base(fake_callback)

# --- ДОБАВЛЕНИЕ НОВОГО ДОКУМЕНТА (ЗАПРОС) ---

@master_router.callback_query(F.data.startswith("add_doc_"))
async def prompt_add_document(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])
    
    # Запоминаем, какому агенту добавляем файл
    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.adding_extra_docs)
    
    # Кнопка отмены, чтобы вернуться в список документов
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_kb_{agent_id}")]
    ])
    
    await callback.message.edit_text(
        "📂 *Добавление нового файла*\n\n"
        "Отправьте мне документ (PDF, TXT, DOCX), который нужно загрузить в базу знаний.\n"
        "Можно отправлять по одному файлу.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# --- ПРИЕМ И ОБРАБОТКА НОВОГО ДОКУМЕНТА ---

@master_router.message(CreateAgentSG.adding_extra_docs, F.document)
async def process_extra_document(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    agent_id = data.get('edit_agent_id')
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
            await message.answer(
                f"Ресурс на сервере не найден", show_alert=True
            )
            await state.clear()
            return 
        else:
            await message.answer(
                f"Ошибка сервера при попытке добавить документ", show_alert=True
            )
            await state.clear()
            return 
    # Временное сообщение
    msg = await message.answer(f"⏳ Проверяю лимиты и анализирую файл `{file_name}`...")


    # ПРОВЕРКА: Проходит ли файл в лимит?
    if response_data['status'] == 'limit_error':

        await msg.edit_text(
            f"🚫 *Лимит базы знаний превышен!*\n\n"
            f"Ваш тариф: *{response_data['current_plan']}* (макс. {response_data['limit']} чанков).\n"
            f"Уже использовано: {response_data['current_count']}.\n"
            f"Файл содержит: {response_data['new_chunks_count']}.\n\n"
            f"Удалите старые документы или повысьте тариф в меню.",
            parse_mode="Markdown"
        )
        return

    await msg.edit_text(f"✅ Файл `{file_name}` принят и обрабатывается ({response_data['new_chunks_count']} чанков).")



    # 7. Возврат в меню базы знаний (через небольшую паузу, чтобы успели прочитать)
    await asyncio.sleep(2)
    fake_callback = types.CallbackQuery(
        id="0", from_user=message.from_user, chat_instance="0",
        message=message, data=f"edit_kb_{agent_id}"
    )
    await show_knowledge_base(fake_callback)
@master_router.callback_query(F.data.startswith("edit_welcome_"))
async def start_edit_welcome(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])
    await state.update_data(edit_agent_id=agent_id)
    await state.set_state(CreateAgentSG.editing_welcome)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✨ Сгенерировать с ИИ", callback_data=f"gen_welcome_{agent_id}")]
    ])
    await callback.message.answer("Введите новое приветственное сообщение или сгенерируйте его с помощью ИИ, которое пользователь увидит при команде /start:", reply_markup=kb)
    await callback.answer()

@master_router.message(CreateAgentSG.editing_welcome)
async def process_welcome_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data.get('edit_agent_id')
    welcome_message = message.text
    
    update_response = await APIupdate.agentWelcomeBy_botID(welcome_message, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        if response_status_agents == status.HTTP_404_NOT_FOUND:
            await message.answer(
                f"Агент с таким bot id не найден",
                reply_markup=get_main_menu()
            )
        else: 
            await message.answer(
                f"Ошибка сервера при попытке обновить welcome message вашего агента",
                reply_markup=get_main_menu()
            )
        await state.clear()
        return 
    
    
    await state.clear()
    await message.answer("✅ Приветствие сохранено!")

@master_router.callback_query(F.data.startswith("gen_welcome_"))
async def generate_welcome_callback(callback: types.CallbackQuery, state: FSMContext):
    agent_id = int(callback.data.split("_")[2])
    
    # Меняем сообщение, чтобы пользователь видел процесс
    await callback.message.edit_text("⏳ *DeepSeek анализирует промпт и генерирует приветствие...*", parse_mode="Markdown")
    
    # 1. Достаем агента из БД, чтобы получить его system_prompt
    agent_json = await APIread.agentBy_botID(agent_id)
    response_status = get_response_status(agent_json)

    if response_status != status.HTTP_200_OK:
        if response_status == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Агент по bot id не найден"
            )
            return 
        else:
            await callback.answer(
                f"Ошибка сервера при попытке получить агента по bot id"
            )
            return 
        
    # 2. Генерируем текст через ИИ
    generated_text = await generate_welcome_with_ai(agent_json['system_prompt'])
    
    # 3. Сохраняем в БД
    update_response = await APIupdate.agentWelcomeBy_botID(generated_text, agent_id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        if response_status_agents == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Агент с таким bot id не найден",
                reply_markup=get_main_menu()
            )
        else: 
            await callback.answer(
                f"Ошибка сервера при попытке обновить welcome message вашего агента",
                reply_markup=get_main_menu()
            )
        await state.clear()
        return 
    
    
    # 4. Очищаем состояние (пользователю больше не нужно вводить текст вручную)
    await state.clear()
    
    # 5. Отправляем результат
    await callback.message.answer(
        f"✅ *ИИ модель придумала отличное приветствие:*\n\n_{generated_text}_", 
        parse_mode="Markdown"
    )
    
    # 6. Возвращаем пользователя в меню карточки агента
    from handlers.master import show_agent_info
    fake_callback = types.CallbackQuery(
        id="0", from_user=callback.from_user, chat_instance="0",
        message=callback.message, data=f"agent_info_{agent_id}"
    )
    await show_agent_info(fake_callback)

@master_router.callback_query(F.data == "tariffs_menu")
async def show_tariffs(callback: types.CallbackQuery):
    """Отображение меню тарифов и текущего статуса пользователя."""
    # Получаем данные пользователя из БД
    tg_id = callback.from_user.id
    
    user_json = await APIread.userBy_tgID(tg_id)
    
    response_status_user = get_response_status(user_json)

    if response_status_user == status.HTTP_404_NOT_FOUND:
        await callback.answer("Ошибка: пользователь не найден.")
        return

    elif response_status_user != status.HTTP_200_OK: 
        await callback.answer(
            f"Ошибка сервера при попытке получить пользователя",
            reply_markup=get_main_menu()
            )
        return 
    
    # Если пользователя вдруг нет, или у него нет тарифа, ставим Free
    current_plan = user_json['subscription_type']

    text = (
        f"💎 *Управление подпиской*\n\n"
        f"Ваш текущий тариф: *{current_plan}*\n\n"
        f"🚀 *Доступные планы:*\n\n"
        f"1️⃣ *Базовый (Free)*\n"
        f"— 1 активный агент\n"
        f"— Лимит базы знаний: 100 чанков\n"
        f"— Цена: 0₽/мес\n\n"
        f"2️⃣ *Продвинутый (Advanced)*\n"
        f"— До 5 активных агентов\n"
        f"— Лимит базы знаний: 500 чанков\n"
        f"— Цена: 1 990₽/мес\n\n"
        f"3️⃣ *Pro*\n"
        f"— До 20 активных агентов\n"
        f"— Лимит базы знаний: Безлимит\n"
        f"— Цена: 9 990₽/мес\n"
    )

    await callback.message.edit_text(
        text, 
        reply_markup=get_tariffs_keyboard(), 
        parse_mode="Markdown"
    )


@master_router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    """Возврат в главное меню из тарифов."""
    await callback.message.edit_text(
        "👋 Привет! Я Мастер-бот для создания AI-агентов.\n\n"
        "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний.",
        reply_markup=get_main_menu()
    )


@master_router.callback_query(F.data.startswith("set_plan_"))
async def process_set_plan(callback: types.CallbackQuery):
    """Имитация оплаты: переключение тарифа в БД."""
    plan_name = callback.data.split("_")[2] # Достаем название плана (Advanced или Pro)
    
    # Имитируем оплату: ставим тариф на 30 дней вперед
    end_date = datetime.now(timezone.utc) + timedelta(days=30)
    
    # Обновляем запись пользователя в базе
    
    update_response = await APIupdate.userSubBy_tgID(plan_name, end_date, callback.from_user.id)

    response_status_agents = get_response_status(update_response)

    if response_status_agents != status.HTTP_200_OK:
        if response_status_agents == status.HTTP_404_NOT_FOUND:
            await callback.answer(
                f"Пользователь не найден",
                reply_markup=get_main_menu()
            )
        else: 
            await callback.answer(
                f"Ошибка сервера при попытке обновить вашу подписку",
                reply_markup=get_main_menu()
            )

        await show_tariffs(callback)
        return 
    
    await callback.answer(f"✅ Тариф {plan_name} успешно активирован на 30 дней!", show_alert=True)
    
    # Сразу обновляем интерфейс, чтобы пользователь увидел изменения
    await show_tariffs(callback)