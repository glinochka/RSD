# Документация RSD

Карта модулей проекта. Каждая папка — отдельный домен с собственным `README.md` и детальными артефактами по мере наполнения.

**Планы и roadmap** (не операционная документация) — в [backlogs/](../backlogs/README.md).

## Backend (`backend/`)

| Модуль | Папка | Кратко |
|--------|-------|--------|
| Инфраструктура | [backend/infrastructure](./backend/infrastructure/) | `server.py`, middleware, config, БД, фоновые воркеры |
| Пользователи | [backend/users](./backend/users/) | Регистрация, JWT, профиль, Telegram-link |
| Агенты | [backend/agents](./backend/agents/) | CRUD агентов, шаблоны, runtime, аналитика |
| Каналы сообщений | [backend/channels](./backend/channels/) | Telegram / MAX / WhatsApp userbot-менеджеры |
| Документы (RAG) | [backend/documents](./backend/documents/) | Загрузка, индексация, Qdrant, reindex jobs |
| Платежи | [backend/payments](./backend/payments/) | YooKassa, подписки, биллинг агентов |
| Партнёры | [backend/referrals](./backend/referrals/) | Промокоды, выплаты, дашборд партнёра |
| Админ-панель | [backend/admin](./backend/admin/) | `/api/admin/*`, рассылки, модерация |
| Sales CRM | [backend/sales](./backend/sales/) | Портал продаж, воронка, контакты |
| Телефония | [telephony](./telephony/) | Voximplant, streaming, internal API |
| Website Builder | [website-builder](./website-builder/) | AI-лендинги, конструктор, заявки, SEO — **production-ready** |
| CRM-интеграции | [backend/crm](./backend/crm/) | AmoCRM и провайдеры |
| Запись (booking) | [backend/admin-booking](./backend/admin-booking/) | Слоты, услуги, напоминания |
| Заявки (applications) | [backend/admin-applications](./backend/admin-applications/) | Формы заявок агента |
| HTTP-интеграции | [backend/http-integrations](./backend/http-integrations/) | Кастомные tool-вызовы агента |
| AI MOP | [backend/ai-mop](./backend/ai-mop/) | Лидогенерация, outreach, follow-up |
| Content Factory | [backend/content-factory](./backend/content-factory/) | Генерация контента для агентов |
| Article Publisher | [backend/article-publisher](./backend/article-publisher/) | Автопубликация статей |

## Смежные сервисы (вне `backend/app`)

| Сервис | Путь | Документация |
|--------|------|--------------|
| Telephony Bridge | `telephony_bridge/` | [telephony_bridge/README.md](../telephony_bridge/README.md) |
| Media Gateway | `telephony_media_gateway/` | [telephony/STREAMING_ARCHITECTURE.md](./telephony/STREAMING_ARCHITECTURE.md) |
| VoxEngine | `voxengine/` | [voxengine/README.md](../voxengine/README.md) |
| WA Bridge | `wa_bridge/` | [wa_bridge/README.md](../wa_bridge/README.md) |

## Как добавлять документацию

1. Откройте `README.md` нужного модуля.
2. Заполните раздел «Документация» — добавьте файл(ы) в ту же папку.
3. Обновите таблицу артефактов в `README.md` модуля (как в [telephony](./telephony/README.md)).
4. При необходимости добавьте ссылку в этот индекс.

Шаблон именования детальных документов: `ENV_VARIABLES.md`, `RUNBOOK.md`, `RFC-*.md`, `STAGE_*.md`.
