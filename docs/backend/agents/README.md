# Backend — агенты

Ядро продукта: создание и настройка AI-агентов, шаблоны, runtime диалогов, каналы, аналитика, публичный API.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API aggregator | `backend/app/router_agents/router.py` (~24 строки, `include_router`) |
| Sub-routers | `core.py`, `crm.py`, `booking.py`, `integrations.py`, `internal.py`, `channels/` |
| Карта маршрутов | [ROUTERS.md](./ROUTERS.md) |
| Shared helpers | `backend/app/router_agents/shared.py` |
| Публичный API | `backend/app/router_agents/public_router.py` |
| DAO / схемы | `backend/app/router_agents/dao.py`, `schemas.py`, `public_schemas.py` |
| Telephony-канал (UI) | `backend/app/router_agents/telephony_channel.py` |
| Telephony-аналитика | `backend/app/router_agents/telephony_analytics.py` |
| Runtime диалогов | `backend/app/services/template_runtime.py` |
| Память агента | `backend/app/services/agent_memory.py` |
| Доступность | `backend/app/services/agent_availability.py` |
| AI authoring | `backend/app/services/ai_authoring.py` |
| Скрипты | `backend/app/services/script_service.py` |
| QA handoff | `backend/app/services/qa_handoff_service.py` |
| Tool confirmation | `backend/app/services/tool_confirmation.py` |
| Human delay | `backend/app/services/human_delay.py` |
| Обработка сообщений | `backend/app/channels/message_processor.py` |
| Промпты | `backend/app/prompts/` |
| Ценообразование шаблонов | `backend/app/agent_template_pricing.py` |
| Template config parser | `backend/app/utils/agent_template_config.py` |
| Userbot JWT | `backend/app/utils/scoped_auth_token.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/agents` | CRUD агентов, каналы, CRM, интеграции, аналитика, контент |
| `/api/v1/agents` | Публичные данные, booking, website leads |

## Связанные модули

- [channels](../channels/) — доставка сообщений
- [documents](../documents/) — база знаний
- [telephony](../../telephony/) — голосовой канал
- [admin-booking](../admin-booking/) — запись на приём
- [admin-applications](../admin-applications/) — заявки
- [crm](../crm/) — CRM tool calls
- [http-integrations](../http-integrations/) — кастомные HTTP tools

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Sub-routers `/api/agents` | `ROUTERS.md` | готово |
| Runtime и tool calls | `RUNTIME.md` | TODO |
| Модель каналов | `CHANNELS.md` | TODO |
| Аналитика | `ANALYTICS.md` | TODO |
| Публичный API | `PUBLIC_API.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
