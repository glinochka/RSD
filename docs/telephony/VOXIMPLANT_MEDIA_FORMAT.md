# Формат медиа WebSocket Voximplant (Критически важно)

> ⚠️ **ВНИМАНИЕ**: Этот документ описывает критически важный формат передачи медиа через WebSocket в Voximplant.
> Нарушение порядка событий или формата приведет к тому, что звук агента не будет слышен абоненту!
> Поддержка Voximplant: https://voximplant.com/docs/guides/media-streams/websocket

## История исправления

**Проблема**: Ранее звук агента не воспроизводился абоненту после подключения WebSocket.

**Причина**: Медиа передавалось в неверном формате — сообщения обрабатывались как обычный JavaScript,
вместо определения их как медиа-сообщений Voximplant.

**Решение**: Строгое следование документации Voximplant для WebSocket media streaming.

## Порядок событий (строго обязателен)

### 1. Сначала ОБЯЗАТЕЛЬНО событие `start`

Перед передачей любых медиа-данных необходимо отправить событие `start` с описанием формата:

```json
{
  "event": "start",
  "sequenceNumber": 0,
  "start": {
    "mediaFormat": {
      "encoding": "audio/x-mulaw",
      "sampleRate": 8000,
      "channels": 1
    },
    "customParameters": {
      "text1": "12312"
    }
  }
}
```

| Поле | Описание | Примечание |
|------|----------|------------|
| `event` | Тип события | Должно быть строго `"start"` |
| `sequenceNumber` | Счетчик сообщений | Начинается с 0 |
| `start.mediaFormat.encoding` | Кодек | `audio/x-mulaw` для μ-law или `audio/l16` для PCM16 |
| `start.mediaFormat.sampleRate` | Частота дискретизации | 8000 Hz для телефонии |
| `start.mediaFormat.channels` | Количество каналов | 1 (mono) |

### 2. Затем события `media`

После успешного `start` можно передавать медиа-чанки:

```json
{
  "event": "media",
  "sequenceNumber": 2,
  "media": {
    "chunk": 1,
    "timestamp": 5,
    "payload": "no+JhoaJjpzSHxAKBgYJ...=="
  }
}
```

| Поле | Описание | Примечание |
|------|----------|------------|
| `event` | Тип события | Должно быть строго `"media"` |
| `sequenceNumber` | Счетчик сообщений | Инкрементируется для каждого сообщения |
| `media.chunk` | Номер чанка | Начинается с 1 |
| `media.timestamp` | Временная метка | Можно использовать Date.now() или счетчик |
| `media.payload` | Аудио-данные | Base64-кодированные аудио-чанки |

### 3. В конце событие `stop`

При завершении передачи:

```json
{
  "event": "stop",
  "sequenceNumber": N
}
```

## Реализация в проекте

### Серверная часть (telephony_media_gateway)

Файлы, отвечающие за формирование сообщений:

- `telephony_media_gateway/src/ws/vox_media.ts` — формирование JSON-сообщений
- `telephony_media_gateway/src/orch/agent_playback.ts` — отправка аудио агента

Ключевые функции:

```typescript
// Начало передачи аудио — ОБЯЗАТЕЛЬНО сначала вызвать!
buildVoxStartMessage(ws)

// Передача аудио-чанка
buildVoxMediaMessage(payload, ws)

// Завершение передачи
buildVoxStopMessage(ws)
```

### VoxEngine (JavaScript-сценарий)

Файл: `voxengine/lib/rsd_media_gateway.js`

Важные моменты:
- Gateway принимает native Vox JSON media (`call.sendMediaTo`)
- Обрабатывает события `start`, `media`, `stop`
- При событии `start` выполняет `bindDownlinkMedia()` для привязки WebSocket к звонку

## Частые ошибки (НЕ ДЕЛАЙТЕ!)

### 1. Отправка `media` без предварительного `start`

❌ Неправильно:
```json
{ "event": "media", "media": { "payload": "..." } }
```

✅ Правильно:
```json
{ "event": "start", "sequenceNumber": 0, "start": { "mediaFormat": {...} } }
{ "event": "media", "sequenceNumber": 1, "media": { "chunk": 1, "timestamp": 0, "payload": "..." } }
```

### 2. Отправка медиа в неправильном формате

❌ Неправильно:
```json
{ "type": "audio", "data": "..." }
```

✅ Правильно:
```json
{ "event": "media", "sequenceNumber": 1, "media": { "chunk": 1, "timestamp": 0, "payload": "..." } }
```

### 3. Неправильный порядок sequenceNumber

❌ Неправильно:
```json
{ "event": "start", "sequenceNumber": 5, ... }
{ "event": "media", "sequenceNumber": 2, ... }
```

✅ Правильно:
```json
{ "event": "start", "sequenceNumber": 0, ... }
{ "event": "media", "sequenceNumber": 1, ... }
{ "event": "media", "sequenceNumber": 2, ... }
```

### 4. Неправильный кодек в mediaFormat

❌ Неправильно:
```json
{ "event": "start", "start": { "mediaFormat": { "encoding": "audio/mp3" } } }
```

✅ Правильно:
```json
{ "event": "start", "start": { "mediaFormat": { "encoding": "audio/x-mulaw" } } }
```

## Проверка вручную

Для тестирования можно использовать `wscat`:

```bash
# Установка
npm install -g wscat

# Подключение к gateway
wscat -c wss://your-server/ws

# Отправка start
> {"type":"session.start","payload":{"call_id":"test-123","connection_id":1,"caller_e164":"+79001234567","codec":"pcmu"}}

# Ответ gateway будет содержать confirmation
```

## Ссылки

- Официальная документация Voximplant: https://voximplant.com/docs/guides/media-streams/websocket
- Файл протокола: [SESSION_PROTOCOL.md](./SESSION_PROTOCOL.md)
- Архитектура потоковой передачи: [STREAMING_ARCHITECTURE.md](./STREAMING_ARCHITECTURE.md)

## Контакты поддержки

При проблемах со звуком в звонках:
1. Проверьте порядок событий в логах
2. Убедитесь, что `start` событие отправляется перед `media`
3. Проверьте формат JSON-сообщений
4. Обратитесь в поддержку Voximplant с логами WebSocket
