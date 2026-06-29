# Публичные формы заявок на лендинге

**Статус:** рабочий (e2e, 2026-06-29). Заявки с опубликованного сайта попадают в дашборд CRM-агента (`admin_applications`, канал `website`).

См. также: [GENERATION.md](./GENERATION.md) — требования к разметке формы в AI HTML (`data-rsd-form="lead"`).

## Поток данных

```
Посетитель заполняет форму на /w/{slug}
        │
        ├─ fullpage (AI HTML) ──► LANDING_FORM_RUNTIME в iframe (FullpageRenderer)
        │                         window.__RSD_LANDING__ = { agentId, apiBase }
        │
        └─ legacy blocks ───────► ContactsBlock (React) + submitWebsiteLead()
        │
        ▼
POST /api/v1/agents/{agent_id}/website/leads
        │
        ▼
website_public_forms.submit_website_lead()
        │
        ▼
admin_applications (status=new, source_channel=website)
```

## Каноническая схема полей

Все публичные формы (AI HTML и блок «Контакты») приводятся к единой схеме:

| key | label | type | required |
|-----|-------|------|----------|
| `fio` | ФИО | text | да |
| `phone` | Телефон | phone | да |
| `message` | Комментарий | textarea | нет |

Алиасы входящих полей (`name`, `tel`, `comment`, …) маппятся в `website_public_forms.map_website_form_payload()`.

## Fullpage (AI HTML)

При открытии `/w/{slug}` фронтенд:

1. Загружает schema: `GET /api/v1/websites/by-slug/{slug}/schema`
2. Рендерит HTML в iframe (`FullpageRenderer`)
3. Инжектит в документ iframe:
   - `window.__RSD_LANDING__` — `agentId` и `apiBase`
   - скрипт `LANDING_FORM_RUNTIME` из `frontend/src/website-builder/utils/landingInteractivity.js`

Скрипт находит `<form>` (кроме `data-rsd-form="search"`), вешает `submit` handler:

- `preventDefault()` — без перезагрузки страницы
- `method="post"`, снимает `action`
- `POST` JSON: `{ fields, client_name }`

AI при генерации должен добавлять `data-rsd-form="lead"`, `name="fio"`, `name="phone"` (см. `WEBSITE_CODER_SYSTEM_PROMPT`).

## Legacy blocks

`ContactsBlock` отправляет через `leadApi.submitWebsiteLead()` при `hasApplications === true`.

`hasApplications` берётся из `agent.has_applications` в schema (или fallback `is_admin_template`).

## API

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/v1/agents/{id}/website/leads` | Создать заявку с лендинга |

Тело запроса (`PublicWebsiteLeadRequest`):

```json
{
  "client_name": "Иван Иванов",
  "fields": { "fio": "Иван Иванов", "phone": "+79991234567", "message": "..." },
  "notes": null
}
```

Условия:

- у агента есть **опубликованный** сайт (`agent_has_published_website`);
- агент активен;
- заполнены обязательные поля ФИО и телефон.

Ответ `200`: `{ "id", "status", "message" }`.

## Schema API и флаг `has_applications`

`GET .../schema` возвращает вложенный объект `agent`. Поле `has_applications` **обязательно** в `WebsiteSchemaAgentEmbed` — без него фронтенд считал `hasApplications = false` и не подключал runtime форм (форма уходила обычным GET с query-параметрами).

Также в embed: `workflow_mode`, `has_booking`, `is_admin_template`.

## Бэкенд: сохранение заявки

`submit_website_lead()`:

1. Валидирует поля по `WEBSITE_UNIFIED_LEAD_FIELDS`
2. Открывает транзакцию: `async with session.begin()` **до** любых запросов к БД
3. Загружает агента, вызывает `AdminApplicationService.create_application()`

Важно: нельзя вызывать `session.get()` до `session.begin()` — иначе SQLAlchemy уже открыл транзакцию и повторный `begin()` падает с `InvalidRequestError` (симптом: `400` и текст «Не удалось отправить заявку»).

## Диагностика

| Симптом | Вероятная причина |
|---------|-------------------|
| Перезагрузка URL с `?fio=...&phone=...` | JS runtime не подключён (`has_applications` не в schema, нет `agent_id`, старый фронт) |
| `POST` → `400` «Не удалось отправить…» | Ошибка БД/сессии на бэкенде (см. traceback `website lead submission failed`) |
| `POST` → `400` с текстом про поля | Пустые ФИО/телефон или невалидные данные |
| `POST` → `404` | Нет опубликованного сайта у агента |
| Заявка не в дашборде при `200` | Смотреть фильтр по каналу/статусу в UI агента |

Пересборка HTML лендинга **не нужна** для исправления отправки — runtime подключается при каждом открытии страницы. Нужен деплой **frontend** (runtime) и **backend** (API + schema).

## Код

| Компонент | Путь |
|-----------|------|
| Сервис заявок | `backend/app/services/website_public_forms.py` |
| Public API | `backend/app/router_agents/public_router.py` |
| Schema embed | `backend/app/router_websites/schemas.py` → `WebsiteSchemaAgentEmbed` |
| Form runtime | `frontend/src/website-builder/utils/landingInteractivity.js` |
| Iframe + config | `frontend/src/website-builder/components/FullpageRenderer.jsx` |
| React форма | `frontend/src/website-builder/components/blocks/ContactsBlock.jsx` |
| Тесты | `backend/app/tests/test_website_public_forms.py` |
