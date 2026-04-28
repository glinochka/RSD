# Sales Manager Template - Workflow Analysis

## 1. Архитектура и компоненты системы

### 1.1 Основные модули

**FSM (Finite State Machine) - `backend/app/services/sales/fsm.py`**
- Управляет жизненным циклом контакта через состояния
- Поддерживает строгие переходы между статусами
- Хранит метаданные контактов в БД

**Tool Registry - `backend/app/services/sales/tool_registry.py`**
- Валидация и регистрация инструментов для LLM
- Управление подтверждениями для рискованных действий
- Идемпотентность выполнения инструментов (TTL 120 сек)
- Лимит размера аргументов: 16 000 байт

**DM Queue Service - `backend/app/services/sales/dm_queue_service.py`**
- Управление очередью исходящих DM-сообщений
- Поддержка отложенной отправки (scheduled_for)
- Retry-логика (max 3 попытки)
- Статистика по статусам очереди

**DM Outreach Worker - `backend/app/services/sales/dm_outreach_worker.py`**
- Фоновый воркер для отправки сообщений через Telegram userbot
- Throttling: минимум 0.5 сек между отправками
- Batch обработка (по умолчанию 10 сообщений)
- Автоматический retry при ошибках подключения

**Template Runtime - `backend/app/services/template_runtime.py`**
- Главный оркестратор всего workflow
- Интеграция с FSM, tool registry, DM queue
- Генерация контента через LLM
- Управление портретом лида

**Analytics Service - `backend/app/services/sales/analytics_service.py`**
- Статистика по агенту (DM queue, контакты, метрики)
- Выборка элементов очереди с фильтрацией

---

## 2. Полный Workflow Sales Manager

### 2.1 Схема FSM (Finite State Machine)

```
DISCOVERED (начальное состояние)
    ↓ ↓
    ↓ └→ SKIPPED (пропущен)
    ↓
QUALIFIED (квалифицирован)
    ↓ ↓
    ↓ └→ SKIPPED
    ↓
QUEUED (добавлен в очередь DM)
    ↓ ↓
    ↓ └→ SKIPPED
    ↓
SENT (отправлено сообщение)
    ↓ ↓ ↓
    ↓ ↓ └→ NO_REPLY (нет ответа)
    ↓ └→ REPLIED_NEGATIVE (негативный ответ)
    ↓
REPLIED_POSITIVE (позитивный ответ)
    ↓
HANDOFF_CRM (передан в CRM)
```

**Терминальные состояния:** HANDOFF_CRM, REPLIED_NEGATIVE, NO_REPLY, SKIPPED

### 2.2 Основной поток выполнения

#### Шаг 1: Инициализация контакта
```python
# Файл: template_runtime.py, строки 867-884
- Создание/получение контакта в FSM (agent_id + user_external_id + source_chat_id)
- Загрузка текущего состояния FSM (по умолчанию DISCOVERED)
- Загрузка metadata контакта (lead_profile, last_qualification)
- Загрузка истории диалога (последние 8 сообщений)
```

#### Шаг 2: Проверка терминального состояния
```python
# Файл: template_runtime.py, строки 892-919
- Если workflow_completion_mode = "auto_finish_on_signal"
- И контакт в терминальном состоянии (HANDOFF_CRM, REPLIED_NEGATIVE, NO_REPLY, SKIPPED)
- → Возврат сообщения "Диалог уже завершен" + noop event
```

#### Шаг 3: Квалификация сообщения
```python
# Файл: template_runtime.py, строки 936-945
# Если lead_initiated_private_dialog = True → автоматическая квалификация как HOT
- Вызов qualify_message() через function calling
- LLM выбирает один из tool calls:
  * engage_lead → decision="engage"
  * ignore_lead → decision="ignore"
  * finish_workflow → decision="finish" (если workflow_completion_mode = auto_finish_on_signal)
```

**Возвращаемые данные квалификации:**
- decision: engage | ignore | finish
- intent: target_hot | target_warm | unsure | non_target | do_not_contact | workflow_completed
- confidence: 0.0-1.0
- reason: текстовое объяснение
- lead_temperature: cold | warm | hot
- stage_hint: first_touch | discovery | value_pitch | handoff
- handoff_ready: boolean
- workflow_outcome: continue | sale_closed | dialog_finished
- lead_heat_score, resilience_score, engagement_score (по шкале 0-100 или 0-10)

#### Шаг 4: Построение профиля лида
```python
# Файл: template_runtime.py, строки 946-959
- Расчет агрегированных скоров:
  * overall = heat*0.45 + resilience*0.2 + engagement*0.35
  * Смешивание с предыдущим профилем: new*0.35 + previous*0.65
  * Тренд: warming/cooling/stable (delta >=4 или <=-4)
  * Bucket: very_hot (>=80) | warm (>=65) | neutral (>=45) | cold (<45)
- Сохранение профиля в metadata контакта
```

#### Шаг 5: Обработка решений

**5.1 Если decision = "finish"**
```python
# Файл: template_runtime.py, строки 966-1010
- Определение целевого состояния FSM:
  * REPLIED_POSITIVE → HANDOFF_CRM
  * SENT → REPLIED_NEGATIVE/REPLIED_POSITIVE
  * DISCOVERED/QUALIFIED/QUEUED → SKIPPED
- Transition в FSM
- Возврат: "Лид переведен в завершенный статус"
```

**5.2 Если intent in {"do_not_contact", "non_target"} или decision = "ignore"**
```python
# Файл: template_runtime.py, строки 1012-1044
- Если текущее состояние = SENT и intent негативный → REPLIED_NEGATIVE
- Transition в SKIPPED
- Возврат через emit_action() → "Лид пропущен: ..."
```

**5.3 Если confidence < min_confidence**
```python
# Файл: template_runtime.py, строки 1045-1074
- Если low_confidence_fallback_to_qa = true и канал = userbot → QA fallback
- Иначе: Transition в SKIPPED
- Возврат через emit_action() → "Лид пропущен: низкая уверенность"
```

**5.4 Если decision = "engage" (основной путь)**

##### 5.4.1 Обновление FSM при положительном ответе
```python
# Файл: template_runtime.py, строки 1076-1096
- Если текущее состояние = SENT и decision = engage → REPLIED_POSITIVE
- Если текущее состояние = DISCOVERED → QUALIFIED
```

##### 5.4.2 Получение контекста предложения
```python
# Файл: template_runtime.py, строки 1097-1101
- Поиск в knowledge base через RAG (semantic search)
- Возврат контекста и sources
```

##### 5.4.3 Генерация DM-сообщения
```python
# Файл: template_runtime.py, строки 1102-1111
- compose_dm():
  * Сбор контекста: qualification, RAG context, chat portrait, history
  * Stage-специфичная инструкция (first_touch/discovery/value_pitch/handoff)
  * LLM генерация (model: template_config.generation_model, default: deepseek-chat)
  * Очистка markdown, лимит 1200 символов
```

**Stage инструкции:**
- `first_touch`: "Сделай ненавязчивое первое касание"
- `discovery`: "Уточни боли, задай 1-2 коротких вопроса"
- `value_pitch`: "Покажи ценность и изменения после внедрения"
- `handoff`: "Предложи передачу на ЛПР, заявку или демо-звонок"

##### 5.4.4 Выполнение sales tools через LLM
```python
# Файл: template_runtime.py, строки 1112-1141
- _execute_sales_tools():
  * Создание SalesToolRegistry с allowed_tools
  * confirmation_policy = "never_confirm" (автономный режим)
  * LLM function calling (до 3 итераций)
  * Выполнение tools: schedule_dm, skip_lead, record_lead_signal, create_crm_lead, mark_contacted
```

**Доступные инструменты:**
1. **schedule_dm**: Добавить DM в очередь
   - Args: text (1-1200 символов), target_user_external_id, source_chat_id
   - Возврат: {"queued": true, "status": "sent_auto"|"draft_requires_review"}

2. **skip_lead**: Пропустить лид
   - Args: reason_code (3-64 символа), reason_text (до 500 символов)
   - Возврат: {"skipped": true}

3. **record_lead_signal**: Записать сигнал квалификации
   - Args: signal_type, score (0.0-1.0), details
   - Возврат: {"recorded": true}

4. **create_crm_lead**: Создать лид в CRM
   - Args: title (3-255 символов), note (до 2000 символов)
   - Возврат: {"crm_lead_created": true}

5. **mark_contacted**: Отметить как контактированный
   - Args: channel (только "telegram_userbot"), campaign_id
   - Возврат: {"marked": true}

##### 5.4.5 Применение FSM транзакций из tool events
```python
# Файл: template_runtime.py, строки 1126-1141, 1882-1923
- Если tool_status = "draft_requires_review" → QUEUED
- Если tool_status = "sent_auto" → QUEUED → SENT
- Если tool_status starts with "skipped_" → SKIPPED
- Если handoff_ready = true и состояние = REPLIED_POSITIVE → HANDOFF_CRM
```

##### 5.4.6 Возврат результата
```python
# Файл: template_runtime.py, строки 1142-1166
- Если есть tool_events → возврат результата из tools
- Иначе → emit_action() с composed_dm
```

#### Шаг 6: Формат ответа (emit_action)
```python
# Файл: template_runtime.py, строки 1686-1738
Возвращаемый статус зависит от mode:
- mode="auto" → "sent_auto": "Auto outreach готов к отправке"
- mode="semi_auto" → "draft_requires_review": "Требуется подтверждение владельца"
- mode="draft_only" → "draft_requires_review": "Черновик outreach (режим draft_only)"
- intent="do_not_contact" → "skipped_do_not_contact"
- intent="non_target" → "skipped_non_target"
- confidence < min_confidence → "skipped_low_confidence"
```

### 2.3 Фоновая отправка DM

#### DM Queue Worker
```python
# Файл: dm_outreach_worker.py
- Polling каждые 5+ секунд
- Получение pending сообщений (limit=batch_size, по умолчанию 10)
- Фильтрация по scheduled_for (отправка только просроченных)
- Throttling: sleep(0.5 сек) между отправками
- Отправка через Telethon TelegramClient
- При успехе → mark_sent()
- При ошибке → mark_failed() с retry (если не auth/not found)
```

#### Retry логика
```python
# Файл: dm_queue_service.py, строки 94-119
- max_retries = 3
- При ошибке: retry_count++
- Если retry_count < max_retries и retry=True → status="pending"
- Иначе → status="failed"
```

---

## 3. Дополнительные фичи (Potential Features)

### 3.1 Умные лимиты и throttling

**Проблема:** Сейчас есть только базовый throttling (0.5 сек между отправками)

**Решение:**
```python
# Добавить в SALES_DEFAULT_CONFIG (router.py):
"dm_limits": {
    "per_minute": 3,      # максимум 3 DM в минуту
    "per_hour": 25,       # максимум 25 DM в час
    "per_day": 120,       # максимум 120 DM в день
    "per_source_chat_per_day": 40  # лимит на чат-источник
}
```

**Реализация:**
- Метод `get_sent_count_in_window()` уже есть в `dm_queue_service.py`
- Добавить проверку лимитов перед enqueue в `SalesToolRegistry.execute_tool()`
- При превышении лимита → отложить отправку (scheduled_for)

### 3.2 A/B тестирование сообщений

**Проблема:** Нет возможности тестировать разные варианты DM

**Решение:**
```python
# Новый tool: "schedule_dm_with_variant"
class _ScheduleDmWithVariantArgs(BaseModel):
    text_variants: List[str]  # несколько вариантов текста
    variant_weights: List[float] = [0.5, 0.5]  # распределение вероятностей
    target_user_external_id: str
    ab_test_id: str  # идентификатор теста
```

**Метрики:**
- Отслеживание variant_id в metadata DM
- Связывание с response (REPLIED_POSITIVE/NEGATIVE)
- Таблица статистики: ab_test_id → variant_id → conversion_rate

### 3.3 Динамическая квалификация на основе истории

**Проблема:** Квалификация зависит только от текущего сообщения

**Решение:**
```python
# В qualify_message() добавить:
"historical_signals": [
    {
        "timestamp": "2025-01-15T10:30:00Z",
        "signal_type": "viewed_profile",
        "score": 0.6
    },
    {
        "timestamp": "2025-01-16T14:20:00Z", 
        "signal_type": "clicked_link",
        "score": 0.8
    }
]
```

**Источники сигналов:**
- Клики по ссылкам из previous DM
- Просмотр профиля/сайта (если есть tracking)
- Время прочтения сообщений
- Паттерны ответов (быстрые vs медленные)

### 3.4 Интеграция с календарем

**Проблема:** Нет учета quiet hours и таймзон лида

**Решение:**
```python
# В SALES_DEFAULT_CONFIG добавить:
"quiet_hours_local": "22:00-09:00",  # не отправлять ночью
"timezone_detection": True,  # определять таймзону лида
```

**Реализация:**
- Парсинг quiet_hours в dm_queue_service
- Определение timezone по external_id (если Telegram) через Telethon
- Откладывание отправки (scheduled_for) если сейчас quiet hours

### 3.5 Follow-up автоматизация

**Проблема:** После отправки DM нет автоматических follow-up

**Решение:**
```python
# Новая таблица: AgentSalesFollowupRule
class AgentSalesFollowupRule:
    agent_id: int
    trigger_state: str  # SENT, QUEUED
    delay_hours: int  # 48, 72, 168 (7 дней)
    follow_up_template: str
    max_follow_ups: int = 2
    enabled: bool = True
```

**Workflow:**
- При transition в SENT → создать follow-up job
- Если NO_REPLY после delay_hours → автоотправка follow-up
- Трекинг количества follow-ups (max_follow_ups)

### 3.6 Sentiment analysis на ответах

**Проблема:** REPLIED_POSITIVE/NEGATIVE определяется только LLM квалификацией

**Решение:**
```python
# Добавить в qualification:
"sentiment_analysis": {
    "polarity": 0.7,  # -1.0 (negative) to 1.0 (positive)
    "subjectivity": 0.6,  # 0.0 (objective) to 1.0 (subjective)
    "emotion": "interest"  # interest, confusion, rejection, enthusiasm
}
```

**Реализация:**
- Использовать dostoevsky/ruSentiLex для русского
- Или отдельный LLM call с emotion classification
- Сохранять в metadata контакта

### 3.7 Lead scoring улучшения

**Проблема:** Скоры основаны только на текущем сообщении

**Решение:**
```python
# Добавить в lead_profile:
"behavioral_score": 0.75,  # на основе действий
"engagement_history": [
    {"date": "2025-01-15", "score": 0.6},
    {"date": "2025-01-16", "score": 0.8}
],
"predicted_conversion_probability": 0.42,  # ML модель
"predicted_value_usd": 500  # ожидаемая стоимость сделки
```

**Источники:**
- Время ответа (быстрые = высокий engagement)
- Длина ответа (подробные = высокий interest)
- Вопросы про цену/условия (высокий buying intent)
- Previous DM open rate (если есть read receipts)

### 3.8 Multi-channel outreach

**Проблема:** Только Telegram userbot

**Решение:**
```python
# Расширить dm_queue_service:
class AgentSalesDmQueue:
    channel: str  # telegram_userbot, whatsapp_userbot, email, linkedin
    fallback_channels: List[str] = []  # если первый канал недоступен
```

**Стратегия:**
- Попытка отправки через primary channel
- При ошибке → fallback на whatsapp/email
- Трекинг preferred_channel в контакте

### 3.9 Lead deduplication

**Проблема:** Один лид может появиться из разных source_chat_id

**Решение:**
```python
# Добавить в FSM:
def find_duplicate_contacts(
    user_external_id: str,
    agent_id: int
) -> List[AgentSalesContact]:
    # Поиск контактов с одним user_external_id но разными source_chat_id
    pass

# В qualify_message():
duplicates = find_duplicate_contacts(user_external_id, agent_id)
if duplicates and any(d.state not in TERMINAL_STATES for d in duplicates):
    return {"decision": "ignore", "reason": "duplicate_active_contact"}
```

**Конфигурация:**
```python
"dedup_window_days": 30,  # игнорировать дубликаты в течение 30 дней
"dedup_strategy": "merge_contacts" | "skip_new"
```

### 3.10 Analytics dashboard метрики

**Проблема:** Базовая аналитика в `analytics_service.py`

**Решение - добавить метрики:**
```python
# Conversion funnel:
{
    "discovered_to_qualified_rate": 0.35,
    "qualified_to_sent_rate": 0.80,
    "sent_to_replied_rate": 0.25,
    "replied_to_handoff_rate": 0.60,
    "overall_conversion_rate": 0.042
}

# Time metrics:
{
    "avg_time_to_first_dm_hours": 2.5,
    "avg_time_to_reply_hours": 12.3,
    "avg_time_to_handoff_days": 5.2
}

# Quality metrics:
{
    "avg_confidence_score": 0.87,
    "avg_lead_score": 72.5,
    "positive_reply_rate": 0.25,
    "spam_complaint_rate": 0.001
}
```

---

## 4. Оптимизация workflow (Unnecessary Actions)

### 4.1 Избыточные LLM вызовы

**Проблема 1: Двойная генерация для qualification + compose**

**Текущий flow:**
```python
# Шаг 1: qualify_message() - один LLM call
qualification = await qualify_message(...)  # deepseek-chat

# Шаг 2: compose_dm() - еще один LLM call
composed_dm = await compose_dm(...)  # deepseek-chat
```

**Оптимизация:**
```python
# Объединить в один вызов с multiple functions:
functions = [
    {"name": "engage_lead_with_message", ...},  # qualification + DM в одном
    {"name": "ignore_lead", ...}
]

# Возврат:
{
    "decision": "engage",
    "intent": "target_hot",
    "confidence": 0.95,
    "composed_message": "Здравствуйте! Увидел ваш запрос..."  # сразу готовый текст
}
```

**Экономия:** 50% LLM calls на каждый engage lead

---

**Проблема 2: Генерация DM даже для ignore/skip**

**Текущий код:**
```python
# Файл: template_runtime.py, строки 1097-1111
# compose_dm() вызывается ДО проверки decision
context_list, sources = await self.retrieve_offer_context(...)
composed_dm = await self.compose_dm(...)  # <-- тратим токены

# Затем в _execute_sales_tools():
if tool_driven is not None:
    return tool_driven
```

**Оптимизация:**
```python
# Перенести compose_dm() ПОСЛЕ qualify и проверки decision
if decision == "ignore" or confidence < min_confidence:
    return emit_action(..., composed_dm=None)  # без генерации

# Генерируем DM только для engage:
if decision == "engage":
    context_list, sources = await self.retrieve_offer_context(...)
    composed_dm = await self.compose_dm(...)
```

**Экономия:** Исключение 40-60% ненужных генераций DM

---

### 4.2 Лишние database queries

**Проблема: Multiple queries для одного контакта**

**Текущий код:**
```python
# template_runtime.py, строки 867-884
await self._ensure_sales_contact_exists(...)  # Query 1: get_or_create
current_state = await self._load_sales_contact_state(...)  # Query 2: select state
metadata = await self._load_sales_contact_metadata(...)  # Query 3: select metadata_json
```

**Оптимизация:**
```python
# Объединить в один метод:
async def load_contact_with_metadata(
    agent_id: int,
    user_external_id: str,
    source_chat_id: str
) -> Tuple[AgentSalesContact, str, dict]:
    async with async_session_maker() as session:
        row = await session.scalar(
            select(AgentSalesContact).where(...)
        )
        if not row:
            row = AgentSalesContact(...)
            session.add(row)
        
        return row, row.state, json.loads(row.metadata_json or "{}")
```

**Экономия:** 3 queries → 1 query на каждое сообщение

---

**Проблема 2: Загрузка истории диалога дважды**

**Текущий код:**
```python
# template_runtime.py, строки 885-891
recent_history = await self._load_recent_channel_history(...)  # вызов 1

# template_runtime.py, строки 1326-1337 в qualify_message
# history снова передается, но уже загружена
```

**Оптимизация:**
```python
# Загрузить историю один раз и передавать через параметры
recent_history = await self._load_recent_channel_history(...)
qualification = await self.qualify_message(..., recent_history=recent_history)
composed_dm = await self.compose_dm(..., recent_history=recent_history)
```

**Экономия:** Исключение дублирующихся queries

---

### 4.3 Избыточные FSM transitions

**Проблема: Промежуточный переход через QUEUED**

**Текущий код:**
```python
# template_runtime.py, строки 1901-1915
elif status == "sent_auto":
    await self._transition_sales_state_safe(..., to_state="QUEUED", ...)  # transition 1
    await self._transition_sales_state_safe(..., to_state="SENT", ...)  # transition 2
```

**Оптимизация:**
```python
# Прямой переход в SENT для mode="auto":
elif status == "sent_auto":
    await self._transition_sales_state_safe(..., to_state="SENT", reason="auto_sent")
```

**Экономия:** 2 database writes → 1 write

---

**Проблема 2: Двойной transition при engage**

**Текущий код:**
```python
# template_runtime.py, строки 1087-1096
if current_sales_state == "DISCOVERED":
    await self._transition_sales_state_safe(..., to_state="QUALIFIED", ...)  # transition 1
    current_sales_state = "QUALIFIED"

# Затем в _apply_fsm_from_tool_events():
await self._transition_sales_state_safe(..., to_state="QUEUED", ...)  # transition 2
```

**Оптимизация:**
```python
# Сразу переходить из DISCOVERED в QUEUED для engage:
if current_sales_state == "DISCOVERED" and decision == "engage":
    target_state = "QUEUED" if will_use_tools else "QUALIFIED"
    await self._transition_sales_state_safe(..., to_state=target_state, ...)
```

**Экономия:** 3 transitions → 2 transitions на engage flow

---

### 4.4 Неэффективный context retrieval

**Проблема: RAG поиск для ignore/skip случаев**

**Текущий код:**
```python
# template_runtime.py, строки 1097-1101
# Поиск контекста выполняется ДО проверки decision
context_list, sources = await self.retrieve_offer_context(
    user_message=user_message,
    knowledge_scope_id=knowledge_scope_id,
    enable_smart_search=self._is_smart_search_enabled(template_config),
)

# Но если decision = "ignore":
if decision == "ignore":
    return emit_action(..., sources=[])  # контекст не используется!
```

**Оптимизация:**
```python
# Перенести RAG поиск внутрь engage блока:
if decision == "engage" and confidence >= min_confidence:
    context_list, sources = await self.retrieve_offer_context(...)
    composed_dm = await self.compose_dm(...)
else:
    return emit_action(..., composed_dm=None, sources=[])
```

**Экономия:** 
- Исключение 40-60% ненужных векторных поисков
- Экономия latency на ~100-300ms для skip случаев

---

### 4.5 Portrait обновление на каждое сообщение

**Проблема: update_chat_portrait() вызывается для каждого сообщения**

**Текущий поток:**
```python
# router.py или message handler:
chat_portrait = await runtime.update_chat_portrait(...)  # LLM call каждый раз
```

**Оптимизация:**
```python
# Добавить rate limiting для portrait updates:
async def update_chat_portrait_if_stale(
    agent_id: int,
    user_external_id: str,
    stale_threshold_minutes: int = 60  # обновлять не чаще раза в час
):
    last_update = await get_portrait_last_update_time(...)
    if datetime.now() - last_update > timedelta(minutes=stale_threshold_minutes):
        return await update_chat_portrait(...)
    else:
        return await load_chat_portrait(...)  # просто загрузить существующий
```

**Или:**
```python
# Обновлять portrait только при значительных изменениях:
if len(user_message) > 50 or any(keyword in user_message for keyword in ["хочу", "нужно", "интересует"]):
    chat_portrait = await runtime.update_chat_portrait(...)
```

**Экономия:** 70-80% portrait LLM calls

---

### 4.6 Idempotency cache очистка на каждый вызов

**Проблема: _cleanup_idempotency_cache() на каждый execute_tool**

**Текущий код:**
```python
# tool_registry.py, строки 171
_cleanup_idempotency_cache()  # линейный проход по всему кешу
```

**Оптимизация:**
```python
# Ленивая очистка с порогом:
_LAST_CLEANUP_TIME = None
_CLEANUP_INTERVAL_SECONDS = 60

def _cleanup_idempotency_cache_lazy():
    global _LAST_CLEANUP_TIME
    now = _now_utc()
    if _LAST_CLEANUP_TIME is None or (now - _LAST_CLEANUP_TIME).total_seconds() > _CLEANUP_INTERVAL_SECONDS:
        _cleanup_idempotency_cache()
        _LAST_CLEANUP_TIME = now
```

**Экономия:** Очистка раз в минуту вместо на каждый вызов

---

### 4.7 DM Worker polling overhead

**Проблема: Постоянный polling каждые 5 секунд даже при пустой очереди**

**Текущий код:**
```python
# dm_outreach_worker.py, строки 32-53
while not self._stop.is_set():
    await self._process_batch()  # query к БД каждые 5 сек
    await asyncio.wait_for(self._stop.wait(), timeout=interval_seconds)
```

**Оптимизация:**
```python
# Adaptive polling с exponential backoff:
empty_batches_count = 0
min_interval = 5
max_interval = 60

while not self._stop.is_set():
    pending = await self._process_batch()
    
    if not pending:
        empty_batches_count += 1
        interval = min(min_interval * (2 ** empty_batches_count), max_interval)
    else:
        empty_batches_count = 0
        interval = min_interval
    
    await asyncio.wait_for(self._stop.wait(), timeout=interval)
```

**Экономия:** При пустой очереди: 12 queries/min → 1 query/min

---

## 5. Улучшение понимания лида LLM

### 5.1 Обогащение контекста квалификации

**Проблема: LLM получает только текущее сообщение**

**Текущий prompt:**
```python
# template_runtime.py, строки 1343-1373
instruction = f"""
Ты модуль pre-sales скрининга.
Продукт: {product_name}. Категория: {offer_type}.
"""
messages = [
    {"role": "system", "content": instruction},
    {"role": "user", "content": "Вот сообщение из чата:\n{user_message}"}
]
```

**Улучшение:**
```python
# Добавить rich context:
instruction = f"""
Ты модуль pre-sales скрининга.

ПРОДУКТ:
- Название: {product_name}
- Категория: {offer_type}
- УТП: {usp}
- Целевая аудитория: {target_audience}
- Typical pain points: {pain_points}

ТЕКУЩИЙ ЛИД:
- FSM статус: {current_sales_state}
- Предыдущие контакты: {previous_contacts_count}
- Lead score history: {lead_score_trend}
- Последний контакт: {last_contact_date}

ИСТОРИЯ ДИАЛОГА:
{format_conversation_history(recent_history)}

КОНТЕКСТ ЧАТА-ИСТОЧНИКА:
- Тип чата: {chat_type}  # группа/канал/тематическая группа
- Тема чата: {chat_topic}
- Активность лида в чате: {activity_level}
"""
```

**Преимущества:**
- LLM видит "большую картину"
- Более точная квалификация based on history
- Меньше false positives

---

### 5.2 Примеры (few-shot learning)

**Проблема: LLM не знает специфику домена**

**Текущий подход:** Zero-shot classification

**Улучшение:**
```python
# Добавить в system prompt примеры:
examples = """
ПРИМЕРЫ КВАЛИФИКАЦИИ:

Сообщение: "Ищем подрядчика для автоматизации отдела продаж. Бюджет до 500к, срок - месяц."
Классификация: engage_lead
  - intent: target_hot
  - confidence: 0.95
  - reason: "Четкий запрос, названы бюджет и срок"
  - lead_temperature: hot
  - stage_hint: discovery

Сообщение: "Интересно, а как это работает?"
Классификация: engage_lead
  - intent: target_warm
  - confidence: 0.70
  - reason: "Проявлен интерес, но нет конкретики"
  - lead_temperature: warm
  - stage_hint: first_touch

Сообщение: "Спамеры, отвалите"
Классификация: ignore_lead
  - intent: do_not_contact
  - confidence: 0.99
  - reason: "Явный негатив и запрос не контактировать"

Сообщение: "Кто-нибудь знает рецепт борща?"
Классификация: ignore_lead
  - intent: non_target
  - confidence: 0.98
  - reason: "Офтоп, не связано с продуктом"
"""
```

**Источники примеров:**
- Исторические данные с высоким conversion rate
- Ручная разметка владельцем агента
- Synthetic examples от GPT-4

---

### 5.3 Structured reasoning (Chain of Thought)

**Проблема: LLM делает judgment без объяснения логики**

**Текущий подход:** Прямой function call

**Улучшение:**
```python
# Добавить промежуточный шаг reasoning:
reasoning_prompt = """
Перед принятием решения, проанализируй по шагам:

1. INTENT DETECTION:
   - О чем говорит сообщение?
   - Связано ли это с нашим продуктом?
   - Есть ли признаки покупательского намерения?

2. BUYER SIGNALS:
   - Упоминание бюджета/сроков/команды? (buying authority)
   - Вопросы про цену/условия/интеграцию? (active research)
   - Описание проблемы/боли? (pain awareness)

3. CONTEXT EVALUATION:
   - Соответствует ли лид целевой аудитории?
   - Какой этап customer journey? (awareness/consideration/decision)
   - История взаимодействий?

4. DECISION:
   - Engage или ignore?
   - Confidence level?
   - Recommended next stage?

Верни структурированный reasoning, затем сделай function call.
"""
```

**Формат ответа:**
```json
{
    "reasoning": {
        "intent": "Лид спрашивает о возможностях автоматизации",
        "buyer_signals": ["упомянут бюджет", "указан срок"],
        "context": "Подходит под целевую аудиторию (B2B, автоматизация)",
        "decision_rationale": "Высокий intent, четкие сигналы покупки"
    },
    "function_call": "engage_lead",
    "args": {...}
}
```

**Преимущества:**
- Explainable AI (можно показать владельцу почему)
- Более консистентные решения
- Проще debugging и улучшение

---

### 5.4 Multi-dimensional lead scoring

**Проблема: Простая формула score = heat*0.45 + resilience*0.2 + engagement*0.35**

**Текущий подход:**
```python
# template_runtime.py, строки 139
fresh_overall = self._clamp_score_0_100(heat * 0.45 + resilience * 0.2 + engagement * 0.35)
```

**Улучшение - добавить dimensions:**
```python
lead_dimensions = {
    # Existing:
    "heat_score": 0.85,  # прогретость/интерес
    "resilience_score": 0.70,  # устойчивость к возражениям
    "engagement_score": 0.90,  # вовлеченность
    
    # New dimensions:
    "buying_authority_score": 0.75,  # decision-making power
    "budget_readiness_score": 0.60,  # финансовая готовность
    "timing_score": 0.80,  # urgency/timing
    "fit_score": 0.95,  # соответствие ICP (Ideal Customer Profile)
    "competitor_awareness_score": 0.50  # знание альтернатив
}

# Взвешенная агрегация:
weights = {
    "heat": 0.20,
    "resilience": 0.10,
    "engagement": 0.15,
    "buying_authority": 0.25,  # самый важный!
    "budget_readiness": 0.15,
    "timing": 0.10,
    "fit": 0.05
}

overall_score = sum(lead_dimensions[dim] * weights[dim] for dim in dimensions)
```

**LLM prompt для новых dimensions:**
```python
# В qualify_message():
"parameters": {
    "buying_authority_score": {
        "type": "number",
        "description": "0-100: Может ли человек принимать решение о покупке? Founder/C-level=90+, Manager=60-80, Individual=20-40"
    },
    "budget_readiness_score": {
        "type": "number", 
        "description": "0-100: Есть ли бюджет? Назван конкретный=90+, Упомянут диапазон=70, Нет упоминания=30"
    },
    "timing_score": {
        "type": "number",
        "description": "0-100: Срочность? 'Срочно/сейчас'=90+, 'в ближайшие недели'=70, 'когда-нибудь'=20"
    }
}
```

---

### 5.5 Negative signals detection

**Проблема: LLM фокусируется на позитиве, пропускает red flags**

**Улучшение - добавить explicit negative signals:**
```python
# В qualify_message() добавить:
"negative_signals": {
    "type": "array",
    "items": {"type": "string"},
    "description": """
    Отметь все присутствующие негативные сигналы:
    - competitor_mention: упоминает конкурентов
    - price_objection: жалуется на цену
    - time_waster: неясные вопросы без конкретики
    - not_decision_maker: не может принимать решения
    - no_budget: нет бюджета
    - spam_intent: спам/реклама
    - wrong_fit: не соответствует ICP
    """
}
```

**Обработка:**
```python
negative_signals = qualification.get("negative_signals", [])

# Penalties:
if "competitor_mention" in negative_signals:
    lead_score *= 0.8  # -20%
if "no_budget" in negative_signals:
    lead_score *= 0.5  # -50%
if "spam_intent" in negative_signals:
    decision = "ignore"  # автоматический skip
```

---

### 5.6 Persona matching

**Проблема: Нет понимания "кто этот человек"**

**Улучшение - добавить persona classification:**
```python
# В qualify_message():
"persona_type": {
    "type": "string",
    "enum": [
        "founder_ceo",      # основатель/CEO (high authority)
        "manager_head",     # руководитель отдела (medium authority)
        "specialist",       # специалист (low authority)
        "agency_partner",   # партнер/агентство
        "competitor",       # конкурент
        "student_learner",  # студент/изучающий
        "unknown"
    ],
    "description": "Тип персоны на основе сообщения и контекста"
}
```

**Использование:**
```python
persona = qualification.get("persona_type")

# Корректировка approach:
if persona == "founder_ceo":
    stage_hint = "value_pitch"  # сразу на ценность
    min_confidence = 0.60  # ниже порог (не упустить)
elif persona == "specialist":
    stage_hint = "discovery"  # сначала квалификация
    min_confidence = 0.80  # выше порог
elif persona == "competitor":
    decision = "ignore"
```

---

### 5.7 Intent hierarchy

**Проблема: Flat intent classification (target_hot, target_warm, etc)**

**Улучшение - иерархическая классификация:**
```python
intent_hierarchy = {
    "buying": {
        "ready_to_buy": 0.95,      # "Хочу купить сейчас"
        "evaluating": 0.80,         # "Сравниваю варианты"
        "interested": 0.65          # "Интересно узнать больше"
    },
    "problem_solving": {
        "acute_pain": 0.85,         # "У нас горит, нужно решение"
        "exploring": 0.60,          # "Думаем как улучшить процесс"
        "curiosity": 0.40           # "Интересно, что есть на рынке"
    },
    "information_seeking": {
        "product_research": 0.70,   # "Как работает ваш продукт?"
        "general_question": 0.45,   # "Что вообще такое автоматизация?"
        "offtopic": 0.10           # "Кто-нибудь знает..."
    },
    "rejection": {
        "not_interested": -0.20,    # "Не интересно"
        "do_not_contact": -0.50,    # "Не пишите мне"
        "spam_report": -1.0         # "Спам!"
    }
}
```

**LLM prompt:**
```python
"intent_category": {
    "type": "string",
    "enum": ["buying", "problem_solving", "information_seeking", "rejection"]
},
"intent_subcategory": {
    "type": "string",
    "description": "Детализация intent_category"
}
```

**Использование:**
```python
category = qualification.get("intent_category")
subcategory = qualification.get("intent_subcategory")

base_confidence = intent_hierarchy[category][subcategory]

# Корректировка на основе дополнительных факторов:
if "budget" in user_message.lower():
    base_confidence += 0.1
if current_sales_state == "REPLIED_POSITIVE":
    base_confidence += 0.05

final_confidence = min(1.0, base_confidence)
```

---

### 5.8 Contextual prompt adaptation

**Проблема: Одинаковый prompt для всех стадий FSM**

**Текущий подход:** Универсальный prompt в qualify_message()

**Улучшение - адаптивный prompt:**
```python
def get_qualification_prompt_for_state(state: str) -> str:
    if state == "DISCOVERED":
        return """
        Это первый контакт с лидом.
        Фокус: Определить базовый fit и интерес.
        Будь либеральнее с порогом (не упусти потенциальных клиентов).
        """
    
    elif state == "SENT":
        return """
        Мы уже отправили первое сообщение.
        Фокус: Оценить качество ответа и готовность продолжать.
        Ищи сигналы:
        - Конкретные вопросы = high engagement
        - Короткие ответы "да/нет" = low engagement
        - Запрос на встречу/демо = ready for handoff
        """
    
    elif state == "REPLIED_POSITIVE":
        return """
        Лид позитивно ответил.
        Фокус: Определить готовность к handoff или нужен дополнительный nurturing.
        Ищи buying signals:
        - Вопросы про цену/условия/интеграцию
        - Упоминание бюджета/сроков
        - Запрос на контакт с sales/demo
        """
    
    return "..."
```

**Применение:**
```python
# В qualify_message():
state_specific_instruction = get_qualification_prompt_for_state(current_sales_state)
instruction = f"{base_instruction}\n\n{state_specific_instruction}"
```

---

### 5.9 Competitor awareness

**Проблема: LLM не знает контекст конкурентов**

**Улучшение:**
```python
# В template_config добавить:
"competitors": [
    {
        "name": "Competitor A",
        "strengths": ["Дешевле", "Быстрая интеграция"],
        "weaknesses": ["Плохая поддержка", "Ограниченный функционал"],
        "key_differentiators": ["Мы предлагаем 24/7 поддержку", "Больше интеграций"]
    }
]
```

**LLM prompt:**
```python
# В qualify_message():
competitor_context = """
КОНКУРЕНТНАЯ СРЕДА:
{format_competitors(config.get("competitors", []))}

При квалификации учитывай:
- Если лид упоминает конкурента → отметь это в reasoning
- Если сравнивает с конкурентом → high buying intent
- Если уже использует конкурента → оцени переключательные барьеры
"""

# В compose_dm():
if "competitor_mention" in qualification:
    instruction += """
    Лид знает о конкуренте. 
    Мягко подчеркни наши уникальные преимущества без прямого негатива.
    """
```

---

### 5.10 Calibration feedback loop

**Проблема: Нет механизма улучшения на основе результатов**

**Решение - добавить feedback:**
```python
# Новая таблица: AgentSalesQualificationFeedback
class AgentSalesQualificationFeedback:
    agent_id: int
    user_external_id: str
    qualification_decision: str  # engage/ignore
    qualification_confidence: float
    actual_outcome: str  # HANDOFF_CRM/REPLIED_NEGATIVE/NO_REPLY
    was_correct: bool  # True если prediction matched outcome
    feedback_timestamp: datetime
```

**Использование:**
```python
# Периодически анализировать feedback:
async def get_qualification_accuracy(agent_id: int) -> dict:
    feedback = await load_feedback(agent_id, last_30_days=True)
    
    return {
        "precision": correct_engage / total_engage,  # из engage сколько конвертировалось
        "recall": correct_engage / total_should_engage,  # не пропустили ли мы лидов
        "false_positive_rate": wrong_engage / total_engage,
        "false_negative_rate": wrong_ignore / total_ignore,
        "optimal_confidence_threshold": calculate_optimal_threshold(feedback)
    }
```

**Адаптация:**
```python
# Если precision низкая → повысить min_confidence
if accuracy["precision"] < 0.6:
    template_config["min_confidence"] = min(0.90, current + 0.05)

# Если recall низкий → понизить min_confidence  
if accuracy["recall"] < 0.7:
    template_config["min_confidence"] = max(0.60, current - 0.05)
```

**Промпт улучшение:**
```python
# Добавлять примеры ошибок в few-shot:
if false_positives:
    examples += """
    ПРИМЕРЫ ЛОЖНЫХ СРАБАТЫВАНИЙ (не повторяй эти ошибки):
    
    Сообщение: "{false_positive_example.message}"
    Неверная классификация: engage (confidence {fp.confidence})
    Правильно: ignore
    Reason: {fp.reason}
    """
```

---

## 6. Рекомендации по приоритетам

### High Priority (Quick Wins)

1. **Объединить LLM calls** (§4.1)
   - Impact: 50% reduction в costs
   - Effort: Low (2-3 hours)

2. **Убрать compose_dm для ignore** (§4.1)
   - Impact: 40-60% reduction в ненужных генерациях
   - Effort: Low (1 hour)

3. **Объединить database queries** (§4.2)
   - Impact: 3x faster response time
   - Effort: Low (2 hours)

4. **Few-shot examples** (§5.2)
   - Impact: +15-20% accuracy
   - Effort: Medium (4-5 hours + data collection)

### Medium Priority (Notable Improvements)

5. **Multi-dimensional scoring** (§5.4)
   - Impact: More accurate lead prioritization
   - Effort: Medium (6-8 hours)

6. **Negative signals** (§5.5)
   - Impact: Reduce false positives by 30%
   - Effort: Low (2 hours)

7. **Adaptive polling** (§4.7)
   - Impact: 90% reduction в idle queries
   - Effort: Low (1-2 hours)

8. **Follow-up automation** (§3.5)
   - Impact: New feature, увеличивает conversion
   - Effort: High (12+ hours)

### Low Priority (Nice to Have)

9. **A/B testing** (§3.2)
   - Impact: Data-driven optimization
   - Effort: High (16+ hours)

10. **Multi-channel** (§3.8)
    - Impact: Reach expansion
    - Effort: Very High (40+ hours)

---

## 7. Заключение

### Сильные стороны текущей реализации:

1. **Модульная архитектура**: FSM, Tool Registry, Queue Service - четкое разделение ответственности
2. **Безопасность**: Идемпотентность, валидация, confirmation policies
3. **Масштабируемость**: Асинхронный worker, batch processing, retry логика
4. **Гибкость**: Конфигурируемые режимы (draft/semi_auto/auto), настраиваемые tools

### Основные узкие места:

1. **Избыточные LLM вызовы**: 2-3 calls на каждый engage (qualification + compose + tools)
2. **Неоптимальные DB queries**: 3-4 queries для загрузки данных контакта
3. **Простое понимание лида**: Отсутствие negative signals, persona matching, competitor awareness
4. **Нет feedback loop**: Система не учится на результатах

### Ожидаемый эффект от оптимизаций:

- **Performance**: 50-70% reduction в latency (за счет меньшего числа LLM calls и DB queries)
- **Cost**: 40-60% reduction в costs (меньше LLM tokens)
- **Accuracy**: +20-30% improvement в precision/recall (за счет better context и few-shot)
- **Conversion**: +15-25% improvement (за счет follow-ups и multi-dimensional scoring)
