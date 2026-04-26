# Sales Manager Workflow Analysis

Документ описывает фактический workflow шаблона `sales_manager` в проекте (по текущему коду), а также дает пример "живого" чата с таймингами вызовов tools/LLM и примерами payload.

## 1) Где начинается workflow

Основной вход идет через Telegram userbot:

- `backend/app/channels/userbot_manager.py`
  - `_fetch_userbot_configs()` подтягивает `template_type` + `template_config`.
  - `_handle_chat_message()` обрабатывает сообщения из групп/чатов (только для `sales_manager`).
  - `_handle_private_message()` обрабатывает личные сообщения.
  - Для chat scanning ответ в группу не отправляется, сообщение только уходит в backend processing.

Второй вход (вне userbot) — API:

- `backend/app/router_agents/router.py` endpoint `/external/chat` вызывает `get_template_runtime().execute(...)` с `template_type` агента.

## 2) Оркестрация обработки сообщения

Единая точка обработки:

- `backend/app/channels/message_processor.py` -> `MessageProcessor.process()`

Что делает процессор:

1. Нормализует `user_external_id`.
2. Резолвит агента и проверяет:
   - активность/подписку;
   - frozen-user ограничения.
3. Логирует входящее сообщение в `AgentAnalyticsMessage` (role=`user`).
4. Обновляет "портрет чата" (`update_chat_portrait`) если включено `enable_chat_portrait`.
5. Запускает шаблонный runtime: `TemplateRuntimeService.execute(...)`.
6. Логирует:
   - tool events (role=`operator`);
   - fallback события (если были);
   - финальный ответ агента (role=`agent`).

## 3) Обновленная логика `sales_manager`

Файл: `backend/app/services/template_runtime.py`, ветка `_execute_sales_manager(...)`.

### 3.1 Основные этапы

1. **FSM bootstrap**
   - Создает/проверяет контакт в FSM (`DISCOVERED`) через `get_or_create_contact`.

2. **Lead screening через FC (LLM #1)**
   - `qualify_message()` теперь использует function-calling с двумя action:
     - `engage_lead` (писать/продолжать диалог),
     - `ignore_lead` (игнорировать лид).
   - В prompt классификации добавляются:
     - `sales_product_name`, `sales_offer_type`, `sales_usp`,
     - текущая стадия FSM,
     - портрет клиента,
     - recent history по каналу.
   - Если выбран `ignore_lead` или `intent in {non_target, do_not_contact}` -> skip path.
   - Если `confidence < min_confidence` -> skip path (или fallback в QA по флагу).

3. **Qualified / conversation path**
   - FSM: `DISCOVERED -> QUALIFIED`.
   - `retrieve_offer_context()` достает RAG-контекст из knowledge base.
   - `compose_dm()` (LLM #2) формирует сообщение на основе стадии:
     - `first_touch` (мягкое первое касание),
     - `discovery` (выявление боли),
     - `value_pitch` (что изменится после внедрения),
     - `handoff` (перевод на ЛПР/заявку/демо).
   - Все сообщения генерируются LLM с учетом портрета, истории и RAG.

4. **Tool-driven action (LLM #3 + function tools)**
   - `_execute_sales_tools()` создает `SalesToolRegistry`.
   - Модель выбирает function tool.
   - Registry валидирует payload, policy подтверждения, idempotency.
   - При `schedule_dm` создается запись в очереди `agent_sales_dm_queue`.
   - Результат формирует `tool_events`.

5. **FSM post-tool transitions**
   - По `tool_status`:
     - `draft_requires_review` -> `QUALIFIED -> QUEUED`
     - `sent_auto` -> `QUALIFIED -> QUEUED -> SENT`
     - `skipped_*` -> `... -> SKIPPED`

### 3.2 Какие tools доступны в sales registry

`backend/app/services/sales/tool_registry.py`:

- `schedule_dm` — поставить DM в очередь.
- `skip_lead` — пропустить лид с причиной.
- `record_lead_signal` — записать сигнал квалификации.
- `create_crm_lead` — создать лид в CRM (заглушка уровня registry/result).
- `mark_contacted` — отметить контакт как обработанный.

Safety:

- Pydantic-валидация аргументов каждого tool.
- Confirmation policy: `never_confirm | always_confirm | confirm_risky`.
- Идемпотентность: ключ по `(agent_id, user_external_id, tool_name, canonical_args)` c TTL cache.
- Ограничение размера tool arguments.

## 4) Очередь и отправка DM

### 4.1 Очередь

Файл: `backend/app/services/sales/dm_queue_service.py`

- `enqueue_dm()` создает запись `pending`.
- `get_pending_messages()` выбирает готовые записи (включая `scheduled_for`).
- `mark_sent()` / `mark_failed()` ведут статус и retry счетчик.

### 4.2 Фоновый воркер

Файл: `backend/app/services/sales/dm_outreach_worker.py`

- `run_forever()` polling cycle (>=5 сек).
- `_process_batch()` берет батч (по умолчанию 10).
- `_send_message()` шлет через Telethon userbot (`client.send_message`).
- Между отправками throttling (`min_interval_seconds=0.5`).
- Ошибки делятся на retry/non-retry эвристикой (auth/not found -> без retry).

## 5) "Реальный" пример чата с таймингами и payload (обновленный)

Ниже пример одного сообщения из группового чата, где лид квалифицируется и ставится в очередь.
Тайминги примерные, но соответствуют текущей архитектуре вызовов.

### 5.1 Входное событие

- Канал: `telegram_userbot` (group chat)
- Сообщение пользователя:  
  `Ищем подрядчика для AI-автоматизации отдела продаж, есть кейсы?`
- `template_type= sales_manager`
- `mode= draft_only`, `confirmation_policy= never_confirm`, `min_confidence=0.75`
- `sales_product_name= ИИ-автоматизация`
- `sales_offer_type= SaaS + внедрение под ключ`
- `sales_usp= подключение за 5 минут, интеграция с CRM, единый дашборд`

### 5.2 Таймлайн обработки

- `T+000ms` Userbot получает `NewMessage` в чате.
- `T+020ms` `_handle_chat_message()` отфильтровал системные/бот-сообщения, собрал `MessageRequest`.
- `T+060ms` `MessageProcessor.process()` стартовал, записал analytics role=`user`.
- `T+120ms` `update_chat_portrait()` -> **LLM call #0** (опционально, если portrait enabled).
- `T+380ms` Runtime `execute()` вошел в `_execute_sales_manager`.
- `T+410ms` FSM `get_or_create_contact` (`DISCOVERED`).
- `T+430ms` `qualify_message()` -> **LLM call #1** (function-calling decision).
- `T+760ms` Получен `tool_call=engage_lead` c `intent/confidence/stage_hint`.
- `T+790ms` FSM transition `DISCOVERED -> QUALIFIED`.
- `T+840ms` `retrieve_offer_context()` (RAG search).
- `T+980ms` `compose_dm()` -> **LLM call #2**.
- `T+1340ms` Получен черновик DM.
- `T+1370ms` `_execute_sales_tools()` -> **LLM call #3** (tool selection).
- `T+1540ms` Модель выбрала tool `schedule_dm` с аргументами.
- `T+1580ms` `SalesToolRegistry.execute_tool("schedule_dm", ...)`:
  - валидация,
  - idempotency check,
  - `DmQueueService.enqueue_dm(...)`.
- `T+1670ms` `tool_status=draft_requires_review`, запись operator analytics.
- `T+1710ms` FSM transition `QUALIFIED -> QUEUED`.
- `T+1760ms` `MessageProcessor` завершает обработку.
- `T+~5s..10s` `DmOutreachWorker` подбирает запись из очереди (зависит от polling-окна).

### 5.3 Что уходит в LLM и что приходит (по шагам)

#### A) Lead screening FC (`qualify_message`)

Уходит в LLM:

- `system`:
  - base prompt агента;
  - инструкция "верни только JSON с intent/confidence/reason";
  - (опционально) portrait block.
- `user`:
  - сырой текст сообщения из чата.

Приходит из LLM (function call):

```json
{
  "tool_call": {
    "name": "engage_lead",
    "arguments": {
      "intent": "target_hot",
      "confidence": 0.91,
      "reason": "явный запрос подрядчика",
      "lead_temperature": "hot",
      "stage_hint": "first_touch",
      "handoff_ready": false
    }
  }
}
```

#### B) Stage-aware DM generation (`compose_dm`)

Уходит в LLM:

- `system`: стиль outreach + текущая стадия + инструкция по стадии + продукт/категория/УТП.
- `user`:
  - исходное сообщение,
  - результат квалификации,
  - RAG контекст (склейка источников).

Приходит из LLM (plain text):

`Здравствуйте! Увидел ваше сообщение в чате про AI-автоматизацию. Если вам актуально, могу коротко подсказать, как внедрить это в вашем процессе и какие кейсы подойдут под ваш формат.`

## 7) Обновление формы создания агента

Для `sales_manager` в форме добавлены поля:

- `Продукт` (`sales_product_name`) — обязательное поле.
- `Что продаете (категория)` (`sales_offer_type`) — обязательное поле.
- `УТП` (`sales_usp`) — опционально.
- `Системный промпт` — обязательный (как и раньше).
- Документация/ссылки для RAG — как и раньше.

Эти поля сохраняются в `template_config` и используются в LLM-решениях на каждом шаге воронки.

#### C) Tool decision (`_execute_sales_tools`)

Уходит в LLM:

- `system`: "управляй действиями через function tools, не пиши свободный ответ".
- `user`: 
  - JSON классификации,
  - черновик outreach,
  - канал.
- `tools`: JSON schema доступных функций (`schedule_dm`, ...).

Приходит из LLM:

- `assistant.tool_calls`:
  - `name="schedule_dm"`
  - `arguments={"text":"...","target_user_external_id":"123456789"}`

После локального исполнения tool в runtime добавляется сообщение role=`tool` с результатом:

```json
{
  "ok": true,
  "tool_name": "schedule_dm",
  "tool_status": "draft_requires_review",
  "latency_ms": 34,
  "result": {"queued": true, "status": "draft_requires_review"}
}
```

## 6) Важные наблюдения и ограничения текущей реализации

- В chat scanning режиме сообщение из группы не получает ответ в сам чат (по дизайну).
- Фактическая отправка в личку асинхронная и зависит от воркера очереди.
- `tool_status="sent_auto"` в runtime отражает policy/режим, а не гарантирует мгновенную доставку в Telegram (реальная доставка подтверждается позже через очередь/воркер).
- Подтверждение risky tools определяется по маркерам в тексте (`подтверждаю`, `confirm`, и т.д.), если policy требует подтверждение.
- Источник правды по действиям — analytics записи `operator` + статусы FSM + таблица очереди DM.

