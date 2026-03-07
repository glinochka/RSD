import os
import uuid
import pdfplumber
from docx import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from fastembed import TextEmbedding, SparseTextEmbedding

from config import settings


# Константы лимитов согласно ТЗ
CHUNK_LIMITS = {
    "Free": 100,
    "Advanced": 500,
    "Pro": 1000000  # Условно безлимит
}

# Инициализация клиентов
qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.DEEPSEEK_API_KEY)

dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5") 
sparse_model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    separators=["\n\n", "\n", ".", " ", ""]
)

async def extract_text(file_path: str) -> str:
    """Извлекает текст в зависимости от расширения файла."""
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

async def get_current_chunks_count(agent_id: int) -> int:
    """Считает количество существующих чанков агента в Qdrant."""
    try:
        result = qdrant_client.count(
            collection_name="agent_documents",
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="agent_id", 
                        match=models.MatchValue(value=agent_id)
                    )
                ]
            )
        )
        return result.count
    except Exception as e:
        print(f"⚠️ Ошибка при подсчете чанков: {e}")
        return 0

from ..router_documents.dao import DocumentDAO
from ..alembic.database import async_session_maker

async def process_document(file_path: str, agent_id: int, document_id: int):
    """
    Фоновая задача для обработки документа с проверкой лимитов тарифа.
    """
        
    try:
        # Извлечение текста и предварительный расчет чанков
        text = await extract_text(file_path)
    
        if not text:
            raise ValueError("Не удалось извлечь текст из файла")

        chunks = text_splitter.split_text(text)

        # Генерация эмбеддингов и формирование точек для Qdrant
        points = []
        for i, chunk_text in enumerate(chunks):
            dense_vector = list(dense_model.embed([chunk_text]))[0]
            sparse_vector = list(sparse_model.embed([chunk_text]))[0]

            # UUID на основе document_id и индекса чанка
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}_{i}"))

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        "": dense_vector.tolist(),
                        "sparse-text": models.SparseVector(
                            indices=sparse_vector.indices.tolist(),
                            values=sparse_vector.values.tolist()
                        )
                    },
                    payload={
                        "agent_id": agent_id,
                        "text": chunk_text,
                        "source": os.path.basename(file_path)
                    }
                )
            )

        # Загрузка в Qdrant
        qdrant_client.upsert(
            collection_name="agent_documents",
            points=points
        )
        async with async_session_maker() as session:
            docDAO = DocumentDAO(session)
            async with session.begin():
                doc = await docDAO.find_one_by_filter(id = document_id)
                await docDAO.update(doc,{'status': 'ready'})



    except Exception as e:
        print(f"❌ Ошибка при индексации документа {e}")
        async with async_session_maker() as session:
            docDAO = DocumentDAO(session)
            async with session.begin():
                doc = await docDAO.find_one_by_filter(id = document_id)
                await docDAO.update(doc,{'status': 'error'})
    finally:
        # Удаляем временный файл после обработки
        if os.path.exists(file_path):
            os.remove(file_path)