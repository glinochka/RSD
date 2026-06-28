# Backend — запись и расписание (Admin Booking)

Слоты, услуги, сотрудники, напоминания, оплата записи — для агентов с доменом booking.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Сервис | `backend/app/services/admin_booking/` |
| Catalog prompt | `backend/app/services/admin_booking/catalog_prompt.py` |
| Payment service | `backend/app/services/admin_booking/payment_service.py` |
| Domains registry | `backend/app/services/admin_booking/domains.py` |
| Tool registry | `backend/app/services/admin_booking/tool_registry.py` |
| **Shared registry core** | `backend/app/services/tool_registry_core.py` |
| Публичный API | `backend/app/router_agents/public_router.py` (`/booking/*`) |
| Кабинет booking routes | `backend/app/router_agents/booking.py` |

## API (публичный)

| Эндпоинт | Описание |
|----------|----------|
| `GET /api/v1/agents/{id}/booking/slots` | Свободные слоты |
| `POST /api/v1/agents/{id}/booking/appointments` | Создание записи |

Управление — через `/api/agents/admin_template/*` (кабинет, sub-router `booking.py`).

## Tool registry

`admin_booking/tool_registry.py` — самый тяжёлый доменный registry; plumbing (idempotency, parsing, schemas) вынесен в `tool_registry_core.py`, бизнес-ветки execute не менялись.

## Связанные модули

- [agents](../agents/) — настройки агента, runtime tools
- [payments](../payments/) — оплата записи

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Домены (booking, ...) | `DOMAINS.md` | TODO |
| Напоминания | `REMINDERS.md` | TODO |
| Tool registry booking | `TOOL_REGISTRY.md` | TODO |
