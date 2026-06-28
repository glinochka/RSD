# Backend — админ-панель

Внутренний API для операторов: пользователи, агенты, рассылки, промокоды, ошибки, article publisher, AI MOP.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Основной router | `backend/app/router_admin/router.py` |
| Sales admin | `backend/app/router_admin/sales_admin.py` → `/api/admin/sales` |
| AI MOP admin | `backend/app/router_admin/ai_mop_admin.py` → `/api/admin/ai-mop` |
| DAO / схемы | `backend/app/router_admin/dao.py`, `schemas.py` |
| Error logs | `backend/app/services/error_log_service.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/admin` | Login, users, agents, broadcasts, promo codes, payouts |
| `/api/admin/sales` | Управление sales-командой |
| `/api/admin/ai-mop` | Настройки AI MOP |

Аутентификация: отдельный admin JWT (`HTTPBearer`).

## Связанные модули

- [users](../users/), [agents](../agents/), [payments](../payments/), [referrals](../referrals/)
- [sales](../sales/) — admin sales endpoints
- [ai-mop](../ai-mop/) — admin AI MOP endpoints
- [article-publisher](../article-publisher/) — настройки публикации

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Роли и доступ | `ACCESS.md` | TODO |
| Массовые рассылки | `BROADCASTS.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
