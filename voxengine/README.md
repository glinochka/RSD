# VoxEngine: RSD inbound (streaming stage 2)

Сценарий `rsd_inbound.js` — Early Media (183) + приветствие + `answer` + WebSocket к `telephony_media_gateway`.

## Файлы

| Файл | Назначение |
|------|------------|
| `rsd_inbound.js` | Точка входа `AppEvents.CallAlerting` |
| `lib/rsd_control.js` | RFC-001 webhook → `telephony_bridge` |
| `lib/rsd_media_gateway.js` | WS `session.start`, μ-law, DTMF → gateway |

## Деплой в Voximplant

**Вариант A — Cloud IDE (один файл, рекомендуется):**

1. Откройте сценарий `rsd_inbound` в Voximplant.
2. Скопируйте **целиком** содержимое `rsd_inbound.bundled.js` из репозитория.
3. Сохраните. Другие файлы (`lib/*`) загружать не нужно.

**Вариант B — несколько файлов:**

1. Создайте приложение и загрузите **все** файлы (`rsd_inbound.js`, `lib/*`) в одну папку сценария.
2. Правило маршрутизации: сценарий `rsd_inbound`, маска номера.
3. **Application → Secrets** (левое меню приложения, не customData routing rule):
   - `RSD_CONNECTION_ID` — ID канала телефонии (из URL `/webhook/voximplant/47` → `47`)
   - `RSD_WEBHOOK_SECRET` — `webhook_secret` канала (RFC-001)
   - `RSD_WEBHOOK_BASE_URL` — публичный HTTPS без path, напр. `https://rsd-ai.ru`
   - `TELEPHONY_MEDIA_WS_URL` — `wss://rsd-ai.ru/ws`
   - `RSD_REQUIRE_EXTENSION` — `true` для общего номера (приветствие + DTMF)

   **Важно:** при входящем PSTN-звонке `VoxEngine.customData()` пустой. Custom data rule работает только при ручном **Start rule** / API. Для prod — только Secrets.

   **Не** используйте `require(Modules.Crypto)` / `require(Modules.WebSocket)` — в актуальном runtime Crypto и WebSocket встроены; `Modules.Crypto` даёт `empty module argument!` и сценарий завершается до звонка.
4. **script_custom_data** правила (JSON):

```json
{
  "connection_id": 42,
  "webhook_base_url": "https://telephony.example.com",
  "media_ws_url": "wss://telephony.example.com/ws",
  "greeting_url": "https://cdn.example/static/rsd_greeting.ulaw"
}
```

Опционально: `greeting_text` (если нет `greeting_url` — TTS `call.say`).

Для **общего входящего номера** (DTMF → добавочный): `"require_extension": true` — приветствие «введите 4 цифры», `call.handleTones(true)`. Набор `+7XXXXXXXXXX,1234` (пауза + 4 цифры): сценарий ~2.5 с ждёт DTMF и **пропускает** pool-приветствие, сразу отвечает и шлёт цифры в gateway.

5. На сервере: `TELEPHONY_BRIDGE_CONTROL_ONLY=true` (bridge только сигнальные события).

## Маршрутизация (этап 7)

| Режим | Настройка в кабинете | Поведение |
|-------|----------------------|-----------|
| A — DTMF | `routing_extension` (4 цифры) | Redis `telephony:route:dtmf:{ext}` → `agent_id`; gateway → orchestrator |
| B — DID | `inbound_numbers[]` или основной номер без добавочного | Redis `telephony:route:did:{e164}` → `connection_id` на `call.inbound` |
| Общий номер | Hub rule + `require_extension: true` в customData | Без DID-маршрута, ожидание DTMF |

SIP trunk (From/To → tenant) — см. [docs/telephony/ROUTING.md](../docs/telephony/ROUTING.md) §7C (`telephony_sip_routes` + `resolve-inbound`).

## Поток звонка

```
CallAlerting
  → POST call.inbound (bridge)
  → startEarlyMedia() + greeting (URL или TTS)
  → answer()
  → POST call.answered
  → WebSocket session.start + call.sendMediaTo(gateway, ULAW)
  → DTMF → WS {type:dtmf} (не HTTP)
  → hangup → POST call.hangup + session.end
```

## Barge-in (этап 6)

Пока агент говорит (`agent.audio.*`), gateway детектирует речь абонента (VAD) и шлёт:

1. Redis `barge_in` → orchestrator (отмена LLM/TTS, `interrupted_agent_text` из уже озвученного текста).
2. WS `{ "type": "barge_in", "payload": { "clear_playback": true } }` → сценарий.

В `rsd_media_gateway.js` на это событие вызывается **`webSocket.clearMediaBuffer()`** (если API доступен в вашей версии VoxEngine), чтобы оборвать исходящий буфер TTS без «договаривания».

Перебивание **не** идёт через HTTP `call.partial_transcript` / bridge — только media gateway.

## Приветствие &lt; 1.2 s

Используйте **короткий** pre-encoded `.ulaw` / `.wav` в `greeting_url` (CDN рядом с Voximplant edge РФ). TTS в Early Media медленнее.

## Проверка gateway

В логах `telephony_media_gateway` после тестового звонка:

- `session.start` с `call_id`
- `audio.in` каждые ~50 кадров с `rtf`

См. [docs/telephony/STREAMING_ARCHITECTURE.md](../docs/telephony/STREAMING_ARCHITECTURE.md).
