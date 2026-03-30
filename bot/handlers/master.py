import os
import asyncio
from fastapi import status
from aiogram import Router, F, Bot, types
from aiogram.exceptions import TelegramBadRequest
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

from keyboards.master_kb import get_main_menu, get_tariffs_keyboard

master_router = Router()

PAYLOAD_PREFIX = "subscription"

# --- Вспомогательная функция для безопасности Markdown ---
def escape_md(text: str) -> str:
    """Экранирует нижнее подчеркивание для стандартного Markdown."""
    if not text:
        return ""
    return text.replace("_", "\\_")


def build_start_menu_text(first_name: str | None = None) -> str:
    if first_name:
        return (
            f"Привет, {first_name}! Это конструктор AI-агентов.\n\n"
            "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний."
        )
    return (
        "Привет! Это конструктор AI-агентов.\n\n"
        "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний."
    )

async def _get_plans_from_backend() -> list[dict]:
    """
    Single source of truth for plans is the backend (/api/payments/plans).
    Returns list of plan dicts as-is from backend.
    """
    data = await APIread.subscriptionPlans()
    response_status = get_response_status(data)
    if response_status != status.HTTP_200_OK:
        return []
    plans = data.get("plans") if isinstance(data, dict) else None
    return plans or []


def _format_price_rub_month(price_rub_month: int) -> str:
    if not price_rub_month:
        return "0\u20bd/\u043c\u0435\u0441"
    # "1 990" grouping for readability (Russian formatting style).
    return f"{price_rub_month:,}".replace(",", " ") + "\u20bd/\u043c\u0435\u0441"


def _format_kb_limit(limit) -> str:
    if limit is None:
        return "\u0411\u0435\u0437\u043b\u0438\u043c\u0438\u0442"
    return f"{limit} \u0447\u0430\u043d\u043a\u043e\u0432"


def _normalize_surrogates(text: str) -> str:
    """
    Convert valid UTF-16 surrogate pairs into proper Unicode symbols
    and drop broken surrogate code points.
    """
    if not text:
        return text
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "ignore")


def _build_tariffs_text(plans: list[dict], current_plan_code: str) -> str:
    # Keep the numbering stable: Free -> Advanced -> Pro.
    order = {"Free": 1, "Advanced": 2, "Pro": 3}
    plans_sorted = sorted(plans, key=lambda p: order.get(p.get("code"), 999))

    lines: list[str] = [
        "\U0001F48E *\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u043e\u0439*",
        "",
        f"\u0412\u0430\u0448 \u0442\u0435\u043a\u0443\u0449\u0438\u0439 \u0442\u0430\u0440\u0438\u0444: *{current_plan_code}*",
        "",
        "\U0001F680 *\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u043f\u043b\u0430\u043d\u044b:*",
        "",
    ]

    emoji_by_code = {"Free": "1\ufe0f\u20e3", "Advanced": "2\ufe0f\u20e3", "Pro": "3\ufe0f\u20e3"}

    for plan in plans_sorted:
        code = plan.get("code")
        title = plan.get("title") or code
        max_agents = plan.get("max_active_agents")
        kb_limit = plan.get("knowledge_base_chunk_limit")
        price = plan.get("price_rub_month", 0)

        if not code:
            continue

        lines.extend(
            [
                f"{emoji_by_code.get(code, '')} *{title}*".strip(),
                f"\u2014 \u0414\u043e {max_agents} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u0430\u0433\u0435\u043d\u0442\u043e\u0432"
                if code != "Free"
                else f"\u2014 {max_agents} \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0439 \u0430\u0433\u0435\u043d\u0442",
                f"\u2014 \u041b\u0438\u043c\u0438\u0442 \u0431\u0430\u0437\u044b \u0437\u043d\u0430\u043d\u0438\u0439: {_format_kb_limit(kb_limit)}",
                f"\u2014 \u0426\u0435\u043d\u0430: {_format_price_rub_month(int(price or 0))}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def _paid_plans_map(plans: list[dict]) -> dict[str, dict]:
    return {p["code"]: p for p in plans if p.get("is_paid") and p.get("code")}


async def safe_edit_callback_message(
    callback: types.CallbackQuery,
    text: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    if not callback.message:
        await callback.answer("Не удалось обновить сообщение", show_alert=True)
        return

    safe_text = _normalize_surrogates(text)

    try:
        await callback.message.edit_text(
            text=safe_text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as e:
        error_text = str(e).lower()
        # Частые кейсы: старое сообщение уже удалено/не редактируемо.
        if "message is not modified" in error_text:
            return
        if "message to edit not found" in error_text or "message can't be edited" in error_text:
            await callback.message.answer(
                text=safe_text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return
        raise


async def safe_callback_answer(
    callback: types.CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    """
    Safe wrapper for callback.answer.
    It avoids crashing when a synthetic CallbackQuery is not mounted to a bot instance.
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except RuntimeError:
        if text and callback.message:
            await callback.message.answer(text)

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
        build_start_menu_text(message.from_user.first_name),
        reply_markup=get_main_menu()
    )

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
    plans = await _get_plans_from_backend()
    plans_by_code = {p.get("code"): p for p in plans if p.get("code")}
    current_plan_code = user_json.get("subscription_type") or "Free"
    current_plan = plans_by_code.get(current_plan_code) or plans_by_code.get("Free") or {}
    current_limit = int(current_plan.get("max_active_agents") or 1)

    #  Проверяем превышение лимита
    if agents_count >= current_limit:
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💎 Повысить тариф", callback_data="tariffs_menu")],
            [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_start")]
        ])
        
        await safe_edit_callback_message(
            callback,
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
    await safe_edit_callback_message(
        callback,
        "🤖 *Создание нового агента*\n\n"
        "Для начала работы мне нужен API токен вашего бота.\n"
        "Получить его можно у @BotFather.",
        parse_mode="Markdown"
    )
    await callback.answer()

@master_router.message(CreateAgentSG.waiting_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    temp_bot = None
    try:
        temp_bot = Bot(token=token)
        bot_info = await temp_bot.get_me()
        
        # --- ПРОВЕРКА ПО УНИКАЛЬНОМУ ID БОТА ---
        # Это защитит от смены username
        existing_agent_json = await APIread.agentBy_botID(bot_info.id)
        response_status = get_response_status(existing_agent_json)

        if response_status == status.HTTP_200_OK:
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

        await state.update_data(agent_id = bot_info.id)
        await message.answer(f"✅ Бот @{escape_md(bot_info.username)} успешно подключен!\nТеперь напиши системный промпт:")
        await state.set_state(CreateAgentSG.waiting_prompt)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        if temp_bot is not None:
            await temp_bot.session.close()

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
        await safe_edit_callback_message(
            callback,
            "У вас пока нет созданных ботов.\nСамое время создать первого!",
            reply_markup=kb,
        )
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

    await safe_edit_callback_message(
        callback,
        "🤖 *Ваши агенты:*\nВыберите бота для просмотра подробной информации:", 
        reply_markup=builder.as_markup(), 
        parse_mode="Markdown"
    )

# --- ИНФОРМАЦИЯ О КОНКРЕТНОМ АГЕНТЕ ---

@master_router.callback_query(F.data.startswith("agent_info_"))
async def show_agent_info(callback: types.CallbackQuery):
    agent_id = int(callback.data.split("_")[2])
    await render_agent_info(callback, agent_id)


async def render_agent_info(callback: types.CallbackQuery, agent_id: int):
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
    external_api_key = agent_json.get("external_api_key")
    
    text = (
        f"🤖 *Управление агентом*\n\n"
        f"ID: `{agent_id}`\n"
        f"🔗 *Бот:* @{bot_name}\n"
        f"📊 *Статус:* {status_text}\n"
        f"👋 *Приветствие:* {welcome_display}\n\n"
        f"🧠 *Промпт:* \n_{escape_md(agent_json['system_prompt'][:200])}..._"
    )

    api_key_button = (
        types.InlineKeyboardButton(
            text="📋 Скопировать API ключ",
            switch_inline_query_current_chat=external_api_key,
        )
        if external_api_key
        else types.InlineKeyboardButton(
            text="📋 Скопировать API ключ",
            callback_data="api_key_unavailable",
        )
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
       [
        types.InlineKeyboardButton(text="📝 Изменить промпт", callback_data=f"edit_prompt_{agent_id}"),
        types.InlineKeyboardButton(text="👋 Изменить приветствие", callback_data=f"edit_welcome_{agent_id}")
        ],
        [api_key_button],
        [types.InlineKeyboardButton(text="📚 Редактировать базу знаний", callback_data=f"edit_kb_{agent_id}")],
        [
            types.InlineKeyboardButton(text=toggle_label, callback_data=f"toggle_agent_{agent_id}"),
            types.InlineKeyboardButton(text="🗑 Удалить бота", callback_data=f"confirm_delete_{agent_id}")
        ],
        [types.InlineKeyboardButton(text="⬅️ К списку агентов", callback_data="my_agents")]
    ])

    await safe_edit_callback_message(callback, text, reply_markup=kb, parse_mode="Markdown")


@master_router.callback_query(F.data == "api_key_unavailable")
async def api_key_unavailable(callback: types.CallbackQuery):
    await safe_callback_answer(
        callback,
        "API ключ временно недоступен. Попробуйте открыть карточку агента еще раз.",
        show_alert=True,
    )

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
    
    new_status = agent_json['is_active']

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
    await render_agent_info(callback, agent_id)

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
    
    await safe_edit_callback_message(
        callback,
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
    
    await safe_edit_callback_message(
        callback,
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
    await safe_edit_callback_message(
        callback,
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
    
    # 4-5. Даем быстрый фидбек и возвращаем в карточку агента без создания новых сообщений
    await callback.answer("✅ Промпт улучшен и сохранен", show_alert=True)
    await render_agent_info(callback, agent_id)

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

    await safe_edit_callback_message(callback, text, reply_markup=builder.as_markup(), parse_mode="Markdown")


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

    await safe_edit_callback_message(callback, text, reply_markup=kb, parse_mode="Markdown")


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
    
    await safe_edit_callback_message(
        callback,
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

    await msg.edit_text(
        f"✅ Файл `{file_name}` принят и обрабатывается ({response_data['new_chunks_count']} чанков).\n"
        f"Текущий тариф: {response_data.get('current_plan', 'unknown')} "
        f"(лимит: {response_data.get('limit', 'unknown')}, уже занято: {response_data.get('current_count', 'unknown')})."
    )



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
    await safe_edit_callback_message(
        callback,
        "Введите новое приветственное сообщение или сгенерируйте его с помощью ИИ, которое пользователь увидит при команде /start:",
        reply_markup=kb
    )
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
    await safe_edit_callback_message(
        callback,
        "⏳ *DeepSeek анализирует промпт и генерирует приветствие...*",
        parse_mode="Markdown"
    )
    
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
    
    # 5-6. Не создаем лишние сообщения: показываем алерт и обновляем карточку
    await callback.answer("✅ Приветствие сгенерировано и сохранено", show_alert=True)
    await render_agent_info(callback, agent_id)

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
    
    current_plan_code = user_json.get('subscription_type') or "Free"
    plans = await _get_plans_from_backend()
    if not plans:
        await safe_edit_callback_message(
            callback,
            "Не удалось загрузить тарифы с сервера. Попробуйте позже.",
            reply_markup=get_main_menu(),
        )
        return

    text = _build_tariffs_text(plans, current_plan_code)

    await safe_edit_callback_message(
        callback,
        text, 
        reply_markup=get_tariffs_keyboard(), 
        parse_mode="Markdown"
    )


@master_router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    """Возврат в главное меню из тарифов."""
    await safe_edit_callback_message(
        callback,
        "👋 Привет! Я Мастер-бот для создания AI-агентов.\n\n"
        "Здесь ты можешь создать своего бота с кастомными промптами и базой знаний.",
        reply_markup=get_main_menu()
    )


@master_router.callback_query(F.data.startswith("set_plan_"))
async def process_set_plan(callback: types.CallbackQuery):
    """Выставляет инвойс Telegram Payments для выбранного тарифа."""
    plan_name = callback.data.split("_")[2]
    plans = await _get_plans_from_backend()
    paid_plans = _paid_plans_map(plans)
    plan = paid_plans.get(plan_name)
    if not plan:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return

    if not settings.BOT_PAYMENT_TOKEN:
        await callback.answer("Платежи не настроены. Обратитесь в поддержку.", show_alert=True)
        return

    if not callback.message:
        await callback.answer("Не удалось открыть платежное окно. Попробуйте еще раз.", show_alert=True)
        return

    payload = f"{PAYLOAD_PREFIX}:{plan_name}:{callback.from_user.id}"
    prices = [
        types.LabeledPrice(
            label=plan.get("title") or plan_name,
            amount=int(plan.get("telegram_amount_kopecks") or 0),
        )
    ]

    await callback.message.answer_invoice(
        title=f"Подписка {plan.get('title') or plan_name}",
        description=plan.get("telegram_invoice_description") or "",
        payload=payload,
        provider_token=settings.BOT_PAYMENT_TOKEN,
        currency="RUB",
        prices=prices,
        need_email=False,
        need_phone_number=False,
        need_shipping_address=False,
        is_flexible=False,
    )
    await callback.answer("Счет выставлен. Завершите оплату в Telegram.", show_alert=True)


def parse_payment_payload(payload: str) -> tuple[str | None, int | None]:
    """
    Формат payload: subscription:<PlanName>:<telegram_id>
    Возвращает (plan_name, telegram_id) или (None, None), если формат некорректный.
    """
    try:
        prefix, plan_name, tg_id_str = payload.split(":")
        if prefix != PAYLOAD_PREFIX:
            return None, None
        return plan_name, int(tg_id_str)
    except (ValueError, AttributeError):
        return None, None


@master_router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Подтверждает чек-аут только для валидного payload и правильного пользователя."""
    plan_name, payload_tg_id = parse_payment_payload(pre_checkout_query.invoice_payload)

    plans = await _get_plans_from_backend()
    paid_plan_codes = set(_paid_plans_map(plans).keys())
    if plan_name not in paid_plan_codes or payload_tg_id != pre_checkout_query.from_user.id:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Не удалось проверить заказ. Попробуйте снова через меню тарифов."
        )
        return

    await pre_checkout_query.answer(ok=True)


@master_router.message(F.successful_payment)
async def handle_successful_payment(message: types.Message):
    """Активирует подписку только после подтвержденного успешного платежа Telegram."""
    successful_payment = message.successful_payment
    plan_name, payload_tg_id = parse_payment_payload(successful_payment.invoice_payload)

    if plan_name not in PAID_SUBSCRIPTION_PLANS or payload_tg_id != message.from_user.id:
        await message.answer("Платеж получен, но не удалось определить тариф. Напишите в поддержку.")
        return

    process_response = await APIcreate.processSuccessfulPayment(
        telegram_id=message.from_user.id,
        plan_name=plan_name,
        currency=successful_payment.currency,
        total_amount=successful_payment.total_amount,
        telegram_payment_charge_id=successful_payment.telegram_payment_charge_id,
        provider_payment_charge_id=successful_payment.provider_payment_charge_id,
        invoice_payload=successful_payment.invoice_payload,
    )
    process_status = get_response_status(process_response)

    if process_status != status.HTTP_200_OK:
        await message.answer("Оплата прошла, но активация подписки временно недоступна. Напишите в поддержку.")
        return

    process_result = process_response.get("status")
    if process_result == "duplicate":
        await message.answer(
            "ℹ️ Этот платеж уже был обработан ранее. Повторная активация не требуется."
        )
        return

    end_date_text = process_response.get("subscription_end_date")
    if end_date_text:
        try:
            end_date_text = end_date_text.replace("T", " ")[:16]
        except Exception:
            pass

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💎 Открыть тарифы", callback_data="tariffs_menu")],
        [types.InlineKeyboardButton(text="⬅️ В меню", callback_data="start_menu")]
    ])
    await message.answer(
        f"✅ Оплата получена!\n"
        f"Тариф *{plan_name}* активирован до *{end_date_text or 'указанной в профиле даты'}*.",
        parse_mode="Markdown",
        reply_markup=kb,
    )
