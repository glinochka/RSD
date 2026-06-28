# Оценка технологического стека RSD

Документ фиксирует: можно ли внедрить **LangChain/LangGraph** в модуль ИИ-агентов, **Kafka** как брокер по проекту, и какие популярные решения **не используются** — суть, области применения и реальные кейсы.

**Дата:** 2026-06-28  
**Связано:** [BACKEND_REFACTOR_PLAN.md](./BACKEND_REFACTOR_PLAN.md), [docs/backend/agents/README.md](../docs/backend/agents/README.md)

---

## 1. Текущий стек (baseline)

| Область | Сейчас в RSD |
|---------|--------------|
| LLM | Прямой `AsyncOpenAI` → DeepSeek (`services/ai_authoring.py`), ручные циклы tool calls |
| LangChain | Только `langchain-text-splitters` для чанкинга документов |
| Оркестрация агента | `TemplateRuntimeService` (~3100 строк): шаблоны, 5 tool registries, sales FSM |
| Очереди | PostgreSQL (`ReindexJob`), polling-воркеры (`asyncio` + `run_forever`) |
| Pub/sub | Redis — telephony, rate limit, leader lock |
| Векторы | Qdrant + sentence-transformers |
| Observability | Метрики telephony (Prometheus endpoint); без Sentry / OpenTelemetry |

**Поток сообщений:**

```
канал → MessageProcessor → TemplateRuntimeService → LLM + tools (CRM, booking, HTTP)
```

---

## 2. LangChain / LangGraph в модуле ИИ-агентов

### 2.1. Суть технологий

| | LangChain | LangGraph |
|---|-----------|-----------|
| **Что это** | Библиотека: chains, retrievers, tools, memory, callbacks | Stateful graphs поверх LC: узлы, рёбра, циклы, checkpointing |
| **Сильная сторона** | Быстрый RAG/prototype | Сложные агенты с ветвлениями и human-in-the-loop |
| **Слабая сторона** | Частые breaking changes, лишние слои | Кривая обучения, нужен checkpoint store |

### 2.2. Можно ли внедрить? — Да, точечно

Уже реализовано вручную то, что LangGraph даёт из коробки:

- guard (frozen, subscription)
- RAG planner → Qdrant
- цикл `for iteration in range(max_tool_iterations)` с tool calls
- confirmation для risky tools (CRM, booking, sales)

Код: `template_runtime.py`, `ai_mop/runtime.py`, `sales` tool loop.

### 2.3. Где LangGraph реально помог бы

| Сценарий | Почему |
|----------|--------|
| Sales FSM + tools + эскалация | Явный граф вместо логики в `template_runtime` + `sales/fsm.py` |
| Human-in-the-loop | `interrupt` + resume с checkpoint при подтверждении CRM/booking |
| Мульти-шаг (квалификация → CRM → DM → follow-up) | Условные переходы между узлами |
| Отладка | Визуализация графа, trace (LangSmith) |

### 2.4. Где НЕ стоит тащить LangChain целиком

| Причина | Деталь |
|---------|--------|
| Рабочий runtime | 5 tool registries с idempotency, domain safety |
| Latency telephony | Лишние абстракции на hot path звонка |
| API churn | LangChain меняется часто; у вас DeepSeek + Groq + OpenRouter |
| RAG | Свой planner + Qdrant — перенос в LC retriever мало даёт |

### 2.5. Рекомендуемая стратегия

```
Не:  заменить template_runtime на LangChain chains
Да:  LangGraph subgraph для нового/сложного template_type

template_runtime.py  ──►  фасад (без изменения API)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            _execute_qa (как есть)   LangGraphRunner
                                   (sales_manager v2, POC)
```

**POC:** один граф для `sales_manager` — узлы `qualify` → `tool_call` → `compose_dm` → `schedule_outreach`, checkpoint в Redis или PostgreSQL.

**Вердикт:** LangGraph — **да** для новых сложных сценариев; полная замена `template_runtime` — **нет**.

### 2.6. Реальные кейсы

- **Klarna** — support bot: ветки «KB» / «тикет» / «оператор»
- **Replit Agent** — multi-step coding с checkpointing
- **LinkedIn** — hiring assistant: resume → score → schedule

---

## 3. Kafka по проекту

### 3.1. Суть

Распределённый **log событий**: producers → topics → consumers с offset, replay, partitioning, долгое хранение.

### 3.2. Что у вас вместо Kafka

| Паттерн | Реализация |
|---------|------------|
| Фоновые задачи | `ContentFactoryWorker`, `AiMopWorker`, `DmOutreachWorker` — poll PG |
| Reindex | `reindex_jobs`, worker каждые 5 сек |
| Real-time telephony | Redis pub/sub (`telephony/redis_store.py`) |
| Сообщения каналов | In-process: userbot → `MessageProcessor` → ответ в том же event loop |

### 3.3. Где Kafka имел бы смысл

| Use case | Зачем |
|----------|-------|
| Analytics pipeline | Все сообщения/звонки/лиды → topic → ClickHouse |
| Decoupling каналов | `inbound.messages` → N независимых consumers |
| Telephony events | `call.started`, `turn.completed` — replay, несколько подписчиков |
| Outbox pattern | CRM/webhook side-effects с гарантией при рестарте |
| Масштаб | 10k+ msg/min, честное распределение по репликам |

### 3.4. Где Kafka — overkill

| Ситуация | Альтернатива |
|----------|--------------|
| 5–10 воркеров, poll 20–300 сек | PostgreSQL job queue (как сейчас) |
| Telephony low-latency | Redis Streams или текущий Redis pub/sub |
| Простые фоновые задачи | **ARQ** / Celery + Redis |
| Одна VPS, Docker Compose | Kafka = +3 контейнера, ops burden |

### 3.5. Лестница сложности

```
1. Сейчас     → PG jobs + asyncio workers
2. Рост       → Redis Streams / ARQ для retry + dead-letter
3. Analytics  → Kafka → ClickHouse
4. Enterprise → Kafka как backbone платформы
```

**Вердикт:** Kafka — при отдельном event/analytics pipeline; сейчас **Redis Streams или улучшение PG queue** дешевле.

### 3.6. Реальные кейсы

- **Uber** — trip events, pricing
- **Netflix** — telemetry, рекомендации
- **Spotify** — play events → ML
- **Банки** — fraud detection в реальном времени

---

## 4. Популярные решения, которых нет в проекте

### 4.1. Celery / ARQ / Dramatiq — task queue

| | |
|---|---|
| **Суть** | Отложенные задачи: retry, cron, приоритеты |
| **Где** | Email, reindex, генерация сайта, webhooks |
| **У вас** | Polling workers в `server.py` lifespan |
| **Кейс** | Shopify — миллионы background jobs |
| **Рекомендация** | **ARQ** (async) при росте воркеров |

### 4.2. Temporal / Inngest — durable workflows

| | |
|---|---|
| **Суть** | Workflow с retry, sleep на дни, saga |
| **Где** | Follow-up через 3/7 дней, onboarding |
| **У вас** | `sales_followup_service`, `ai_mop/followup_service` |
| **Кейс** | Stripe — payment sagas |
| **Рекомендация** | При цепочках на **недели** — сильнее LangGraph |

### 4.3. LiteLLM / Portkey — LLM gateway

| | |
|---|---|
| **Суть** | Единый proxy, fallback, rate limit, cost tracking |
| **Где** | Мульти-модель, A/B, бюджет per-agent |
| **У вас** | Прямые ключи; `ai_mop/llm_cost.py` вручную |
| **Кейс** | Jasper — роутинг при outage провайдера |
| **Рекомендация** | При 3+ провайдерах и billing per agent |

### 4.4. LlamaIndex

| | |
|---|---|
| **Суть** | RAG-фреймворк: индексы, query engines |
| **Где** | Hybrid search, rerank, multi-doc |
| **У вас** | Qdrant + свой planner |
| **Кейс** | Notion AI |
| **Рекомендация** | Если RAG усложнится; сейчас свой код OK |

### 4.5. OpenTelemetry + Sentry

| | |
|---|---|
| **Суть** | Tracing, error tracking, dashboards |
| **Где** | Production SaaS с SLA |
| **У вас** | Логи + telephony Prometheus |
| **Кейс** | Datadog у Airbnb |
| **Рекомендация** | **Sentry** — быстрый win; **OTel** — trace backend → bridge → gateway |

### 4.6. S3 / MinIO — object storage

| | |
|---|---|
| **Суть** | Файлы вне диска контейнера |
| **У вас** | `WEBSITE_ASSETS_PATH`, local mount |
| **Кейс** | Любой SaaS с upload |
| **Рекомендация** | При multi-replica backend или CDN для сайтов |

### 4.7. ClickHouse / TimescaleDB

| | |
|---|---|
| **Суть** | Аналитика по миллионам событий |
| **У вас** | `AgentAnalyticsMessage` в PostgreSQL |
| **Кейс** | Amplitude, PostHog |
| **Рекомендация** | Когда дашборды тормозят PG |

### 4.8. Pinecone / Weaviate (managed vector)

| | |
|---|---|
| **Суть** | Vector DB как сервис |
| **У вас** | Self-hosted Qdrant |
| **Кейс** | Стартапы без DevOps |
| **Рекомендация** | Менять нет смысла, если Qdrant стабилен |

### 4.9. Guardrails AI / NeMo Guardrails

| | |
|---|---|
| **Суть** | Валидация output LLM (PII, jailbreak) |
| **У вас** | `redact_pii_text`, CRM denylist, sanitization |
| **Кейс** | Банки — блокировка утечки данных |
| **Рекомендация** | Regulated industries |

### 4.10. Kubernetes

| | |
|---|---|
| **Суть** | Оркестрация, autoscaling |
| **У вас** | Docker Compose на VPS |
| **Кейс** | 50+ микросервисов |
| **Рекомендация** | При 3+ нодах и telephony replicas |

### 4.11. Feature flags (Unleash / LaunchDarkly)

| | |
|---|---|
| **Суть** | Включение фич без деплоя |
| **У вас** | `TELEPHONY_ENABLED` через env |
| **Кейс** | Netflix — rollout на 5% |
| **Рекомендация** | A/B шаблонов агентов |

### 4.12. Webhook delivery (Svix / Hookdeck)

| | |
|---|---|
| **Суть** | Надёжная доставка webhooks клиентам |
| **У вас** | Входящие (Voximplant, YooKassa) |
| **Кейс** | Stripe Connect |
| **Рекомендация** | При исходящих webhooks для клиентов |

---

## 5. Матрица приоритетов

| Решение | Срочность | Условие внедрения |
|---------|-----------|-------------------|
| **Sentry + OTel** | Высокая | Продакшен SLA, отладка telephony |
| **parse_agent_template_config** (см. refactor plan) | Высокая | Техдолг, 1 час |
| **LangGraph** | Средняя | Новый сложный agent flow / sales v2 |
| **LiteLLM** | Средняя | Унификация LLM + cost per agent |
| **Redis Streams / ARQ** | Средняя | Retry/dead-letter для воркеров |
| **MinIO/S3** | Средняя | Multi-replica, CDN |
| **Kafka** | Низкая | Analytics pipeline, 5+ consumers |
| **Temporal** | Низкая–средняя | Follow-up на недели |
| **ClickHouse** | Низкая | PG analytics тормозит |
| **Celery** | Низкая | ARQ предпочтительнее (async) |

---

## 6. Рекомендуемый roadmap

| Этап | Действия |
|------|----------|
| **Сейчас** | Sentry; утилиты из [BACKEND_REFACTOR_PLAN.md](./BACKEND_REFACTOR_PLAN.md) фаза 1 |
| **Квартал** | LangGraph POC на `sales_manager`; Redis Streams для DM queue |
| **Рост** | MinIO; OTel trace backend → telephony stack |
| **Масштаб** | Kafka + ClickHouse; Temporal для nurture-цепочек |

---

*Обновлять при принятии архитектурных решений или появлении новых интеграций.*
