import asyncio
import os
import re
import uuid
from html import unescape
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import pdfplumber
from docx import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from config import settings

from ..subscription_plans import get_subscription_plan, UNLIMITED_KNOWLEDGE_BASE_CHUNKS
from .embeddings import embed_dense_for_chunks, get_active_embedding_profile, run_in_cpu_pool


def get_chunk_limit_by_plan(plan_code: str) -> int:
    """
    Returns chunk limit for plan.
    Unlimited is implemented as a large number to keep comparisons simple.
    """
    plan = get_subscription_plan(plan_code) or get_subscription_plan("Free")
    limit = plan.get("knowledge_base_chunk_limit")
    if limit is UNLIMITED_KNOWLEDGE_BASE_CHUNKS:
        return 1_000_000_000
    return int(limit)

# Инициализация клиентов
qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

indexing_semaphore = asyncio.Semaphore(settings.EMBEDDING_MAX_CONCURRENT_DOCUMENTS)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.EMBEDDING_CHUNK_SIZE,
    chunk_overlap=settings.EMBEDDING_CHUNK_OVERLAP,
    separators=["\n\n", "\n", ".", " ", ""]
)

def extract_text_sync(file_path: str) -> str:
    """Синхронное извлечение текста (вызывать через run_in_cpu_pool / extract_text)."""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    if ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            text = "".join([page.extract_text() or "" for page in pdf.pages])
    elif ext == ".docx":
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    return text


async def extract_text(file_path: str) -> str:
    """Извлекает текст в зависимости от расширения файла."""
    return await run_in_cpu_pool(extract_text_sync, file_path)


def _extract_text_from_html(raw_html: str) -> str:
    html_without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    html_without_tags = re.sub(r"<[^>]+>", " ", html_without_scripts)
    normalized = re.sub(r"\s+", " ", unescape(html_without_tags))
    return normalized.strip()


def fetch_public_url_text_sync(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Поддерживаются только публичные http/https ссылки")

    request = Request(
        url,
        headers={
            "User-Agent": "RSDKnowledgeBot/1.0 (+https://rsd.ai)",
            "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=20) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        body = response.read()
        if not body:
            return ""
        encoding = response.headers.get_content_charset() or "utf-8"
        decoded = body.decode(encoding, errors="ignore")
        if "text/html" in content_type or "<html" in decoded.lower():
            return _extract_text_from_html(decoded)
        return re.sub(r"\s+", " ", decoded).strip()


async def fetch_public_url_text(url: str) -> str:
    return await run_in_cpu_pool(fetch_public_url_text_sync, url)

async def get_current_chunks_count(
    agent_id: int | None = None,
    project_id: int | None = None,
    embedding_profile_key: str | None = None,
) -> int:
    """Считает количество существующих чанков агента или проекта в Qdrant."""
    try:
        must_conditions = []
        if agent_id is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="agent_id",
                    match=models.MatchValue(value=agent_id)
                )
            )
        if project_id is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="project_id",
                    match=models.MatchValue(value=project_id)
                )
            )
        if not must_conditions:
            return 0
        if embedding_profile_key:
            must_conditions.append(
                models.FieldCondition(
                    key="embedding_profile_key",
                    match=models.MatchValue(value=embedding_profile_key),
                )
            )
        result = await qdrant_client.count(
            collection_name="agent_documents",
            count_filter=models.Filter(
                must=must_conditions
            )
        )
        return result.count
    except Exception as e:
        print(f"⚠️ Ошибка при подсчете чанков: {e}")
        return 0

from ..router_documents.dao import DocumentDAO
from ..dao.project_document_dao import ProjectDocumentDAO
from ..alembic.database import async_session_maker

async def _upsert_document_chunks(
    *,
    chunks: list[str],
    agent_id: int | None,
    document_id: int,
    content_hash: str | None,
    source: str,
    project_id: int | None = None,
):
    embedding_profile = get_active_embedding_profile()
    dense_vectors = await run_in_cpu_pool(
        embed_dense_for_chunks,
        chunks,
    )

    if len(dense_vectors) != len(chunks):
        raise RuntimeError("Ошибка генерации эмбеддингов: неверное количество векторов")

    # Генерация эмбеддингов и формирование точек для Qdrant
    points = []
    for i, chunk_text in enumerate(chunks):
        dense_vector = dense_vectors[i]
        # UUID на основе document_id и индекса чанка
        point_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{document_id}_{embedding_profile['profile_key']}_{embedding_profile['schema_version']}_{i}",
            )
        )

        payload = {
            "document_id": document_id,
            "content_hash": content_hash,
            "text": chunk_text,
            "source": source,
            "embedding_profile_key": embedding_profile["profile_key"],
            "embedding_schema_version": embedding_profile["schema_version"],
            "embedding_model_name": embedding_profile["model_name"],
        }
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if project_id is not None:
            payload["project_id"] = project_id

        points.append(
            models.PointStruct(
                id=point_id,
                vector=dense_vector.tolist(),
                payload=payload,
            )
        )

    # Загрузка в Qdrant батчами — один большой upsert сильнее бьёт по CPU Qdrant/хоста
    upsert_batch = 48
    for start in range(0, len(points), upsert_batch):
        batch = points[start : start + upsert_batch]
        await qdrant_client.upsert(
            collection_name="agent_documents",
            points=batch,
        )
        await asyncio.sleep(0)


async def process_document(
    file_path: str,
    agent_id: int,
    document_id: int,
    content_hash: str | None = None,
    source_name: str | None = None,
    project_id: int | None = None,
):
    """
    Фоновая задача для обработки документа с проверкой лимитов тарифа.
    """

    try:
        async with indexing_semaphore:
            # Извлечение текста и предварительный расчет чанков
            text = await extract_text(file_path)

            if not text:
                raise ValueError("Не удалось извлечь текст из файла")

            chunks = text_splitter.split_text(text)
            await _upsert_document_chunks(
                chunks=chunks,
                agent_id=agent_id if project_id is None else None,
                document_id=document_id,
                content_hash=content_hash,
                source=source_name or os.path.basename(file_path),
                project_id=project_id,
            )
        async with async_session_maker() as session:
            docDAO = DocumentDAO(session)
            async with session.begin():
                doc = await docDAO.find_one_by_filter(id = document_id)
                await docDAO.update(doc, {'status': 'ready'})



    except Exception as e:
        print(f"❌ Ошибка при индексации документа {e}")
        async with async_session_maker() as session:
            docDAO = DocumentDAO(session)
            async with session.begin():
                doc = await docDAO.find_one_by_filter(id = document_id)
                await docDAO.update(doc, {'status': 'error'})
    finally:
        # Удаляем временный файл после обработки
        if os.path.exists(file_path):
            os.remove(file_path)


async def process_text_source(
    *,
    text: str,
    source_name: str,
    agent_id: int,
    document_id: int,
    content_hash: str | None = None,
    project_id: int | None = None,
):
    try:
        async with indexing_semaphore:
            chunks = text_splitter.split_text(text)
            if not chunks:
                raise ValueError("Не удалось получить чанки из текста")
            await _upsert_document_chunks(
                chunks=chunks,
                agent_id=agent_id if project_id is None else None,
                document_id=document_id,
                content_hash=content_hash,
                source=source_name,
                project_id=project_id,
            )
        async with async_session_maker() as session:
            docDAO = DocumentDAO(session)
            async with session.begin():
                doc = await docDAO.find_one_by_filter(id=document_id)
                await docDAO.update(doc, {"status": "ready"})
    except Exception as e:
        print(f"❌ Ошибка при индексации текстового источника {e}")
        async with async_session_maker() as session:
            docDAO = DocumentDAO(session)
            async with session.begin():
                doc = await docDAO.find_one_by_filter(id=document_id)
                await docDAO.update(doc, {"status": "error"})


async def _collect_document_chunks_from_qdrant(
    *,
    agent_runtime_id: int,
    document_id: int,
    source_profile_key: str | None = None,
) -> tuple[list[str], str | None, str | None]:
    must_conditions = [
        models.FieldCondition(
            key="agent_id",
            match=models.MatchValue(value=agent_runtime_id),
        ),
        models.FieldCondition(
            key="document_id",
            match=models.MatchValue(value=document_id),
        ),
    ]
    if source_profile_key:
        must_conditions.append(
            models.FieldCondition(
                key="embedding_profile_key",
                match=models.MatchValue(value=source_profile_key),
            )
        )

    all_points = []
    next_offset = None
    while True:
        points, next_offset = await qdrant_client.scroll(
            collection_name="agent_documents",
            scroll_filter=models.Filter(must=must_conditions),
            with_payload=True,
            with_vectors=False,
            limit=256,
            offset=next_offset,
        )
        all_points.extend(points)
        if next_offset is None:
            break

    # Legacy fallback: allow reading old points that don't have embedding_profile_key payload.
    if not all_points and source_profile_key:
        points, _ = await qdrant_client.scroll(
            collection_name="agent_documents",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="agent_id",
                        match=models.MatchValue(value=agent_runtime_id),
                    ),
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    ),
                ]
            ),
            with_payload=True,
            with_vectors=False,
            limit=2048,
        )
        all_points.extend(points)

    chunks = []
    source_name: str | None = None
    content_hash: str | None = None
    for point in all_points:
        payload = point.payload or {}
        text = (payload.get("text") or "").strip()
        if not text:
            continue
        chunks.append(text)
        if source_name is None:
            source_name = payload.get("source")
        if content_hash is None:
            content_hash = payload.get("content_hash")
    return chunks, source_name, content_hash


async def process_project_document(
    file_path: str,
    project_id: int,
    document_id: int,
    content_hash: str | None = None,
    source_name: str | None = None,
):
    """Фоновая задача для обработки документа уровня проекта."""
    try:
        async with indexing_semaphore:
            text = await extract_text(file_path)
            if not text:
                raise ValueError("Не удалось извлечь текст из файла")
            chunks = text_splitter.split_text(text)
            await _upsert_document_chunks(
                chunks=chunks,
                agent_id=None,
                document_id=document_id,
                content_hash=content_hash,
                source=source_name or os.path.basename(file_path),
                project_id=project_id,
            )
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                doc = await doc_dao.find_one_by_filter(id=document_id)
                if doc:
                    await doc_dao.update(doc, {"status": "ready"})
    except Exception as e:
        print(f"❌ Ошибка при индексации проектного документа {e}")
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                doc = await doc_dao.find_one_by_filter(id=document_id)
                if doc:
                    await doc_dao.update(doc, {"status": "error"})
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


async def process_project_text_source(
    *,
    text: str,
    source_name: str,
    project_id: int,
    document_id: int,
    content_hash: str | None = None,
):
    """Фоновая задача для обработки текстового источника уровня проекта."""
    try:
        async with indexing_semaphore:
            chunks = text_splitter.split_text(text)
            if not chunks:
                raise ValueError("Не удалось получить чанки из текста")
            await _upsert_document_chunks(
                chunks=chunks,
                agent_id=None,
                document_id=document_id,
                content_hash=content_hash,
                source=source_name,
                project_id=project_id,
            )
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                doc = await doc_dao.find_one_by_filter(id=document_id)
                if doc:
                    await doc_dao.update(doc, {"status": "ready"})
    except Exception as e:
        print(f"❌ Ошибка при индексации проектного текстового источника {e}")
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                doc = await doc_dao.find_one_by_filter(id=document_id)
                if doc:
                    await doc_dao.update(doc, {"status": "error"})


async def _collect_project_document_chunks_from_qdrant(
    *,
    project_id: int,
    document_id: int,
    source_profile_key: str | None = None,
) -> tuple[list[str], str | None, str | None]:
    must_conditions = [
        models.FieldCondition(
            key="project_id",
            match=models.MatchValue(value=project_id),
        ),
        models.FieldCondition(
            key="document_id",
            match=models.MatchValue(value=document_id),
        ),
    ]
    if source_profile_key:
        must_conditions.append(
            models.FieldCondition(
                key="embedding_profile_key",
                match=models.MatchValue(value=source_profile_key),
            )
        )

    all_points = []
    next_offset = None
    while True:
        points, next_offset = await qdrant_client.scroll(
            collection_name="agent_documents",
            scroll_filter=models.Filter(must=must_conditions),
            with_payload=True,
            with_vectors=False,
            limit=256,
            offset=next_offset,
        )
        all_points.extend(points)
        if next_offset is None:
            break

    chunks = []
    source_name: str | None = None
    content_hash: str | None = None
    for point in all_points:
        payload = point.payload or {}
        text = (payload.get("text") or "").strip()
        if not text:
            continue
        chunks.append(text)
        if source_name is None:
            source_name = payload.get("source")
        if content_hash is None:
            content_hash = payload.get("content_hash")
    return chunks, source_name, content_hash


async def reindex_project_document_from_existing_chunks(
    *,
    project_id: int,
    document_id: int,
    source_profile_key: str | None = None,
) -> tuple[int, str | None, str | None]:
    chunks, source_name, content_hash = await _collect_project_document_chunks_from_qdrant(
        project_id=project_id,
        document_id=document_id,
        source_profile_key=source_profile_key,
    )
    if not chunks:
        raise ValueError("No existing chunks found in Qdrant for project document")

    await _upsert_document_chunks(
        chunks=chunks,
        agent_id=None,
        document_id=document_id,
        content_hash=content_hash,
        source=source_name or f"project-document:{document_id}",
        project_id=project_id,
    )
    return len(chunks), source_name, content_hash


async def reindex_document_from_existing_chunks(
    *,
    agent_runtime_id: int,
    document_id: int,
    source_profile_key: str | None = None,
) -> tuple[int, str | None, str | None]:
    chunks, source_name, content_hash = await _collect_document_chunks_from_qdrant(
        agent_runtime_id=agent_runtime_id,
        document_id=document_id,
        source_profile_key=source_profile_key,
    )
    if not chunks:
        raise ValueError("No existing chunks found in Qdrant for document")

    await _upsert_document_chunks(
        chunks=chunks,
        agent_id=agent_runtime_id,
        document_id=document_id,
        content_hash=content_hash,
        source=source_name or f"document:{document_id}",
    )
    return len(chunks), source_name, content_hash
