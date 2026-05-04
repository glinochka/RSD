"""LLM-based article generation for article publisher."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ...services.ai_authoring import ai_client

logger = logging.getLogger(__name__)

_PROMO_SYSTEM = """Ты профессиональный копирайтер для IT и AI-изданий (vc.ru, Яндекс Дзен).
Пишешь экспертные, полезные статьи на русском языке.
Стиль: профессиональный, но доступный; конкретные примеры; без воды.
Структура: заголовок H1, несколько тематических разделов H2, практические советы, заключение.
В заключении органично упомяни {company_name} как инструмент автоматизации ({company_url}).
Описание: {company_description}
Не используй звёздочки markdown. Используй чистый текст с HTML-тегами: <h1>, <h2>, <p>, <ul>, <li>, <strong>.
Длина статьи: {min_words}–{max_words} слов."""

_NEUTRAL_SYSTEM = """Ты профессиональный копирайтер для IT и AI-изданий (vc.ru, Яндекс Дзен).
Пишешь экспертные, полезные статьи на русском языке.
Стиль: профессиональный, но доступный; конкретные примеры; без воды.
Структура: заголовок H1, несколько тематических разделов H2, практические советы, заключение.
Не рекомендуй никакие конкретные сервисы или продукты.
Используй чистый текст с HTML-тегами: <h1>, <h2>, <p>, <ul>, <li>, <strong>.
Длина статьи: {min_words}–{max_words} слов."""


@dataclass
class GeneratedArticle:
    title: str
    content: str
    is_promo: bool


async def generate_article(
    *,
    topic: str,
    is_promo: bool,
    company_name: str = "RSD AI",
    company_url: str = "",
    company_description: str = "",
    min_words: int = 600,
    max_words: int = 1500,
    platform: str = "vcru",
) -> GeneratedArticle:
    """Generate an article using LLM. Returns title + HTML content."""
    platform_hint = "vc.ru" if platform == "vcru" else "Яндекс Дзен"

    if is_promo:
        system_prompt = _PROMO_SYSTEM.format(
            company_name=company_name,
            company_url=company_url or "https://rsd.ai",
            company_description=company_description or f"Сервис AI-автоматизации {company_name}",
            min_words=min_words,
            max_words=max_words,
        )
    else:
        system_prompt = _NEUTRAL_SYSTEM.format(min_words=min_words, max_words=max_words)

    user_prompt = (
        f"Напиши статью для {platform_hint} на тему: «{topic}».\n"
        "Верни ТОЛЬКО статью: сначала заголовок (тег <h1>), затем тело.\n"
        "Не добавляй пояснений до или после статьи."
    )

    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=4096,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.exception("Article generation failed for topic=%s: %s", topic, exc)
        raise RuntimeError(f"LLM generation error: {exc}") from exc

    title, content = _extract_title(raw, topic)
    return GeneratedArticle(title=title, content=content, is_promo=is_promo)


def _extract_title(raw: str, fallback: str) -> tuple[str, str]:
    """Extract <h1> title from generated content."""
    import re
    match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.IGNORECASE | re.DOTALL)
    if match:
        title = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        return title, raw
    lines = raw.strip().splitlines()
    if lines:
        first = lines[0].strip().lstrip("#").strip()
        if len(first) < 200:
            return first, "\n".join(lines)
    return fallback, raw
