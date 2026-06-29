# Website Builder — документация

AI-конструктор одностраничных лендингов для агентов: первичная генерация HTML, редактор, публикация, заявки с форм, SEO, кастомные домены.

## Статус модуля

| Область | Статус | Примечание |
|---------|--------|------------|
| Первичная AI-генерация (fullpage) | **Рабочий** | 4 LLM-прохода, `data-*` интерактивность, санитизация + runtime |
| Превью / конструктор (iframe) | **Рабочий** | `FullpageRenderer`, меню / карусель / FAQ / формы |
| Публичная отдача `/w/{slug}` | **Рабочий** | Опубликованные сайты, виджет агента |
| Заявки с лендинга → дашборд агента | **Рабочий** | e2e: `POST /website/leads` → `admin_applications` |
| AI-редактирование по промпту | **Рабочий** | Smart merge + полная перегенерация секций |
| SEO / favicon / OG | **Рабочий** | Панель SEO в конструкторе |
| Экспорт ZIP | **Рабочий** | Статический архив |
| Кастомные домены | **Рабочий** | DNS TXT-верификация |

**Вердикт (2026-06-29):** модуль конструктора сайтов считается **полностью рабочим** для production-сценария «создать лендинг → опубликовать → собрать заявки в CRM агента».

Регрессии по интерактивности (бургер, FAQ, отзывы) устранены усилением промптов генерации и платформенного JS-runtime; см. [GENERATION.md](./GENERATION.md).

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router (кабинет) | `backend/app/router_websites/router.py` |
| Публичная отдача | `backend/app/router_websites/public_router.py` → `/public-website` |
| Public agent API (заявки) | `backend/app/router_agents/public_router.py` |
| DAO / схемы | `backend/app/router_websites/dao.py`, `schemas.py` |
| Генерация | `backend/app/services/website_generation_service.py` |
| Интерактивность (бэкенд) | `backend/app/services/website_interactivity.py` |
| Санитизация | `backend/app/services/website_sanitization_service.py` |
| HTML cleanup | `backend/app/services/website_html_cleanup.py` |
| Public forms | `backend/app/services/website_public_forms.py` |
| SEO | `backend/app/services/website_seo_service.py`, `website_seo_defaults.py` |
| Export | `backend/app/services/website_export_service.py` |
| Frontend конструктор | `frontend/src/website-builder/` |
| Form + UI runtime | `frontend/src/website-builder/utils/landingInteractivity.js` |
| Fullpage renderer | `frontend/src/website-builder/components/FullpageRenderer.jsx` |
| Static assets | mount `/assets/websites` в `server.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/v1/websites` | CRUD сайтов, блоки, домены, publish, AI generate/edit |
| `/public-website` | Публичная отдача опубликованных сайтов |
| `/api/v1/agents/{id}/website/leads` | Заявки с публичного лендинга → `admin_applications` |
| `/api/v1/agents/{id}/public-data` | Публичные данные агента для виджета и форм |
| `/assets/websites` | Статика (favicon, OG, загрузки) |

## Документация по подсистемам

| Тема | Файл |
|------|------|
| AI-генерация и интерактивность | [GENERATION.md](./GENERATION.md) |
| Публичные формы и заявки | [PUBLIC_FORMS.md](./PUBLIC_FORMS.md) |

## Тесты

```bash
python -m pytest backend/app/tests/test_website_public_forms.py -q
python -m pytest backend/app/tests/test_website_interactivity.py -q
python -m pytest backend/app/tests/test_website_generation_save.py -q
```

## Типовой сценарий

1. Пользователь создаёт сайт: `POST /api/v1/websites/generate/create-and-generate` (или generate для существующего).
2. Фоновая задача: 4 LLM-прохода → `apply_generated_html` (sanitize → cleanup chat widgets → inject runtime).
3. В конструкторе: превью в iframe, AI-правки через `edit-prompt`.
4. Публикация: `POST /api/v1/websites/{id}/publish`.
5. Посетитель на `/w/{slug}`: интерактивные элементы + форма → заявка в дашборде агента.

## Связанные модули

- [agents](../backend/agents/) — привязка сайта к агенту, public-data, leads API
- [admin-applications](../backend/admin-applications/) — хранение заявок с лендинга (`source_channel=website`)
