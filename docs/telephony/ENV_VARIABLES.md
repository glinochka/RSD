# Переменные окружения: телефония

Шаблон для копирования в корневой `.env`: [.env.telephony.example](../../.env.telephony.example).

## Архитектура (после рефакторинга)

| Контур | Сервис | Роль |
|--------|--------|------|
| Сигнал | `telephony_bridge` | `call.inbound` / `call.answered` / `call.hangup` |
| Media | `telephony_media_gateway` | WS μ-law, VAD, streaming STT, barge-in |
| Dialog | `telephony_orchestrator` | LLM stream, синтагмы, stream TTS |
| Control | `backend` + `telephony_worker` | Credentials, resolve, preview `/turn`, метрики |
| Hot state | Redis | Session, dialog, `telephony:route:*`, pub/sub |

PSTN **не** использует HTTP `/internal/telephony/turn` (ответ `410`). Preview в браузере — `caller_e164` с префиксом `preview:`.

---

## Общие секреты

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `INTERNAL_API_KEY` | да | Fallback internal API |
| `INTERNAL_REQUEST_SIGNING_SECRET` | рекомендуется | HMAC bridge/worker → backend |
| `TELEPHONY_INTERNAL_API_KEY` | при `TELEPHONY_ENABLED` | Ключ bridge → backend; если пусто — `INTERNAL_API_KEY` |
| `TELEPHONY_BRIDGE_API_KEY` | да (bridge) | Защита HTTP bridge |
| `ENCRYPTION_KEY` | да | Шифрование credentials канала |

```bash
openssl rand -hex 32
```

---

## Platform pool (один номер Voximplant)

Задаются **только в `.env`**, не в UI агента. См. [EXTERNAL_SERVICES.md](./EXTERNAL_SERVICES.md).

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TELEPHONY_SHARED_POOL_E164` | — | Общий входящий DID (E.164) |
| `TELEPHONY_VOXIMPLANT_ACCOUNT_ID` | — | Account ID (Settings → API) |
| `TELEPHONY_VOXIMPLANT_API_KEY` | — | API Key Voximplant |
| `TELEPHONY_VOXIMPLANT_APPLICATION_ID` | — | Application ID сценария |
| `TELEPHONY_VOXIMPLANT_RULE_ID` | — | ID правила входящих |
| `TELEPHONY_OPERATOR_TRANSFER_E164` | — | Номер перевода на живого оператора |

Агент в UI: только `routing_extension` (4 цифры). API: `GET /api/agents/channels/telephony/platform`.

---

## Backend + telephony_worker + telephony_orchestrator

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TELEPHONY_ENABLED` | `false` | Internal API телефонии; orchestrator не стартует без `true` |
| `TELEPHONY_ORCHESTRATOR_ENABLED` | `true` | Процесс `python -m app.telephony.orchestrator_main` |
| `TELEPHONY_STREAMING_ENABLED` | `true` | Потоковый LLM + TTS (PSTN); при `false` orchestrator выходит |
| `TELEPHONY_WEBHOOK_BASE_URL` | — | Публичный HTTPS bridge **без path** (UI + VoxEngine) |
| `TELEPHONY_MAX_TURN_SECONDS` | `30` | Лимит реплики (preview / метаданные) |
| `TELEPHONY_MAX_CALL_MINUTES` | `15` | Лимит звонка |
| `TELEPHONY_MAX_TURNS` | `15` | Макс. ходов диалога |
| `TELEPHONY_TURNS_RETENTION_DAYS` | `90` | Retention `agent_telephony_turns` |
| `TELEPHONY_WEBHOOK_SIGNATURE_TTL_SECONDS` | `300` | Окно HMAC webhook |
| `TELEPHONY_WEBHOOK_RATE_LIMIT_PER_CONNECTION` | `120` | Rate limit / connection |
| `TELEPHONY_WEBHOOK_RATE_LIMIT_PER_IP` | `240` | Rate limit / IP |
| `TELEPHONY_WEBHOOK_RATE_WINDOW_SECONDS` | `60` | Окно rate limit |
| `DEEPSEEK_API_KEY` | — | LLM при `TELEPHONY_LLM_MODE=chat` |
| `TELEPHONY_LLM_MODE` | `chat` | `chat` \| `groq` |
| `TELEPHONY_GROQ_MODEL` | `llama-3.1-8b-instant` | Модель Groq |
| `GROQ_API_KEY` | при groq | Groq API |
| `TELEPHONY_LLM_TIMEOUT_SECONDS` | `8` | Таймаут LLM на ход (тестовый профиль) |
| `TELEPHONY_LLM_RETRY_TIMEOUT_SECONDS` | `5` | Повтор после таймаута |
| `TELEPHONY_PREVIEW_LLM_TIMEOUT_SECONDS` | `8` | LLM для preview в браузере |
| `TELEPHONY_SYNTAGMA_MIN_CHARS` | `12` | Мин. длина синтагмы при нарезке |
| `TELEPHONY_CRM_FILLER_THRESHOLD_MS` | `1500` | `play_filler` при долгих CRM-tools |
| `TELEPHONY_SSML_ENABLED` | `true` | SSML в ответе |
| `TELEPHONY_STREAM_TTS_PROVIDER` | `yandex` | PSTN stream TTS: `yandex` \| `elevenlabs` \| `openai` |
| `TELEPHONY_VOICE_ID` | `default` | Голос TTS: `alice` (ElevenLabs), `alena:rc` (Yandex RC), `filipp` |
| `YANDEX_SPEECHKIT_API_KEY` | при yandex | STT (gateway) + stream TTS + preview |
| `YANDEX_SPEECHKIT_FOLDER_ID` | рекомендуется | Каталог Yandex Cloud |
| `ELEVENLABS_API_KEY` | при elevenlabs | ElevenLabs Flash stream |
| `TELEPHONY_TTS_PROVIDER` | `voximplant` | **Только preview** в браузере: `yandex` \| `openai` \| `voximplant` |
| `TELEPHONY_TTS_TIMEOUT_SECONDS` | `10` | Таймаут TTS (preview + stream TTS) |
| `OPENAI_API_KEY` | при openai preview | Preview TTS/STT |
| `VOICE_STT_BACKEND` | `auto` | Batch STT для preview `/turn` |
| `REDIS_URL` | — | Обязателен для orchestrator + bridge sessions |
| `TELEPHONY_REDIS_SESSION_TTL_SEC` | `7200` | TTL session/dialog keys |
| `TELEPHONY_DIALOG_MAX_TURNS` | `16` | Длина `telephony:dialog:{call_id}` |
| `TELEPHONY_DEDICATED_POOL_ENABLED` | `true` | Pool telephony_worker |
| `TELEPHONY_DEDICATED_POOL_SIZE` | `8` | Размер pool |
| `TELEPHONY_WORKER_PORT` | `8001` | Порт worker |
| `TELEPHONY_TURN_LATENCY_ALERT_P95_MS` | `3000` | Алерт turn latency |
| `TELEPHONY_E2R_ALERT_P90_MS` | `3000` | Алерт p90 E2R |
| `VOXIMPLANT_API_BASE_URL` | Voximplant API | Валидация канала в UI |
| `TELEPHONY_VOXIMPLANT_API_TIMEOUT_SECONDS` | `15` | Таймаут Voximplant API |
| `QDRANT_URL` | — | KB для LLM (worker/orchestrator) |

Redis-ключи маршрутизации: `telephony:route:dtmf:{ext}`, `telephony:route:did:{e164}` — см. [ROUTING.md](./ROUTING.md).

---

## telephony_bridge (control-only)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TELEPHONY_BRIDGE_API_KEY` | — | Обязательно |
| `TELEPHONY_BACKEND_URL` | — | Docker: `http://telephony_worker:8001` |
| `TELEPHONY_BACKEND_INTERNAL_KEY` | — | = `TELEPHONY_INTERNAL_API_KEY` |
| `TELEPHONY_BACKEND_SIGNING_SECRET` | — | = `INTERNAL_REQUEST_SIGNING_SECRET` |
| `TELEPHONY_SESSION_STORE` | `memory` | `redis` рекомендуется в prod |
| `REDIS_URL` | при redis | Сессии dedup webhook |
| `TELEPHONY_BACKEND_REQUEST_TIMEOUT_MS` | `15000` | Таймаут к backend |
| `TELEPHONY_BRIDGE_CONTROL_ONLY` | `true` | `false` — устаревший dual-path |
| `TELEPHONY_WEBHOOK_SIGNATURE_TTL_SECONDS` | `300` | HMAC |
| `TELEPHONY_WEBHOOK_RATE_LIMIT_*` | см. backend | Rate limit |
| `PORT` | `8100` | HTTP |

События `call.recording_ready`, `call.partial_transcript`, `dtmf` (HTTP) → **410**.

---

## telephony_media_gateway

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PORT` | `8200` | HTTP + WebSocket |
| `NODE_ENV` | `development` | `production` запрещает `STT_PROVIDER=mock` |
| `TELEPHONY_MEDIA_WS_URL` | — | Публичный `wss://…/ws` для VoxEngine |
| `TELEPHONY_MEDIA_WS_PATH` | `/ws` | Путь WS |
| `TELEPHONY_MEDIA_AUDIO_FRAME_MS` | `20` | Кадр μ-law (мс) |
| `TELEPHONY_MEDIA_LOG_LEVEL` | `info` | `info` \| `silent` |
| `TELEPHONY_MEDIA_MAX_CONTROL_BYTES` | `65536` | Лимит JSON control |
| `TELEPHONY_MEDIA_LOOPBACK_TRANSPORT` | `vox` | `vox` \| `binary` \| `both` |
| `TELEPHONY_MEDIA_LOOPBACK_MODE` | `echo` | `echo` \| `silence` |
| `TELEPHONY_MEDIA_PIPELINE_ENABLED` | `true` | `false` — только loopback |
| `STT_PROVIDER` | `yandex` | `yandex` \| `deepgram` \| `mock` (dev) |
| `TURN_SILENCE_MS` | `400` | Тишина → `stt.final` |
| `STT_FINAL_WAIT_MS` | `80` | Ожидание final STT после VAD EOU |
| `STT_PARTIAL_LOG_EVERY` | `5` | Частота логов partial |
| `VAD_MODEL_PATH` | `./models/silero_vad.onnx` | Silero ONNX; иначе energy VAD |
| `VAD_SPEECH_THRESHOLD` | `0.5` | Порог Silero |
| `VAD_ENERGY_THRESHOLD` | `0.02` | Energy fallback |
| `YANDEX_SPEECHKIT_API_KEY` | при yandex | gRPC STT |
| `YANDEX_SPEECHKIT_FOLDER_ID` | рекомендуется | |
| `DEEPGRAM_API_KEY` | при deepgram | |
| `TELEPHONY_STT_LANGUAGE` | `ru-RU` | |
| `REDIS_URL` | — | Pub/sub orchestrator |
| `TELEPHONY_ORCH_EVENTS_ENABLED` | `true` | Публикация событий |
| `TELEPHONY_ORCH_EVENTS_CHANNEL` | `telephony:orch:events` | gateway → orchestrator |
| `TELEPHONY_ORCH_REPLIES_CHANNEL` | `telephony:orch:replies` | orchestrator → gateway |
| `TELEPHONY_BARGE_IN_ENABLED` | `true` | VAD во время `agent.audio.*` |
| `TELEPHONY_BARGE_IN_SPEECH_FRAMES` | `2` | Кадров речи до `barge_in` |

Модель VAD: `cd telephony_media_gateway && npm run download:vad`.

---

## Voximplant (secrets приложения)

| Secret | Описание |
|--------|----------|
| `RSD_WEBHOOK_SECRET` | = `webhook_secret` канала |
| `RSD_WEBHOOK_BASE_URL` | = `TELEPHONY_WEBHOOK_BASE_URL` |
| `TELEPHONY_MEDIA_WS_URL` | = публичный `wss://…/ws` |

Сценарий: [voxengine/README.md](../../voxengine/README.md). Протокол: [SESSION_PROTOCOL.md](./SESSION_PROTOCOL.md).

---

## Docker Compose

```bash
docker compose up -d redis backend telephony_worker telephony_bridge \
  telephony_orchestrator telephony_media_gateway
```

Сервисы: `docker-compose.yml` — `telephony_bridge`, `telephony_media_gateway`, `telephony_orchestrator`, `telephony_worker`.

---

## Удалено / не используется

| Переменная | Причина |
|------------|---------|
| `TELEPHONY_RECORD_SILENCE_SEC` | Legacy `record` → `/turn` |
| `TELEPHONY_ENDPOINT_SILENCE_MS` в bridge | Endpointing в gateway (`TURN_SILENCE_MS`) |
| `TELEPHONY_LLM_MODE=realtime` | Не реализовано; только `chat` \| `groq` |
| HTTP `call.partial_transcript` | Partial только через gateway |
