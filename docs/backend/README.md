# Backend — карта модулей

Все домены backend сгруппированы по папкам `docs/backend/<module>/`. Каждая папка содержит `README.md` с путями к коду и чеклистом документации.

## Слои архитектуры

```
server.py
├── middleware (infrastructure)
├── router_*          → HTTP API по доменам
├── services/         → бизнес-логика, воркеры
├── channels/         → долгоживущие коннекторы мессенджеров
├── telephony/        → голос (отдельный пакет, docs в docs/telephony/)
├── qdrant/           → векторный поиск (см. documents)
└── alembic/          → ORM, миграции (см. infrastructure)
```

## Модули по API surface

| Router | Префикс | Документация |
|--------|---------|--------------|
| `router_users` | `/api/users` | [users](./users/) |
| `router_agents` | `/api/agents` | [agents](./agents/) |
| `router_agents/public` | `/api/v1/agents` | [agents](./agents/) |
| `router_documents` | `/api/documents` | [documents](./documents/) |
| `router_payments` | `/api/payments` | [payments](./payments/) |
| `router_referrals` | `/api/referrals` | [referrals](./referrals/) |
| `router_admin` | `/api/admin` | [admin](./admin/) |
| `router_sales` | `/api/sales`, `/api/sales/management` | [sales](./sales/) |
| `router_telephony` | `/api/internal/telephony` | [../telephony/](../telephony/) |
| `router_websites` | `/api/v1/websites` | [../website-builder/](../website-builder/) |

## Сервисные модули (без отдельного router)

| Домен | Документация |
|-------|--------------|
| Каналы мессенджеров | [channels](./channels/) |
| CRM | [crm](./crm/) |
| Booking | [admin-booking](./admin-booking/) |
| Applications | [admin-applications](./admin-applications/) |
| HTTP integrations | [http-integrations](./http-integrations/) |
| AI MOP | [ai-mop](./ai-mop/) |
| Content Factory | [content-factory](./content-factory/) |
| Article Publisher | [article-publisher](./article-publisher/) |

## Общий индекс

[../README.md](../README.md)
