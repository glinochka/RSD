# Руководство по миграции на упрощенную телефонию

## Проблема

Существующая архитектура не позволяет слышать ответы ИИ-агента:
- Сообщение "Введите добавочный номер" слышно (использует `call.say()` Voximplant)
- Приветствие агента и ответы LLM не слышны (сложная цепочка streaming TTS → WebSocket)

## Причина проблемы

Сложная архитектура с 4 слоями:
1. VoxEngine → WebSocket → Media Gateway (Node.js)
2. Media Gateway → Redis pub/sub
3. Orchestrator (Python) → streaming TTS (gRPC)
4. Audio chunks → Redis → Media Gateway → WebSocket → VoxEngine

Множество точек отказа:
- Redis pub/sub может не работать
- WebSocket сессии могут не регистрироваться
- TTS поток может не генерировать аудио
- Формат аудио (PCM16 → μ-law) может быть некорректным

## Решение: Упрощенная архитектура

### Новая схема

```
PSTN → VoxEngine (rsd_simplified.js)
    ↓ HTTP webhook
Backend (/api/internal/telephony/simplified/*)
    ↓ JSON response
VoxEngine → call.say() / call.startASR()
```

**Ключевые изменения:**
1. **TTS** → `call.say()` встроенный в Voximplant
2. **ASR** → `call.startASR()` встроенный в Voximplant
3. **Нет Media Gateway** → WebSocket для аудио не нужен
4. **Нет streaming** → простой HTTP request/response

## Файлы изменений

### Новые файлы

1. **`voxengine/rsd_simplified.js`** - Новый VoxEngine сценарий
2. **`backend/app/telephony/simplified_orchestrator.py`** - Упрощенный оркестратор
3. **`backend/app/router_telephony/webhooks.py`** - Webhook endpoints
4. **`docs/telephony/SIMPLIFIED_ARCHITECTURE.md`** - Документация архитектуры

### Измененные файлы

1. **`backend/app/router_telephony/router.py`** - Добавлен импорт webhooks router

## Инструкция по внедрению

### Шаг 1: Настройка Backend

#### 1.1 Убедитесь что RSD_WEBHOOK_SECRET настроен

```bash
# .env или environment variables
RSD_WEBHOOK_SECRET=your-secure-random-secret
```

#### 1.2 Перезапустите backend

Новые endpoints будут доступны автоматически:
- `POST /api/internal/telephony/simplified/webhook/call.inbound`
- `POST /api/internal/telephony/simplified/webhook/call.answered`
- `POST /api/internal/telephony/simplified/webhook/asr.result`
- `POST /api/internal/telephony/simplified/webhook/call.hangup`

### Шаг 2: Настройка Voximplant

#### 2.1 Создайте новое приложение в Voximplant

1. Войдите в Voximplant Management Panel
2. Создайте новое приложение: `rsd_simplified`
3. Создайте сценарий:
   - Название: `rsd_inbound_simplified`
   - Язык: JavaScript
   - Скопируйте содержимое из `voxengine/rsd_simplified.js`

#### 2.2 Настройте Application Secrets

В настройках приложения добавьте Secrets:

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `RSD_CONNECTION_ID` | `42` | ID подключения в RSD |
| `RSD_WEBHOOK_BASE_URL` | `https://api.yoursite.com` | URL вашего API |
| `RSD_WEBHOOK_SECRET` | `your-secret` | Должен совпадать с backend |
| `VOX_TTS_VOICE` | `Tatyana` | Голос TTS (Tatyana, Maxim, etc.) |
| `VOX_ASR_LANGUAGE` | `ru-RU` | Язык распознавания |

#### 2.3 Создайте routing rule

1. Создайте правило (rule) для входящих звонков
2. Привяжите сценарий `rsd_inbound_simplified`
3. В Custom Data можно добавить JSON для переопределения:

```json
{
  "connection_id": 42,
  "webhook_base_url": "https://api.yoursite.com",
  "require_extension": true,
  "tts_voice": "Tatyana"
}
```

#### 2.4 Привяжите номер телефона

1. Выберите номер для тестирования
2. Привяжите к новому приложению `rsd_simplified`
3. Убедитесь что routing rule активно

### Шаг 3: Тестирование

#### 3.1 Проверка webhook вручную

```bash
# Test inbound
curl -X POST https://api.yoursite.com/api/internal/telephony/simplified/webhook/call.inbound \
  -H "X-RSD-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "test-123",
    "connection_id": 42,
    "caller_e164": "+79123456789",
    "event": "call.inbound",
    "payload": {"caller_e164": "+79123456789"}
  }'

# Expected response:
# {"greeting_text":null,"voice_id":"Tatyana","destination":null}
```

#### 3.2 Тестовый звонок

1. Позвоните на тестовый номер
2. Вы должны услышать приветствие агента
3. Поговорите - агент должен отвечать голосом

### Шаг 4: Мониторинг и отладка

#### Логи VoxEngine

В Voximplant Management Panel → Applications → rsd_simplified → Logs:
- Ищите `[rsd]` в логах
- Проверьте что webhooks возвращают 200

#### Логи Backend

```bash
# Ищите логи simplified_orch:
grep "simplified_orch" /var/log/rsd/backend.log
```

Ожидаемые сообщения:
- `simplified_orch: call registered call_id=...`
- `simplified_orch: ASR final transcript_len=...`
- `webhook_asr_result: call_id=... transcript_len=...`

#### Проверка webhook response

Если TTS не работает, проверьте response от backend:

```python
# Должно возвращаться:
{
    "action": "say",
    "text": "Здравствуйте! Чем могу помочь?",
    "voice_id": "Tatyana"
}
```

### Шаг 5: Полная миграция

После успешного тестирования:

1. Переведите все номера на новое приложение
2. Можно удалить `telephony_media_gateway` (Node.js сервер на порту 8200)
3. Можно отключить `telephony_bridge` если не используется для других целей
4. Старый orchestrator можно оставить для обратной совместимости

## Откат

Если нужно вернуться к старой системе:

1. В Voximplant переключите номера обратно на старое приложение
2. Старый сценарий: `rsd_inbound.js`
3. Старые endpoints остаются доступны

## Сравнение архитектур

| Параметр | Старая система | Новая система |
|----------|---------------|---------------|
| Сервисов | 4 (bridge, gateway, orchestrator, backend) | 2 (VoxEngine, backend) |
| WebSocket | Да (port 8200) | Нет |
| Redis для аудио | Да (pub/sub chunks) | Нет |
| TTS | Yandex gRPC streaming | Voximplant native |
| ASR | Yandex/Deepgram | Voximplant native |
| Latency | Высокая (chunking) | Низкая (direct) |
| Debug | Сложный | Простой |

## Troubleshooting

### Не слышно приветствия

1. Проверьте VoxEngine логи - webhooks возвращают 200?
2. Проверьте backend логи - `simplified_orch` вызывается?
3. Проверьте RSD_WEBHOOK_SECRET - совпадает?

### Не слышно ответов LLM

1. Проверьте `webhook_asr_result` - вызывается?
2. Проверьте что ASR включен в Voximplant (тарифный план)
3. Проверьте логи `handle_asr_result` - транскрипция приходит?

### Ошибки 401/403

1. Проверьте `X-RSD-Secret` header
2. Проверьте `RSD_WEBHOOK_SECRET` в backend
3. Должны совпадать

## Контакты и поддержка

При проблемах:
1. Проверьте логи VoxEngine в панели управления
2. Проверьте логи backend
3. Сравните конфигурацию секретов
