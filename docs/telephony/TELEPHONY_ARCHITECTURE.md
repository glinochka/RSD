# Архитектура модуля телефонии RSD

## Обзор

Модуль телефонии реализует голосового AI-агента, принимающего входящие PSTN-звонки через Voximplant. Система работает в режиме реального времени: распознаёт речь абонента (STT), генерирует ответ (LLM), синтезирует голос (TTS) и воспроизводит через телефонную линию.

---

## Компоненты системы

```
┌──────────────┐     PSTN      ┌──────────────────┐
│   Абонент    │ ◄────────────►│   Voximplant     │
│  (телефон)   │               │   (SIP/RTP)      │
└──────────────┘               └────────┬─────────┘
                                        │ WebSocket (µ-law 8kHz)
                                        ▼
                               ┌──────────────────┐
                               │  VoxEngine       │
                               │  (rsd_inbound)   │
                               └──┬──────────┬────┘
                      HTTP webhook │          │ WebSocket (µ-law)
                                   ▼          ▼
                    ┌───────────────────┐  ┌─────────────────────┐
                    │ Telephony Bridge  │  │ Telephony Media      │
                    │ (Node.js :8100)   │  │ Gateway (Node.js     │
                    │ signal events     │  │ :8200) audio+STT     │
                    └────────┬──────────┘  └──────────┬───────────┘
                             │ HTTP                    │ Redis pub/sub
                             ▼                        ▼
                    ┌──────────────────────────────────────────────┐
                    │           Backend (Python/FastAPI)            │
                    │                                              │
                    │  ┌─────────────────────────────────────────┐ │
                    │  │  Orchestrator Worker (Redis subscriber)  │ │
                    │  │  - dialog state machine                  │ │
                    │  │  - LLM streaming                         │ │
                    │  │  - TTS streaming                         │ │
                    │  └─────────────────────────────────────────┘ │
                    │                                              │
                    │  ┌────────────┐  ┌──────────┐  ┌──────────┐ │
                    │  │ PostgreSQL │  │  Redis   │  │  Qdrant  │ │
                    │  │ (calls,    │  │ (pubsub, │  │ (RAG KB) │ │
                    │  │  turns)    │  │  cache)  │  │          │ │
                    │  └────────────┘  └──────────┘  └──────────┘ │
                    └──────────────────────────────────────────────┘
```

### 1. VoxEngine Script (`voxengine/rsd_inbound.bundled.js`)

Сценарий Voximplant Cloud IDE — точка входа для входящих PSTN-звонков.

**Ответственность:**
- Приём входящего вызова (`CallEvents.Incoming`)
- Отправка control-событий (call.inbound, call.answered, call.hangup) на Telephony Bridge через HTTP webhook
- Установка WebSocket-соединения с Media Gateway для передачи аудио
- Дуплексный медиа-мост: аудио абонента → WS, аудио агента ← WS
- Обработка DTMF-тонов и перенаправление на оператора

**Конфигурация (Application Secrets):**
- `RSD_CONNECTION_ID` — ID телефонного подключения
- `RSD_WEBHOOK_SECRET` — HMAC-секрет для подписи вебхуков
- `RSD_WEBHOOK_BASE_URL` — URL Telephony Bridge
- `TELEPHONY_MEDIA_WS_URL` — WSS-адрес Media Gateway
- `RSD_REQUIRE_EXTENSION` — режим IVR с вводом добавочного номера

### 2. Telephony Bridge (`telephony_bridge/`, Node.js, порт 8100)

Принимает HTTP-вебхуки от VoxEngine и маршрутизирует управляющие события.

**Ответственность:**
- Верификация HMAC-подписей вебхуков
- Rate limiting (120 req/connection/min, 240 req/IP/min)
- Проксирование signal-событий в Backend API
- Resolve входящего номера (DID/SIP-маршрутизация)
- Управление сессиями звонков (in-memory или Redis)

**Ключевые endpoints (проксирует в Backend):**
- `/api/internal/telephony/webhook-auth`
- `/api/internal/telephony/resolve-inbound`
- `/api/internal/telephony/resolve`
- `/api/internal/telephony/call-event`

### 3. Telephony Media Gateway (`telephony_media_gateway/`, Node.js, порт 8200)

Real-time аудио-процессинг: приём µ-law аудио от Voximplant, VAD, STT, воспроизведение ответа.

**Ответственность:**
- WebSocket-сервер для приёма/отправки аудио
- VAD (Voice Activity Detection) — Silero ONNX или energy-based
- Turn-taking — определение конца реплики по тишине
- Streaming STT (Yandex SpeechKit v3 / Deepgram)
- Barge-in detection — прерывание агента абонентом
- Playback pacer — потактовая отправка PCM16 аудио (20ms фреймы)
- Redis pub/sub: отправка событий оркестратору, приём ответов

**Audio pipeline:**
```
µ-law frame (160 bytes, 20ms)
    → PCM16 conversion
    → VAD (Silero/Energy, threshold 0.35)
    → TurnTaking (silence >= 350ms → utterance_end)
    → STT stream (Yandex/Deepgram)
    → stt.final event → Redis publish
```

**Playback pipeline (ответ агента):**
```
Redis reply (agent.audio.start)
    → buildVoxStartMessage (обязательно!)
    → agent.audio.chunk (PCM16 base64)
    → enqueuePcm16Playback → pacer (20ms interval)
    → buildVoxMediaMessage → WS → Voximplant → абонент
    → agent.audio.end → buildVoxStopMessage
```

### 4. Backend Orchestrator Worker (`backend/app/telephony/orchestrator_worker.py`)

Главный мозг системы — подписывается на Redis-события от Media Gateway и координирует генерацию ответа.

**Ответственность:**
- Подписка на `telephony:orch:events` (Redis pub/sub)
- Dialog State Machine (GREET → LISTEN → CLARIFY → ACT → CONFIRM → CLOSE → HANDOFF)
- Маршрутизация по DTMF-добавочному номеру
- Вызов LLM для генерации ответа (streaming)
- Streaming TTS для синтеза голоса
- Публикация аудио-чанков в `telephony:orch:replies`
- Управление barge-in (отмена текущего ответа)
- Filler-фразы при длительных CRM-операциях

### 5. Backend API (`backend/app/router_telephony/`)

REST API для телефонных операций.

**Endpoints:**
- `POST /api/internal/telephony/webhook-auth` — аутентификация вебхука
- `POST /api/internal/telephony/resolve-inbound` — маршрутизация по DID/SIP
- `POST /api/internal/telephony/resolve` — получение конфигурации агента
- `POST /api/internal/telephony/call-event` — создание/обновление записи звонка
- `POST /api/internal/telephony/turn` — preview turn shim (не для PSTN)
- `POST /api/internal/telephony/cancel` — отмена текущего turn
- `GET /api/internal/telephony/metrics` — метрики задержек

---

## Жизненный цикл входящего звонка

| Шаг | Событие | Описание |
|-----|---------|----------|
| 1 | PSTN → Voximplant | Абонент набирает номер |
| 2 | VoxEngine: CallEvents.Incoming | Сценарий принимает вызов |
| 3 | HTTP: `call.inbound` → Bridge → Backend | Регистрация звонка в БД |
| 4 | VoxEngine: answer() | Вызов принят |
| 5 | HTTP: `call.answered` → Bridge → Backend | Обновление статуса |
| 6 | WS: `session.start` → Media Gateway | Открытие медиа-сессии |
| 7 | Redis: `session.start` → Orchestrator | Инициализация диалога |
| 8 | TTS: Welcome message → абонент | Приветствие агента |
| 9 | Абонент говорит → µ-law → Media GW | Захват аудио |
| 10 | VAD + STT → `stt.final` → Redis | Распознавание речи |
| 11 | Orchestrator: LLM streaming | Генерация ответа |
| 12 | TTS streaming → Redis → Media GW → Vox | Озвучка ответа |
| 13 | (повтор шагов 9-12) | Диалоговый цикл |
| 14 | Hangup / transfer | Завершение звонка |

---

## Бюджет задержек (Latency Budget)

### End-to-Response (E2R) — от конца речи абонента до первых звуков ответа

| Этап | Описание | Целевой P90 | Типичное значение |
|------|----------|-------------|-------------------|
| **VAD silence** | Детекция конца реплики (тишина) | 450 ms | 350 ms (настройка `TURN_SILENCE_MS`) |
| **STT final wait** | Ожидание финала от STT-провайдера | — | 50 ms (`STT_FINAL_WAIT_MS`) |
| **STT processing** | Полное время STT от начала utterance | 400 ms | 200–600 ms |
| **LLM TTFT** | Time-to-first-token от LLM | 300 ms | 150–500 ms (DeepSeek/Groq) |
| **TTS TTFA** | Time-to-first-audio от TTS | 150 ms | 80–200 ms (Yandex stream) |
| **CRM execute** | Вызов внешних API (если есть) | 1000 ms | 300–2000 ms |
| **SIP overhead** | Сетевые задержки SIP/RTP | 1200 ms | — (один раз при setup) |
| **E2R total** | **Суммарная задержка** | **3000 ms** | **800–1500 ms** (QA), **1200–2500 ms** (CRM) |

### Разбивка по типу шаблона

#### QA-агент (база знаний)
```
Абонент замолчал
  → 350ms VAD silence (ожидание конца реплики)
  → 50ms STT final wait
  → ~200ms RAG-поиск в Qdrant
  → ~200ms LLM streaming first token (DeepSeek/Groq)
  → ~100ms TTS first audio frame (Yandex SpeechKit v3)
  ─────────────────────────────────────
  ≈ 900 ms до первых звуков ответа (оптимальный)
  ≈ 1200–1500 ms (типичный)
```

#### CRM-агент (function calling)
```
Абонент замолчал
  → 350ms VAD silence
  → 50ms STT final wait
  → ~500ms CRM execute (внешние API)
  → ~300ms LLM processing (с tool calls)
  → ~100ms TTS first audio frame
  ─────────────────────────────────────
  ≈ 1300 ms до первых звуков (оптимальный)
  ≈ 2000–2500 ms (типичный)
  
  * Если CRM > 500ms — воспроизводится filler: "Секунду, гляну в расписании."
```

### Filler-фразы (удержание внимания)

При превышении порога `TELEPHONY_CRM_FILLER_THRESHOLD_MS` (по умолчанию 500 ms) автоматически воспроизводится удерживающая фраза:
- CRM-запросы: *"Секунду, гляну в расписании."*
- RAG-запросы: *"Сейчас уточню по базе, минутку."*
- Общая: *"Секунду, сейчас посмотрю."*

Filler-аудио кешируется в RAM как PCM16 для мгновенного воспроизведения.

---

## Barge-in (прерывание агента)

Абонент может прервать ответ агента. Механизм:

1. **Media Gateway** отслеживает VAD-фреймы во время playback
2. **Grace period** — первые 300 ms после `agent.audio.start` barge-in игнорируется
3. **Speech frames** — минимум 2 последовательных VAD-фрейма (~40 ms речи)
4. **DTMF suppress** — 1000 ms после DTMF barge-in подавляется
5. При срабатывании:
   - Публикуется `barge_in` событие в Redis
   - Orchestrator отменяет текущий LLM/TTS stream
   - Отправляется `agent.audio.end` с reason=barge_in
   - Прерванный текст сохраняется для контекста следующего ответа

---

## Dialog State Machine

```
GREET → LISTEN → CLARIFY (если < 3 слов)
                → ACT (запись/бронь)
                → CONFIRM (дата/телефон)
                → CLOSE (прощание)
                → HANDOFF (оператор)
```

Переходы определяются regex-паттернами + intent detection. Каждое состояние модифицирует system prompt для LLM.

---

## Streaming TTS Pipeline

Текст LLM разбивается на синтагмы (по знакам препинания, минимум `TELEPHONY_SYNTAGMA_MIN_CHARS` символов) и каждая синтагма синтезируется параллельно с генерацией следующей:

```
LLM token stream
  → buffer → extract_complete_syntagmas (≥ min_chars, на , . ! ? …)
  → syntagma → TTS stream (Yandex/ElevenLabs/OpenAI fallback)
  → PCM16 frames (320 bytes = 20ms @ 8kHz mono)
  → Redis publish → Media Gateway → Voximplant → абонент
```

**Провайдеры TTS (с fallback):**
1. Yandex SpeechKit v3 (primary, streaming, ru-RU оптимизирован)
2. ElevenLabs (multilingual v2, MP3 → PCM16 resample)
3. OpenAI TTS-1 (WAV → PCM16 resample)

---

## Redis-каналы

| Канал | Направление | Содержимое |
|-------|-------------|------------|
| `telephony:orch:events` | Media GW → Orchestrator | `session.start`, `stt.final`, `barge_in`, `dtmf`, `session.end` |
| `telephony:orch:replies` | Orchestrator → Media GW | `agent.audio.start`, `agent.audio.chunk`, `agent.audio.end`, `agent.play_filler`, `call.transfer` |

---

## Аудио формат

| Параметр | Значение |
|----------|----------|
| Codec (uplink) | µ-law (PCMU) 8 kHz mono |
| Codec (downlink) | PCM16 LE 8 kHz mono |
| Frame size | 320 bytes (20 ms) |
| Voximplant WS format | JSON с base64 media или start/media/stop events |

**Критически важно:** Для воспроизведения аудио в Voximplant необходимо строго соблюдать порядок:
1. `start` event (устанавливает формат `audio/l16`, 8000 Hz, mono)
2. `media` events (base64 PCM16 данные)
3. `stop` event

Без `start` event аудио **не будет** воспроизведено абоненту.

---

## Конфигурация (ключевые env-переменные)

### Media Gateway
| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| `TURN_SILENCE_MS` | 350 | Тишина для определения конца реплики |
| `STT_FINAL_WAIT_MS` | 50 | Ожидание final от STT после utterance_end |
| `STT_PROVIDER` | yandex | STT провайдер (yandex/deepgram/mock) |
| `VAD_SPEECH_THRESHOLD` | 0.35 | Порог VAD для определения речи |
| `TELEPHONY_BARGE_IN_PLAYBACK_GRACE_MS` | 300 | Grace period barge-in после начала playback |
| `TELEPHONY_BARGE_IN_SPEECH_FRAMES` | 2 | Мин. VAD-фреймов для barge-in |
| `TELEPHONY_DOWNLINK_READY_TIMEOUT_MS` | 250 | Fallback timeout для готовности downlink |
| `TELEPHONY_MEDIA_AUDIO_FRAME_MS` | 20 | Интервал отправки фреймов (ms) |

### Backend/Orchestrator
| Переменная | Описание |
|------------|----------|
| `TELEPHONY_ENABLED` | Включение модуля телефонии |
| `TELEPHONY_STREAMING_ENABLED` | Streaming mode (обязательно для PSTN) |
| `TELEPHONY_SSML_ENABLED` | SSML-обёртка для просодии |
| `TELEPHONY_CRM_FILLER_THRESHOLD_MS` | Порог для filler-фразы (500 ms) |
| `TELEPHONY_SYNTAGMA_MIN_CHARS` | Мин. длина синтагмы для TTS |
| `TELEPHONY_STREAM_TTS_PROVIDER` | Провайдер TTS (yandex/elevenlabs/openai) |
| `TELEPHONY_TTS_TIMEOUT_SECONDS` | Таймаут TTS-синтеза (10s) |
| `TELEPHONY_VOICE_ID` | Голос по умолчанию |
| `TELEPHONY_LLM_MODE` | LLM провайдер (chat/groq) |
| `TELEPHONY_GROQ_MODEL` | Модель Groq (llama-3.1-8b-instant) |
| `TELEPHONY_DIALOG_MAX_TURNS` | Макс. реплик в истории |
| `TELEPHONY_REDIS_SESSION_TTL_SEC` | TTL Redis-сессии |
| `TELEPHONY_TURN_LATENCY_ALERT_P95_MS` | Порог алерта P95 |
| `TELEPHONY_E2R_ALERT_P90_MS` | Порог E2R алерта P90 |

### Telephony Bridge
| Переменная | Описание |
|------------|----------|
| `TELEPHONY_BRIDGE_API_KEY` | API ключ бриджа |
| `TELEPHONY_BACKEND_URL` | URL бэкенда |
| `TELEPHONY_BACKEND_INTERNAL_KEY` | Ключ для internal API |
| `TELEPHONY_BACKEND_REQUEST_TIMEOUT_MS` | Таймаут запросов (15s) |
| `TELEPHONY_BRIDGE_CONTROL_ONLY` | Только signal-события (true для streaming) |

---

## Маршрутизация входящих звонков

Поддерживается три режима маршрутизации:
1. **DID** — по вызываемому номеру (called_e164)
2. **SIP** — по SIP-заголовкам (sip_from, sip_to)
3. **DTMF IVR** — абонент вводит 4-значный добавочный номер

При `RSD_REQUIRE_EXTENSION=true` абоненту воспроизводится приглашение ввести добавочный номер, и до ввода 4 цифр основной агент не подключается.

---

## Хранение данных

| Таблица | Содержимое |
|---------|-----------|
| `agent_telephony_calls` | Записи звонков (status, duration, recording_url, metadata) |
| `agent_telephony_turns` | Реплики (role, transcript, latency_ms) |
| `agent_channel_connections` | Телефонные подключения (credentials, phone_number) |

**Redis-ключи (горячие данные):**
- `telephony:session:{connection_id}` — кеш resolve-конфига
- `telephony:call:{external_call_id}` — маппинг call_id → db_id
- `telephony:dialog:{call_id}` — состояние FSM + последние реплики
- `telephony:agent_text:{call_id}` — текущий озвучиваемый текст (для barge-in)

---

## Отказоустойчивость

- **Backend недоступен при inbound:** Bridge возвращает degraded-ответ, VoxEngine переводит на оператора
- **TTS-провайдер упал:** автоматический fallback (Yandex → ElevenLabs → OpenAI)
- **LLM timeout:** filler-фраза + retry, при повторном сбое — перевод на оператора
- **STT empty (тишина):** после 2 пустых utterances предлагается DTMF-меню
- **Stream cancelled (barge-in):** немедленная отмена LLM + TTS stream через cancel scope

---

## Метрики и мониторинг

Endpoint `GET /api/internal/telephony/metrics` возвращает:
- P50/P90/P95 для каждого этапа latency budget
- Количество звонков (started, completed, transferred)
- Prometheus-формат на `/api/internal/telephony/metrics/prometheus`

---

---

## Сборка VoxEngine-сценария

```bash
node voxengine/scripts/bundle.mjs
```

Собирает `rsd_inbound.js` + `lib/rsd_control.js` + `lib/rsd_media_gateway.js` + `lib/rsd_transfer.js` в единый файл `rsd_inbound.bundled.js` для загрузки в Voximplant Cloud IDE.

---

## Docker-сервисы

В `docker-compose.yml` телефония представлена отдельными сервисами:
- `telephony_bridge` (порт 8100)
- `telephony_media_gateway` (порт 8200)
- `telephony_orchestrator` (Redis subscriber, без порта)
- `telephony_worker` (порт 8001, выделенный FastAPI для internal API)
