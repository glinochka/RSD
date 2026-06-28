# Backend — заявки (Admin Applications)

Формы заявок и обработка входящих applications для агентов.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Сервис | `backend/app/services/admin_applications/` |
| Tool registry | `backend/app/services/admin_applications/tool_registry.py` |
| Модели | `backend/app/alembic/models.py` (`AdminApplication`, ...) |

## Точки входа

- Настройка в кабинете агента (`/api/agents/...`)
- Tool calls в runtime через `get_admin_application_service()`

## Связанные модули

- [agents](../agents/) — runtime, UI настроек
- [admin-booking](../admin-booking/) — соседний домен admin_* сервисов

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Жизненный цикл заявки | `APPLICATION_LIFECYCLE.md` | TODO |
| Tool registry | `TOOL_REGISTRY.md` | TODO |
