# Backend — документы и RAG

Загрузка документов агента, чанкинг, эмбеддинги, поиск в Qdrant, фоновая переиндексация.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router | `backend/app/router_documents/` |
| Qdrant search | `backend/app/qdrant/search_service.py` |
| Embeddings | `backend/app/qdrant/embeddings.py` |
| Reindex jobs | `backend/app/services/reindex_jobs.py` |
| Инициализация Qdrant | `backend/server.py` (коллекция `agent_documents`) |

## API

| Префикс | Описание |
|---------|----------|
| `/api/documents` | CRUD документов, контекст для агента, reindex jobs |

Ключевые эндпоинты: `POST /`, `GET /getContextBy_agentID`, `POST /reindex-jobs`, `POST /link`.

## Внешние зависимости

- **Qdrant** — векторное хранилище (`QDRANT_URL`, `QDRANT_API_KEY`)
- Dense embeddings — модель задаётся в `qdrant/embeddings.py`

## Связанные модули

- [agents](../agents/) — привязка документов к агенту
- [infrastructure](../infrastructure/) — reindex worker

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Схема индексации | `INDEXING.md` | TODO |
| Reindex jobs | `REINDEX_JOBS.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
