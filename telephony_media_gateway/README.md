# telephony_media_gateway

Media plane для потоковой телефонии RSD: WebSocket μ-law, VAD, streaming STT, turn-taking (этап 3+).

> ⚠️ **Важно**: Формат медиа-сообщений Voximplant критически важен для работы звука!
> Подробности: [VOXIMPLANT_MEDIA_FORMAT.md](../docs/telephony/VOXIMPLANT_MEDIA_FORMAT.md)

## Этап 3 (VAD + streaming STT)

- **Silero VAD** (ONNX Runtime, 8 kHz, окна 256 samples) или energy fallback
- Пока VAD=speech → streaming STT: **Yandex SpeechKit v3** gRPC `REAL_TIME` или **Deepgram** (`STT_PROVIDER`)
- События `stt.partial` / `stt.final` на WebSocket (orchestrator подключится на этапе 4)
- Turn-taking: тишина ≥ `TURN_SILENCE_MS` (default 400 ms) → `stt.final`
- Метрики в логах и в payload final: `stt_partial_ms`, `stt_final_ms`, `vad_speech_ratio`

## Этап 6 (barge-in)

- Пока активен `agent.audio.*`, VAD на входящем μ-law → `barge_in` в orchestrator + WS `clear_playback` для VoxEngine
- `TELEPHONY_BARGE_IN_ENABLED` (default `true`), `TELEPHONY_BARGE_IN_SPEECH_FRAMES` (default `2` ≈ 40 ms @ 20 ms/frame)

## Запуск

```bash
cd telephony_media_gateway
npm install
npm run download:vad   # опционально; без модели — energy VAD
STT_PROVIDER=mock npm start
```

Smoke-тест пайплайна (без ключей):

```bash
npm run test:pipeline
```

Docker Compose: сервис `telephony_media_gateway` (порт `8200`).

## Переменные

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `PORT` | `8200` | HTTP + WS |
| `TELEPHONY_MEDIA_WS_PATH` | `/ws` | Путь WebSocket |
| `TELEPHONY_MEDIA_PIPELINE_ENABLED` | `true` | Включить VAD/STT (не loopback) |
| `STT_PROVIDER` | `yandex` | `yandex` \| `deepgram` \| `mock` |
| `TURN_SILENCE_MS` | `400` | Endpointing (мс) |
| `VAD_MODEL_PATH` | `./models/silero_vad.onnx` | Silero ONNX |
| `YANDEX_SPEECHKIT_API_KEY` | — | Yandex STT (Api-Key) |
| `YANDEX_SPEECHKIT_FOLDER_ID` | — | Folder ID (опционально) |
| `DEEPGRAM_API_KEY` | — | Deepgram streaming |

Полный список: [ENV_VARIABLES.md](../docs/telephony/ENV_VARIABLES.md).

## Связанные документы

- [STREAMING_ARCHITECTURE.md](../docs/telephony/STREAMING_ARCHITECTURE.md)
- [SESSION_PROTOCOL.md](../docs/telephony/SESSION_PROTOCOL.md)
- [TELEPHONY_STREAMING_REFACTOR.md](../TELEPHONY_STREAMING_REFACTOR.md)
