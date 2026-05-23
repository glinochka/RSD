# Рефакторинг голосового ИИ-агента под потоковую архитектуру (SaaS)

Документ описывает переход от текущей реализации телефонии RSD к целевой модели из ТЗ (P90 600–800 мс, barge-in, потоковый STT/LLM/TTS). **Обратная совместимость не требуется** — продуктовый PSTN-канал ещё не в проде.

---

## 1. Как устроено сейчас (аудит)

### 1.1 Компоненты

| Слой | Путь | Роль |
|------|------|------|
| UI / канал | `backend/app/router_agents/telephony_channel.py`, `frontend` | Подключение Voximplant, webhook URL, аналитика |
| Bridge | `telephony_bridge/` | HTTP webhook → state machine → ответ **списком actions** |
| Backend | `backend/app/router_telephony/`, `channels/telephony_dialogue.py` | Resolve, call-event, **turn по готовой записи** |
| БД | `agent_telephony_calls`, `agent_telephony_turns` | Метаданные, транскрипты после хода |
| Оркестратор (логический) | `services/telephony_orchestrator.py` | Состояния GREET/LISTEN/… поверх **полного** ответа LLM |
| Preview (браузер) | `router_agents/telephony_preview.py`, `TelephonyVoicePreview.jsx` | **Отдельный контур**, не PSTN |

### 1.2 Продуктовый поток звонка (PSTN) — фактическая модель

Сейчас это **последовательный HTTP-цикл**, а не media pipeline:

```
Voximplant VoxEngine (сценарий вне репозитория)
    → POST /webhook/voximplant/:connection_id
    → telephony_bridge (CallSession: RINGING → GREETING → LISTENING → …)
    → actions: answer | play_tts | record | transfer | stop_tts
    → при record: тишина 400–700 ms → call.recording_ready
    → POST /internal/telephony/turn (audio URL | base64 | transcript)
    → batch STT (faster-whisper / OpenAI через voice_transcription.py)
    → template_runtime.execute() целиком
    → ответ: reply_text + reply_chunks → play_tts (Voximplant TTS)
```

**Ключевые ограничения:**

1. **Нет потока аудио в приложение** — `startMediaStream()` в провайдере по сути отдаёт `record`, не WebSocket G.711 (`telephony_bridge/src/providers/voximplant.ts`).
2. **LLM не стримится в прод-путь** — `telephony_dialogue.py` ждёт полный `template_runtime.execute()`; `telephony/streaming.py` (`stream_answer_sentences`) **нигде не подключён**.
3. **TTS не потоковый** — синтез на стороне CPaaS по готовому тексту; Yandex/OpenAI TTS только для **браузерного preview** (`telephony/tts_service.py`).
4. **Turn = событие webhook** — задержка = запись + HTTP round-trip + batch STT + полный LLM + TTS; KPI production (E2R &lt; 1.5 s) недостижимы без смены архитектуры.
5. **Сессия** — bridge: memory/Redis для `CallSession`; backend: `partial_store` in-memory; нет **sticky stateful worker** на звонок.
6. **Маршрутизация** — один DID на connection; DTMF → синтетический transcript (`telephony/dtmf.py`), без Redis «добавочный → agent_id».
7. **Barge-in** — есть `stop_tts` + `telephony/cancel`, но без `clearMediaBuffer` на media-канале и без отмены потокового TTS.

### 1.3 Что не путать: браузерный preview

| | Продукт (PSTN) | Preview (браузер) |
|--|----------------|-------------------|
| Вход | Voximplant → bridge | `POST` preview API, WebRTC/микрофон |
| STT | Запись/CPaaS → backend whisper | Web Speech API / загрузка аудио |
| TTS | Voximplant actions | Yandex/OpenAI в браузере |
| Цель рефакторинга | **Да** | **Нет** (оставить тонкий shim, общий только runtime агента) |

Preview после рефакторинга: по-прежнему вызывает `process_phone_turn` (или лёгкий HTTP «turn» без media gateway), **без** VoxEngine/WebSocket/Silero.

---

## 2. Целевая архитектура (по ТЗ)

```
┌─────────────────────────────────────────────────────────────┐
│  Сигнальный контур (Voximplant VoxEngine / SIP)              │
│  - 183 Early Media, answer, DTMF, transfer                   │
│  - WebSocket μ-law ↔ Media Gateway                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ PCM frames 20–30 ms
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Media Gateway (новый сервис, РФ edge)                       │
│  Silero VAD → streaming STT → turn-taking (350–450 ms)       │
│  ← streaming TTS bytes ← orchestrator                       │
│  barge-in: clear buffer + cancel upstream                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ gRPC/WS events (не HTTP turn)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Dialog Orchestrator (stateful worker, 1 процесс ≈ N сессий) │
│  Redis: prompt, history, tool cache (<5 ms)                  │
│  LLM stream + chunking по пунктуации                         │
└───────────────────────────┬─────────────────────────────────┘
                            │ CRM / template_runtime (async tools)
                            ▼
                     backend FastAPI (control plane)
```

**Разделение:** `telephony_bridge` в текущем виде (webhook + record loop) **заменяется** на пару «VoxEngine сценарий + Media Gateway»; backend остаётся control plane (каналы, credentials, аналитика, billing).

---

## 3. Этапы рефакторинга

Каждый этап рассчитан на **один сфокусированный промпт** в Cursor (или 1–2 дня). Крупные этапы разбиты на подэтапы **A/B**.

---

### Этап 1. Границы сервисов и контракты (control vs media)

**Цель:** зафиксировать новые границы и остановить развитие HTTP-turn как основного media-пути.

**Задачи:**

1. Добавить в репозиторий пакет `telephony_media_gateway/` (скелет: WS server, health, config) и `docs/telephony/STREAMING_ARCHITECTURE.md` с диаграммой выше.
2. Описать **протокол сессии** (JSON over WebSocket или gRPC):
   - `session.start` { `call_id`, `connection_id`, `caller_e164`, `codec`: `pcmu` }
   - `audio.in` / `audio.out` (binary frames)
   - `stt.partial` / `stt.final`
   - `agent.audio.start` / `agent.audio.chunk` / `agent.audio.end`
   - `barge_in`, `session.end`
3. В `telephony_bridge` пометить `@deprecated` маршрут record→`call.recording_ready`→turn; в README указать «только до этапа 4».
4. Вынести из preview зависимость от bridge: явный флаг `source: browser_preview` в API (уже частично есть через `preview:` caller).

**Пояснение:** без чёткого контракта media↔orchestrator следующие этапы расползутся. Backend RFC-001 webhook остаётся для **сигнальных** событий (inbound, hangup, DTMF), но не для каждой реплики.

**Критерий готовности:** схема событий в репо + пустой gateway поднимается в compose.

---

### Этап 2. VoxEngine + Early Media (сигнальный контур)

**Цель:** звонок принимается на Voximplant с 183 и мгновенным приветствием; media идёт в gateway, не в HTTP record.

#### 2A — VoxEngine сценарий (репозиторий)

**Задачи:**

1. Добавить `voxengine/rsd_inbound.js` (или `.voxengine`): `183 Session Progress` → буфер приветствия из статики/RAM → `answer` → `VoxEngine.createWebSocket` к `TELEPHONY_MEDIA_WS_URL`.
2. Проброс `customData`: `connection_id`, `call_id`, `called_number`, `caller_id`.
3. Обработка `DTMF.Tone` → отдельное WS-сообщение `dtmf` (не HTTP webhook на каждую цифру, если нагрузка высокая).

#### 2B — Минимальный приём audio в gateway

**Задачи:**

1. WS: принять μ-law, логировать RTF, отдавать эхо/тишину (loopback) для проверки RTP path.
2. Control webhook: только `call.inbound` / `call.answered` / `call.hangup` → backend `call-event` (упростить bridge).

**Пояснение:** Early Media снимает 1–2 с до первого голоса без ожидания полного answer+HTTP round-trip.

**Критерий готовности:** тестовый звонок → слышно приветствие &lt; 1.2 s → WS подключён (лог gateway).

---

### Этап 3. VAD + Streaming STT + Turn-taking (входящий поток) ✅

**Цель:** речь уходит в STT **до** конца фразы; финал реплики через 350–450 ms тишины (по ТЗ).

**Реализовано:** `telephony_media_gateway` — Silero/energy VAD, Yandex gRPC v3 / Deepgram / mock STT, `stt.partial`/`stt.final`, метрики; backend `/turn` не вызывает batch STT для PSTN (`recording_url` только preview).

**Задачи:**

1. В gateway: интеграция **Silero VAD** (ONNX Runtime, чанки 20–30 ms, RTF контроль).
2. Пока VAD=speech → gRPC **Yandex SpeechKit v3 REAL_TIME** (альтернатива: env `STT_PROVIDER=deepgram`).
3. Эмитить `stt.partial` в orchestrator; при silence ≥ `TURN_SILENCE_MS` (default 400) → `stt.final` + сброс буфера.
4. Удалить зависимость prod-пути от `voice_transcription.py` / `recording_url` (оставить только preview/fallback).
5. Метрики: `stt_partial_ms`, `stt_final_ms`, `vad_speech_ratio`.

**Пояснение:** это главный разрыв с текущим `record` + batch STT. Bridge `call.partial_transcript` станет внутренним событием gateway, не CPaaS webhook.

**Критерий готовности:** на тестовом звонке в логах видны partial каждые 50–100 ms и один final после паузы.

---

### Этап 4. Stateful Dialog Orchestrator + Redis ✅

**Цель:** контекст диалога в RAM воркера, промпты и история из Redis (&lt; 5 ms), минимум обращений к PostgreSQL во время звонка.

**Реализовано:** `app/telephony/orchestrator_main.py`, Redis-ключи, событийный `telephony_orchestrator.py`, pub/sub gateway↔orchestrator, батч turns в Postgres.

**Задачи:**

1. Новый процесс `backend/app/telephony/orchestrator_worker.py` (или отдельный `telephony_orchestrator/`):
   - подписка на `stt.final` / `barge_in`;
   - **affinity**: `call_id` → один asyncio task / worker slot;
   - при старте сессии: `HGETALL telephony:session:{connection_id}` + `telephony:agent:{agent_id}:prompt`.
2. Redis-ключи:
   - `telephony:route:dtmf:{extension}` → `agent_id`
   - `telephony:route:did:{e164}` → `connection_id`
   - `telephony:dialog:{call_id}` → list последних N реплик + tool results cache TTL
3. На `session.start`: один раз `resolve` из Postgres → положить в Redis; далее только orchestrator.
4. Переписать `telephony_orchestrator.py` под **событийную** модель (не ждать полный ответ для смены state).
5. PostgreSQL: писать turns **батчем** на `stt.final` / `hangup`, не на каждый partial.

**Пояснение:** текущий `CallSession` в bridge и `partial_store` in-memory заменяются этим слоем. `telephony_bridge` после этапа 7 — тонкий адаптер или удалён.

**Критерий готовности:** 3 параллельных звонка, Redis hit для prompt/history, в Postgres не более 1–2 запросов на звонок до hangup.

---

### Этап 5. Исходящий поток: LLM stream → chunk TTS → RTP ✅

**Цель:** TTFT LLM 150–300 ms, TTFA TTS 50–150 ms; абонент слышит начало ответа, пока LLM дописывает конец.

**Реализовано:** `stream_pipeline.py`, `stream_tts.py`, `outbound_publish.py`, syntagma streaming в orchestrator, `agent.audio.*` / `agent.play_filler` в media gateway, отмена по `call_id` в `stream_cancel.py`, метрики `llm_first_token_ms` / `tts_first_byte_ms` в `call.metadata_`.

#### 5A — LLM streaming + нарезка

**Задачи:**

1. Подключить `stream_answer_sentences` (или OpenAI Realtime / Groq Llama-3-8B по env) **в orchestrator**, не в HTTP turn.
2. Нарезка по `, . ! ?` и минимальной длине синтагмы (config).
3. Параллельно: `template_runtime` для tools — при tool &gt; 1.5 s отправить в gateway `play_filler` (кэш wav в RAM).
4. Отмена: `telephony/stream_cancel.py` по `call_id` при `barge_in`.

#### 5B — Streaming TTS

**Задачи:**

1. Адаптер: **ElevenLabs Flash v2.5** или **Yandex SpeechKit v3 stream** → PCM/μ-law chunks в gateway.
2. Убрать prod-зависимость от `play_tts` Voximplant как единственного пути (оставить fallback).
3. Первый chunk → `agent.audio.start` сразу после первой синтагмы.

**Пояснение:** сейчас `reply_chunks` формируются **после** полного LLM — это нужно инвертировать.

**Критерий готовности:** `llm_first_token_ms` + `tts_first_byte_ms` в metadata звонка; E2R p50 &lt; 2 s на стенде.

---

### Этап 6. Barge-in (прерывание) ✅

**Цель:** при голосе абонента во время ответа — остановка &lt; 100 ms, отмена LLM/TTS.

**Реализовано:** VAD barge-in в `telephony_media_gateway` (`barge_in_detector`, `agent_playback_tracker`), `clearMediaBuffer` в `voxengine/lib/rsd_media_gateway.js`, отмена stream + `interrupted_agent_text` из Redis `telephony:spoken:{call_id}` в `orchestrator_worker`, удалён bridge `handleBargeInDuringSpeech`.

**Задачи:**

1. VAD во время `agent.audio.*` → событие `barge_in`.
2. VoxEngine: `clearMediaBuffer` / stop playback (документировать в сценарии).
3. Orchestrator: cancel LLM stream + TTS stream; в следующий `stt.final` передать `interrupted_agent_text` (логика уже есть в `telephony_dialogue`, перенести в worker).
4. Удалить дублирующий bridge `handleBargeInDuringSpeech` HTTP-путь.

**Критерий готовности:** 90% тестов «перебить бота» — тишина агента &lt; 100 ms, нет «договаривания» старого TTS.

---

### Этап 7. Маршрутизация по агентам (DTMF / DID / SIP) ✅

**Цель:** варианты A/B/C из ТЗ без ручной привязки «один номер = один connection» в UI.

**Реализовано:** `telephony/routing.py`, Redis `telephony:route:dtmf:{ext}` / `telephony:route:did:{e164}`, API `PATCH /agents/channels/telephony/routing`, `POST /internal/telephony/resolve-inbound`, DTMF → orchestrator worker, DID на `call.inbound`, UI добавочный + список DID, SIP (7C) `telephony_sip_routes`.

**Задачи:**

1. **Вариант A:** API админки / onboarding — регистрация `extension (4 цифры)` → `agent_id` в Redis; VoxEngine собирает DTMF → `telephony:route:dtmf:{ext}`.
2. **Вариант B:** `called_number` на inbound → `telephony:route:did:{e164}` → `connection_id` (миграция credentials: optional `inbound_numbers[]`).
3. **Вариант C:** SIP trunk — маппинг `From`/`To` header → tenant (отдельная таблица `telephony_sip_routes`, этап можно отложить подэтапом 7C).
4. UI: поле «добавочный» / список DID; валидация уникальности extension.

**Пояснение:** текущий `telephony_channel` привязывает один `phone_number_e164` к connection — расширить модель данных, не ломая preview.

**Критерий готовности:** звонок на общий номер + DTMF `1234` стартует нужного агента; звонок на выделенный DID — без DTMF.

---

### Этап 8. Control plane, наблюдаемость, compliance ✅

**Цель:** эксплуатация в РФ, бюджет задержек, ФЗ-152 минимум.

**Реализовано:** `latency_budget.py`, p90 в `/metrics` + Prometheus, `purge_hot_dialog`, preview-only `/turn`, `recording_turn_legacy.ts`, RUNBOOK/COMPLIANCE/KPI, `TELEPHONY_E2R_ALERT_P90_MS`.

**Задачи:**

1. Latency budget table в метриках (Prometheus / `agent_telephony_calls.metadata`): sip, vad, stt_final, llm_ttft, tts_ttfa, e2r.
2. Деплой: gateway + orchestrator + Redis в **одном регионе** с Voximplant edge РФ.
3. SIP TLS + SRTP в Voximplant/SBC; чеклист из `docs/telephony/COMPLIANCE_CHECKLIST.md` обновить под SRTP.
4. Retention: turns в Postgres, hot dialog только Redis.
5. Удалить/архивировать: `recording_turn.ts`, batch STT в `turn_handler`, неиспользуемый HTTP `/turn` (оставить internal только для preview shim).

**Критерий готовности:** дашборд p90 E2R 600–850 ms на 50 фраз; runbook обновлён.

---

### Этап 9. Preview и тесты (изоляция от PSTN) ✅

**Цель:** браузерный тест логики агента не ломается и не тянет media stack.

**Реализовано:** `preview_guard.py`, `channel=browser_preview`, `/turn` 410 для PSTN, `test_vad_unit.mjs`, orchestrator integration test, WS `load_parallel_calls.mjs`, `replay_ws_trace.mjs`.

**Задачи:**

1. `telephony_preview.py`: явно документировать `channel=browser_preview`; запретить вызов media gateway.
2. Опционально: «симулятор latency» — воспроизведение recorded WS trace для QA.
3. E2E тесты: unit gateway VAD; integration orchestrator+mock STT; **без** Voximplant в CI.
4. Нагрузка: перенести `load_parallel_calls.mjs` на WS-сессии, не webhook turn.

**Пояснение:** preview остаётся для UX в кабинете; prod — только этапы 1–8.

---

## 4. Сводка: что удалить / что оставить

| Компонент | Действие |
|-----------|----------|
| `telephony_bridge` HTTP record loop | ✅ Удалён (control-only) |
| `turn_handler` batch STT | ✅ Только preview; PSTN → 410 |
| `telephony/streaming.py` | ✅ Подключён через `stream_pipeline.py` |
| `telephony_dialogue.process_phone_turn` | Сузить до вызова из orchestrator + preview |
| `partial_store` in-memory | Заменить Redis + gateway |
| `TelephonyVoicePreview.jsx` | Оставить, без gateway |
| RFC-001 webhook | Сократить до сигнальных событий + DTMF optional |
| `agent_telephony_*` таблицы | Оставить для аналитики |

---

## 5. Рекомендуемый порядок и оценка

| Этап | Ориентир | Результат |
|------|----------|-----------|
| 1 | 1 промпт | Контракты, скелет gateway |
| 2A+2B | 1–2 промпта | WS audio + Early Media |
| 3 | 1 промпт | VAD + Yandex STT stream |
| 4 | 1 промпт | Orchestrator + Redis |
| 5A+5B | 2 промпта | LLM+TTS stream |
| 6 | 1 промпт | Barge-in |
| 7 | 1–2 промпта | DTMF/DID routing |
| 8 | 1 промпт | Metrics, compliance, cleanup |
| 9 | 1 промпт | Preview isolation |

**Параллельно недопустимо:** этапы 5 и 3 (нужен final STT); этап 4 до 3 (нужны события `stt.final`).

---

## 6. Стек по ТЗ (маппинг на env)

| ТЗ | Переменные / модуль |
|----|---------------------|
| Voximplant G.711 WS | `TELEPHONY_MEDIA_WS_URL`, `voxengine/rsd_inbound.js` |
| Silero VAD | `VAD_MODEL_PATH`, onnxruntime в gateway |
| Yandex STT v3 | `YANDEX_SPEECHKIT_*`, gRPC |
| Deepgram (опция) | `DEEPGRAM_API_KEY` |
| OpenAI Realtime / Groq | `TELEPHONY_LLM_MODE=realtime\|groq` |
| ElevenLabs / Yandex TTS stream | `TELEPHONY_TTS_PROVIDER` |
| Redis | `REDIS_URL` (обязателен prod) |

---

## 7. Первый промпт для реализации (этап 1)

Скопировать в Cursor:

> Реализуй этап 1 из `TELEPHONY_STREAMING_REFACTOR.md`: создай скелет `telephony_media_gateway` (WS, health, config), файл протокола событий, обнови `docs/telephony/README.md`, пометь deprecated HTTP record-path в bridge. Preview не трогай.

---

*Документ: `TELEPHONY_STREAMING_REFACTOR.md`. Связан с историческим планом MVP: `TELEPHONY_AI_OPERATOR_PLAN.md` (этапы 0–4 считать заменёнными этим рефакторингом для prod PSTN).*
