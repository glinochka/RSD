# Backend — партнёрская программа

Промокоды партнёров, баланс, заявки на выплаты, дашборд.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router | `backend/app/router_referrals/` |
| Сервис | `backend/app/services/referral.py` |
| Выплаты | `backend/app/services/partner_payouts.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/referrals` | Partner dashboard, promo codes, payouts |

Ключевые эндпоинты: `GET /partner/dashboard`, `POST /partner/promo-codes`, `POST /partner/payouts`.

## Связанные модули

- [payments](../payments/) — применение промокодов при оплате
- [admin](../admin/) — модерация выплат (`AdminPartnerPayoutUpdateRequest`)

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Модель начислений | `PAYOUT_MODEL.md` | TODO |
| Статусы выплат | `PAYOUT_STATUSES.md` | TODO |
