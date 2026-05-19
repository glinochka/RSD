# Телефония RSD — документация этапа 0

Этап 0 («Подготовка и проектирование») зафиксирован в репозитории до начала разработки `telephony_bridge` и API канала.

## Результаты этапа 0

| Артефакт | Файл |
|----------|------|
| Выбор CPaaS (Voximplant) + чеклист тестового аккаунта | [CPaaS_DECISION.md](./CPaaS_DECISION.md) |
| RFC webhook (события, идентификаторы, HMAC) | [RFC-001-webhook-contract.md](./RFC-001-webhook-contract.md) |
| KPI задержки (MVP vs production) | [KPI_LATENCY.md](./KPI_LATENCY.md) |
| Юридический чеклист (черновик) | [COMPLIANCE_CHECKLIST.md](./COMPLIANCE_CHECKLIST.md) |
| Переменные окружения | [ENV_VARIABLES.md](./ENV_VARIABLES.md) |
| JSON Schema credentials v1 | [../../schemas/telephony/credentials.v1.schema.json](../../schemas/telephony/credentials.v1.schema.json) |
| Pydantic-модель (валидация в backend) | `backend/app/telephony/credentials.py` |
| Шаблон `.env` | [../../.env.telephony.example](../../.env.telephony.example) |

## Утверждённые решения

- **CPaaS:** Voximplant (первая интеграция).
- **`AgentChannelConnection.provider`:** `telephony_voximplant`.
- **Поле `provider` внутри JSON credentials:** `voximplant`.
- **Webhook (публичный):** `POST {TELEPHONY_WEBHOOK_BASE_URL}/webhook/voximplant/{connection_id}`.
- **Внутренний контракт событий:** RSD Telephony Webhook v1 ([RFC-001](./RFC-001-webhook-contract.md)); bridge нормализует нативные callback Voximplant в этот формат.

## Этап 1 (реализован)

| Компонент | Путь |
|-----------|------|
| Миграция | `backend/app/alembic/migration/versions/e2f3a4b5c6d7_add_telephony_tables.py` |
| Internal API | `backend/app/router_telephony/` → `/api/internal/telephony/*` |
| Канал (UI API) | `POST /api/agents/channels/add-telephony`, `POST .../telephony/validate` |
| Bridge | `telephony_bridge/` → `:8100`, webhook `/webhook/voximplant/:connection_id` |
| Compose | сервис `telephony_bridge` в `docker-compose.yml` |

Включение: `TELEPHONY_ENABLED=true`, `TELEPHONY_WEBHOOK_BASE_URL`, ключи из `.env.telephony.example`.

## Этап 3 (UI)

- Создание агента и модалка каналов: подключение Voximplant, валидация, webhook URL.
- Аналитика: вкладка «Звонки», `GET /api/agents/analytics/telephony/calls`.
- Чаты: фильтр канала `phone`.

## Следующий шаг

Этап 2: MVP диалог STT → LLM → TTS — см. [TELEPHONY_AI_OPERATOR_PLAN.md](../../TELEPHONY_AI_OPERATOR_PLAN.md).
