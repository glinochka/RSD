# Backend — AI MOP

Автоматизированная лидогенерация: импорт лидов, outreach (DM/email), follow-up, LLM pipeline.

## Код в репозитории

| Компонент | Путь |
|-----------|------|
| Worker | `backend/app/services/ai_mop/worker.py` |
| Service / runtime | `backend/app/services/ai_mop/service.py`, `runtime.py` |
| Outreach | `outreach.py`, `email_outreach.py`, `dm_hooks.py` |
| Lead pipeline | `lead_import.py`, `lead_lookup.py`, `lead_status.py`, `lead_recovery.py` |
| Follow-up | `followup_service.py` |
| LLM | `llm_helpers.py`, `llm_cost.py`, `tools.py` |
| Admin API | `backend/app/router_admin/ai_mop_admin.py` |

## Фоновый воркер

`get_ai_mop_worker()` — стартует в `server.py` при включённых настройках.

## Связанные модули

- [admin](../admin/) — `/api/admin/ai-mop`
- [channels](../channels/) — DM hooks
- [sales](../sales/) — пересечение по контактам

## Документация

| Артефакт | Файл | Статус |
|----------|------|--------|
| Обзор модуля | этот файл | готово |
| Pipeline состояний | `PIPELINE.md` | TODO |
| Outreach окна | `SEND_WINDOW.md` | TODO |
| LLM cost tracking | `LLM_COST.md` | TODO |
| Переменные окружения | `ENV_VARIABLES.md` | TODO |
