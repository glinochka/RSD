from openai import AsyncOpenAI

from ..config import settings


ai_client = AsyncOpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)


def _clean_plain_text(text: str) -> str:
    if not text:
        return ""
    return text.replace("#", "").replace("*", "").strip()


async def improve_prompt_with_ai(current_prompt: str) -> str:
    """
    Turn a rough role description into a structured system prompt.
    """
    instruction = (
        "Ты — эксперт по разработке системных промптов для больших языковых моделей. "
        "Твоя задача: взять сырое описание роли бота и превратить его в четкую, структурированную инструкцию.\n\n"
        "Используй следующую структуру:\n"
        "1. Роль и контекст.\n"
        "2. Основные задачи.\n"
        "3. Стиль общения и ограничения.\n"
        "4. Правило: всегда использовать предоставленные документы из базы знаний.\n\n"
        f"Текущее описание/промпт: {current_prompt}\n\n"
        "Напиши только текст итогового промпта, без лишних вступлений.\n"
        "ВАЖНО: Отвечай только чистым текстом. Не используй markdown-форматирование."
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": instruction}],
        temperature=1.0,
    )
    return (response.choices[0].message.content or "").strip()


async def generate_welcome_with_ai(system_prompt: str) -> str:
    """
    Generate a short welcome message based on an agent's system prompt.
    """
    prompt = (
        "Ты профессиональный копирайтер. Напиши короткое, дружелюбное и вовлекающее приветственное "
        "сообщение (максимум 2-3 предложения) для Telegram-бота от первого лица. "
        "Пользователь увидит это сообщение после нажатия кнопки /start.\n\n"
        "Обязательно опирайся на системный промпт бота, чтобы передать его характер и суть работы.\n"
        "Пиши только текст приветствия, без кавычек и лишних пояснений.\n\n"
        f"Системный промпт бота:\n{system_prompt}\n\n"
        "ВАЖНО: Отвечай только чистым текстом. Не используй markdown-форматирование."
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.7,
    )
    return (response.choices[0].message.content or "").strip()


async def generate_answer_with_context(question: str, context_list: list, system_prompt: str) -> str:
    if not context_list:
        context_text = "Информации в базе знаний не найдено."
    else:
        context_parts = [f"Источник: {c.get('source', 'Unknown')}\nТекст: {c.get('text', '')}" for c in context_list]
        context_text = "\n\n---\n\n".join(context_parts)

    full_system_prompt = (
        f"{system_prompt}\n\n"
        "ВАЖНО: Отвечай только чистым текстом.\n"
        "ЗАПРЕЩЕНО использовать markdown-форматирование."
    )
    user_prompt = f"КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:\n{context_text}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}"

    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    raw_answer = (response.choices[0].message.content or "").strip()
    if not raw_answer:
        return "Не удалось сформулировать ответ. Задайте вопрос чуть подробнее."
    cleaned = _clean_plain_text(raw_answer)
    return cleaned or "Не удалось сформулировать ответ. Задайте вопрос чуть подробнее."
