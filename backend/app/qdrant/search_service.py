import json
import re
from typing import List, Dict, Any
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from config import settings

from openai import AsyncOpenAI

from .embeddings import embed_dense_for_query, get_active_embedding_profile, run_in_cpu_pool



ai_client = AsyncOpenAI(
    api_key = settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

_SMALL_TALK_PATTERNS = (
    r"^\s*(привет|здравствуйте|добрый день|добрый вечер|hi|hello|hey)\s*[!.,?]*\s*$",
    r"^\s*(как дела|как ты|что нового)\s*[!.,?]*\s*$",
    r"^\s*(спасибо|благодарю|ок|хорошо|понял|понятно)\s*[!.,?]*\s*$",
)


def _looks_like_small_talk(query: str) -> bool:
    text = (query or "").strip().lower()
    if not text:
        return True
    if len(text) <= 2:
        return True
    return any(re.match(pattern, text) for pattern in _SMALL_TALK_PATTERNS)


async def plan_rag_queries(original_query: str, *, max_queries: int = 3) -> list[str]:
    """
    Планирует RAG-поиск через function calling.

    В smart-режиме LLM может решить, что RAG не нужен (например, small-talk),
    тогда возвращается пустой список и векторный поиск не выполняется.
    """
    safe_max_queries = max(1, min(max_queries, 3))
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты планируешь поиск по базе знаний (RAG). "
                        "Сначала определи, нужен ли вообще поиск по базе знаний для ответа. "
                        "Если запрос пользователя — small-talk/приветствие/вежливая реплика, "
                        "или ответ не требует фактов из базы знаний, верни should_search=false и пустой queries. "
                        "Если поиск нужен, верни should_search=true и 1-3 точных поисковых формулировки без воды."
                    ),
                },
                {"role": "user", "content": original_query}
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "extract_rag_plan",
                        "description": "Решает, нужен ли RAG и какие запросы использовать.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "should_search": {
                                    "type": "boolean",
                                    "description": "Нужен ли поиск по базе знаний для этого запроса.",
                                },
                                "queries": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 0,
                                    "maxItems": safe_max_queries,
                                }
                            },
                            "required": ["should_search", "queries"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            tool_choice={
                "type": "function",
                "function": {"name": "extract_rag_plan"},
            },
            temperature=0.1,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        if not tool_calls:
            raise ValueError("LLM не вернул function call для RAG-плана")

        args_raw = tool_calls[0].function.arguments or "{}"
        payload = json.loads(args_raw)
        should_search = bool(payload.get("should_search"))
        raw_queries = payload.get("queries")
        if not isinstance(raw_queries, list):
            raise ValueError("Некорректный формат queries")
        if not should_search:
            return []

        queries: list[str] = []
        for item in raw_queries:
            text = str(item or "").strip()
            if text and text not in queries:
                queries.append(text)
            if len(queries) >= safe_max_queries:
                break

        if not queries:
            fallback_query = (original_query or "").strip()
            return [fallback_query] if fallback_query else []
        return queries
    except Exception:
        fallback_query = (original_query or "").strip()
        if _looks_like_small_talk(fallback_query):
            return []
        return [fallback_query] if fallback_query else []






# Инициализируем асинхронный клиент
q_client = AsyncQdrantClient(url=settings.QDRANT_URL)

async def search_knowledge_base(
    query: str,
    agent_id: int,
    limit: int = 5,
    *,
    max_queries: int = 3,
    max_chunks_per_query: int = 2,
    use_smart_search: bool = True,
) -> List[Dict[str, Any]]:
    """Поиск по базе знаний с использованием актуального API query_points."""
    try:
        raw_query = (query or "").strip()
        if not raw_query:
            return []

        planned_queries = (
            await plan_rag_queries(raw_query, max_queries=max_queries)
            if use_smart_search
            else [raw_query]
        )
        if not planned_queries:
            return []

        embedding_profile = get_active_embedding_profile()
        if use_smart_search:
            effective_limit = max(1, min(max_chunks_per_query, 2, limit))
        else:
            effective_limit = max(1, min(limit, 6))

        results: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        max_planned_queries = 3 if use_smart_search else 1
        for planned_query in planned_queries[:max_planned_queries]:
            dense_vector = await run_in_cpu_pool(embed_dense_for_query, planned_query)

            search_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="agent_id",
                        match=models.MatchValue(value=agent_id)
                    ),
                    models.FieldCondition(
                        key="embedding_profile_key",
                        match=models.MatchValue(value=embedding_profile["profile_key"]),
                    )
                ]
            )

            response = await q_client.query_points(
                collection_name="agent_documents",
                query=dense_vector,
                query_filter=search_filter,
                limit=effective_limit,
                with_payload=True
            )

            if not response.points:
                legacy_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="agent_id",
                            match=models.MatchValue(value=agent_id)
                        )
                    ]
                )
                response = await q_client.query_points(
                    collection_name="agent_documents",
                    query=dense_vector,
                    query_filter=legacy_filter,
                    limit=effective_limit,
                    with_payload=True
                )

            for hit in response.points:
                text = hit.payload.get("text", "")
                source = hit.payload.get("source", "Unknown")
                dedupe_key = (str(source), str(text))
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                results.append({
                    "text": text,
                    "source": source,
                    "score": hit.score,
                    "rag_query": planned_query,
                })

        return results

    except Exception as e:
        print(f"❌ Критическая ошибка при поиске в Qdrant: {e}")
        import traceback
        traceback.print_exc()
        return []
# Добавьте в конец services/search_service.py

async def delete_agent_vectors(agent_id: int):
    """Удаляет все векторы, принадлежащие конкретному агенту."""
    try:
        await q_client.delete(
            collection_name="agent_documents",
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="agent_id",
                        match=models.MatchValue(value=agent_id),
                    )
                ]
            ),
        )
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении векторов из Qdrant: {e}")
        return False
    
async def delete_document_vectors(document_id: int):
    """Удаляет векторы конкретного документа из Qdrant."""
    try:
        await q_client.delete(
            collection_name="agent_documents",
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            ),
        )
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении векторов документа: {e}")
        return False