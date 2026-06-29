# `/api/agents` — структура sub-routers

После рефакторинга (фаза 4) `router_agents/router.py` — только aggregator. Все маршруты подключаются через `include_router`; префикс `/api/agents` общий, OpenAPI paths не менялись.

## Aggregator

| Файл | Роль |
|------|------|
| `router_agents/router.py` | Сборка всех sub-routers, re-export из `shared.py` для тестов и maintenance jobs |

Порядок подключения:

```
internal → crm → integrations → core → channels/telegram → channels/whatsapp → channels/max → booking
```

## Sub-routers

| Модуль | Файл | Содержимое |
|--------|------|------------|
| Internal | `internal.py` | `/internal/userbot_clients`, `/internal/whatsapp_userbot_clients`, `/internal/process_message` |
| CRM | `crm.py` | `/crm/connect`, `/crm/validate`, `/crm/health`, `/crm/rotate_secret` |
| HTTP integrations | `integrations.py` | `/http_integration/connect`, `/http_integration/deactivate` |
| Core | `core.py` | CRUD агента, каналы (общие), analytics, content jobs, AI authoring, external widget/chat |
| Telegram | `channels/telegram.py` | userbot auth/QR/session, bot token, YouTube OAuth, broadcast |
| WhatsApp | `channels/whatsapp.py` | WA userbot auth, Business API, broadcast |
| MAX | `channels/max.py` | MAX bot/userbot, telephony platform/routing, broadcast |
| Booking | `booking.py` | admin booking CRUD (`/admin_template/*`) |

## Общие зависимости

| Файл | Назначение |
|------|------------|
| `shared.py` | imports, helpers, JWT (`ScopedAuthToken`), DAO-вызовы — shared между sub-routers |
| `dao.py` | `AgentDAO`, `AgentChannelConnectionDAO.fetch_active_channel_configs`, CRM/HTTP DAO |
| `schemas.py`, `public_schemas.py` | Pydantic-модели запросов/ответов |

## Публичный API (отдельно)

| Файл | Префикс |
|------|---------|
| `public_router.py` | `/api/v1/agents` — public-data, booking slots/appointments, [website leads](../../website-builder/PUBLIC_FORMS.md) |

## Utils, вынесенные из router

| Утилита | Путь | Использование |
|---------|------|---------------|
| `ScopedAuthToken` | `utils/scoped_auth_token.py` | JWT для userbot auth (4 scope) |
| `parse_agent_template_config` | `utils/agent_template_config.py` | парсинг template_config агента |
| WhatsApp JID | `utils/whatsapp_jid.py` | нормализация external_id, bridge HTTP |

## Добавление нового домена

1. Создать `router_agents/<domain>.py` с `router = APIRouter()`.
2. Импортировать shared helpers из `shared.py` (не дублировать imports).
3. Подключить в `router.py` через `include_router`.
4. Обновить эту таблицу.
