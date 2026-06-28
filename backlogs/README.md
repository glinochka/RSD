# Backlogs — планы и оценки

Черновики, roadmap'ы и технические оценки. **Не** операционная документация — для неё см. [docs/README.md](../docs/README.md).

| Документ | Содержание | Статус |
|----------|------------|--------|
| [TECH_STACK_EVALUATION.md](./TECH_STACK_EVALUATION.md) | LangChain/LangGraph, Kafka, альтернативный стек | оценка |
| [PROJECT_PORTAL_PLAN.md](./PROJECT_PORTAL_PLAN.md) | Эволюция в портал «Проект» | план |
| [BACKEND_REFACTOR_PLAN.md](./BACKEND_REFACTOR_PLAN.md) | Дедупликация и ООП в backend | фазы 1–4 ✅, фаза 5 — backlog |
| [TELEPHONY_ARCHITECTURE.md](./TELEPHONY_ARCHITECTURE.md) | Архитектура телефонии | референс |
| [TELEPHONY_LATENCY_OPTIMIZATION_PLAN.md](./TELEPHONY_LATENCY_OPTIMIZATION_PLAN.md) | Оптимизация задержек звонков | план |
| [SECURITY_STAGE1_RECON_PENTEST.md](./SECURITY_STAGE1_RECON_PENTEST.md) | Security recon, pentest чеклист | аудит |

## Как добавлять

1. Новый план — файл `*_PLAN.md` или `*_EVALUATION.md` в эту папку.
2. Строка в таблице выше.
3. При необходимости — ссылка из [README.md](../README.md) (раздел «Backlogs»).

Операционные runbook'и и RFC остаются в `docs/` (например `docs/telephony/RUNBOOK.md`).
