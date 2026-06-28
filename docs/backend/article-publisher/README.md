# Backend — Article Publisher

Автоматическая генерация и публикация статей (топики, расписание, изображения).

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Worker | `backend/app/services/article_publisher/worker.py` |
| Admin endpoints | `backend/app/router_admin/router.py` (ArticlePublisher*) |
| Модели | `ArticlePublisherImage` и связанные в `alembic/models.py` |

## Фоновый воркер

`get_article_publisher_worker()` — стартует в `server.py`.

## Admin API

Настройки и ручной запуск через `/api/admin/...` (схемы `ArticlePublisher*` в `router_admin/schemas.py`).

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Расписание и топики | `SCHEDULING.md` | TODO |
| Генерация изображений | `IMAGES.md` | TODO |

## Связанные модули

- [admin](../admin/) — управление
- [content-factory](../content-factory/) — смежная генерация контента
