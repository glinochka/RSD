# Backend — Sales CRM

Внутренний портал продаж: контакты, воронка, счета, управление командой, DM outreach.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| API router | `backend/app/router_sales/` |
| Sales FSM / логика | `backend/app/services/sales/` |
| Internal sales | `backend/app/services/internal_sales.py` |
| Excel import | `backend/app/services/sales_excel_import.py` |
| Мой налог (счета) | `backend/app/services/sales_moy_nalog_invoice.py` |
| DM outreach worker | `backend/app/services/sales/dm_outreach_worker.py` |
| Contact resolver | `backend/app/services/sales/contact_target_resolver.py` |
| Admin sales API | `backend/app/router_admin/sales_admin.py` |

## API

| Префикс | Описание |
|---------|----------|
| `/api/sales` | Login, contacts, invoices (портал менеджера) |
| `/api/sales/management` | Команда, воронка, импорт (руководитель) |

## Связанные модули

- [agents](../agents/) — `AgentSalesContact`, импортированные контакты
- [channels](../channels/) — DM outreach через userbot
- [admin](../admin/) — admin sales endpoints

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| FSM контакта | `CONTACT_FSM.md` | TODO |
| DM outreach | `DM_OUTREACH.md` | TODO |
| Импорт Excel | `EXCEL_IMPORT.md` | TODO |
