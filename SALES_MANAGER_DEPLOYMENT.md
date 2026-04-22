# Sales Manager - Инструкция по применению

## ✅ Что реализовано

Все этапы 5-9 успешно реализованы для шаблона `sales_manager`:

1. **Этап 5** - Сканирование чатов Telegram userbot
2. **Этап 6** - Очередь отправки DM с лимитами
3. **Этап 7** - UI конфигурация в frontend
4. **Этап 8** - Аналитика и мониторинг
5. **Этап 9** - Тесты и feature flag

---

## 📦 Файлы для применения

### Backend

#### Модели (обновлены)
- `backend/app/alembic/models.py` 
  - Добавлена модель `AgentSalesDmQueue`
  - Добавлена связь в `Agent.sales_dm_queue`

#### Новые сервисы
- `backend/app/services/sales/dm_queue_service.py` - управление очередью
- `backend/app/services/sales/dm_outreach_worker.py` - воркер отправки
- `backend/app/services/sales/analytics_service.py` - аналитика

#### Обновленные сервисы
- `backend/app/channels/userbot_manager.py` - сканирование чатов
- `backend/app/services/sales/tool_registry.py` - schedule_dm с очередью

#### Миграция БД
- `backend/app/alembic/migration/versions/c5d2e9f3a1b4_add_agent_sales_dm_queue.py`

#### Тесты
- `backend/app/tests/test_sales_manager.py` - комплексные тесты

### Frontend

#### Обновлены
- `frontend/src/pages/createAgent.jsx`
  - Добавлена UI секция для sales_manager конфигурации
  - Добавлена валидация (только userbot)
  - Добавлена информация о параметрах по умолчанию

### Документация
- `SALES_MANAGER_IMPLEMENTATION.md` - полное описание реализации

---

## 🚀 Шаги применения

### 1. Применить миграцию БД

```bash
cd backend
alembic upgrade head
```

Это создаст таблицу `agent_sales_dm_queue` с необходимыми индексами.

### 2. Обновить код на сервере

Скопировать все обновленные файлы:

```bash
# Backend
cp -r backend/app/services/sales/* /path/to/prod/backend/app/services/sales/
cp backend/app/alembic/models.py /path/to/prod/backend/app/alembic/
cp backend/app/channels/userbot_manager.py /path/to/prod/backend/app/channels/

# Frontend (если используется)
cp frontend/src/pages/createAgent.jsx /path/to/prod/frontend/src/pages/
```

### 3. Перезагрузить сервисы

```bash
# Backend API
systemctl restart rsd-api

# Userbot manager
systemctl restart rsd-userbot

# DM outreach worker (новый!)
systemctl restart rsd-dm-worker
```

### 4. Инициализировать DM worker в server.py

В `backend/server.py` нужно добавить инициализацию воркера:

```python
from app.services.sales.dm_outreach_worker import get_dm_outreach_worker

# В main():
dm_worker = get_dm_outreach_worker()
# Добавить в list of background tasks
```

---

## ⚙️ Конфигурация

### Environment Variables

```bash
# Включение sales_manager (по умолчанию true)
SALES_MANAGER_ENABLED=true

# Интервал опроса очереди DM (секунды)
DM_QUEUE_POLL_INTERVAL_SECONDS=5

# Размер батча обработки
DM_QUEUE_BATCH_SIZE=10

# Минимальный интервал между отправками (секунды)
DM_QUEUE_MIN_INTERVAL_SECONDS=0.5
```

### Template Config по умолчанию

```json
{
  "mode": "draft_only",
  "qualification_model": "deepseek-chat",
  "generation_model": "deepseek-chat",
  "min_confidence": 0.75,
  "scan_scope": {
    "include_chat_ids": [],
    "exclude_chat_ids": []
  },
  "dm_limits": {
    "per_minute": 3,
    "per_hour": 25,
    "per_day": 120
  },
  "cooldown_days": 14,
  "dedup_window_days": 30
}
```

---

## 🧪 Тестирование

### Unit тесты

```bash
cd backend
pytest app/tests/test_sales_manager.py -v
```

### Интеграционные тесты

```bash
# Создать тестового агента с sales_manager шаблоном
# Проверить:
# 1. Сканирование чатов (check logs)
# 2. Добавление в очередь (SELECT * FROM agent_sales_dm_queue)
# 3. Отправка (проверить статус в БД и логи)
```

### Manual тестирование

1. Создать агента с шаблоном "Менеджер продаж"
2. Загрузить документацию
3. Подключить Telegram userbot
4. Добавить юзербота в тестовый чат
5. Написать целевое сообщение (например, о товаре, вопрос о услуге)
6. Проверить:
   - Таблица `agent_sales_contacts` - новый контакт
   - Таблица `agent_sales_dm_queue` - новое сообщение в очереди
   - Логи воркера - попытка отправки

---

## 📊 Мониторинг

### Метрики для отслеживания

```sql
-- Статистика очереди
SELECT status, COUNT(*) FROM agent_sales_dm_queue WHERE agent_id = ? GROUP BY status;

-- Контакты по состояниям
SELECT state, COUNT(*) FROM agent_sales_contacts WHERE agent_id = ? GROUP BY state;

-- Ошибки отправки
SELECT COUNT(*), last_error FROM agent_sales_dm_queue 
WHERE agent_id = ? AND status = 'failed' 
GROUP BY last_error;

-- Скорость отправки (за последний час)
SELECT COUNT(*) FROM agent_sales_dm_queue 
WHERE agent_id = ? AND status = 'sent' AND sent_at > NOW() - INTERVAL 1 HOUR;
```

### Логирование

Проверять логи воркера:

```bash
tail -f /var/log/rsd/dm-worker.log
```

Ключевые события для мониторинга:
- `DmOutreachWorker starting/stopping`
- `Processing X queued DM messages`
- `Sent DM via userbot: queue_id=...`
- `Failed to send DM: ...`

---

## ⚠️ Важные замечания

### Безопасность

1. **Draft-only mode** - все сообщения требуют подтверждения на этом этапе
2. **Rate limiting** - встроены лимиты 3/мин, 25/час, 120/день
3. **Деdup** - повторные контакты с одним пользователем блокируются через cooldown
4. **Audit trail** - все действия логируются в `AgentAnalyticsMessage`

### Производительность

1. DM worker обрабатывает батчами по 10 сообщений
2. Интервал между сообщениями: 0.5 сек (можно настроить)
3. Retry mechanism - максимум 3 попытки per сообщение
4. Очистка старых записей через `dm_queue_service.cleanup_old_records()`

### Поддерживаемые каналы

На текущий момент:
- ✅ Telegram userbot (реализован)
- ⏳ WhatsApp userbot (планируется)
- ⏳ Discord userbot (планируется)

---

## 🔄 Update процедура

Если нужно обновить в будущем:

1. Git pull новых файлов
2. `alembic upgrade head` (если есть новые миграции)
3. Перезагрузить сервисы
4. Проверить логи: `tail -f /var/log/rsd/*.log`

---

## 📞 Troubleshooting

### Сообщения не отправляются

```bash
# 1. Проверить очередь
SELECT * FROM agent_sales_dm_queue WHERE agent_id = ? ORDER BY created_at DESC;

# 2. Проверить статус воркера
systemctl status rsd-dm-worker

# 3. Проверить логи
journalctl -u rsd-dm-worker -n 100
```

### Контакты не создаются

```bash
# 1. Проверить логи userbot manager
tail -f /var/log/rsd/userbot-manager.log

# 2. Проверить шаблон агента
SELECT template_type, template_config FROM agents WHERE id = ?;

# 3. Проверить template runtime логи
```

### Низкая rate квалификации

```bash
# 1. Проверить LLM модель в config
# 2. Увеличить min_confidence если много false positives
# 3. Обновить RAG документацию для лучшего контекста
```

---

## ✅ Чеклист готовности к production

- [ ] Миграция БД применена
- [ ] Все файлы скопированы на сервер
- [ ] Environment variables установлены
- [ ] Сервисы перезагружены
- [ ] Логи проверены (нет ошибок)
- [ ] DM worker running
- [ ] Тестовый агент создан и работает
- [ ] Мониторинг настроен
- [ ] Документация актуальна

---

**Дата реализации:** 22 апреля 2026 г.
**Версия:** 1.0.0
**Статус:** ✅ Ready for MVP

