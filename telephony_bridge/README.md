# telephony_bridge

Control-only HTTP webhook: Voximplant → internal backend (`call.inbound`, `call.answered`, `call.hangup`).

Media, STT, TTS и DTMF — через `telephony_media_gateway` + orchestrator ([STREAMING_ARCHITECTURE.md](../docs/telephony/STREAMING_ARCHITECTURE.md)).

Legacy `record` → `/internal/telephony/turn` **удалён** (ответ `410` на `call.recording_ready` / `call.partial_transcript`).

## Запуск

```bash
cd telephony_bridge
npm install
PORT=8100 npm start
```

Docker: сервис `telephony_bridge` (:8100), `TELEPHONY_BRIDGE_CONTROL_ONLY=true` по умолчанию.

## Документация

- [docs/telephony/README.md](../docs/telephony/README.md)
- [voxengine/README.md](../voxengine/README.md)
