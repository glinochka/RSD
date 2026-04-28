# Чек-лист деплоя оптимизации LLM-запросов

## ✅ Pre-Deploy

- [x] Все тесты проходят
  - [x] `test_template_runtime_sales.py` (12/12)
  - [x] `test_sales_manager.py` (12/12)
- [x] Обратная совместимость сохранена
- [x] Документация создана
  - [x] `LLM_REQUEST_OPTIMIZATION.md` - детальное описание
  - [x] `OPTIMIZATION_SUMMARY.md` - краткая сводка
  - [x] `OPTIMIZATION_EXAMPLES.md` - примеры
  - [x] `DEPLOYMENT_CHECKLIST.md` - этот файл
- [x] Код review (самопроверка)

## 📋 Deploy Steps

### 1. Backup

```bash
# Создать бэкап текущей версии
git tag pre-llm-optimization-$(date +%Y%m%d)
git push --tags

# Бэкап базы данных (если есть миграции)
# pg_dump ... (не требуется для этого релиза)
```

### 2. Deploy

```bash
# Pull latest changes
git pull origin main

# Перезапустить сервисы
docker-compose restart backend
# ИЛИ
systemctl restart rsd-backend
```

### 3. Smoke Test

```bash
# Проверить health check
curl http://localhost:8000/health

# Отправить тестовое сообщение через API
curl -X POST http://localhost:8000/api/v1/agents/external/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "message": "Ищем решение для автоматизации",
    "external_user_id": "test_user_123"
  }'
```

## 📊 Post-Deploy Monitoring (первые 24 часа)

### Метрики для отслеживания:

#### 1. Latency (Response Time)

**Где смотреть:**
- Application logs
- APM dashboard (если есть)
- Database slow query log

**Ожидаемое поведение:**
- ✅ Latency снизилась на 30-50%
- ⚠️ Если latency выросла - проверить логи, откатить

**Threshold для алерта:**
- p50 > 3000ms
- p95 > 5000ms
- p99 > 8000ms

---

#### 2. LLM API Calls

**Где смотреть:**
- OpenAI/Anthropic dashboard
- Application logs (добавить логирование)

**Ожидаемое поведение:**
- ✅ Количество запросов снизилось на 33-67%
- ⚠️ Если не снизилось - проверить код

**Пример логирования (TODO - добавить):**
```python
logger.info("sales_manager_llm_calls", extra={
    "template_type": "sales_manager",
    "portrait_called": False,
    "unified_called": True,
    "tools_called": True,
    "total_llm_calls": 3,
    "latency_ms": 2455,
})
```

---

#### 3. Error Rate

**Где смотреть:**
- Application error logs
- Sentry/error tracking

**Ожидаемое поведение:**
- ✅ Error rate не изменился или снизился
- ⚠️ Если error rate вырос > 5% - откатить

**Типичные ошибки:**
- `JSONDecodeError` - проверить моки в тестах
- `KeyError` - проверить обработку unified response
- Timeout - увеличить timeout для объединенного запроса

---

#### 4. Quality Metrics

**Где смотреть:**
- User feedback
- Manual review sample messages
- A/B test dashboard (если настроен)

**Ожидаемое поведение:**
- ✅ Качество ответов не изменилось
- ⚠️ Если качество упало - собрать примеры, проанализировать

**Как проверить:**
- Взять 50-100 реальных сообщений
- Сравнить ответы до/после
- Оценить relevance, correctness, tone

---

#### 5. Cost Savings

**Где смотреть:**
- OpenAI/Anthropic billing dashboard
- Custom cost tracking

**Ожидаемое поведение:**
- ✅ Cost снизилась на 35-60%
- ⚠️ Если cost не изменилась - проверить billing period

**Расчет ожидаемой экономии:**
```
Старая стоимость: X tokens/message × Y messages/day × $Z/1M tokens
Новая стоимость: (X × 0.5) tokens/message × Y messages/day × $Z/1M tokens
Экономия: ~50% × daily cost
```

---

## 🚨 Rollback Plan

### Когда откатывать:

- ❌ Error rate вырос > 5%
- ❌ Latency p95 > 8000ms стабильно
- ❌ Качество ответов заметно упало (user complaints > 10)
- ❌ Критическая ошибка в production

### Как откатить:

#### Вариант 1: Git Revert (быстрый)

```bash
# Откатить последний коммит
git revert HEAD
git push origin main

# Перезапустить сервис
docker-compose restart backend
```

#### Вариант 2: Tag Rollback (средний)

```bash
# Вернуться к тегу перед оптимизацией
git checkout pre-llm-optimization-20260428
git push --force origin main

# Перезапустить сервис
docker-compose restart backend
```

#### Вариант 3: Code Rollback (длинный, но безопасный)

В `template_runtime.py`, метод `_execute_sales_manager`:

```python
# Заменить:
unified = await self._qualify_and_compose_unified(...)
qualification = unified["qualification"]
composed_dm = unified["composed_dm"]

# На:
qualification = await self.qualify_message(...)
composed_dm = await self.compose_dm(...)
```

И вернуть старые константы:
```python
max_iterations = 4  # было 3
max_tool_iterations = 3  # было 2
```

---

## 📈 A/B Testing (опционально)

### Если нужно постепенное раскатывание:

1. **Feature Flag:**
```python
USE_UNIFIED_QUALIFY = os.getenv("USE_UNIFIED_QUALIFY", "true") == "true"

if USE_UNIFIED_QUALIFY:
    unified = await self._qualify_and_compose_unified(...)
else:
    # Старое поведение
    qualification = await self.qualify_message(...)
```

2. **Постепенное раскатывание:**
- День 1-2: 10% трафика
- День 3-4: 50% трафика
- День 5-7: 100% трафика

3. **Сравнение метрик:**
- Latency: unified vs legacy
- Cost: unified vs legacy
- Quality: unified vs legacy

---

## 📝 Post-Deploy Tasks

### День 1-3:

- [ ] Проверить все метрики (latency, error rate, cost)
- [ ] Просмотреть sample сообщений (50-100 шт)
- [ ] Собрать feedback от пользователей
- [ ] Проверить логи на необычные паттерны

### Неделя 1:

- [ ] Добавить детальное логирование LLM calls
- [ ] Настроить дашборд для monitoring
- [ ] Провести manual review качества (200-500 сообщений)
- [ ] Сравнить cost до/после (actual vs expected)

### Месяц 1:

- [ ] Собрать статистику за месяц
- [ ] Провести A/B тест (если не делали)
- [ ] Оптимизировать дальше (кэширование, batching)
- [ ] Написать post-mortem / success report

---

## 🎯 Success Criteria

### Минимум (чтобы не откатывать):
- ✅ Error rate не вырос > 5%
- ✅ Latency p95 < 5000ms
- ✅ No critical bugs

### Целевые KPI:
- 🎯 Latency снизилась на 30-50%
- 🎯 Cost снизилась на 35-60%
- 🎯 Качество ответов не изменилось (±5%)
- 🎯 User satisfaction не снизился

### Идеально:
- 🏆 Latency снизилась на 50%+
- 🏆 Cost снизилась на 60%+
- 🏆 Качество улучшилось
- 🏆 User satisfaction вырос

---

## 📞 Contacts

**Если что-то пошло не так:**

1. Проверить логи: `docker logs rsd-backend --tail 1000`
2. Проверить метрики: [monitoring dashboard URL]
3. Откатить по инструкции выше
4. Сообщить в команду: [Slack channel / email]

---

## 📚 Дополнительные материалы

- [LLM_REQUEST_OPTIMIZATION.md](./LLM_REQUEST_OPTIMIZATION.md) - полное описание
- [OPTIMIZATION_SUMMARY.md](./OPTIMIZATION_SUMMARY.md) - краткая сводка
- [OPTIMIZATION_EXAMPLES.md](./OPTIMIZATION_EXAMPLES.md) - примеры до/после
- [SALES_MANAGER_WORKFLOW_ANALYSIS.md](./SALES_MANAGER_WORKFLOW_ANALYSIS.md) - оригинальный анализ

---

**Дата деплоя:** _____________

**Кто деплоил:** _____________

**Результат:** ☐ Success  ☐ Partial  ☐ Rollback

**Комментарии:**

____________________________________________________

____________________________________________________

____________________________________________________
