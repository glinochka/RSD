# Формат медиа WebSocket Voximplant (Критически важно)

> ⚠️ **ВНИМАНИЕ**: Этот документ описывает критически важный формат передачи медиа через WebSocket в Voximplant.
> Нарушение порядка событий или формата приведет к тому, что звук агента не будет слышен абоненту!
> Поддержка Voximplant: https://voximplant.com/docs/guides/media-streams/websocket

## TL;DR — рабочий формат downlink-аудио (агент → абонент)

| Параметр | Значение |
|----------|----------|
| `mediaFormat.encoding` | `audio/l16` (PCM16) |
| Разрядность | 16-bit signed |
| Порядок байт (endianness) | **little-endian (LE), отправляется КАК ЕСТЬ** |
| Частота дискретизации | 8000 Hz |
| Каналы | 1 (mono) |
| Размер кадра | 320 байт (20 мс @ 8 кГц PCM16) |

Оркестратор (Python) отдаёт PCM16 LE в `audio_pcm16_b64`. Gateway передаёт эти байты
в `media.payload` **без конверсии endianness**. Управляется через `AUDIO_FORMAT=l16`
(значение по умолчанию).

## История исправления

### 1. Звук не воспроизводился вообще

**Причина**: медиа передавалось в неверном формате — сообщения обрабатывались как обычный
JavaScript, вместо определения их как медиа-сообщений Voximplant.

**Решение**: строгое следование протоколу `start → media → stop` с корректным `mediaFormat`.

### 2. Шум и треск вместо речи (endianness / кодек)

**Симптом**: вместо речи слышен шум/треск. Проявлялось на всех TTS-провайдерах (Yandex, ElevenLabs).

**Ключевая улика в логах**: `WebSocket.MediaEventStarted ; encoding = PCM16` — Voximplant
интерпретирует payload WebSocket-медиа как **PCM16 little-endian**, независимо от того, что
объявлено в `mediaFormat.encoding`.

**Две независимые причины шума (обе были последовательно внесены и исправлены):**

1. **`AUDIO_FORMAT=mulaw`** (коммит `99580a8`). Объявление `audio/x-mulaw` в `mediaFormat`
   НЕ заставляет Voximplant декодировать payload как μ-law — он всё равно читает его как PCM16.
   В результате μ-law-байты проигрываются как PCM16 → шум.
2. **Конверсия PCM16 LE → BE** (коммит `4aba41a`, по мотивам RFC 3551 «L16 = big-endian»).
   Voximplant WebSocket media ожидает **little-endian**, поэтому перестановка байт LE→BE
   также даёт шум.

**Решение**: отправлять PCM16 **little-endian как есть** (`AUDIO_FORMAT=l16`, без конверсии
endianness). Это восстанавливает разборчивую речь.

> ⚠️ RFC 3551 определяет `L16` как big-endian, но Voximplant в этом WebSocket-протоколе
> ожидает little-endian. Не доверяйте RFC здесь — ориентируйтесь на поведение Voximplant.

## Порядок событий (строго обязателен)

### 1. Сначала ОБЯЗАТЕЛЬНО событие `start`

Перед передачей любых медиа-данных необходимо отправить событие `start` с описанием формата:

```json
{
  "event": "start",
  "sequenceNumber": 0,
  "start": {
    "mediaFormat": {
      "encoding": "audio/l16",
      "sampleRate": 8000,
      "channels": 1
    }
  }
}
```

| Поле | Описание | Примечание |
|------|----------|------------|
| `event` | Тип события | Должно быть строго `"start"` |
| `sequenceNumber` | Счетчик сообщений | Начинается с 0 |
| `start.mediaFormat.encoding` | Кодек | **`audio/l16`** (PCM16) — рабочее значение. `audio/x-mulaw` НЕ работает: payload всё равно читается как PCM16 |
| `start.mediaFormat.sampleRate` | Частота дискретизации | 8000 Hz для телефонии |
| `start.mediaFormat.channels` | Количество каналов | 1 (mono) |

> ⚠️ `media.payload` всегда трактуется Voximplant как **PCM16 little-endian**. Передавайте
> PCM16 LE как есть (без перестановки байт и без μ-law-кодирования).

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
{ "event": "start", "start": { "mediaFormat": { "encoding": "audio/l16" } } }
```

### 5. μ-law payload или конверсия LE → BE (шум вместо речи)

❌ Неправильно — payload в μ-law (Voximplant читает его как PCM16 → шум):
```text
AUDIO_FORMAT=mulaw  # pcm16LeToMulaw(payload)
```

❌ Неправильно — перестановка байт LE → BE (Voximplant ждёт little-endian → шум):
```text
FORCE_ENDIAN_BE=true  # pcm16LeToBe(payload)
```

✅ Правильно — PCM16 little-endian как есть:
```text
AUDIO_FORMAT=l16   # (по умолчанию), без конверсии endianness
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
