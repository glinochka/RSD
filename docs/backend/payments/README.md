# Backend — платежи и подписки

YooKassa, тарифы, подписки пользователей, биллинг агентов, автопродление, turnkey-заявки.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router | `backend/app/router_payments/` |
| Планы подписок | `backend/app/subscription_plans.py` |
| Биллинг агента | `backend/app/services/agent_billing.py` |
| Автоплатёж | `backend/app/services/agent_autopay.py` |
| Maintenance cron | `backend/app/services/subscription_maintenance.py`, `agent_billing_maintenance.py` |
| Способы оплаты | `backend/app/services/user_payment_methods.py` |
| Turnkey requests | DAO в `router_payments/dao.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/payments` | Планы, YooKassa, payment methods, turnkey |

Ключевые эндпоинты: `GET /plans`, `POST /yookassa/create`, `POST /yookassa/webhook`, `POST /yookassa/agent-billing/create`.

## Фоновые задачи

- `downgrade_expired_subscriptions_once()` — cron каждый час
- `process_agent_autopay_renewals_once()`
- `deactivate_expired_agent_maintenance_once()`

## Связанные модули

- [users](../users/) — владелец подписки
- [agents](../agents/) — биллинг и maintenance агента
- [admin](../admin/) — подарочные подписки, промокоды

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| YooKassa webhook | `YOOKASSA.md` | TODO |
| Тарифы и планы | `SUBSCRIPTION_PLANS.md` | TODO |
| Биллинг агента | `AGENT_BILLING.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
