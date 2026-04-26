# PROJECT SCALING: Шаблон "ИИ контент-завод" (Kling AI -> YouTube Shorts)

## Контекст задачи

Цель: реализовать **4-й шаблон агента** — **"ИИ контент-завод"**, который:

- получает от пользователя базовый бриф компании (название + деятельность),
- по расписанию генерирует сценарий через LLM,
- отправляет сценарий в Kling AI для генерации видео,
- публикует готовый ролик в подключенный канал.

Для текущего MVP:

- канал публикации: только **YouTube**,
- формат: короткие видео **без склеек**,
- частотность: **ежедневно** (фиксированная, без гибких правил),
- без ручного/авто-одобрения.

---

## Что сейчас реально есть в проекте (проверено по коду)

### 1) Архитектура уже поддерживает шаблонную модель и фоновые процессы

Фактически в проекте есть:

- `backend` (FastAPI + Postgres + Qdrant),
- `frontend` (React/Vite),
- канал-менеджеры (`telegram_userbot`, `whatsapp_userbot`),
- фоновый worker-подход (например, reindex worker),
- отдельные сервисы и runtime-оркестрация шаблонов.

Ключевые точки:

- `backend/server.py` — запуск фоновых задач.
- `backend/app/services/template_runtime.py` — единая точка исполнения шаблонов.

### 2) `content_factory` уже присутствует в доменной модели, но без продуктовой реализации

В схеме и API уже поддержаны:

- `template_type` с `content_factory`,
- `template_config` в `Agent`,
- создание/обновление агента через существующие endpoints.

Но фактически:

- в runtime `content_factory` сейчас обрабатывается как QA-like сценарий (через RAG/text answer),
- отдельного видео-пайплайна (script -> Kling -> publish) пока нет.

### 3) Есть готовый паттерн "очередь + воркер + статусная модель"

На `sales_manager` уже реализован производственный шаблон:

- queue table,
- queue service,
- background worker,
- статусы, ретраи, аналитика.

Это критично: `content_factory` можно строить по уже проверенному шаблону внедрения.

### 4) Каналы подключений уже унифицированы

В `AgentChannelConnection` есть универсальная модель подключений:

- `provider`,
- `connection_type`,
- `external_id`,
- `encrypted_credentials`,
- `is_primary/is_active`.

Это позволяет добавить YouTube как еще один provider без отдельной системы хранения интеграций.

### 5) Безопасное хранение секретов уже есть

В проекте используется шифрование credential bundle:

- `encrypt_token/decrypt_token` и смежные механизмы.

Значит OAuth tokens YouTube можно хранить в уже принятом security-подходе.

### 6) YouTube и Kling интеграций пока нет

По коду отсутствуют:

- клиенты YouTube upload API,
- клиент Kling API,
- таблицы/воркеры для контент-job pipeline.

---

## Что важно зафиксировать до реализации

1. `content_factory` должен быть не "чатовым" шаблоном, а **pipeline-шаблоном** (job-driven).
2. Источник правды по прогрессу — отдельная job-таблица, а не только текстовые логи.
3. Архитектуру сразу делать с адаптером publisher-каналов:
   - MVP: `youtube`,
   - потом: `tiktok`, `pinterest`.
4. Склейка сегментов не входит в MVP, но модель данных должна позволять добавить ее без миграции ядра.

---

## Дополнительные фичи для "ИИ контент-завода" (после MVP, но учесть в дизайне)

Ниже фичи, которые целесообразно заложить архитектурно:

1. **Approval workflow**
   - Режимы: auto-approve / manual review.
   - Статусы: `awaiting_approval`, `approved`, `rejected`.

2. **Segmented rendering + stitching**
   - Генерация 7-8 кусков по 8 секунд.
   - Склейка в итоговый ролик отдельным сервисом.

3. **Frequency engine**
   - Не только daily, но и custom cron/rules.
   - Настройки quiet-hours и timezone-aware scheduling.

4. **Multi-channel publishing adapters**
   - YouTube/TikTok/Pinterest через единый publisher interface.

5. **Контент-политики и guardrails**
   - Бренд-тон, запрещенные темы, compliance-правила.

6. **A/B контент-варианты**
   - Несколько сценариев/хедлайнов на один день.

7. **Операционный аудит**
   - Полный event trail: от генерации сценария до публикации.

---

## Поэтапный план реализации

Ниже план разбит на этапы и рассчитан на внедрение без ломки текущих потоков.

### Этап 0. Архитектурная фиксация `content_factory` как pipeline-шаблона

**Цель этапа:** отделить текстовый runtime от workflow генерации контента.

Что сделать:

- Зафиксировать продуктовую семантику:
  - `content_factory` не отвечает на входящие сообщения как основной режим работы;
  - работает через планировщик и job-воркер.
- Ввести/описать service boundary:
  - `ContentFactoryOrchestrator`,
  - `ScriptService`,
  - `KlingClient`,
  - `PublisherRouter`.
- Сохранить совместимость с текущим `template_runtime` для fallback/технических запросов.

Результат:

- четкая архитектурная модель без дублирования бизнес-логики.

---

### Этап 1. Продуктовая модель `template_config` для `content_factory`

**Цель этапа:** формально описать минимально достаточную конфигурацию шаблона.

Что сделать:

- В `_normalize_template_config` добавить отдельную ветку `content_factory`.
- Ввести и валидировать поля:
  - `company_name` (required),
  - `company_activity` (required),
  - `brand_tone` (optional),
  - `content_language` (default `ru`),
  - `daily_posting_enabled` (default `true`),
  - `daily_post_time` (default `10:00`),
  - `timezone` (default `UTC`),
  - `video_duration_seconds` (MVP max = 8),
  - `kling_model` (default/configurable).
- Обновить схемы API для create/update agent.

Результат:

- `content_factory` становится управляемым продуктовым шаблоном, а не просто строковым `template_type`.

---

### Этап 2. UI/UX онбординг шаблона "Контент-завод"

**Цель этапа:** сделать шаблон доступным пользователю через текущий UI.

Что сделать:

- В `createAgent` разблокировать выбор `content_factory` (снять `disabled`).
- Добавить форму конфигурации:
  - название компании,
  - деятельность,
  - тон коммуникации,
  - язык.
- Добавить UX-подсказку:
  - MVP публикует короткие видео в YouTube,
  - без склеек, 1 публикация в день.
- Передавать поля в `template_config` через существующий flow создания агента.

Результат:

- пользователь может создать и сохранить контент-агента без ручного JSON.

---

### Этап 3. Таблица контент-задач и статусная модель

**Цель этапа:** получить прозрачный и устойчивый pipeline-level source of truth.

Что сделать:

- Добавить новую миграцию и ORM модель `agent_content_jobs`.
- Поля MVP:
  - `agent_id`,
  - `status` (`planned`, `script_ready`, `rendering`, `rendered`, `publishing`, `published`, `failed`),
  - `scheduled_for`, `started_at`, `finished_at`,
  - `script_text`, `script_model`,
  - `kling_task_id`, `video_url`,
  - `youtube_video_id`, `youtube_video_url`,
  - `retry_count`, `max_retries`, `last_error`,
  - `metadata`.
- Индексы:
  - `(status, scheduled_for)`,
  - `agent_id`,
  - `kling_task_id`,
  - `youtube_video_id`.

Результат:

- формализованный жизненный цикл каждой публикации.

---

### Этап 4. Content Job Service (очередь и оркестрация)

**Цель этапа:** реализовать надежный job lifecycle manager.

Что сделать:

- Реализовать `content_job_service.py`:
  - `enqueue_daily_jobs(now)`,
  - `claim_next_job()`,
  - `mark_status()`,
  - `mark_failed()` с retry policy.
- Дедуп daily-jobs:
  - уникальная логика "1 job per agent per content date per provider=youtube".
- Retry policy:
  - сетевые/временные ошибки -> retry,
  - конфиг/авторизация -> fail-fast.

Результат:

- управляемый pipeline, устойчивый к временным сбоям.

---

### Этап 5. Script Generation Service (LLM)

**Цель этапа:** генерировать короткий production-ready сценарий под Kling ограничения.

Что сделать:

- Реализовать `script_service.py`:
  - построение промпта из `template_config`,
  - генерация текста сценария,
  - post-processing/sanitization.
- Для MVP enforce:
  - один клип,
  - длительность под лимит (<= 8 секунд),
  - без многочастных сценариев.
- Сохранять сценарий и метаданные в job.

Результат:

- повторяемая и контролируемая генерация контент-скрипта.

---

### Этап 6. Kling Adapter Layer

**Цель этапа:** интегрировать генерацию видео как отдельный технологический адаптер.

Что сделать:

- Реализовать `kling_client.py`:
  - `submit_render(...) -> kling_task_id`,
  - `poll_render(...) -> status/video_url/error`.
- Добавить:
  - таймауты,
  - backoff,
  - idempotency для submit.
- Безопасное логирование (без утечки секретов).

Результат:

- стабильный внешний rendering adapter для pipeline.

---

### Этап 7. YouTube подключение и публикация

**Цель этапа:** завершить полный E2E цикл публикации.

Что сделать:

- Добавить YouTube provider в `AgentChannelConnection`:
  - `provider="youtube"`,
  - `connection_type="oauth"`.
- Реализовать endpoints:
  - `by_youtube_oauth_start`,
  - `by_youtube_oauth_callback`,
  - `youtube/health`.
- Реализовать `youtube_client.py`:
  - refresh token flow,
  - upload short,
  - возврат `video_id/url`.
- Встроить публикацию в worker после `rendered`.

Результат:

- ежедневный job доходит до реальной публикации в YouTube.

---

### Этап 8. Фоновый worker и запуск в runtime

**Цель этапа:** поставить pipeline на автономный цикл выполнения.

Что сделать:

- Реализовать `content_factory_worker.py`:
  1) claim job,
  2) generate script,
  3) Kling submit/poll,
  4) publish YouTube,
  5) finalize status.
- Подключить worker в `backend/server.py` в lifecycle (как уже сделано для других фоновых задач).
- Добавить feature flag:
  - `CONTENT_FACTORY_ENABLED`.

Результат:

- автономная ежедневная обработка без ручного запуска.

---

### Этап 9. Аналитика, аудит, наблюдаемость

**Цель этапа:** обеспечить эксплуатационную прозрачность и поддержку.

Что сделать:

- Логировать ключевые pipeline-события в `AgentAnalyticsMessage` (`role=operator`):
  - script_generated,
  - kling_submitted,
  - kling_rendered,
  - youtube_published,
  - publish_failed.
- Добавить базовые метрики:
  - jobs total/published/failed,
  - avg render latency,
  - retry rate.
- Добавить API чтения jobs:
  - список,
  - фильтрация по статусу,
  - детализация по job.

Результат:

- управляемая эксплуатация и быстрая диагностика инцидентов.

---

## MVP-срез (что запускать первым)

Чтобы быстро получить ценность и минимальный риск, запускать в таком объеме:

1. `content_factory` template config + UI-онбординг.
2. `agent_content_jobs` + daily enqueue.
3. LLM script generation под 8-секундный формат.
4. Kling submit/poll.
5. YouTube OAuth + upload.
6. Базовые статусы/ретраи/логи.

Это даст рабочий "ИИ контент-завод" с ежедневной публикацией коротких видео.

---

## Риски и как их снять заранее

1. **Лимиты Kling по длительности**
   - В MVP жестко ограничить сценарий одним коротким клипом.
   - Архитектурно заложить поле под future segments.

2. **Нестабильность внешних API**
   - Таймауты + ретраи + идемпотентность submit.
   - Явные `failed` статусы и `last_error` для каждой job.

3. **Проблемы YouTube OAuth/refresh**
   - Health endpoint + авто-refresh токенов перед upload.
   - Разделять auth-errors и transient-errors.

4. **Дубли ежедневных публикаций**
   - Daily dedup rule на уровне enqueue.
   - Проверка published job за дату перед созданием новой.

5. **Утечки секретов в логах**
   - Никогда не писать OAuth токены в логи.
   - Логировать только безопасные метаданные/идентификаторы.

---

## Итого

Проект уже имеет сильный фундамент для шаблона "ИИ контент-завод": шаблонная модель агента, единый runtime-подход, универсальные channel connections, шифрование credential данных и рабочий паттерн queue/worker из `sales_manager`.

Главный разрыв сейчас: `content_factory` есть в данных, но отсутствует как отдельный pipeline выполнения.

Правильная стратегия — внедрить `content_factory` как job-driven workflow (script -> Kling -> YouTube) с прозрачной статусной моделью, после чего постепенно добавлять approval flow, склейку сегментов и мультиканальную публикацию (TikTok/Pinterest) без переработки ядра.

