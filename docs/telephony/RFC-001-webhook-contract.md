# RFC-001: Контракт webhook телефонии RSD (v1)

| | |
|---|---|
| **Статус** | Принят (этап 0) |
| **Версия схемы** | `schema_version: 1` |
| **Аудитория** | `telephony_bridge`, backend (`router_telephony`), CPaaS-адаптеры |
| **Провайдер MVP** | Voximplant → нормализация в этот контракт |

## 1. Назначение

Единый формат событий между CPaaS и `telephony_bridge`. Backend **не** принимает сырой webhook CPaaS — только bridge после проверки подписи и нормализации. Bridge вызывает backend через internal API (`/internal/telephony/*`).

## 2. Endpoint

```
POST {TELEPHONY_WEBHOOK_BASE_URL}/webhook/voximplant/{connection_id}
Content-Type: application/json; charset=utf-8
```

| Параметр | Тип | Описание |
|----------|-----|----------|
| `connection_id` | integer (path) | FK → `agent_channel_connections.id` |
| Тело | JSON | Конверт события (см. §4) |

`connection_id` дублируется в теле для логов и идемпотентности; **должен совпадать** с path, иначе `400`.

## 3. Аутентификация и подпись

Секрет: `webhook_secret` из `encrypted_credentials` канала (генерируется при подключении канала на этапе 1).

### 3.1 Заголовки (обязательные)

| Заголовок | Описание |
|-----------|----------|
| `X-RSD-Telephony-Timestamp` | Unix time (секунды, UTC), строка цифр |
| `X-RSD-Telephony-Signature` | Hex HMAC-SHA256 (нижний регистр), 64 символа |

### 3.2 Строка для подписи

```
v1\n{timestamp}\n{connection_id}\n{raw_body}
```

- `raw_body` — байты тела запроса как получены (без пересборки JSON).
- `connection_id` — из path URL.
- Окно допустимого времени: **±300 с** (как `INTERNAL_REQUEST_SIGNATURE_TTL_SECONDS`).

### 3.3 Вычисление подписи

```python
import hmac, hashlib

def sign(secret: str, timestamp: str, connection_id: int, raw_body: bytes) -> str:
    msg = f"v1\n{timestamp}\n{connection_id}\n".encode() + raw_body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
```

Сравнение: `hmac.compare_digest` (constant-time).

### 3.4 Ошибки

| Код | Условие |
|-----|---------|
| `401` | Нет заголовков, неверная подпись, просрочен timestamp |
| `400` | Невалидный JSON, `connection_id` mismatch, неизвестный `event` |
| `404` | Неизвестный `connection_id` или канал отключён |
| `200` | Событие принято (в т.ч. дубликат — см. §7) |

## 4. Конверт события

Все события — один JSON-объект:

```json
{
  "schema_version": 1,
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event": "call.inbound",
  "emitted_at": "2026-05-18T10:15:30.123Z",
  "call_id": "vox-call-abc123",
  "connection_id": 42,
  "payload": {}
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `schema_version` | int | да | Всегда `1` для этой версии RFC |
| `event_id` | string (UUID) | да | Уникальный ID события у отправителя |
| `event` | string (enum) | да | См. §5 |
| `emitted_at` | string (ISO 8601) | да | Время события у CPaaS/bridge |
| `call_id` | string | да | Внешний ID звонка у CPaaS |
| `connection_id` | int | да | ID канала RSD |
| `payload` | object | да | Поля зависят от `event` |

## 5. Типы событий

### 5.1 `call.inbound`

Входящий звонок на номер агента (до или в момент answer — по политике адаптера).

```json
{
  "payload": {
    "caller_e164": "+79001234567",
    "called_e164": "+79007654321",
    "provider_session_id": "optional-native-id"
  }
}
```

**Действие bridge:** создать сессию, `POST /internal/telephony/call-event` (`status=ringing`), подготовить приветствие.

### 5.2 `call.answered`

Звонок принят (медиа доступно).

```json
{
  "payload": {
    "caller_e164": "+79001234567",
    "answered_at": "2026-05-18T10:15:31.000Z"
  }
}
```

**Действие bridge:** state → `GREETING` / `LISTENING`, начать сценарий диалога.

### 5.3 `call.recording_ready`

Доступна запись фрагмента или всего звонка.

```json
{
  "payload": {
    "recording_url": "https://...",
    "recording_duration_sec": 12,
    "leg": "user_turn",
    "turn_index": 2
  }
}
```

| `leg` | Значение |
|-------|----------|
| `user_turn` | Реплика абонента |
| `full_call` | Полная запись звонка |

**Действие bridge:** передать URL в backend при необходимости; не логировать полный URL с токеном в plain text.

### 5.4 `call.hangup`

Завершение звонка.

```json
{
  "payload": {
    "reason": "completed",
    "duration_sec": 145,
    "initiator": "caller"
  }
}
```

| `reason` | Описание |
|----------|----------|
| `completed` | Нормальное завершение |
| `busy` | Занято |
| `no_answer` | Нет ответа |
| `failed` | Ошибка сети/провайдера |
| `transferred` | Перевод на оператора |

| `initiator` | `caller` \| `agent` \| `system` |

**Действие bridge:** закрыть сессию, `call-event` → `completed` / `failed` / `transferred`.

### 5.5 `dtmf`

Нажата клавиша DTMF.

```json
{
  "payload": {
    "digit": "0",
    "duration_ms": 120
  }
}
```

**MVP:** `0` → transfer на `operator_transfer_e164`. Остальные цифры — логировать, опционально в сценарии.

## 6. Ответ bridge на webhook

Синхронный HTTP-ответ CPaaS (если провайдер ждёт команды в теле ответа):

```json
{
  "ok": true,
  "actions": [
    { "type": "answer" },
    { "type": "play_tts", "text": "Здравствуйте, чем могу помочь?" }
  ]
}
```

| `type` | Поля | Описание |
|--------|------|----------|
| `answer` | — | Принять вызов |
| `play_tts` | `text`, optional `voice_id` | Синтез речи |
| `play_url` | `url` | Воспроизвести аудио |
| `record` | `max_sec`, `silence_sec` | Запись реплики |
| `transfer` | `e164` | Перевод |
| `hangup` | optional `reason` | Завершить |

На этапе 1 допустим пустой `actions: []` при `ok: true` — сценарий полностью в VoxEngine.

## 7. Идемпотентность

Ключ дедупликации в bridge: `(connection_id, call_id, event, event_id)`.

Повторная доставка с тем же `event_id` → `200` без побочных эффектов.

Разные `event_id` при одном логическом событии — обрабатывать по бизнес-правилам (например, второй `call.hangup` игнорировать).

## 8. Маппинг Voximplant (справочно)

| Voximplant (пример) | RSD `event` |
|---------------------|-------------|
| IncomingCall / параметры сценария | `call.inbound` |
| Call connected | `call.answered` |
| Recording finished | `call.recording_ready` |
| Call disconnected | `call.hangup` |
| DTMF received | `dtmf` |

Точные имена callback задаются в VoxEngine; адаптер `providers/voximplant.ts` (этап 1) обязан выдавать только конверт §4.

## 9. Безопасность (минимум этап 0)

- HTTPS только на публичном ingress.
- Не логировать `webhook_secret`, `api_key`, полные `recording_url` с query-токенами.
- Rate limit по `connection_id` + IP (этап 4).

## 10. Эволюция

- `schema_version: 2` — streaming partial STT (`call.partial_transcript`), barge-in — отдельный RFC.
- Обратная совместимость: bridge принимает v1, пока все каналы не мигрированы.
