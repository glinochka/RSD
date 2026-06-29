# Website Builder — документация

Генерация лендингов для агентов: блоки, публикация, кастомные домены, SEO, безопасность.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router (кабинет) | `backend/app/router_websites/router.py` |
| Публичная отдача | `backend/app/router_websites/public_router.py` → `/public-website` |
| DAO / схемы | `backend/app/router_websites/dao.py`, `schemas.py` |
| Генерация | `backend/app/services/website_generation_service.py` |
| SEO | `backend/app/services/website_seo_service.py`, `website_seo_defaults.py` |
| Санитизация | `backend/app/services/website_sanitization_service.py` |
| HTML cleanup | `backend/app/services/website_html_cleanup.py` |
| CSS isolation | `backend/app/services/website_css_isolation.py` |
| Interactivity | `backend/app/services/website_interactivity.py` |
| Export | `backend/app/services/website_export_service.py` |
| Public forms | `backend/app/services/website_public_forms.py` |
| Form runtime (frontend) | `frontend/src/website-builder/utils/landingInteractivity.js` |
| Fullpage renderer | `frontend/src/website-builder/components/FullpageRenderer.jsx` |
| Static assets | mount `/assets/websites` в `server.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/v1/websites` | CRUD сайтов, блоки, домены, publish |
| `/public-website` | Публичная отдача опубликованных сайтов |
| `/api/v1/agents/{id}/website/leads` | Заявки с публичного лендинга → `admin_applications` |
| `/assets/websites` | Статика (изображения и т.д.) |

## Документация по этапам

| Этап | Файл | Статус |
|------|------|--------|
| Кастомные домены | [STAGE_7_CUSTOM_DOMAINS.md](./STAGE_7_CUSTOM_DOMAINS.md) | есть |
| SEO / meta | [STAGE_8_SEO_META.md](./STAGE_8_SEO_META.md) | есть |
| Безопасность | [STAGE_9_SECURITY.md](./STAGE_9_SECURITY.md) | есть |
| Генерация (LLM) | `STAGE_GENERATION.md` | TODO |
| Блоки и шаблоны | `BLOCKS.md` | TODO |
| Public forms | [PUBLIC_FORMS.md](./PUBLIC_FORMS.md) | есть |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |

## Связанные модули

- [agents](../backend/agents/) — привязка сайта к агенту
- [telephony](../telephony/) — не пересекается напрямую
