# Backend — инфраструктура

Общие компоненты FastAPI-приложения: точка входа, middleware, конфигурация, БД, фоновые задачи.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Точка входа | `backend/server.py` |
| Конфигурация | `backend/app/config.py`, `backend/app/origins.py` |
| Middleware | `backend/app/middleware/` |
| Логирование | `backend/app/logger_config.py` |
| Модели / миграции | `backend/app/alembic/` |
| Утилиты | `backend/app/utils/` |
| Зависимости | `backend/requirements-*.txt` |

## Фоновые воркеры (lifespan в `server.py`)

| Воркер | Путь | Флаг / условие |
|--------|------|----------------|
| Subscription cron | `services/subscription_maintenance.py`, `agent_autopay.py`, `agent_billing_maintenance.py`, `onboarding_email_maintenance.py` | всегда |
| Reindex worker | `services/reindex_jobs.py` | всегда |
| Telegram userbot | `channels/userbot_manager.py` | всегда |
| MAX bot / userbot | `channels/max_bot_manager.py`, `max_userbot_manager.py` | всегда |
| WhatsApp userbot | `channels/whatsapp_userbot_manager.py` | всегда |
| Content Factory | `services/content_factory_worker.py` | `CONTENT_FACTORY_ENABLED` |
| DM Outreach (sales) | `services/sales/dm_outreach_worker.py` | по настройкам sales |
| Article Publisher | `services/article_publisher/worker.py` | по настройкам |
| AI MOP | `services/ai_mop/worker.py` | по настройкам |

## Middleware (порядок — от внешнего к внутреннему)

- `SecurityAuditMiddleware`
- `RateLimitMiddleware`
- `CSPMiddleware`
- `SelectiveCORSMiddleware`
- HTTPS enforcement для credentialed-запросов (`server.py`)

## Зависимости от других модулей

Все API-роутеры подключаются в `server.py`. Qdrant инициализируется при старте (коллекция `agent_documents`).

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модулей | [../../README.md](../../README.md) | готово |
| Переменные окружения (глобальные) | `ENV_VARIABLES.md` | TODO |
| Runbook деплоя | [../../../deployment/VPS_STAGE2_DEPLOY.md](../../../deployment/VPS_STAGE2_DEPLOY.md) | частично |
| Схема миграций | `MIGRATIONS.md` | TODO |
