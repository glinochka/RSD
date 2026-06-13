"""Auto topic generation via web search (DuckDuckGo HTML) and RSS feeds."""
from __future__ import annotations

import logging
import random
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DDG_URL = "https://html.duckduckgo.com/html/"
_RSS_FEEDS = [
    "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/",
    "https://habr.com/ru/rss/hubs/machine_learning/articles/",
    "https://habr.com/ru/rss/hubs/it/articles/",
    "https://vc.ru/rss/ai",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

_FALLBACK_TOPICS = [
    "Как ИИ меняет рынок труда в 2025 году",
    "Топ-5 нейросетей для автоматизации бизнеса",
    "ChatGPT vs Claude vs Gemini: полное сравнение",
    "Автоматизация маркетинга с помощью искусственного интеллекта",
    "Как внедрить AI в малый бизнес: пошаговое руководство",
    "Промпт-инжиниринг: советы для эффективной работы с LLM",
    "RAG vs Fine-tuning: что выбрать для корпоративного AI",
    "Тренды IT-автоматизации в 2025: что нужно знать",
    "No-code AI инструменты для предпринимателей",
    "Кейсы успешного внедрения AI в российском бизнесе",
]


async def fetch_topics_from_search(
    categories: list[str], count: int = 10,
) -> list[str]:
    """Search DuckDuckGo for trending topics in given categories."""
    topics: list[str] = []
    for category in categories[:3]:
        query = f"{category} новости тренды 2025"
        try:
            results = await _ddg_search(query, max_results=5)
            topics.extend(results)
        except Exception as exc:
            logger.warning("DDG search failed for category=%s: %s", category, exc)

    if len(topics) < count:
        try:
            rss_topics = await _fetch_rss_topics(count - len(topics))
            topics.extend(rss_topics)
        except Exception as exc:
            logger.warning("RSS fetch failed: %s", exc)

    topics = _deduplicate(topics)
    if not topics:
        logger.warning("All topic sources failed, using fallbacks")
        topics = random.sample(_FALLBACK_TOPICS, min(count, len(_FALLBACK_TOPICS)))

    return topics[:count]


async def _ddg_search(query: str, max_results: int = 5) -> list[str]:
    async with httpx.AsyncClient(
        headers=_HEADERS, follow_redirects=True, timeout=15.0
    ) as client:
        response = await client.post(
            _DDG_URL,
            data={"q": query, "b": "", "kl": "ru-ru"},
        )
        response.raise_for_status()
        html = response.text

    titles: list[str] = []
    matches = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
    for raw in matches[:max_results]:
        clean = re.sub(r"<[^>]+>", "", raw).strip()
        if clean and len(clean) > 15:
            titles.append(clean)
    return titles


async def _fetch_rss_topics(count: int) -> list[str]:
    topics: list[str] = []
    feed = random.choice(_RSS_FEEDS)
    async with httpx.AsyncClient(headers=_HEADERS, timeout=10.0) as client:
        response = await client.get(feed)
        response.raise_for_status()
        xml = response.text

    titles = re.findall(r"<title><!\[CDATA\[(.*?)]]></title>", xml)
    if not titles:
        titles = re.findall(r"<title>(.*?)</title>", xml)[1:]

    for t in titles[:count]:
        clean = re.sub(r"<[^>]+>", "", t).strip()
        if clean and len(clean) > 10:
            topics.append(clean)
    return topics


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result
