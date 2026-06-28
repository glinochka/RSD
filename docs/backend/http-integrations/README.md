# Backend — HTTP-интеграции агентов

Кастомные HTTP tool-вызовы: конфигурация, валидация, executor для LLM runtime.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Executor | `backend/app/services/http_integration/executor.py` |
| Tool registry | `backend/app/services/http_integration/tool_registry.py` |
| **Shared registry core** | `backend/app/services/tool_registry_core.py` |
| Errors | `backend/app/services/http_integration/errors.py` |
| DAO | `backend/app/router_agents/dao.py` (`AgentHttpIntegrationDAO`) |

## Точки входа

- CRUD интеграций в `/api/agents/http_integration/*` (sub-router `integrations.py`)
- Валидация конфига при сохранении (`validate_integration_config_dict`)
- Вызов из `template_runtime`

Plumbing tool registry — в `tool_registry_core.py`; domain registry хранит HTTP-specific limits и execute.

## Связанные модули

- [agents](../agents/) — runtime
- [crm](../crm/) — типовые CRM вместо кастомного HTTP

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Формат конфигурации | `CONFIG_SCHEMA.md` | TODO |
| Executor и безопасность | `SECURITY.md` | TODO |
