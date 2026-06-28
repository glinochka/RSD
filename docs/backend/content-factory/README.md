# Backend — Content Factory

Генерация контента для агентов (jobs, worker, runtime).

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Worker | `backend/app/services/content_factory_worker.py` |
| Runtime | `backend/app/services/content_factory_runtime.py` |
| Jobs | `backend/app/services/content_job_service.py` |
| Kling (видео) | `backend/app/services/kling_client.py` |
| YouTube | `backend/app/services/youtube_client.py` |
| Модель jobs | `AgentContentJob` в `alembic/models.py` |

## Фоновый воркер

`CONTENT_FACTORY_ENABLED=true` → `get_content_factory_worker().run_forever()` в `server.py`.

## Связанные модули

- [agents](../agents/) — контент привязан к агенту

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Job lifecycle | `JOBS.md` | TODO |
| Внешние API (Kling, YouTube) | `EXTERNAL_APIS.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
