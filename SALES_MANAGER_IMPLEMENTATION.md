# Sales Manager Template - Implementation Summary

## Этапы 5-9: Полная реализация

Данный документ резюмирует реализацию этапов 5-9 для sales_manager шаблона агента.

### Этап 5: Интеграция с Telegram userbot сканированием чатов ✅

**Файлы:** `backend/app/channels/userbot_manager.py`

**Что сделано:**
- Расширена функция `_fetch_userbot_configs()` для получения информации о template_type и template_config
- Добавлена функция `_handle_chat_message()` для обработки сообщений из групповых чатов
- Добавлена функция `_handle_private_message()` с поддержкой маршрутизации на основе template_type
- Обновлена функция `_run_one_client()` для регистрации обоих типов обработчиков (ЛС и чаты)

**Фильтры чатов:**
- Пропускаются системные сообщения (event.message.action)
- Пропускаются сообщения от ботов (sender.bot == True)
- Обрабатываются только сообщения для template_type='sales_manager'
- Для sales_manager сообщения из чатов не отправляют ответ, только обрабатываются в backend

---

### Этап 6: Очередь отправки ЛС и защитные лимиты ✅

**Файлы:**
- `backend/app/alembic/models.py` - новая модель AgentSalesDmQueue
- `backend/app/alembic/migration/versions/c5d2e9f3a1b4_add_agent_sales_dm_queue.py` - миграция
- `backend/app/services/sales/dm_queue_service.py` - сервис управления очередью
- `backend/app/services/sales/dm_outreach_worker.py` - фоновый воркер для отправки

**Структура очереди:**
```sql
agent_sales_dm_queue:
  - id (PK)
  - agent_id (FK, indexed)
  - target_user_external_id (indexed)
  - source_chat_id
  - message_text (Text)
  - status: pending, sending, sent, failed, skipped (indexed)
  - retry_count, max_retries
  - scheduled_for, sent_at
  - metadata_json
  - created_at, updated_at (indexed)
```

**Сервис DmQueueService:**
- `enqueue_dm()` - добавить сообщение в очередь
- `get_pending_messages()` - получить сообщения готовые к отправке
- `mark_sent()` - отметить успешно отправленное
- `mark_failed()` - отметить ошибку с автоматическим retry
- `get_queue_stats()` - статистика очереди
- `get_sent_count_in_window()` - подсчет отправленных в временном окне
- `cleanup_old_records()` - очистка старых записей

**Воркер DmOutreachWorker:**
- `run_forever()` - основной цикл обработки (интервал опроса 5+ сек)
- `_process_batch()` - обработка батча сообщений (макс 10 за раз)
- `_send_message()` - отправка через Telethon userbot с error handling

**Лимиты и throttling:**
- Минимальный интервал между сообщениями: 0.5 сек
- Retry logic: 3 попытки с backoff
- Различие между временными ошибками (retry) и постоянными (no retry)

---

### Этап 7: UI конфигурация шаблона ✅

**Файлы:** `frontend/src/pages/createAgent.jsx`

**Что добавлено:**
- Новая опция в выборе шаблона: "Менеджер продаж (Telegram userbot)" с BETA badge
- Валидация: sales_manager доступен ТОЛЬКО с Telegram userbot
- Информационный блок с параметрами по умолчанию:
  - Режим: draft_only (все требуют подтверждения)
  - Модель: DeepSeek-chat
  - Min confidence: 0.75
  - Лимиты: 3/мин, 25/час, 120/день
  - Cooldown: 14 дней
  - Dedup window: 30 дней
- Подсказка о том, что дополнительная конфигурация доступна после создания

---

### Этап 8: Аналитика и мониторинг ✅

**Файлы:** `backend/app/services/sales/analytics_service.py`

**Функции:**

1. **get_sales_manager_stats(agent_id)**
   - Метрика очереди: pending, sending, sent, failed, skipped
   - Метрики контактов: DISCOVERED, QUALIFIED, QUEUED, SENT, REPLIED_*, HANDOFF_CRM
   - Статистика за 24ч: кол-во сообщений
   - Статистика за 7 дней: квалифицированные лиды, положительные ответы, отправленные ДМ

2. **get_sales_manager_dm_queue(agent_id, status, limit, offset)**
   - Получение элементов очереди с фильтрацией по статусу
   - Пагинация (limit, offset)
   - Результат содержит: ID, target user, status, retry count, timestamps, errors

**Возвращаемые метрики:**
```json
{
  "queue": {
    "pending": 5,
    "sending": 0,
    "sent": 42,
    "failed": 2,
    "skipped": 3,
    "total": 52
  },
  "contacts": {
    "discovered": 100,
    "qualified": 45,
    "queued": 10,
    "sent": 32,
    "replied_positive": 8,
    "replied_negative": 2,
    "no_reply": 22
  },
  "metrics": {
    "qualified_leads_7d": 45,
    "positive_replies_total": 8,
    "sent_dms_7d": 32,
    "messages_last_24h": 156
  }
}
```

---

### Этап 9: Тестирование и rollout ✅

**Файлы:**
- `backend/app/tests/test_sales_manager.py` - unit и integration тесты
- Environment variables для feature flag

**Тесты:**

1. **Config Normalization**
   - `test_sales_manager_template_config_normalization()` - валидация конфига

2. **DM Queue Service**
   - `test_dm_queue_service_enqueue_and_retrieve()` - добавление и получение
   - `test_dm_queue_service_mark_sent()` - отметка успеха
   - `test_dm_queue_service_mark_failed_with_retry()` - retry logic

3. **FSM Transitions**
   - `test_sales_fsm_transitions()` - валидные переходы
   - `test_sales_fsm_illegal_transition()` - блокировка неправильных переходов

4. **Tool Registry**
   - `test_sales_tool_registry_schedule_dm()` - инструмент schedule_dm
   - `test_sales_tool_registry_execute_schedule_dm()` - выполнение
   - `test_sales_tool_registry_skip_lead()` - skip_lead инструмент

5. **Feature Flag**
   - `TestSalesManagerFeatureFlag` класс для rollout проверок

**Feature Flag:**
```bash
SALES_MANAGER_ENABLED=true  # по умолчанию включен
```

Флаг позволяет контролировать доступность шаблона на production.

---

## Архитектурный обзор

### Data Flow

```
Telegram Group/Chat
        ↓
userbot_manager._handle_chat_message()
        ↓
MessageProcessor.process()
        ↓
template_runtime._execute_sales_manager()
        ↓
qualify_message() → LLM classifies
        ↓
[low confidence] → skip
[non-target] → skip
[target] ↓
retrieve_offer_context() → RAG search
        ↓
compose_dm() → Generate message
        ↓
_execute_sales_tools() → schedule_dm tool
        ↓
DmQueueService.enqueue_dm()
        ↓
AgentSalesDmQueue (DB)
        ↓
DmOutreachWorker.run_forever()
        ↓
_send_message() via Telethon
        ↓
User DM
```

### Safety & Limits

- **Rate Limiting:** DmQueueService вычисляет `get_sent_count_in_window()`
- **Dedup:** FSM контакты с cooldown_until блокируют повторные касания
- **Retry Policy:** 3 попытки с backoff для временных ошибок
- **Confirmation Policy:** draft_only mode требует подтверждения
- **Compliance:** Все действия логируются в AgentAnalyticsMessage

---

## Использование

### Создание Sales Manager агента

1. Выбрать шаблон "Менеджер продаж (Telegram userbot)"
2. Подключить Telegram userbot
3. Загрузить документацию продукта для RAG
4. Сохранить агента

### Получение статистики

```python
from app.services.sales.analytics_service import get_sales_manager_stats

stats = await get_sales_manager_stats(agent_id=123)
# Возвращает: queue stats, contacts states, metrics
```

### Мониторинг очереди

```python
from app.services.sales.analytics_service import get_sales_manager_dm_queue

queue = await get_sales_manager_dm_queue(
    agent_id=123,
    status="pending",
    limit=50,
    offset=0
)
# Возвращает: список элементов очереди с деталями
```

---

## Дальнейшее развитие

Функции для v2:

1. **Advanced Scheduling**
   - Выбор оптимального времени отправки (quiet hours)
   - Экспоненциальное распределение отправок

2. **A/B Testing**
   - Разные варианты первого сообщения
   - Отслеживание conversion rate

3. **Multi-Channel**
   - WhatsApp userbot scanning
   - Discord userbot support

4. **CRM Integration**
   - Auto-create leads при positive replies
   - Sync with sales pipeline

5. **Advanced Analytics**
   - Cohort analysis
   - Funnel tracking
   - ROI по кампаниям

---

## Миграции БД

Для применения всех изменений:

```bash
alembic upgrade head
```

Это создаст таблицу `agent_sales_dm_queue` с необходимыми индексами.

---

## Заключение

Реализованы все этапы 5-9:
- ✅ Сканирование чатов через userbot
- ✅ Очередь отправки DM с лимитами
- ✅ UI конфигурация в frontend
- ✅ Аналитика и мониторинг
- ✅ Тесты и feature flag

Sales Manager шаблон готов к MVP запуску в режиме `draft_only` с полным контролем и аудитом.
