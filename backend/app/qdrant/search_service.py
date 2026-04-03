from typing import List, Dict, Any
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from config import settings

from openai import AsyncOpenAI

from .embeddings import embed_dense_for_query, run_in_cpu_pool



ai_client = AsyncOpenAI(
    api_key = settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

async def rewrite_query(original_query: str) -> str:
    """Оптимизация запроса пользователя для векторного поиска."""
    try:
        response = await ai_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Переформулируй запрос пользователя в поисковый запрос для базы знаний. Верни только текст запроса."},
                {"role": "user", "content": original_query}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception:
        return original_query # Если упало — ищем по оригиналу






# Инициализируем асинхронный клиент
q_client = AsyncQdrantClient(url=settings.QDRANT_URL)

async def search_knowledge_base(query: str, agent_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Поиск по базе знаний с использованием актуального API query_points."""
    try:
        # 1. Переписываем запрос (LLM)
        optimized_query = await rewrite_query(query)
        
        # 2. Генерируем эмбеддинг (вне event loop — не блокируем API)
        dense_vector = await run_in_cpu_pool(embed_dense_for_query, optimized_query)

        # 3. Фильтр по конкретному агенту
        search_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="agent_id", 
                    match=models.MatchValue(value=agent_id)
                )
            ]
        )

        # 4. ВАЖНО: Используем новый метод query_points вместо удаленного search
        response = await q_client.query_points(
            collection_name="agent_documents",
            query=dense_vector,
            query_filter=search_filter,
            limit=limit,
            with_payload=True
        )

        # 5. Сбор результатов (они теперь лежат внутри response.points)
        results = []
        for hit in response.points:
            results.append({
                "text": hit.payload.get("text", ""),
                "source": hit.payload.get("source", "Unknown"),
                "score": hit.score
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