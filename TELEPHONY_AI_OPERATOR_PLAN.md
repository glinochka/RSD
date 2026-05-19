# План реализации канала «ИИ-оператор по телефону»

Документ описывает поэтапную реализацию голосового канала для платформы RSD: входящие звонки → диалог с агентом → CRM/эскалация. План начинается с **MVP** (запись → STT → существующий runtime агента → TTS), но каждый этап закладывает расширения под **низкую задержку**, **потоковый диалог** и **человекоподобное общение**.

---

## 1. Цели и границы

### 1.1 Продуктовая цель

Пользователь в интерфейсе управления агентом подключает облачную телефонию (CPaaS), указывает ключи и номер. На входящий звонок отвечает ИИ-оператор с тем же промптом, шаблоном и CRM, что и в Telegram/WhatsApp.

### 1.2 Технические принципы (наследуем от RSD)

| Принцип | Как уже сделано в проекте | Как применить к телефонии |
|--------|---------------------------|---------------------------|
| Канал = запись в БД | `AgentChannelConnection` (`provider`, `encrypted_credentials`) | `provider: telephony_voximplant` (или универсальный `telephony`) |
| Обработка диалога | `MessageProcessor` + `template_runtime` | MVP: вызывать тот же runtime **после STT**; позже — отдельный `CallDialogueOrchestrator` |
| Изолированный bridge | `wa_bridge/` (Express, API key, webhook в backend) | `telephony_bridge/` — сессии звонков, медиа, webhook CPaaS |
| Голос → текст | `voice_transcription.py` (faster-whisper / OpenAI) | MVP: переиспользовать; production: streaming STT |
| Аналитика | `AgentAnalyticsMessage.channel` | Значение `phone` + отдельная таблица метрик звонка |
| Эскалация | `qa_handoff_service` | Transfer на номер оператора + email владельцу |

### 1.3 Что **не** входит в MVP (но заложено в архитектуре)

- Исходящий обзвон (cold call)
- Полноценный SIP trunk «с коробочной АТС клиента» без облака
- Юридический пакет 152-ФЗ «под ключ» (отдельный этап compliance)
- Несколько CPaaS-провайдеров одновременно

### 1.4 Рекомендуемый CPaaS для первой интеграции

**Этап 0 (выбор):** один провайдер с webhook + ASR/TTS в РФ.

| Критерий | Voximplant | Mango Office | Twilio (если нужен global) |
|----------|------------|--------------|----------------------------|
| РФ, номера | Да | Да | Ограниченно |
| Webhook + сценарии | Да | Да | Да |
| Встроенные ASR/TTS | Да | Частично / партнёры | Да (через Media Streams) |
| Документация для ИИ-бота | Хорошая | Средняя | Отличная |

**Рекомендация для MVP:** Voximplant (или Mango, если уже есть договор у команды). В коде абстрагировать `TelephonyProvider` — смена провайдера не должна ломать `MessageProcessor`.

---

## 2. Целевая архитектура

```
┌─────────────┐     PSTN/SIP      ┌──────────────────┐
│  Абонент    │ ────────────────► │  CPaaS (АТС)      │
└─────────────┘                   └────────┬─────────┘
                                         │ webhook / media
                                         ▼
                              ┌──────────────────────┐
                              │  telephony_bridge     │  ← новый сервис (как wa_bridge)
                              │  - сессии звонков     │
                              │  - STT/TTS адаптер    │
                              │  - state machine      │
                              └────────┬─────────────┘
                                         │ internal API
                                         ▼
                              ┌──────────────────────┐
                              │  backend (FastAPI)    │
                              │  - channel CRUD       │
                              │  - process_turn       │
                              │  - template_runtime   │
                              │  - CRM / handoff      │
                              └────────┬─────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              PostgreSQL            Redis (опц.)         LLM / Qdrant
```

**MVP-поток одного «хода» диалога:**

1. CPaaS → bridge: `call.started` (номер, `connection_id`, `caller_id`).
2. Bridge: приветствие (TTS или статический wav).
3. Bridge: запись реплики абонента (VAD / таймаут тишины 1.5–2.5 с).
4. Bridge → backend: `POST /internal/telephony/turn` `{ connection_id, audio_base64 | transcript }`.
5. Backend: STT (если пришло аудио) → `template_runtime.execute(..., source_channel="phone")`.
6. Backend → bridge: `{ reply_text, actions: [hangup|transfer|play_url] }`.
7. Bridge: TTS → воспроизведение → шаг 3 (цикл) или завершение.

**Целевой поток (после оптимизации):** streaming media WebSocket, partial STT, incremental LLM, streaming TTS, barge-in.

---

## 3. Этапы реализации

### Этап 0 — Подготовка и проектирование (3–5 рабочих дней) ✅

**Цель:** зафиксировать контракты, провайдера и KPI до написания кода.

**Статус:** выполнен в репозитории (2026-05-18). Индекс артефактов: [`docs/telephony/README.md`](docs/telephony/README.md).

#### Что сделано

1. **CPaaS:** утверждён **Voximplant** — [`docs/telephony/CPaaS_DECISION.md`](docs/telephony/CPaaS_DECISION.md) (чеклист тестового аккаунта и номера; таблицу окружения заполняет команда вне git).
2. **Webhook RFC:** [`docs/telephony/RFC-001-webhook-contract.md`](docs/telephony/RFC-001-webhook-contract.md) — события `call.inbound`, `call.answered`, `call.recording_ready`, `call.hangup`, `dtmf`; `call_id`, `connection_id`; HMAC `X-RSD-Telephony-Signature`.
3. **KPI:** [`docs/telephony/KPI_LATENCY.md`](docs/telephony/KPI_LATENCY.md).

   | Метрика | MVP (допустимо) | Цель (production) |
   |---------|-----------------|-------------------|
   | Время до первого голоса агента | &lt; 4 с | &lt; 1.2 с |
   | Время от конца фразы абонента до начала ответа | 3–8 с | &lt; 1.5 с |
   | Перебивание (barge-in) | Нет | Да |
   | Одновременные звонки на агента | 1–3 (тест) | N (по тарифу) |

4. **Юридический чеклист:** [`docs/telephony/COMPLIANCE_CHECKLIST.md`](docs/telephony/COMPLIANCE_CHECKLIST.md).
5. **Схема credentials:** JSON Schema [`schemas/telephony/credentials.v1.schema.json`](schemas/telephony/credentials.v1.schema.json), пример [`docs/telephony/credentials.example.json`](docs/telephony/credentials.example.json), Pydantic [`backend/app/telephony/credentials.py`](backend/app/telephony/credentials.py) (`provider` в БД: `telephony_voximplant`).

#### Результат этапа

- [x] Утверждённый провайдер (Voximplant); чеклист тестового номера.
- [x] RFC webhook + схема JSON credentials.
- [x] Env: [`docs/telephony/ENV_VARIABLES.md`](docs/telephony/ENV_VARIABLES.md), шаблон [`.env.telephony.example`](.env.telephony.example).

#### Зависимости

Нет.

---

### Этап 1 — Фундамент: данные, API канала, telephony_bridge (1.5–2 недели) ✅

**Цель:** в системе появляется сущность «телефонный канал», bridge принимает webhook, backend знает, какому агенту принадлежит звонок.

**Статус:** реализовано в репозитории (2026-05-18). Миграция `e2f3a4b5c6d7`, `router_telephony`, `telephony_bridge/`, Docker Compose.

#### 1.1 База данных

**Файлы:** `backend/app/alembic/migration/versions/..._add_telephony.py`, `backend/app/alembic/models.py`

1. Расширить допустимые `provider` (валидация в `router_agents`): `telephony_voximplant` (или `telephony` + поле `provider_variant` в JSON).
2. Таблица **`agent_telephony_calls`** (новая):

   | Поле | Тип | Назначение |
   |------|-----|------------|
   | `id` | UUID / bigint | PK |
   | `connection_id` | FK → `agent_channel_connections` | Канал |
   | `agent_id` | FK | Денормализация для аналитики |
   | `external_call_id` | string, unique | ID у CPaaS |
   | `caller_e164` | string | Номер абонента (хранить с учётом PII-политики) |
   | `status` | enum | `ringing`, `active`, `completed`, `failed`, `transferred` |
   | `started_at`, `ended_at` | datetime | |
   | `duration_sec` | int | |
   | `recording_url` | text, nullable | Ссылка у провайдера |
   | `metadata` | JSONB | DTMF, причина сброса, latency stats |

3. Таблица **`agent_telephony_turns`** (опционально в MVP, желательно сразу):

   | Поле | Назначение |
   |------|------------|
   | `call_id` | FK |
   | `role` | `user` / `agent` / `system` |
   | `transcript` | текст после STT или до TTS |
   | `latency_ms` | STT + LLM + TTS |
   | `created_at` | |

4. В `AgentAnalyticsMessage` разрешить `channel = 'phone'` (уже string — достаточно константы в коде).

#### 1.2 Backend API (управление каналом)

**Файлы:** `backend/app/router_agents/router.py`, `schemas.py`, `dao.py`

Эндпоинты по аналогии с WhatsApp:

| Метод | Путь | Действие |
|-------|------|----------|
| `POST` | `/agents/channels/add-telephony` | Создать connection, проверить credentials у CPaaS |
| `GET` | `/agents/channels` | Уже есть — добавить сериализацию telephony |
| `DELETE` | `/agents/channels` | Отключить канал, деактивировать сценарий у провайдера |
| `POST` | `/agents/channels/telephony/validate` | Test API key + номер |

**Валидация при подключении:**

- Запрос к API CPaaS: аккаунт активен, номер привязан к application/rule.
- Сгенерировать `webhook_secret`, вернуть пользователю **готовый URL** для вставки в кабинет CPaaS:  
  `https://<telephony-bridge-host>/webhook/voximplant/<connection_id>`

**Шифрование:** `encrypt_token` / существующий механизм для `encrypted_credentials`.

#### 1.3 Internal API для bridge

**Файлы:** `backend/app/router_telephony/` (новый router), `utils/internal_auth.py`

| Метод | Путь | Назначение |
|-------|------|------------|
| `POST` | `/internal/telephony/resolve` | По `connection_id` + `caller` → `agent_id`, prompt, template_config |
| `POST` | `/internal/telephony/turn` | Один ход диалога (см. этап 2) |
| `POST` | `/internal/telephony/call-event` | Старт/конец звонка, запись в `agent_telephony_calls` |

Защита: тот же паттерн, что `is_internal_request` + API key bridge.

#### 1.4 Сервис `telephony_bridge/`

**Структура (по образцу `wa_bridge/`):**

```
telephony_bridge/
  package.json
  Dockerfile
  src/
    server.ts          # Express / Fastify
    config.ts
    providers/
      voximplant.ts    # парсинг webhook, команды CPaaS
      types.ts         # TelephonyProvider interface
    session/
      call_session.ts  # state machine
    security/
      verify_signature.ts
```

**Обязательные env:**

- `TELEPHONY_BRIDGE_API_KEY`
- `TELEPHONY_BACKEND_URL`
- `TELEPHONY_BACKEND_INTERNAL_KEY`
- `TELEPHONY_WEBHOOK_BASE_URL`

**MVP-эндпоинты bridge:**

- `POST /webhook/voximplant/:connection_id` — входящие события.
- `GET /health`

**State machine (минимум):**

```
IDLE → RINGING → GREETING → LISTENING → PROCESSING → SPEAKING → LISTENING → … → END
                      ↘ TRANSFER → END
                      ↘ HANGUP → END
```

Состояние сессии: in-memory Map + **опционально Redis** (заложить интерфейс `SessionStore` с первого дня — для горизонтального масштабирования на этапе 5).

#### 1.5 Инфраструктура

- Docker Compose: сервис `telephony-bridge`, порт, сеть с backend.
- Nginx / ingress: публичный HTTPS только на bridge (не на internal API).
- Логирование: `call_id`, `connection_id`, без полного аудио в логах.

#### Критерии приёмки этапа 1

- [x] В БД создаётся `AgentChannelConnection` с `provider=telephony_voximplant` (`POST /api/agents/channels/add-telephony`).
- [x] Webhook доходит до bridge (`POST /webhook/voximplant/:connection_id`), возвращается 200.
- [x] Bridge вызывает `/api/internal/telephony/resolve` и `/call-event`.
- [x] Звонок пишется в `agent_telephony_calls` со статусами.

#### Задел под оптимизацию

- `TelephonyProvider` interface с методами `handleWebhook`, `playAudio`, `startMediaStream`, `transfer`.
- `SessionStore` abstraction (memory → Redis).
- Поля `latency_ms` в turns с первого дня.

---

### Этап 2 — MVP диалог: STT → агент → TTS (2–2.5 недели)

**Цель:** абонент звонит, слышит приветствие, задаёт вопрос голосом, получает осмысленный ответ ИИ; звонок можно завершить или перевести на оператора.

#### 2.1 Поток обработки хода (`/internal/telephony/turn`)

**Файлы:** `backend/app/router_telephony/turn_handler.py`, переиспользование:

- `backend/app/services/voice_transcription.py` — STT;
- `backend/app/channels/message_processor.py` — **не вызывать напрямую** (там завязка на `bot_id`), а вынести общую логику или добавить thin-wrapper:

**Рекомендуемый подход:**

Создать `backend/app/channels/telephony_dialogue.py`:

```python
async def process_phone_turn(
    *,
    agent_id: int,
    call_id: str,
    user_transcript: str,
    caller_e164: str,
    runtime_context: dict,
) -> PhoneTurnResult:
    # 1) те же проверки: subscription, frozen, availability
    # 2) template_runtime.execute(..., source_channel="phone")
    # 3) analytics log role=user/agent, channel=phone
    # 4) вернуть reply_text + optional actions
```

Дублировать проверки из `MessageProcessor.process`, не копировать весь метод — по возможности рефакторинг в `_shared_agent_guards()` (отдельный маленький PR внутри этапа).

#### 2.2 Промпт для голоса (MVP)

Добавить в `template_config` или автоматически префикс при `source_channel == "phone"`:

- Короткие фразы (1–3 предложения).
- Без markdown, списков, эмодзи.
- Уточняющие вопросы по одному.
- Явное «Сейчас соединю с оператором» при handoff.

**Файл:** `backend/app/services/telephony_prompt.py` — `apply_phone_style_instructions(base_prompt) -> str`.

#### 2.3 TTS (MVP)

**Вариант A (быстрее):** TTS провайдера (Voximplant TTS) — синтез на стороне bridge по тексту от backend.

**Вариант B:** backend возвращает `audio_base64` (Yandex SpeechKit / OpenAI TTS) — больше контроля над голосом.

Для MVP выбрать **один** путь; второй спрятать за `TtsAdapter` interface.

**Файл:** `telephony_bridge/src/tts/adapter.ts`

#### 2.4 Сценарий в CPaaS (MVP)

1. Входящий на номер → HTTP callback на bridge.
2. Answer call.
3. Play greeting (из `welcome_message` агента или дефолт).
4. Record user speech (max 15–30 s, end on silence).
5. HTTP POST turn → play TTS response.
6. Loop до: `max_turns`, `hangup` intent, `transfer` action, таймаут 5 мин.

#### 2.5 Действия агента (structured output)

Расширить ответ runtime или пост-обработку:

```json
{
  "reply_text": "Записал вас на завтра в 15:00.",
  "actions": []
}
```

Триггеры (MVP — keyword + LLM flag):

| Условие | Действие bridge |
|---------|-----------------|
| `requires_owner_handoff` из template | `transfer` на `operator_transfer_e164` |
| «до свидания», `hangup` tool | `hangup` |
| Ошибка LLM / timeout | «Извините, техническая ошибка» + transfer или hangup |

Интеграция с `qa_handoff_service.escalate_to_operator(..., channel="phone")`.

#### 2.6 Ограничения MVP (явно)

- Один говорящий в момент времени (нет barge-in).
- Полная запись фразы до STT (не streaming).
- DTMF: только «0 — оператор» (опционально).
- Макс. 10–15 ходов диалога на звонок.

#### Критерии приёмки этапа 2

- [ ] Тестовый звонок: приветствие → вопрос → ответ по базе знаний агента.
- [ ] CRM-tool срабатывает (если подключён), как в чате.
- [ ] Эскалация: фраза «соедините с человеком» → transfer.
- [ ] Транскрипт ходов в БД + записи в `AgentAnalyticsMessage`.
- [ ] Средняя задержка ответа измерена и залогирована.

#### Задел под оптимизацию

- `PhoneTurnResult` с полями `partial`, `end_of_turn`, `confidence` (пока не используются).
- Отдельный timeout для LLM (3 s) vs общий (8 s).
- Очередь фоновых задач для долгих CRM-вызовов («одну секунду, проверяю в системе» — filler TTS на этапе 5).

---

### Этап 3 — UI и UX подключения канала (1 неделя) ✅

**Цель:** владелец агента подключает телефонию без участия разработчика.

**Статус:** реализовано в репозитории (2026-05-18).

#### 3.1 Frontend

**Файлы:** `frontend/src/pages/createAgent.jsx`, `agentsPage.jsx`, `frontend/src/services/agentService.js`, `frontend/src/config/constants.js`

1. Блок **«Телефония (ИИ-оператор)»** рядом с Telegram/WhatsApp:
   - переключатель «Включить телефонный канал»;
   - поля: API key, Account ID, Application ID, номер E.164, номер оператора для перевода;
   - кнопка «Проверить подключение»;
   - read-only: **Webhook URL** (копировать в буфер);
   - статус: подключено / ошибка валидации.

2. `agentService.addTelephonyChannel`, `validateTelephonyChannel`, `removeChannel`.

3. На карточке агента — бейдж «📞 Телефония» и номер.

#### 3.2 Аналитика (базовая)

**Файлы:** `AgentDetailedAnalyticsPage.jsx` или новая вкладка

- Фильтр канала `phone`.
- Список последних звонков: дата, длительность, статус, caller (маскированный +7900***1234).
- Прослушивание записи (ссылка CPaaS) — если `record_calls=true`.

#### Критерии приёмки этапа 3

- [x] Подключение канала end-to-end из UI (`createAgent`, модалка каналов на `agentsPage`).
- [x] Отключение канала через существующий `removeChannel` (деактивация сценария CPaaS — этап 4+).
- [x] В аналитике: вкладка «Звонки», фильтр канала `phone` в чатах, API `GET /api/agents/analytics/telephony/calls`.

---

### Этап 4 — Надёжность, безопасность, эксплуатация (1 неделя)

**Цель:** MVP можно показывать пилотным клиентам.

#### 4.1 Безопасность

- Проверка подписи webhook (HMAC-SHA256 с `webhook_secret`).
- Rate limit на webhook (по `connection_id` и IP).
- Internal API только из private network / mTLS.
- Не логировать API keys; PII mask в логах (`utils/pii.py`).

#### 4.2 Идемпотентность

- `external_call_id` + event type — dedup в bridge (как `INBOUND_DEDUP` в wa_bridge).
- Повторный webhook не создаёт второй звонок в БД.

#### 4.3 Отказоустойчивость

| Сбой | Поведение |
|------|-----------|
| Backend недоступен | «Сервис временно недоступен» + transfer на оператора или голосовая почта |
| STT пустой | «Не расслышал, повторите, пожалуйста» |
| LLM timeout | Filler + один retry, затем transfer |
| CPaaS timeout | Завершить звонок корректно |

#### 4.4 Мониторинг

- Метрики: `calls_started`, `calls_completed`, `turn_latency_p95`, `transfer_rate`, `stt_empty_rate`.
- Алерт если `turn_latency_p95 > 10s` (MVP) / `> 2s` (после оптимизации).

#### 4.5 Compliance (минимум для пилота)

- IVR в начале: «Разговор может быть записан…»
- Флаг `record_calls` в credentials.
- Retention policy для `agent_telephony_turns` (90 дней — настраиваемо).

#### Критерии приёмки этапа 4

- [x] Нагрузочный тест: 3 параллельных звонка без падения (`telephony_bridge/scripts/load_parallel_calls.mjs`).
- [x] Пентест чеклист webhook (подделка, replay): [docs/telephony/WEBHOOK_PENTEST_CHECKLIST.md](docs/telephony/WEBHOOK_PENTEST_CHECKLIST.md).
- [x] Runbook: [docs/telephony/RUNBOOK.md](docs/telephony/RUNBOOK.md).

#### Runbook (кратко)

| Симптом | Действие |
|---------|----------|
| 401 на webhook | Проверить `webhook_secret`, timestamp ±300s, raw body signing |
| 429 | Rate limit по connection/IP — см. `TELEPHONY_WEBHOOK_RATE_LIMIT_*` |
| Backend 502 из bridge | `TELEPHONY_ENABLED`, сеть docker, internal key + HMAC |
| Метрики | `GET /metrics` (bridge), `GET /api/internal/telephony/metrics` (backend) |
| Retention | Cron `POST /api/internal/telephony/retention/purge`, `TELEPHONY_TURNS_RETENTION_DAYS=90` |

**Статус:** реализовано в репозитории (2026-05-18).

---

## 4. Этапы оптимизации (после MVP)

Ниже — путь к **короткому таймингу** и **человекоподобному** диалогу. Каждый этап можно выпускать отдельным релизом.

---

### Этап 5 — Снижение задержки: streaming и параллельный pipeline (2–3 недели)

**Цель:** время от конца речи абонента до начала ответа агента **&lt; 2 с** (p50), **&lt; 3 с** (p95).

#### 5.1 Streaming STT

- Перейти с «запись файла → batch STT» на **streaming ASR** (Voximplant ASR realtime, Deepgram, Yandex Streaming, OpenAI Realtime API — по выбору).
- Bridge отправляет partial transcripts на backend: `POST /internal/telephony/partial` (только логировать до `is_final`).

#### 5.2 Endpointing (определение конца реплики)

- VAD + пауза 400–700 ms (настраиваемо) вместо фиксированных 2.5 s тишины.
- Не ждать полной записи 30 s — резать раньше.

#### 5.3 Параллельный конвейер

```
[Абонент говорит] ──► STT partial ──► (накопление)
                              │
                              ▼ is_final
                         LLM start ──► TTS start (на первых 5–10 словах)
```

- **LLM:** streaming tokens; TTS запускать на первом законченном предложении.
- **Filler audio:** при CRM-tool &gt; 1.5 s — проигрывать «Секунду, смотрю в расписании…» (кэшированные wav).

#### 5.4 Инфраструктура

- Redis для сессий (обязательно).
- Отдельный pool воркеров для telephony (не блокировать HTTP backend долгим LLM — очередь Celery/ARQ или dedicated worker).

#### Критерии приёмки

- [ ] p50 end-of-speech → first audio &lt; 2 s на тестовом наборе 50 фраз.
- [ ] Partial STT виден в debug-логах turn.

---

### Этап 6 — Человекоподобный диалог: turn-taking, barge-in, prosody (2–3 недели)

**Цель:** разговор воспринимается как живой оператор, а не IVR с паузами.

#### 6.1 Barge-in (перебивание)

- Во время TTS слушать канал; при голосе абонента — **остановить воспроизведение** &lt; 200 ms.
- Отменить текущий LLM stream (abort controller).
- Новый ход с учётом того, что абонент перебил («слышал, вы спрашиваете про…»).

#### 6.2 Диалоговая модель (orchestrator)

**Файл:** `backend/app/services/telephony_orchestrator.py`

Состояния поверх template runtime:

| Состояние | Поведение |
|-----------|-----------|
| `GREET` | Короткое приветствие + «чем помочь?» |
| `LISTEN` | STT + endpointing |
| `CLARIFY` | Один уточняющий вопрос, не три |
| `ACT` | CRM / booking tools |
| `CONFIRM` | Переспрос критичных данных (дата, телефон) |
| `CLOSE` | «Могу ещё чем-то помочь?» → hangup |
| `HANDOFF` | Transfer |

LLM получает **сжатый контекст звонка** (последние 6–8 реплик), не полный chat portrait из мессенджера — портрет для phone настраивать отдельно (`enable_phone_portrait`).

#### 6.3 Backchannel («угу», «понял»)

- На длинной реплике абонента (&gt; 5 s) — короткий ACK mid-utterance (осторожно, не перебивать смысл).

#### 6.4 Голос и просодия

- Единый `voice_id` на агента в UI.
- SSML / паузы для номеров и дат: «пятнадцать ноль-ноль».
- Эмоциональный тон: neutral-friendly (не «радиоведущий»).

#### 6.5 DTMF и мультимодальность

- «Нажмите 1 для записи, 2 для оператора» — fallback при плохом STT.

#### Критерии приёмки

- [ ] Barge-in работает в 90% тестовых сценариев.
- [ ] Слепое сравнение: 5 респондентов — «естественность» ≥ 4/5.

---

### Этап 7 — Production-grade: масштаб, мульти-провайдер, исходящие (3+ недели)

**Цель:** коммерческий тариф «телефония» с SLA.

#### 7.1 Multi-provider

- Реализации: `VoximplantProvider`, `TwilioProvider`, `MangoProvider`.
- Фабрика по `credentials.provider`.

#### 7.2 Исходящие звонки

- API: «перезвонить клиенту» из CRM / дашборда.
- Очередь исходящих, лимиты, quiet hours (timezone из `template_config`).

#### 7.3 Очереди и несколько операторов

- Hunt group для transfer.
- Whisper/coach mode (оператор слышит ИИ до подключения) — опционально.

#### 7.4 Биллинг

- Учёт минут в подписке (`subscription` + metering).
- Себестоимость: CPaaS + STT + TTS + LLM на звонок.

#### 7.5 Качество

- Offline eval: набор 100 типовых диалогов, regression после смены модели.
- A/B голосов и промптов.

---

## 5. Сводная дорожная карта

| Этап | Содержание | Ориентир | Накопительный результат |
|------|------------|----------|-------------------------|
| 0 | Подготовка, RFC, CPaaS | 3–5 дн | Готовность к разработке |
| 1 | БД, API, bridge, webhook | 1.5–2 нед | Звонок доходит до агента |
| 2 | MVP диалог STT→LLM→TTS | 2–2.5 нед | **Рабочий ИИ-оператор** |
| 3 | UI + базовая аналитика | 1 нед | Самообслуживание клиентов |
| 4 | Security, ops, compliance min | 1 нед | Пилот на клиентах |
| 5 | Streaming, latency | 2–3 нед | Быстрые ответы |
| 6 | Barge-in, orchestrator | 2–3 нед | «Живой» диалог |
| 7 | Scale, multi-CPaaS, outbound | 3+ нед | Коммерческий продукт |

**До пилотного MVP (этапы 0–2):** ~4–5 недель.  
**До «идеала» (этапы 0–6):** ~3–4 месяца при одной команде.

---

## 6. Изменения по репозиторию (чеклист файлов)

### Новые компоненты

| Путь | Назначение |
|------|------------|
| `telephony_bridge/` | Webhook, сессии, TTS/STT адаптеры |
| `backend/app/router_telephony/` | Internal + публичные API телефонии |
| `backend/app/channels/telephony_dialogue.py` | Обёртка над template runtime для phone |
| `backend/app/services/telephony_prompt.py` | Голосовые инструкции к промпту |
| `backend/app/services/telephony_orchestrator.py` | Этап 6 |
| `backend/app/alembic/migration/versions/*_telephony*.py` | Таблицы звонков |

### Изменяемые компоненты

| Путь | Изменение |
|------|-----------|
| `backend/app/alembic/models.py` | Модели `AgentTelephonyCall`, `AgentTelephonyTurn` |
| `backend/app/router_agents/router.py` | CRUD канала telephony |
| `backend/app/router_agents/schemas.py` | Pydantic-схемы credentials |
| `backend/app/channels/message_processor.py` | Enum `Channel.TELEPHONY` (опционально), shared guards |
| `backend/app/config.py` | Env: TTS provider, telephony limits |
| `frontend/src/pages/createAgent.jsx` | UI блок телефонии |
| `frontend/src/services/agentService.js` | API методы |
| `docker-compose*.yml` | Сервис telephony-bridge |

---

## 7. Переменные окружения (сводка)

### Backend

```env
TELEPHONY_ENABLED=true
TELEPHONY_INTERNAL_API_KEY=...
TELEPHONY_MAX_TURN_SECONDS=30
TELEPHONY_MAX_CALL_MINUTES=15
TELEPHONY_TTS_PROVIDER=voximplant  # voximplant | yandex | openai
YANDEX_SPEECHKIT_API_KEY=...       # если yandex
```

### telephony_bridge

```env
TELEPHONY_BRIDGE_API_KEY=...
TELEPHONY_BACKEND_URL=http://backend:8000
TELEPHONY_BACKEND_INTERNAL_KEY=...
TELEPHONY_WEBHOOK_BASE_URL=https://telephony.example.com
TELEPHONY_SESSION_STORE=memory     # redis на этапе 5
REDIS_URL=...
```

---

## 8. Тестирование

### 8.1 Автотесты

| Уровень | Что тестировать |
|---------|-----------------|
| Unit | `telephony_prompt`, парсинг webhook, state machine transitions |
| Integration | `/internal/telephony/turn` с mock LLM и mock STT |
| E2E | Запись wav → turn → ожидаемый текст ответа (без реального CPaaS) |

**Файл:** `backend/app/tests/test_telephony_turn.py`

### 8.2 Ручные сценарии (MVP)

1. Входящий → приветствие → вопрос по FAQ → корректный ответ.
2. Запрос записи в CRM → подтверждение данных.
3. «Оператор» / handoff → transfer на мобильный.
4. Молчание абонента → повторный prompt.
5. Подписка истекла → вежливый отказ + hangup.
6. Параллельные 2 звонка на разных агентов.

### 8.3 Набор для регрессии latency (этап 5+)

- 50 аудиофраз (шум, акцент, короткие/длинные).
- Замер: `eos_to_first_audio_ms`, `stt_final_ms`, `llm_first_token_ms`, `tts_first_byte_ms`.

---

## 9. Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Высокая задержка MVP отпугнёт пилотов | Высокая | Честный positioning «бета»; этап 5 в приоритете после первого пилота |
| STT ошибается на именах/адресах | Средняя | CONFIRM state; DTMF fallback; повторение распознанного |
| CRM tool долгий | Высокая | Filler TTS; async tool + callback (этап 5) |
| Юридические требования к записи | Средняя | IVR disclaimer; opt-out по регионам |
| Стоимость минут CPaaS + LLM | Средняя | Лимиты в подписке; metering с этапа 7 |

---

## 10. Definition of Done для MVP (этапы 1–3)

Продукт считается готовым к ограниченному пилоту, когда:

1. Пользователь подключает телефонию в UI без ручной настройки БД.
2. Входящий звонок обрабатывается выбранным агентом с его промптом и CRM.
3. Транскрипт и метаданные звонка доступны в аналитике.
4. Эскалация на оператора работает.
5. Задокументированы env, webhook URL и runbook на сбои.
6. Замерена baseline-задержка для планирования этапа 5.

---

## 11. Следующий шаг для команды

1. Утвердить CPaaS (этап 0).
2. Создать ветку `feature/telephony-mvp`.
3. Реализовать этап 1 (параллельно: миграция БД + skeleton `telephony_bridge`).
4. Подключить тестовый номер и пройти сценарий этапа 2 вручную.
5. Закрыть UI (этап 3) и отдать 1–2 пилотным клиентам.
6. По метрикам latency решить приоритет этапов 5 vs 6.

---

*Документ: `TELEPHONY_AI_OPERATOR_PLAN.md` — живой план; при смене провайдера обновить разделы 1.4, 2.4 и 7.1.*
