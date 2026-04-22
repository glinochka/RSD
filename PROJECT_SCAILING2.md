# PROJECT_SCAILING2

## Контекст и цель

Цель: реализовать 3-й шаблон агента — `sales_manager` (название можно финализировать как `sales_agent`), который работает через `Telegram userbot`, сканирует доступные чаты, определяет целевые сообщения через LLM (DeepSeek), использует RAG для контекста продукта и отправляет персонализированные предложения в ЛС.

Ограничение текущего этапа: только `Telegram userbot` как канал подключения (с возможностью расширения на другие каналы в будущем).

---

## Проверка текущей архитектуры (сверка с кодом)

### Что подтверждено в текущем коде

- **Единый runtime обработки сообщений уже есть**
  - Основная бизнес-обработка: `backend/app/channels/message_processor.py`
  - Единая точка выполнения шаблонов: `backend/app/services/template_runtime.py`
- **Шаблоны уже централизованы**
  - Поддержка в runtime: `qa`, `crm_admin`, `lead_generation`, `content_factory`
  - Нормализация/валидация в API: `backend/app/router_agents/router.py` (`SUPPORTED_TEMPLATE_TYPES`, `_normalize_template_type`, `_normalize_template_config`)
- **DeepSeek и function calling уже интегрированы**
  - Клиент и генерация: `backend/app/services/ai_authoring.py`
  - Контур function calling: `backend/app/services/template_runtime.py`
  - Safety/validation/idempotency для tools: `backend/app/services/crm/tool_registry.py`
- **Telegram userbot уже работает в production-логике**
  - Менеджер клиентов Telethon: `backend/app/channels/userbot_manager.py`
  - Подключение userbot через request/verify flow: `backend/app/router_agents/router.py` (`/userbot/request_code`, `/userbot/verify_code`)
- **RAG уже встроен и используется в runtime**
  - Поиск по knowledge base: `backend/app/qdrant/search_service.py`
  - Вызов из шаблонного runtime: `template_runtime._execute_qa_like(...)`

### Что в `ARCHITECTURE_DIAGRAM.md` уже частично устарело

- Диаграмма указывает `bot/core/message_processor.py` как ядро; фактически ядро бизнес-обработки находится в `backend/app/channels/message_processor.py`.
- Диаграмма описывает checks через backend API-фасад, а текущая реализация проверок подписки/frozen и логирования выполняется напрямую через БД-модели SQLAlchemy внутри backend.
- В диаграмме userbot-менеджеры указаны в bot-сервисе, но фактически они запускаются backend-сервисом.
- Function calling для CRM уже production-уровня (tool registry + confirmation policy + idempotency), а в диаграмме это отражено не полностью.

Вывод: фундамент для нового шаблона уже есть, задача — добавить специализированный `sales`-runtime и отдельный pipeline проактивного аутрича.

---

## Предлагаемый шаблон: `sales_manager` (Telegram userbot)

## Базовый принцип работы

1. Userbot получает входящие события из чатов, где состоит аккаунт.
2. Кандидатные сообщения проходят фильтрацию (чтобы не слать в личку на любое сообщение).
3. LLM-классификатор определяет, является ли сообщение целевым для предложения услуги.
4. Для целевых сообщений извлекается релевантный контекст из RAG.
5. Генерируется персонализированное первое сообщение в ЛС.
6. Отправка в ЛС идет через policy-слой (лимиты, дедупликация, cool-down, комплаенс).
7. Все этапы логируются в analytics/audit.

---

## Дополнительные фичи для шаблона (целесообразные)

Ниже фичи, которые дадут практическую ценность и снизят риски блокировок/спама.

### 1) Двухэтапная LLM-валидация лида (must-have)

- Stage A: `intent classifier` (целевой / нецелевой / uncertain)
- Stage B: `contact policy checker` (можно ли писать сейчас с учетом правил)
- Это снижает ложные срабатывания и неэтичные outreach-сценарии.

### 2) Smart dedup + cooldown (must-have)

- Не писать одному и тому же пользователю повторно в заданное окно (например, 7-30 дней).
- Хранить `contacted_at`, `campaign_id`, `source_chat_id`, `reason`.
- Фильтр дублей до вызова LLM генерации (экономия токенов и меньше риска блокировок).

### 3) Rate limiting и распределенная очередь отправки (must-have)

- Лимиты на уровне агента и аккаунта userbot: в минуту/час/сутки.
- Плавная отправка (throttling/jitter), чтобы имитировать естественное поведение.
- Очередь задач (например, DB-backed queue на первом этапе; далее Redis/RQ/Celery).

### 4) Human-in-the-loop режимы (must-have)

- `auto`: отправлять автоматически
- `semi-auto`: отправка только после подтверждения владельцем
- `draft-only`: только черновики и reason-коды без отправки
- Это уменьшает риск ошибок на раннем запуске.

### 5) Function calling tools для sales-пайплайна (must-have)

- Рекомендуемые tools:
  - `schedule_dm` — поставить сообщение в очередь
  - `skip_lead` — зафиксировать, почему пропущено
  - `lookup_contact_history` — проверить историю контактов/исключений
  - `create_lead_in_crm` — создать лид при положительной реакции
  - `tag_lead` — назначить сегмент/тег
- Логика через tool-calling позволит прозрачно контролировать действия LLM и аудит.

### 6) Запретные сегменты и allow/deny правила (must-have)

- Ignore списки: чаты, слова-маркеры, пользователи.
- Blacklist/whitelist по chat_id/user_id/regex.
- Анти-таргетинг по ролям/фразам (например, “не предлагать конкурентам/вакансиям/службе поддержки”).

### 7) RAG-персонализация оффера (should-have)

- Релевантные карточки офферов по нишам и pain-points.
- Разные “тональности” сообщений по сегменту.
- A/B варианты первой фразы.

### 8) Quality feedback loop (should-have)

- Метки исхода: `sent`, `delivered`, `reply_positive`, `reply_negative`, `ignored`, `blocked`.
- Переобучение/перетюнинг prompt и правил по статистике.

### 9) FSM-клиент кампаний (should-have)

- FSM по жизненному циклу outreach:
  - `DISCOVERED` -> `QUALIFIED` -> `QUEUED` -> `SENT` -> `REPLIED` -> `HANDOFF/CRM`
- Позволяет предсказуемо управлять повторными касаниями и эскалацией.

### 10) Compliance & safety layer (must-have)

- Ограничения на агрессивность текста, частоту, запрещенные формулировки.
- Четкая пометка причины, почему именно этот лид выбран (explainability).
- Экспорт журналов для разбора спорных случаев.

---

## Архитектурный план реализации по этапам

Ниже roadmap с целями каждого этапа. Этапы построены так, чтобы быстро выйти в controlled-beta без поломки текущих шаблонов.

## Этап 0. Формализация требований и safety-политик
**Цель этапа:** зафиксировать бизнес-правила outreach до кодирования, чтобы не закладывать рискованные допущения.

- Определить критерии “целевого сообщения” (intent taxonomy).
- Согласовать лимиты и правила комплаенса (max DMs/day, cooldown, запреты).
- Зафиксировать режимы запуска: `draft-only`, `semi-auto`, `auto`.
- Принять решение по имени шаблона: `sales_manager` или `sales_agent` (везде единообразно).

**Результат:** технический RFC с policy-таблицей и SLA по безопасности.

## Этап 1. Контракты шаблона и модель конфигурации
**Цель этапа:** добавить шаблон в API и схемы без изменения поведения текущих агентов.

- Расширить `SUPPORTED_TEMPLATE_TYPES` в `backend/app/router_agents/router.py`.
- Добавить новый type в regex схем:
  - `backend/app/router_agents/schemas.py`
- Реализовать нормализацию `template_config` под sales (аналогично CRM-подходу).
- Рекомендуемая структура `template_config.sales_manager`:
  - `mode`: `draft_only | semi_auto | auto`
  - `qualification_model`: `deepseek-chat`
  - `generation_model`: `deepseek-chat`
  - `min_confidence`: float (например, 0.75)
  - `scan_scope`: include/exclude chat ids
  - `dm_limits`: per_minute/per_hour/per_day
  - `cooldown_days`
  - `dedup_window_days`
  - `allowed_languages`
  - `offer_profile_id` (ссылка на профиль оффера в базе знаний)

**Результат:** агент с новым шаблоном создается/валидируется через текущий API.

## Этап 2. Sales runtime в template engine
**Цель этапа:** внедрить отдельную бизнес-ветку выполнения шаблона внутри единого runtime.

- В `backend/app/services/template_runtime.py`:
  - Добавить ветку `if normalized == "sales_manager": ...`
  - Вынести в `TemplateRuntimeService._execute_sales_manager(...)`
- Разделить логику на sub-steps:
  - `qualify_message(...)`
  - `retrieve_offer_context(...)`
  - `compose_dm(...)`
  - `emit_action(...)` (draft/schedule/send)
- Для классификации и генерации использовать DeepSeek через текущий `ai_client`.

**Результат:** runtime умеет принимать входящее сообщение и выдавать управляемое действие по sales-policy.

## Этап 3. Function calling для действий sales-агента
**Цель этапа:** перевести “решение + действие” в управляемый tool-driven процесс, а не свободный текст.

- Создать `sales tool registry` по аналогии с CRM:
  - Вариант: `backend/app/services/sales/tool_registry.py`
- Минимальный набор tools:
  - `schedule_dm`
  - `skip_lead`
  - `record_lead_signal`
  - `create_crm_lead` (если CRM подключена)
  - `mark_contacted`
- Добавить ограничения:
  - лимиты payload
  - idempotency key
  - confirmation policy для рискованных действий
- Логировать tool events в `AgentAnalyticsMessage` (`role=operator`, `tool_status`, `latency_ms`).

**Результат:** контролируемый action-layer с аудитом и повторяемостью.

## Этап 4. FSM жизненного цикла контакта
**Цель этапа:** сделать поведение агента детерминированным по состояниям клиента.

- Ввести сущность состояния контакта (новая таблица, например `agent_sales_contacts`):
  - ключи: `agent_id`, `user_external_id`, `source_chat_id`
  - поля: `state`, `last_contacted_at`, `last_reason`, `cooldown_until`, `metadata`
- FSM переходы:
  - `DISCOVERED` -> `QUALIFIED`
  - `QUALIFIED` -> `QUEUED` / `SKIPPED`
  - `QUEUED` -> `SENT`
  - `SENT` -> `REPLIED_POSITIVE | REPLIED_NEGATIVE | NO_REPLY`
  - `REPLIED_POSITIVE` -> `HANDOFF_CRM`
- Добавить строгие guards переходов (чтобы исключить гонки/дубли).

**Результат:** предсказуемый pipeline outreach с прозрачной историей.

## Этап 5. Интеграция с Telegram userbot сканированием чатов
**Цель этапа:** реализовать ingestion не только из ЛС, а из доступных чатов userbot.

- Расширить `backend/app/channels/userbot_manager.py`:
  - обработка входящих из групп/чатов (не только `event.is_private`)
  - фильтры: system/service messages, сообщения от ботов, self-messages
- Добавить адаптер события в формат `SalesScanRequest`.
- Внедрить канал-безопасность:
  - respect allow/deny chat list
  - throttled scanning

**Результат:** агент обнаруживает релевантные лиды в чатах и не ломает текущий private-message flow.

## Этап 6. Очередь отправки ЛС и защитные лимиты
**Цель этапа:** безопасная и управляемая отправка сообщений в ЛС.

- Добавить очередь задач outbound (первый релиз: БД-таблица + воркер).
- Ввести лимиты:
  - per agent / per userbot account
  - burst control + random jitter
- Реализовать retry policy с backoff и причинами ошибок.
- Учитывать frozen/blacklist/cooldown перед фактической отправкой.

**Результат:** стабильная доставка без резких всплесков активности.

## Этап 7. UI/UX конфигурация шаблона
**Цель этапа:** дать владельцу агента полный контроль над поведением sales-агента.

- Обновить `frontend/src/pages/createAgent.jsx`:
  - новый option шаблона
  - блок настроек `sales_manager`
- Параметры UI:
  - режим работы (`draft_only/semi_auto/auto`)
  - лимиты и cooldown
  - сканируемые чаты (list)
  - текстовые рамки/offer profile
  - “не писать повторно N дней”
- Добавить подсказки и предупреждения о рисках.

**Результат:** шаблон настраивается без ручного редактирования JSON.

## Этап 8. Аналитика, мониторинг и контроль качества
**Цель этапа:** измеримость эффективности и быстрая диагностика.

- Новые метрики:
  - qualified rate
  - dm sent rate
  - positive reply rate
  - complaint/block indicators
  - tokens/cost per qualified lead
- Дашборды по каналу `telegram_userbot` и по кампаниям.
- Экспорт логов для аудита (кто, когда, почему получил outreach).

**Результат:** data-driven оптимизация и безопасный масштаб.

## Этап 9. Тестирование и выпуск
**Цель этапа:** выпуск без регрессий текущих шаблонов (`qa`, `crm_admin`).

- Unit:
  - нормализация `template_config`
  - FSM transitions
  - tool_registry validations
- Integration:
  - userbot event -> qualify -> queue -> send
  - idempotency/dedup
- Regression:
  - существующие шаблоны и каналы
- Rollout:
  - feature flag `sales_manager_enabled`
  - канареечный запуск на ограниченных аккаунтах

**Результат:** контролируемый production rollout.

---

## Предлагаемая последовательность внедрения (MVP -> Production)

### MVP (быстрый запуск, 1-2 итерации)

- Этап 1 + Этап 2 (базовая ветка runtime)
- Этап 5 (скан чат-сообщений в userbot)
- Этап 6 (минимальные лимиты и dedup)
- Режим только `draft_only` или `semi_auto`

### Beta

- Этап 3 (полноценный function calling для действий)
- Этап 4 (FSM контактов)
- Этап 8 (расширенная аналитика)

### Production

- Политики комплаенса и anti-abuse в полном объеме
- Автоматический режим `auto` только после прохождения KPI/guardrails
- Подготовка абстракции channel adapter для будущих каналов

---

## Ключевые риски и как их закрыть

- **Риск блокировок аккаунта userbot**  
  Закрытие: лимиты, jitter, cooldown, deny-правила, semi-auto режим по умолчанию.

- **Риск нецелевых/агрессивных сообщений**  
  Закрытие: двухэтапная квалификация + policy checker + human review.

- **Риск дублей и раздражения аудитории**  
  Закрытие: dedup storage, last_contacted, кампанийные ограничения.

- **Риск регрессий существующих шаблонов**  
  Закрытие: изоляция ветки `sales_manager`, feature flag, регрессионные тесты.

---

## Итог

Текущая архитектура проекта уже достаточно зрелая для добавления `sales_manager` шаблона без радикального рефакторинга: есть единый runtime, userbot-канал, RAG, DeepSeek и готовый паттерн function calling (на примере CRM). Оптимальный путь — внедрять поэтапно: сначала безопасный MVP с ограниченным outreach, затем tool-driven actions + FSM + продвинутая аналитика.
