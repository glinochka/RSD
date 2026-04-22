# 🚀 Sales Manager - Quick Start

## Что нужно сделать после получения кода

### Шаг 1: Миграция БД (обязательно)
```bash
cd backend
alembic upgrade head
```

### Шаг 2: Проверить логи (убедиться что ошибок нет)
```bash
# Backend
python server.py

# Проверить вывод в консоль
```

### Шаг 3: Запустить тесты
```bash
cd backend
pytest app/tests/test_sales_manager.py -v
```

### Шаг 4: Создать тестового агента в UI
1. Открыть `createAgent.jsx`
2. Выбрать "Менеджер продаж (Telegram userbot)" в dropdown
3. Заполнить данные
4. Сохранить

### Шаг 5: Проверить таблицу в БД
```sql
SELECT * FROM agent_sales_dm_queue LIMIT 5;
SELECT * FROM agent_sales_contacts WHERE agent_id = <YOUR_AGENT_ID> LIMIT 5;
```

---

## Структура кода

### Основные файлы для понимания

```
backend/app/
├── services/sales/
│   ├── dm_queue_service.py       ← Управление очередью
│   ├── dm_outreach_worker.py     ← Фоновая отправка  
│   ├── analytics_service.py      ← Статистика
│   └── tool_registry.py          ← LLM инструменты
├── channels/
│   └── userbot_manager.py        ← Сканирование чатов
├── alembic/
│   ├── models.py                 ← БД модели
│   └── migration/versions/       ← Миграции
└── tests/
    └── test_sales_manager.py     ← Тесты

frontend/src/
└── pages/
    └── createAgent.jsx           ← UI конфигурация
```

---

## Ключевые функции

### DmQueueService
```python
# Добавить сообщение в очередь
await DmQueueService.enqueue_dm(
    agent_id=123,
    target_user_external_id=456,
    message_text="Hello"
)

# Получить статистику
stats = await DmQueueService.get_queue_stats(agent_id=123)
# {'pending': 5, 'sending': 0, 'sent': 42, 'failed': 2, ...}
```

### Analytics
```python
# Получить все метрики
stats = await get_sales_manager_stats(agent_id=123)
# {queue: {...}, contacts: {...}, metrics: {...}}

# Получить элементы очереди
queue = await get_sales_manager_dm_queue(
    agent_id=123, 
    status="pending"
)
```

### MessageProcessor flow
```
telegram_message → userbot_manager → MessageProcessor 
→ template_runtime._execute_sales_manager() 
→ qualify + compose → schedule_dm tool 
→ enqueue_dm() 
→ worker sends async
```

---

## Лимиты и параметры

| Параметр | Значение | Настраивается |
|----------|----------|---------------|
| Rate: мин | 3/мин | ✅ config.dm_limits.per_minute |
| Rate: час | 25/час | ✅ config.dm_limits.per_hour |
| Rate: день | 120/день | ✅ config.dm_limits.per_day |
| Cooldown | 14 дн | ✅ config.cooldown_days |
| Min confidence | 0.75 | ✅ config.min_confidence |
| Интервал батча | 0.5 сек | ✅ DM_QUEUE_MIN_INTERVAL_SECONDS |
| Опрос очереди | 5 сек | ✅ DM_QUEUE_POLL_INTERVAL_SECONDS |

---

## Отладка проблем

### Проблема: Сообщения не добавляются в очередь

**Решение:**
1. Проверить логи `_handle_chat_message()` - добавляются ли контакты
2. Проверить, что `template_type='sales_manager'` в БД
3. Проверить LLM ответ - может быть low confidence

```python
# Debug: прямой вызов
from app.services.sales.dm_queue_service import DmQueueService
await DmQueueService.enqueue_dm(
    agent_id=YOUR_AGENT_ID,
    target_user_external_id=USER_ID,
    message_text="test"
)
```

### Проблема: Воркер не отправляет

**Решение:**
1. Проверить, запущен ли DmOutreachWorker
2. Проверить логи: есть ли `_process_batch()` вызовы
3. Проверить Telethon credentials - валидны ли

```sql
-- Check queue
SELECT * FROM agent_sales_dm_queue 
WHERE agent_id = YOUR_AGENT_ID 
ORDER BY created_at DESC;

-- Check status
SELECT status, COUNT(*) FROM agent_sales_dm_queue 
WHERE agent_id = YOUR_AGENT_ID 
GROUP BY status;
```

### Проблема: LLM не квалифицирует

**Решение:**
1. Проверить min_confidence в config
2. Проверить RAG документацию (достаточно ли контекста)
3. Увеличить температуру модели или сменить модель

---

## Мониторинг в production

### Логи для отслеживания

```bash
# Все события sales_manager
grep "sales_manager\|DmOutreach\|schedule_dm" /var/log/rsd/backend.log

# Только ошибки
grep "ERROR.*sales\|ERROR.*DmOutreach" /var/log/rsd/backend.log

# Отправки в реальном времени
tail -f /var/log/rsd/backend.log | grep "Sent DM"
```

### Метрики для Prometheus (future)

```python
# Уже есть логирование, нужно добавить метрики
dm_queue_size = Gauge('dm_queue_pending', 'Pending DM messages')
dm_sent_total = Counter('dm_sent_total', 'Total DMs sent')
dm_failed_total = Counter('dm_failed_total', 'Total DMs failed')
```

---

## API Endpoints (для добавления в router)

### Получить статистику
```
GET /agents/{agent_id}/sales_stats
→ {queue: {...}, contacts: {...}, metrics: {...}}
```

### Получить очередь
```
GET /agents/{agent_id}/sales_dm_queue?status=pending&limit=50&offset=0
→ [{id, target_user, status, retry_count, ...}, ...]
```

### Отметить как reviewed (future)
```
POST /agents/{agent_id}/sales_dm_queue/{queue_id}/approve
POST /agents/{agent_id}/sales_dm_queue/{queue_id}/reject
```

---

## Дополнительно

### Где находятся ключевые строки кода

**Создание контакта FSM:**
- `template_runtime.py` → `_execute_sales_manager()`
- Строка: `sales_fsm.create_or_get_contact(source_user_id)`

**Квалификация сообщения:**
- `template_runtime.py` → `_qualify_message()`
- Использует LLM для classification

**Отправка через Telethon:**
- `dm_outreach_worker.py` → `_send_message()`
- Строка: `await client.send_message(target_id, text)`

**Обработка чатов:**
- `userbot_manager.py` → `_handle_chat_message()`
- Регистрация в `_run_one_client()`

---

## Готов к использованию ✅

Все файлы созданы и готовы к использованию. Начните с шага 1 (миграция БД) и проверьте логи!
