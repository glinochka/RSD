# План оптимизации backend: дедупликация и развитие ООП

Документ фиксирует технический долг в `backend/app`, приоритеты рефакторинга и границы — что делать и чего **не** делать.

**Принцип:** расширять уже работающие абстракции (`CRMProvider`, `BookingProvider`, `MessageProcessor`), а не вводить ООП ради ООП.

**Связанная документация:** [docs/README.md](../docs/README.md), [docs/backend/README.md](../docs/backend/README.md), [TECH_STACK_EVALUATION.md](./TECH_STACK_EVALUATION.md).

---

## 1. Текущее состояние

### 1.1. ООП, которое уже работает (не ломать)

| Область | Паттерн | Код |
|---------|---------|-----|
| CRM | `CRMProvider` ABC + `build_provider()` | `services/crm/providers/`, `services/crm/factory.py` |
| Booking | `BookingProvider` ABC + `AdminBookingService` | `services/admin_booking/providers/`, `service.py` |
| Домены booking | `DomainConfig` registry | `services/admin_booking/domains.py` |
| Сообщения | `MessageProcessor` + `Channel` enum | `channels/message_processor.py` |
| HTTP tools | `executor.py` (SSRF, auth) отдельно от registry | `services/http_integration/` |
| Tool confirmation | общий модуль | `services/tool_confirmation.py` |
| Telephony | `OrchestratorWorker`, pipeline, Redis | `telephony/` |
| Article publish | `ArticlePublisher` Protocol | `services/article_publisher/publishers/base.py` |
| Инфраструктура | `PgLeaderLock`, `BaseDAO` | `channels/leader_lock.py`, `BaseDAO.py` |

### 1.2. ООП задумано, но не доделано

| Абстракция | Статус |
|------------|--------|
| `ChannelManager` ABC | Описан в `channels/base.py`, **ни один менеджер не реализует** |
| `UserbotManager`, `MaxUserbotManager`, `WhatsAppUserbotManager` | ~90% одинаковый `run_forever()` polling loop |

### 1.3. Основные дубли (технический долг)

| # | Hotspot | Копий | Файлы |
|---|---------|-------|-------|
| 1 | LLM tool registry boilerplate | 5 | `crm/`, `admin_booking/`, `admin_applications/`, `sales/`, `http_integration/` tool_registry.py |
| 2 | Userbot polling loop | 3 | `userbot_manager.py`, `max_userbot_manager.py`, `whatsapp_userbot_manager.py` |
| 3 | `_fetch_*_configs()` SQL | 4 | те же + `max_bot_manager.py` |
| 4 | Inbound pipeline (human delay → process → reply) | 3 | handlers в userbot-менеджерах |
| 5 | Userbot JWT create/decode | 4 scope | `router_agents/router.py` (~2650–2810) |
| 6 | `_parse_template_config()` | 9 | booking, message_processor, sales, ai_mop, content_job, telephony/agent_guards |
| 7 | WhatsApp JID normalization | 4 | message_processor, router_agents, outreach_send, whatsapp_userbot_manager |
| 8 | WhatsApp bridge HTTP client | 2 | whatsapp_userbot_manager, sales/outreach_send |
| 9 | Admin DAO pagination | 4+ | router_users, router_agents, router_admin, router_payments dao |

### 1.4. Крупные монолиты (отдельная задача — декомпозиция, не ООП)

| Файл | Строк | Рекомендация |
|------|-------|--------------|
| `router_agents/router.py` | ~9900 | Разбить на sub-routers по доменам |
| `services/template_runtime.py` | ~3100 | Не абстрагировать; выносить только утилиты |
| `services/website_generation_service.py` | ~1350 | Оставить связным pipeline |

---

## 2. Цели рефакторинга

1. **Убрать механический дубль** — один источник правды для template_config, idempotency, JWT scopes, WhatsApp JID.
2. **Доделать задуманное ООП** — `ChannelManager` → `PollingChannelManager`.
3. **Сохранить доменные границы** — CRM Amo ≠ Bitrix, Telegram ≠ WhatsApp transport.
4. **Не ухудшить тесты** — каждый этап сопровождается прогоном `backend/app/tests/`.

---

## 3. Фазы работ

### Фаза 0 — подготовка (1–2 дня)

- [x] Зафиксировать baseline: `pytest backend/app/tests/` green.
- [ ] Добавить в CI (если ещё нет) smoke на `test_admin_booking_tool_registry`, `test_telephony_*`, `test_sales_*`.
- [x] Создать ветку `refactor/backend-dedup` или вести мелкими PR по фазам. *(выполнено одним коммитом в `host/telephony`)*

**Критерий готовности:** все тесты зелёные до начала изменений.

---

### Фаза 1 — быстрые wins (низкий риск, 2–3 дня)

#### 1.1. `parse_agent_template_config()` — единая утилита

**Создать:** `backend/app/utils/agent_template_config.py`

```python
def parse_agent_template_config(raw: str | dict | None) -> dict[str, Any]:
    ...
```

**Заменить копии в:**
- `services/admin_booking/service.py`
- `channels/message_processor.py`
- `telephony/agent_guards.py`
- `services/content_job_service.py`
- `services/sales/sales_followup_service.py`, `agent_outreach_service.py`
- `services/ai_mop/service.py`, `followup_service.py`

**Тесты:** unit-тест на edge cases (None, invalid JSON, non-dict).

**ROI:** ~9 копий → 1 функция, ~1 час работы.

---

#### 1.2. `utils/whatsapp_jid.py`

**Создать:**
- `normalize_whatsapp_external_id(value) -> str`
- `external_id_to_jid(value) -> str` (с валидацией)
- `bridge_post(path, json, timeout)` — общий HTTP-клиент к WA bridge

**Заменить в:**
- `channels/message_processor.py`
- `router_agents/router.py` (`_whatsapp_user_external_to_jid`)
- `services/sales/outreach_send.py`
- `channels/whatsapp_userbot_manager.py` (analytics helper — отдельная функция с документированной семантикой)

**Тесты:** перенести/дополнить `test_sales_contact_pool`, добавить unit на JID.

---

#### 1.3. `ScopedAuthToken` для userbot JWT

**Создать:** `backend/app/utils/scoped_auth_token.py`

```python
class ScopedAuthToken:
    def __init__(self, scope: str, ttl_minutes: int = 10): ...
    def create(self, **claims) -> str: ...
    def decode(self, token: str, *, required_keys: list[str] | None = None) -> dict: ...
```

**Scopes:** `userbot_auth`, `userbot_qr_auth`, `max_userbot_auth`, `whatsapp_userbot_auth`.

**Заменить:** 4 пары `_create_*` / `_decode_*` в `router_agents/router.py`.

**Тесты:** unit на scope mismatch, expiry, missing required keys.

---

**Критерий готовности фазы 1:** нет регрессий в tests; grep по `_parse_template_config` — только util + thin wrappers (если нужны).

**Статус:** ✅ выполнено (`bc0e9f2`, 2026-06-28).

---

### Фаза 2 — tool registry core (средний риск, 3–5 дней)

#### 2.1. Общий модуль `services/tool_registry_core.py`

**Вынести:**
| Компонент | Описание |
|-----------|----------|
| `IdempotencyCache` | TTL get/set, cleanup |
| `parse_tool_arguments(raw, model_type) -> BaseModel` | JSON + Pydantic + size limit |
| `build_openai_tool_schema(name, model, description)` | OpenAI function schema |
| `ToolExecutionResult` | dataclass: ok, data, latency_ms, error |
| `now_utc()` | единый helper |

**Оставить в доменных registry:**
- `_TOOL_MODELS`, descriptions
- `_execute_impl(tool_name, args)` — бизнес-логика
- domain-specific safety (CRM field denylist, booking YooKassa, sales confirmation)
- `*NeedsConfirmationError` — по домену

**Порядок миграции:**
1. `sales/tool_registry.py` (проще всего)
2. `crm/tool_registry.py`
3. `admin_applications/tool_registry.py`
4. `http_integration/tool_registry.py`
5. `admin_booking/tool_registry.py` (самый тяжёлый — последним)

**Важно:** idempotency cache — **per-registry instance**, не глобальный (избежать коллизий tool names).

**Тесты:** существующие `test_admin_booking_tool_registry.py`, CRM/sales registry tests должны проходить без изменения поведения.

---

**Критерий готовности фазы 2:** 5 registry используют core; дубли `_cleanup_idempotency_cache` / `_now_utc` удалены.

**Статус:** ✅ выполнено (`bc0e9f2`, 2026-06-28).

---

### Фаза 3 — Channel managers (средний риск, 4–6 дней)

#### 3.1. `PollingChannelManager(ChannelManager)`

**Создать:** `backend/app/channels/polling_manager.py`

```python
class PollingChannelManager(ChannelManager):
    def __init__(
        self,
        *,
        lock_key: int,
        lock_name: str,
        poll_interval_setting: str,
        channel_name: str,
    ): ...

    async def fetch_configs(self) -> list[dict]: ...      # abstract
    async def run_worker(self, cfg: dict, stop: Event): ...  # abstract
    def config_fingerprint(self, cfg: dict) -> str: ...  # optional override

    async def run_forever(self) -> None: ...  # shared
    async def shutdown(self) -> None: ...     # shared
    @property
    def active_count(self) -> int: ...
```

**Мигрировать:**
1. `MaxUserbotManager` (самый простой)
2. `WhatsAppUserbotManager` (fingerprint restart logic — override)
3. `UserbotManager` (Telegram-specific trigger words остаются в `run_worker`)

`MaxBotManager` — оценить отдельно (другой transport, но тот же fetch pattern).

#### 3.2. `AgentChannelConnectionDAO.fetch_active_configs(provider)`

**Создать** в `router_agents/dao.py` (сейчас DAO почти пустой):

```python
async def fetch_active_channel_configs(
    provider: str,
    *,
    template_types: set[str] | None = None,
) -> list[dict[str, Any]]: ...
```

**Убрать:** `_fetch_userbot_configs`, `_fetch_max_configs`, `_fetch_whatsapp_configs`, `_fetch_max_bot_configs`.

#### 3.3. `human_reply_pipeline()` (опционально, внутри фазы 3)

**Создать:** `backend/app/channels/inbound_pipeline.py`

Context manager для фаз human delay (online → read → process → typing) с injectable hooks для channel-specific send.

**Не объединять:** Telethon `action()`, WA bridge read/typing endpoints.

---

**Критерий готовности фазы 3:**
- `UserbotManager`, `MaxUserbotManager`, `WhatsAppUserbotManager` наследуют `PollingChannelManager`
- `ChannelManager` ABC используется
- polling loop — одна реализация

**Статус:** ✅ выполнено (`bc0e9f2`, 2026-06-28). `human_reply_pipeline` — не делали (опционально).

---

### Фаза 4 — декомпозиция router_agents (высокий объём, 5–10 дней)

**Цель:** уменьшить `router_agents/router.py` без изменения API contract.

**Предлагаемые sub-routers:**

| Sub-router | Префикс / тег | Содержимое |
|------------|---------------|------------|
| `router_agents/channels/telegram.py` | `/api/agents` | userbot auth, QR, session |
| `router_agents/channels/max.py` | `/api/agents` | MAX userbot |
| `router_agents/channels/whatsapp.py` | `/api/agents` | WA userbot, bridge |
| `router_agents/crm.py` | `/api/agents` | CRM connections |
| `router_agents/booking.py` | `/api/agents` | admin booking CRUD |
| `router_agents/integrations.py` | `/api/agents` | HTTP integrations |
| `router_agents/core.py` | `/api/agents` | CRUD агента, templates, analytics |

**Подключение:** `router_agents/router.py` становится aggregator:

```python
router = APIRouter(prefix="/api/agents")
router.include_router(core_router)
router.include_router(channels_telegram_router)
...
```

**Порядок:** выносить по одному домену за PR; не трогать schemas/dao.

---

**Критерий готовности фазы 4:** `router.py` < 2000 строк; OpenAPI paths не изменились.

**Статус:** ✅ выполнено (`bc0e9f2`, 2026-06-28). `router.py` — 24 строки (aggregator).

---

### Фаза 5 — DAO и admin pagination (низкий приоритет, 2–3 дня)

**Оценить** идентичность `count_for_admin` / `list_for_admin` в:
- `router_users/dao.py`
- `router_agents/dao.py`
- `router_admin/dao.py`
- `router_payments/dao.py`

**Если паттерн совпадает:** helper в `BaseDAO`:

```python
async def admin_list(
    model, filters, search_fields, page, page_size, order_by
) -> tuple[list, int]: ...
```

**Если отличается** — оставить как есть, задокументировать различия.

**Статус:** backlog.

---

## 4. Что НЕ делать

| Область | Причина |
|---------|---------|
| Глубокая унификация CRM AmoCRM / Bitrix24 | Разные API; общий `_request` base — максимум |
| Единый `UserbotClient` interface | Telethon / PyMax / WA bridge несовместимы на transport layer |
| Рефакторинг `template_runtime.py` в class hierarchy | Риск сломать tool routing и template-specific prompts |
| Слияние `website_html_cleanup` и `website_sanitization_service` | Разные задачи: декоративная очистка vs XSS |
| Глобальный idempotency cache для всех registries | Коллизии имён tools между доменами |
| `CrmBookingProvider` → один mega-provider | Decorator pattern осознанный: local DB = source of truth |
| Telephony module split | Уже декомпозирован |
| ООП для FastAPI route handlers | Composition (sub-routers) вместо inheritance |
| `admin_booking/tool_registry.py` execute elif-chain | Вынести plumbing (фаза 2), бизнес-ветки не трогать |

---

## 5. Матрица приоритетов

| Задача | ROI | Риск | Фаза |
|--------|-----|------|------|
| `parse_agent_template_config` | высокий | низкий | 1 |
| `whatsapp_jid` + `bridge_post` | высокий | низкий | 1 |
| `ScopedAuthToken` | средний | низкий | 1 |
| `tool_registry_core` | высокий | средний | 2 |
| `PollingChannelManager` | высокий | средний | 3 |
| `fetch_active_channel_configs` | средний | средний | 3 |
| `human_reply_pipeline` | средний | средний | 3 |
| sub-routers `router_agents` | средний | высокий | 4 |
| `BaseDAO.admin_list` | низкий | низкий | 5 |

---

## 6. Метрики успеха

| Метрика | Было | Цель | Факт (2026-06-28) |
|---------|------|------|-------------------|
| Копий `_parse_template_config` | 9 | 1 | 1 (`utils/agent_template_config.py`) |
| Копий idempotency cache logic | 5 | 0 (в core) | 0 (`services/tool_registry_core.py`) |
| Строк дублированного polling loop | ~300 | < 50 | вынесено в `channels/polling_manager.py` |
| `router_agents/router.py` строк | ~9900 | < 2000 (после фазы 4) | 24 |
| Реализаций `ChannelManager` | 0 | 3+ | 3 (Telegram, MAX, WhatsApp userbot) |
| Регрессии в pytest | 0 | 0 | unit-тесты dedup/core/polling добавлены |

---

## 7. Порядок PR (рекомендуемый)

```
PR-1  utils/agent_template_config.py + замены
PR-2  utils/whatsapp_jid.py + bridge_post
PR-3  utils/scoped_auth_token.py + router_agents cleanup
PR-4  services/tool_registry_core.py + sales registry
PR-5  tool_registry_core → crm, applications, http_integration
PR-6  tool_registry_core → admin_booking
PR-7  channels/polling_manager.py + MaxUserbotManager
PR-8  PollingChannelManager → WhatsApp, Telegram
PR-9  AgentChannelConnectionDAO.fetch_active_channel_configs
PR-10 router_agents: вынос telegram userbot routes
PR-11 router_agents: вынос whatsapp, max, crm, booking (по одному PR)
```

Каждый PR — отдельно мержится после green CI.

---

## 8. Риски и митигация

| Риск | Митигация |
|------|-----------|
| Сломать tool execution в production | Поэтапная миграция registry; не менять `_execute_impl` сигнатуры |
| Race в channel managers при рефакторинге | Сохранить fingerprint restart logic WhatsApp; тесты на leader lock |
| JWT scope regression | Unit-тесты на все 4 scope до и после |
| Рост import cycles | Новые utils без зависимости от routers |
| Scope creep | Фазы 1–3 — обязательный минимум; 4–5 — по мере ресурсов |

---

## 9. Связь с документацией модулей

После каждой фазы обновлять README соответствующего модуля в `docs/backend/`:

| Фаза | Документация |
|------|--------------|
| 1 | `docs/backend/agents/`, `docs/backend/channels/` |
| 2 | `docs/backend/crm/`, `docs/backend/admin-booking/`, `docs/backend/http-integrations/` |
| 3 | `docs/backend/channels/README.md` — секция PollingChannelManager |
| 4 | `docs/backend/agents/ROUTERS.md` (создать) |

---

## 10. Чеклист перед стартом фазы

- [x] Прочитан этот план и согласован scope PR
- [x] Baseline tests green
- [x] Нет параллельных крупных изменений в тех же файлах
- [ ] Для фазы 3+: проверена работа userbot managers на staging

---

## 11. Прогресс

| Фаза | Статус | Коммит | Дата | Примечание |
|------|--------|--------|------|------------|
| 0 | частично | — | 2026-06-28 | CI smoke — backlog |
| 1 | ✅ | `bc0e9f2` | 2026-06-28 | utils: template_config, whatsapp_jid, ScopedAuthToken |
| 2 | ✅ | `bc0e9f2` | 2026-06-28 | `tool_registry_core`, 5 domain registries |
| 3 | ✅ | `bc0e9f2` | 2026-06-28 | PollingChannelManager, fetch_active_channel_configs |
| 4 | ✅ | `bc0e9f2` | 2026-06-28 | sub-routers, aggregator router.py |
| 5 | backlog | — | — | BaseDAO.admin_list |

**Документация:** обновлены `docs/backend/agents/`, `docs/backend/channels/`, `docs/backend/crm/`, `docs/backend/admin-booking/`, `docs/backend/http-integrations/` (коммит после `bc0e9f2`).

**Следующие шаги:**
1. Staging-проверка userbot managers (Telegram / MAX / WhatsApp).
2. Фаза 5 — по необходимости.
3. Опционально: `human_reply_pipeline`, CI smoke tests.

---

*Документ создан: 2026-06-28. Обновлено: 2026-06-28 (фазы 1–4 завершены).*


