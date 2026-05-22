# Переменные окружения: телефония

Шаблон для копирования: [.env.telephony.example](../../.env.telephony.example).

## Общие секреты

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `INTERNAL_API_KEY` | да | Fallback для internal API |
| `INTERNAL_REQUEST_SIGNING_SECRET` | рекомендуется | HMAC bridge/worker → backend; в bridge дублируется как `TELEPHONY_BACKEND_SIGNING_SECRET` |
| `TELEPHONY_INTERNAL_API_KEY` | при enabled | Ключ bridge → backend; если пусто — `INTERNAL_API_KEY` |
| `TELEPHONY_BRIDGE_API_KEY` | да (bridge) | Защита bridge |

## Backend (FastAPI + telephony_worker)

| Переменная | Обязательно | По умолчанию | Описание |
|------------|-------------|--------------|----------|
| `TELEPHONY_ENABLED` | нет | `false` | Internal API телефонии |
| `TELEPHONY_WEBHOOK_BASE_URL` | при подключении канала | — | Публичный HTTPS bridge без path (URL в UI) |
| `TELEPHONY_MAX_TURN_SECONDS` | нет | `30` | Макс. длина записи реплики |
| `TELEPHONY_MAX_CALL_MINUTES` | нет | `15` | Макс. длительность звонка |
| `TELEPHONY_MAX_TURNS` | нет | `15` | Макс. ходов диалога |
| `TELEPHONY_TTS_PROVIDER` | нет | `voximplant` | Боевой звонок: Voximplant; тест в браузере: `yandex`/`openai` или fallback на них при `voximplant` |
| `YANDEX_SPEECHKIT_API_KEY` | при yandex / preview | — | Yandex SpeechKit для `/telephony/preview/speak` |
| `TELEPHONY_TTS_TIMEOUT_SECONDS` | нет | `20` | Таймаут синтеза речи для preview |
| `TELEPHONY_WEBHOOK_SIGNATURE_TTL_SECONDS` | нет | `300` | Окно timestamp webhook |
| `TELEPHONY_WEBHOOK_RATE_LIMIT_PER_CONNECTION` | нет | `120` | Rate limit / connection / окно |
| `TELEPHONY_WEBHOOK_RATE_LIMIT_PER_IP` | нет | `240` | Rate limit / IP / окно |
| `TELEPHONY_WEBHOOK_RATE_WINDOW_SECONDS` | нет | `60` | Окно rate limit (сек) |
| `TELEPHONY_TURNS_RETENTION_DAYS` | нет | `90` | Retention `agent_telephony_turns` |
| `TELEPHONY_LLM_TIMEOUT_SECONDS` | нет | `25` | Таймаут LLM на ход (crm_admin + Qdrant) |
| `TELEPHONY_LLM_RETRY_TIMEOUT_SECONDS` | нет | `15` | Повтор после таймаута |
| `TELEPHONY_PREVIEW_LLM_TIMEOUT_SECONDS` | нет | `60` | Таймаут LLM для теста в браузере |
| `TELEPHONY_TURN_LATENCY_ALERT_P95_MS` | нет | `10000` | Алерт в `/metrics` |
| `TELEPHONY_STREAMING_ENABLED` | нет | `true` | Разбивка ответа на предложения для раннего TTS (runtime — всегда `template_runtime`) |
| `TELEPHONY_ENDPOINT_SILENCE_MS` | нет | `600` | Endpointing (bridge) |
| `TELEPHONY_CRM_FILLER_THRESHOLD_MS` | нет | `1500` | Filler при долгих CRM-tools |
| `TELEPHONY_DEDICATED_POOL_ENABLED` | нет | `true` | Отдельный pool для turn |
| `TELEPHONY_DEDICATED_POOL_SIZE` | нет | `8` | Размер pool |
| `TELEPHONY_WORKER_PORT` | нет | `8001` | Порт telephony_worker |
| `TELEPHONY_SSML_ENABLED` | нет | `true` | SSML/просодия в ответе |
| `TELEPHONY_BARGE_IN_ENABLED` | нет | `true` | Используется bridge |
| `TELEPHONY_BACKCHANNEL_MIN_MS` | нет | `5000` | Используется bridge |
| `REDIS_URL` | при redis sessions | — | Redis |
| `VOXIMPLANT_API_BASE_URL` | нет | Voximplant API | Валидация канала |
| `TELEPHONY_VOXIMPLANT_API_TIMEOUT_SECONDS` | нет | `15` | Таймаут Voximplant API |
| `VOICE_STT_BACKEND` | нет | `auto` | STT для turn |
| `OPENAI_API_KEY` | при openai STT | — | STT fallback |
| `DEEPSEEK_API_KEY` | да | — | LLM (template_runtime) |
| `ENCRYPTION_KEY` | да | — | Шифрование credentials канала |

## telephony_bridge

| Переменная | Обязательно | По умолчанию | Описание |
|------------|-------------|--------------|----------|
| `TELEPHONY_BRIDGE_API_KEY` | да | — | Защита bridge |
| `TELEPHONY_BACKEND_URL` | да | — | Docker: `http://telephony_worker:8001` |
| `TELEPHONY_BACKEND_INTERNAL_KEY` | да | — | Обычно = `TELEPHONY_INTERNAL_API_KEY` |
| `TELEPHONY_BACKEND_SIGNING_SECRET` | рекомендуется | — | Обычно = `INTERNAL_REQUEST_SIGNING_SECRET` |
| `TELEPHONY_SESSION_STORE` | нет | `memory` | `memory` \| `redis` |
| `REDIS_URL` | при redis | — | Сессии звонков |
| `PORT` | нет | `8100` | HTTP-порт |
| `TELEPHONY_RECORD_SILENCE_SEC` | нет | `0` | Тишина для `record` (0 = из `TELEPHONY_ENDPOINT_SILENCE_MS`) |
| `TELEPHONY_BACKEND_REQUEST_TIMEOUT_MS` | нет | `15000` | Таймаут fetch к backend |
| `TELEPHONY_MAX_TURNS` | нет | `15` | Лимит ходов в bridge |
| `TELEPHONY_MAX_CALL_MINUTES` | нет | `15` | Лимит длительности |
| `TELEPHONY_MAX_TURN_SECONDS` | нет | `30` | Макс. запись реплики |
| `TELEPHONY_STREAMING_ENABLED` | нет | `true` | Partial / ранний TTS |
| `TELEPHONY_ENDPOINT_SILENCE_MS` | нет | `600` | Endpointing |
| `TELEPHONY_CRM_FILLER_THRESHOLD_MS` | нет | `1500` | Порог filler |
| `TELEPHONY_BARGE_IN_ENABLED` | нет | `true` | Перебивание |
| `TELEPHONY_BACKCHANNEL_MIN_MS` | нет | `5000` | Backchannel |
| `TELEPHONY_SSML_ENABLED` | нет | `true` | SSML в TTS |
| `TELEPHONY_WEBHOOK_SIGNATURE_TTL_SECONDS` | нет | `300` | HMAC webhook |
| `TELEPHONY_WEBHOOK_RATE_LIMIT_*` | нет | см. backend | Rate limit |
| `TELEPHONY_TURN_LATENCY_ALERT_P95_MS` | нет | `10000` | Метрики bridge |

## Docker Compose

См. `docker-compose.yml`: сервисы `backend`, `telephony_worker`, `telephony_bridge`, `redis`.

## Генерация секретов

```bash
openssl rand -hex 32
```
