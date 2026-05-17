from openai import AsyncOpenAI
import logging
import re

from ..config import settings

logger = logging.getLogger(__name__)

ai_client = AsyncOpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

_TEMPLATE_VAR_RE = re.compile(r"(\{\{[^{}]+\}\}|\$\{[^{}]+\}|%\([^)]+\)s)")
_INTERNAL_ASSIGNMENT_RE = re.compile(
    r"\b(staff_id|resource_id|service_id|agent_id|appointment_id|client_external_id|"
    r"slot_id|user_id|chat_id|template_id|lookup_staff_id|new_staff_id|new_resource_id)\s*=\s*\S+",
    re.IGNORECASE,
)


def _clean_plain_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("#", "").replace("*", "")
    cleaned = _TEMPLATE_VAR_RE.sub("технические данные скрыты", cleaned)
    cleaned = _INTERNAL_ASSIGNMENT_RE.sub("технические данные скрыты", cleaned)
    return cleaned.strip()


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
        "ВАЖНО: Промпт должен быть кратким и лаконичным. Не более"
        "ВАЖНО: Отвечай только чистым текстом. Не используй markdown-форматирование. "
        "Никогда не выводи названия переменных/шаблонов и их значения ({{...}}, ${...}, key=value, JSON/XML-поля)."
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
        "ВАЖНО: Отвечай только чистым текстом. Не используй markdown-форматирование. "
        "Никогда не выводи названия переменных/шаблонов и их значения ({{...}}, ${...}, key=value, JSON/XML-поля)."
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.7,
    )
    return (response.choices[0].message.content or "").strip()


def _polish_answer(raw_answer: str | None) -> str:
    text = (raw_answer or "").strip()
    if not text:
        return "Не удалось сформулировать ответ. Задайте вопрос чуть подробнее."
    cleaned = _clean_plain_text(text)
    return cleaned or "Не удалось сформулировать ответ. Задайте вопрос чуть подробнее."


async def generate_answer_with_context(
    question: str,
    context_list: list,
    system_prompt: str,
    *,
    chat_model: str | None = None,
) -> str:
    if not context_list:
        context_text = "Информации в базе знаний не найдено."
    else:
        context_parts = [f"Источник: {c.get('source', 'Unknown')}\nТекст: {c.get('text', '')}" for c in context_list]
        context_text = "\n\n---\n\n".join(context_parts)

    base_system = (
        f"{system_prompt}\n\n"
        "ВАЖНО: Отвечай только чистым текстом.\n"
        "ЗАПРЕЩЕНО использовать markdown-форматирование.\n"
        "ЗАПРЕЩЕНО показывать названия переменных/шаблонов и их значения ({{...}}, ${...}, key=value, JSON/XML-поля)."
    )

    user_prompt = f"КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:\n{context_text}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}"
    model = (chat_model or "deepseek-chat").strip() or "deepseek-chat"

    response = await ai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": base_system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
    )
    return _polish_answer(response.choices[0].message.content)
