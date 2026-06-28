# Backend — пользователи и аутентификация

Регистрация, вход, JWT, сброс пароля, привязка Telegram, профиль пользователя.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router | `backend/app/router_users/` |
| DAO | `backend/app/router_users/dao.py` |
| Схемы | `backend/app/router_users/schemas.py` |
| JWT | `backend/app/utils/JWT.py` |
| Security helpers | `backend/app/utils/security.py`, `internal_auth.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/users` | Публичный API пользователей |

Ключевые эндпоинты: `POST /registration`, `POST /login`, `POST /refresh`, `GET /me`, `POST /telegram-link/*`, password reset.

## Зависимости

- PostgreSQL (`alembic/models.py` — таблица `users`)
- Email-отправка (верификация, сброс пароля)
- Rate limiting на login/registration

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Потоки auth (JWT, refresh) | `AUTH_FLOWS.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
| Модель данных | `DATA_MODEL.md` | TODO |
