# Backend — CRM-интеграции

Подключение внешних CRM к агенту (AmoCRM и др.), tool registry для LLM.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Factory | `backend/app/services/crm/factory.py` |
| Tool registry | `backend/app/services/crm/tool_registry.py` |
| AmoCRM provider | `backend/app/services/crm/providers/amocrm.py` |
| DAO агента | `backend/app/router_agents/dao.py` (`AgentCrmConnectionDAO`) |

## Точки входа

- Настройка CRM в кабинете агента (`/api/agents/...`)
- Tool calls в `template_runtime` через `build_provider()`

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| AmoCRM | `AMOCRM.md` | TODO |
| Tool registry | `TOOL_REGISTRY.md` | TODO |
| Добавление провайдера | `NEW_PROVIDER.md` | TODO |

## Связанные модули

- [agents](../agents/) — runtime tool calls
- [http-integrations](../http-integrations/) — альтернатива для кастомных API
