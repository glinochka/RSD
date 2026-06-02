# Сводка рефакторинга телефонии

## Проблема

Звонок совершался, адресация по агенту после DTMF работала, сообщение "Введите добавочный код" слышно, **но не слышно ответы ИИ-агента** (ни приветствие, ни ответы LLM).

## Корневая причина

Слишком сложная архитектура с множеством точек отказа:
- 4 независимых сервиса (signal, media, dialog, control planes)
- Streaming audio через WebSocket с PCM16 → μ-law конвертацией
- Redis pub/sub для аудио-чанков
- Сложный playback pacing и barge-in detection
- Множественные fallback слои

## Решение

Полная переработка на упрощенную архитектуру с использованием **встроенных TTS и ASR Voximplant**.

## Созданные файлы

### 1. VoxEngine сценарий
**`voxengine/rsd_simplified.js`** (464 строки)
- Использует `call.say()` для TTS (встроенный Voximplant)
- Использует `call.startASR()` для распознавания речи
- HTTP webhooks к backend вместо WebSocket
- Поддержка DTMF для адресации по добавочному номеру
- Поддержка transfer и hangup

### 2. Backend оркестратор
**`backend/app/telephony/simplified_orchestrator.py`** (295 строк)
- Упрощенный orchestrator без streaming
- In-memory state management
- Нет Redis pub/sub для аудио
- Прямое взаимодействие с LLM

### 3. Webhook endpoints
**`backend/app/router_telephony/webhooks.py`** (244 строки)
- `/webhook/call.inbound` - входящий звонок
- `/webhook/call.answered` - звонок отвечен
- `/webhook/asr.result` - результат распознавания
- `/webhook/call.hangup` - завершение звонка
- `/response/next` - polling для async (опционально)

### 4. Документация
**`docs/telephony/SIMPLIFIED_ARCHITECTURE.md`** - Архитектура новой системы
**`docs/telephony/MIGRATION_GUIDE.md`** - Пошаговая инструкция по внедрению

## Измененные файлы

### `backend/app/router_telephony/router.py`
- Добавлен импорт `from .webhooks import router as webhooks_router`
- Добавлен `router.include_router(webhooks_router, prefix="/simplified")`

## Ключевые улучшения

### 1. Архитектура
| Параметр | Было | Стало |
|----------|------|-------|
| Сервисов | 4 | 2 |
| WebSocket | Да | Нет |
| Redis для аудио | Да | Нет |
| Слои fallback | 3 | 1 |

### 2. Надежность
- Убраны сложные цепочки преобразования аудио
- Нет WebSocket соединений которые могут обрываться
- Нет Redis pub/sub для аудио-чанков
- Прямое использование проверенных Voximplant TTS/ASR

### 3. Простота отладки
- HTTP request/response легко логировать
- Видны все промежуточные состояния
- Проще воспроизвести проблему

### 4. Задержка
- Нет chunking и buffering аудио
- Нет конвертации форматов
- Меньше сетевых hop'ов

## Как использовать

### Backend
Уже готово к использованию. Endpoints доступны по:
```
/api/internal/telephony/simplified/webhook/call.inbound
/api/internal/telephony/simplified/webhook/call.answered
/api/internal/telephony/simplified/webhook/asr.result
/api/internal/telephony/simplified/webhook/call.hangup
```

### Voximplant
1. Создайте новое приложение
2. Загрузите `rsd_simplified.js` как сценарий
3. Настройте Application Secrets:
   - `RSD_WEBHOOK_BASE_URL`
   - `RSD_WEBHOOK_SECRET`
   - `RSD_CONNECTION_ID`
4. Создайте routing rule
5. Привяжите номер

### Тестирование
1. Позвоните на номер
2. Должно работать:
   - Приветствие от агента (TTS)
   - Распознавание вашей речи (ASR)
   - Ответы агента (TTS через LLM)

## Что можно удалить (опционально)

После успешной миграции:
- `telephony_media_gateway/` (Node.js WebSocket сервер)
- `telephony_bridge/` (если не используется для других целей)
- Старый `orchestrator_worker.py` (можно оставить для совместимости)
- Redis pub/sub для аудио-чанков

## Совместимость

Новая система **полностью совместима** со старой:
- Старые endpoints продолжают работать
- Можно переключаться между системами
- Можно использовать обе параллельно для разных номеров

## Дальнейшие улучшения

1. **Мониторинг** - добавить метрики для новой системы
2. **Barge-in** - реализовать прерывание речи агента
3. **Custom TTS** - интеграция с внешними TTS через Voximplant HTTP API
4. **Аналитика** - детальное логирование диалогов
