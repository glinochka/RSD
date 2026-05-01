# CRM Admin Template Upgrade Plan

## Текущее состояние

### Архитектура
Шаблон `crm_admin` реализован как единый template_type с параметром `domain_type` в `template_config`, который определяет подшаблон. Сейчас поддерживается два значения: `beauty_salon` и `dental_clinic`.

### Проблемы текущей реализации

1. **Жёсткие хардкоды ролей и ресурсов:**
   - `AdminStaff.role` ограничен CHECK-constraint: `IN ('master','doctor')`
   - `AdminResource.resource_type` ограничен: `IN ('chair','room','equipment')`
   - `AdminService.target_role` привязан к тем же ролям
   - Эти ограничения не позволяют добавить новые домены без миграции БД

2. **Дублирование ресурсов (ключевая проблема пользователя):**
   - В салоне красоты: 1 кресло = 1 мастер. Отдельный ресурс "кресло" избыточен, если мастер = кресло
   - В стоматологии: 1 кабинет = 1 врач, если в клинике каждый врач работает в своём кабинете
   - Но: в крупных клиниках кабинет может быть разделяемым ресурсом (2 врача делят 1 кабинет) — тогда разделение оправдано
   - Нужна **опциональность** ресурсов: пользователь сам решает, нужны ли ему отдельные ресурсы

3. **Захардкоженная доменная инструкция:**
   - `_crm_admin_domain_instruction()` — простой if/else на два домена
   - `buildAdminDomainPromptAppendix()` на фронте — дублирование логики

4. **Дублирование UI на фронте:**
   - Отдельные state-массивы `beautyMasters` / `dentalDoctors` и `beautyServices` / `dentalServices`
   - Полная копия UI-блока для каждого домена с минимальными различиями (label "Мастера" vs "Врачи")

---

## План апгрейда

### Фаза 1: Доменный реестр (Domain Registry)

**Цель:** Заменить хардкоды `CRM_DOMAIN_TYPES` на расширяемый реестр подшаблонов.

#### 1.1 Создать файл конфигурации доменов

**Файл:** `backend/app/services/admin_booking/domains.py`

Реестр подшаблонов — словарь Python, описывающий каждый домен:

```python
DOMAIN_REGISTRY: dict[str, DomainConfig] = {
    "beauty_salon": DomainConfig(
        label_ru="Салон красоты",
        label_en="Beauty Salon",
        staff_role_default="master",
        staff_label_ru="Мастер",
        resource_examples=["chair"],       # подсказки для пользователя
        resources_mode="optional",         # "none" | "optional" | "required"
        resource_linked_to_staff=True,     # по умолчанию 1 ресурс = 1 сотрудник
        domain_instruction_ru=(
            "Предметная область: салон красоты. "
            "Используй терминологию мастер/услуга и уточняй предпочтения по времени."
        ),
        default_services_hints=["Стрижка", "Окрашивание", "Маникюр"],
    ),
    "dental_clinic": DomainConfig(
        label_ru="Стоматологическая клиника",
        label_en="Dental Clinic",
        staff_role_default="doctor",
        staff_label_ru="Врач",
        resource_examples=["room"],
        resources_mode="optional",
        resource_linked_to_staff=True,
        domain_instruction_ru=(
            "Предметная область: стоматологическая клиника. "
            "Используй терминологию врач/процедура и уточняй длительность приема."
        ),
        default_services_hints=["Осмотр", "Чистка", "Лечение кариеса"],
    ),
    "auto_service": DomainConfig(
        label_ru="Автосервис",
        label_en="Auto Service",
        staff_role_default="mechanic",
        staff_label_ru="Механик",
        resource_examples=["bay", "lift"],  # подъёмник, бокс
        resources_mode="optional",
        resource_linked_to_staff=False,     # механик и подъёмник — разные сущности
        domain_instruction_ru=(
            "Предметная область: автосервис. "
            "Используй терминологию механик/бокс/подъёмник/работа. "
            "Уточняй марку и модель автомобиля, характер неисправности."
        ),
        default_services_hints=["Замена масла", "Диагностика", "Шиномонтаж"],
    ),
    "spa": DomainConfig(
        label_ru="СПА-салон",
        label_en="SPA",
        staff_role_default="therapist",
        staff_label_ru="Терапевт / Массажист",
        resource_examples=["room", "cabin"],
        resources_mode="optional",
        resource_linked_to_staff=False,     # комната и терапевт — разные сущности
        domain_instruction_ru=(
            "Предметная область: СПА-салон. "
            "Используй терминологию терапевт/кабинет/процедура. "
            "Уточняй предпочтения по типу процедуры и длительности."
        ),
        default_services_hints=["Массаж классический", "Обёртывание", "Сауна"],
    ),
    "med_center": DomainConfig(
        label_ru="Медицинский центр",
        label_en="Medical Center",
        staff_role_default="doctor",
        staff_label_ru="Врач",
        resource_examples=["room", "equipment"],
        resources_mode="optional",
        resource_linked_to_staff=False,     # кабинет может быть разделяемым
        domain_instruction_ru=(
            "Предметная область: медицинский центр. "
            "Используй терминологию врач/кабинет/приём/процедура. "
            "Уточняй специализацию врача и направление."
        ),
        default_services_hints=["Первичный приём", "УЗИ", "Анализы", "ЭКГ"],
    ),
    "custom": DomainConfig(
        label_ru="Другое (настроить вручную)",
        label_en="Custom",
        staff_role_default="specialist",
        staff_label_ru="Специалист",
        resource_examples=[],
        resources_mode="optional",
        resource_linked_to_staff=False,
        domain_instruction_ru="",  # пустая — пользователь пишет свою инструкцию
        default_services_hints=[],
        custom_domain=True,        # флаг для UI — показать расширенные настройки
    ),
}
```

#### 1.2 Dataclass `DomainConfig`

```python
@dataclass(frozen=True)
class DomainConfig:
    label_ru: str
    label_en: str
    staff_role_default: str
    staff_label_ru: str
    resource_examples: list[str]
    resources_mode: str               # "none" | "optional" | "required"
    resource_linked_to_staff: bool    # если True — ресурс создаётся автоматически под сотрудника
    domain_instruction_ru: str
    default_services_hints: list[str]
    custom_domain: bool = False
```

#### 1.3 API-эндпоинт для получения реестра доменов

**Файл:** `backend/app/router_agents/router.py`

```
GET /api/agents/admin/domain-registry
```

Возвращает JSON со всеми доступными доменами, их настройками и подсказками. Фронтенд использует этот эндпоинт вместо хардкода `CRM_DOMAIN_OPTIONS`.

---

### Фаза 2: Миграция БД — снятие жёстких ограничений

**Цель:** Убрать хардкоды ролей и типов ресурсов из CHECK-constraints.

#### 2.1 Миграция `AdminStaff`

- **Убрать** CHECK-constraint `ck_admin_staff_role` (`IN ('master','doctor')`)
- **Заменить** на мягкую валидацию: `String(32)` + валидация на уровне приложения через `DOMAIN_REGISTRY[domain_type].staff_role_default`
- Старые значения `master` и `doctor` продолжают работать — обратная совместимость

#### 2.2 Миграция `AdminResource`

- **Убрать** CHECK-constraint `ck_admin_resources_type` (`IN ('chair','room','equipment')`)
- **Расширить** `resource_type` до `String(32)` с произвольными значениями
- Добавить в `AdminResource` **nullable** поле `linked_staff_id` (FK → `admin_staff.id`):
  - Когда `resource_linked_to_staff=True` — ресурс создаётся автоматически при создании сотрудника и привязывается через `linked_staff_id`
  - Когда `resource_linked_to_staff=False` — ресурсы управляются отдельно, `linked_staff_id = NULL`

#### 2.3 Миграция `AdminService`

- Поле `target_role` — убрать привязку к `master/doctor`, разрешить произвольные строки (максимум 32 символа)
- Валидация: при создании service проверять, что `target_role` соответствует `DOMAIN_REGISTRY[domain_type].staff_role_default` или кастомной роли

#### 2.4 Новые индексы

- `AdminResource`: добавить индекс на `linked_staff_id` для быстрого поиска привязанных ресурсов

#### 2.5 Скрипт миграции данных

Alembic-миграция:
1. Убрать старые CHECK-constraints
2. Расширить String(16) → String(32) где требуется
3. Добавить колонку `linked_staff_id`
4. Для существующих агентов с `domain_type=beauty_salon` — привязать кресла к мастерам (если count совпадает)
5. Для существующих агентов с `domain_type=dental_clinic` — привязать кабинеты к врачам

---

### Фаза 3: Backend — Унификация логики

#### 3.1 Обновить `_crm_admin_domain_instruction()`

**Файл:** `backend/app/services/template_runtime.py`, строки 817-826

Заменить if/else на lookup из реестра:

```python
@staticmethod
def _crm_admin_domain_instruction(*, domain_type: str) -> str:
    from .admin_booking.domains import DOMAIN_REGISTRY
    config = DOMAIN_REGISTRY.get(domain_type)
    if config is None or not config.domain_instruction_ru:
        return ""
    return config.domain_instruction_ru
```

Для `custom` доменов — инструкция берётся из `template_config.custom_domain_instruction` (пользователь пишет её в UI).

#### 3.2 Обновить `_migrate_crm_admin_config()`

**Файл:** `backend/app/router_agents/router.py`, строки 503-639

- Заменить `CRM_DOMAIN_TYPES = {"beauty_salon", "dental_clinic"}` на `set(DOMAIN_REGISTRY.keys())`
- Добавить поддержку новых полей в `template_config`:
  - `resources_enabled: bool` — включены ли ресурсы (по умолчанию из `DomainConfig.resources_mode`)
  - `resource_linked_to_staff: bool` — привязаны ли ресурсы к сотрудникам
  - `custom_staff_role: str | None` — кастомная роль для домена "custom"
  - `custom_staff_label: str | None` — кастомное название роли для UI
  - `custom_resource_types: list[str] | None` — кастомные типы ресурсов для домена "custom"
  - `custom_domain_instruction: str | None` — кастомная инструкция для домена "custom"

#### 3.3 Обновить `_resolve_admin_agent()`

**Файл:** `backend/app/router_agents/router.py`, строки 1890-1929

- Заменить хардкод `CRM_DOMAIN_TYPES` на `DOMAIN_REGISTRY.keys()`

#### 3.4 Обновить `_default_crm_admin_config()`

**Файл:** `backend/app/router_agents/router.py`, строки 481-500

- Добавить новые поля с дефолтами:
  - `resources_enabled: True`
  - `resource_linked_to_staff: True`
  - Остальное — без изменений

#### 3.5 Логика привязки ресурсов к сотрудникам

**Файл:** `backend/app/services/admin_booking/providers/local.py`

При `resource_linked_to_staff=True`:
- `create_staff()` — автоматически создаёт ресурс и привязывает его через `linked_staff_id`
- `delete_staff()` — автоматически удаляет привязанный ресурс
- `list_resources()` — скрывает привязанные ресурсы (они не отображаются как отдельные)
- `create_appointment()` — при указании `staff_id` автоматически подставляет привязанный `resource_id`
- `check_availability()` — проверка слотов учитывает привязанные ресурсы автоматически

При `resource_linked_to_staff=False`:
- Ресурсы управляются отдельно, как сейчас
- Пользователь явно создаёт ресурсы и привязывает их к расписанию

#### 3.6 Обновить tool_registry

**Файл:** `backend/app/services/admin_booking/tool_registry.py`

- `_ListStaffArgs.role` — убрать `pattern="^(master|doctor)$"`, заменить на `max_length=32`
- `_ListServicesArgs.target_role` — аналогично
- Когда `resource_linked_to_staff=True` — не выдавать ресурсные инструменты (`list_resources` etc.) в `tools_for_llm()`, так как ресурсы автоматически следуют за сотрудниками. Это упростит жизнь LLM

#### 3.7 Обновить системный промпт

**Файл:** `backend/app/services/template_runtime.py`, строка 631+

Добавить в системный промпт контекст о ресурсной модели:
- Если `resource_linked_to_staff=True`: "Каждый сотрудник — это одновременно рабочее место. Не нужно отдельно выбирать ресурс."
- Если `resource_linked_to_staff=False`: "Сотрудники и рабочие места (ресурсы) — это отдельные сущности. При записи может потребоваться выбрать и сотрудника, и ресурс."

---

### Фаза 4: Frontend — Универсальный UI

#### 4.1 Обновить `CRM_DOMAIN_OPTIONS`

**Файл:** `frontend/src/pages/createAgent.jsx`, строки 30-33

Заменить хардкод на динамическую загрузку из `GET /api/agents/admin/domain-registry`:

```jsx
const CRM_DOMAIN_OPTIONS = domainRegistry.map(d => ({
  value: d.key,
  label: d.label_ru,
}));
```

#### 4.2 Унифицировать state сотрудников и услуг

**Файл:** `frontend/src/pages/createAgent.jsx`

Вместо отдельных `beautyMasters` / `dentalDoctors` — единый `staffList`:

```jsx
const [staffList, setStaffList] = useState([]);
const [serviceList, setServiceList] = useState([]);
```

Label и role берутся из выбранного домена реестра:
- `roleLabel` = `domainConfig.staff_role_default`
- Заголовок блока = `domainConfig.staff_label_ru` (множественное число)

#### 4.3 Убрать дублирование UI-блоков

Заменить два блока "Настройки салона красоты" (строки 1605-1669) и "Настройки стоматологии" (строки 1670-1728) на **один универсальный блок**:

```jsx
<div className="admin-template-onboarding-block">
  <h4>{domainConfig.label_ru} — Настройки</h4>
  
  {/* Ресурсы — показывать только если resources_mode !== "none" */}
  {domainConfig.resources_mode !== "none" && !domainConfig.resource_linked_to_staff && (
    <ResourceConfigSection
      resourceExamples={domainConfig.resource_examples}
      resources={resources}
      setResources={setResources}
    />
  )}
  
  {/* Сотрудники — всегда */}
  <label>{domainConfig.staff_label_ru}:</label>
  <CardCarousel addCard={...}>
    {staffList.map(s => <StaffCard roleLabel={domainConfig.staff_role_default} ... />)}
  </CardCarousel>
  
  {/* Услуги — всегда */}
  <label>Услуги:</label>
  <CardCarousel addCard={...}>
    {serviceList.map(s => <ServiceCard staffList={staffList} ... />)}
  </CardCarousel>
</div>
```

#### 4.4 Блок настроек для домена "custom"

Когда `domain_type === "custom"`:

```jsx
<div className="admin-template-onboarding-block">
  <h4>Кастомный домен — Настройка</h4>
  
  <label>Название роли сотрудника:</label>
  <input placeholder="Например: Тренер, Инструктор, Консультант" ... />
  
  <label>Доменная инструкция (для ИИ):</label>
  <textarea placeholder="Опишите сферу деятельности..." ... />
  
  <FeatureToggle
    title="Включить отдельные ресурсы (комнаты, оборудование)"
    helpText="Включите, если сотрудники и рабочие места — разные сущности"
  />
  
  {resourcesEnabled && (
    <ResourceConfigSection ... />
  )}
  
  <label>Сотрудники:</label>
  <CardCarousel ... />
  
  <label>Услуги:</label>
  <CardCarousel ... />
</div>
```

#### 4.5 Обновить `buildAdminDomainPromptAppendix()`

**Файл:** `frontend/src/pages/createAgent.jsx`, строки 64-90

Сделать универсальным — не зависящим от конкретного домена:

```jsx
const buildAdminDomainPromptAppendix = (domainConfig, staffList, serviceList, resources) => {
  const staffNames = staffList.map(m => `${m.firstName} ${m.lastName}`.trim()).filter(Boolean);
  const serviceNames = serviceList.map(s => s.title).filter(Boolean);
  
  const lines = [
    '---',
    'Admin domain profile:',
    `domain_type: ${domainConfig.key}`,
    `staff_role: ${domainConfig.staff_role_default}`,
    `staff: ${staffNames.join(', ') || '-'}`,
    `services: ${serviceNames.join(', ') || '-'}`,
  ];
  
  if (!domainConfig.resource_linked_to_staff && resources.length > 0) {
    lines.push(`resources: ${resources.map(r => r.title).join(', ')}`);
  }
  
  return lines.join('\n');
};
```

#### 4.6 Обновить логику создания агента (onSubmit)

**Файл:** `frontend/src/pages/createAgent.jsx`, строки 831-865

Вместо `const staffRole = domainType === 'beauty_salon' ? 'master' : 'doctor'`:

```jsx
const staffRole = domainConfig.staff_role_default;
```

Логика создания ресурсов при `resource_linked_to_staff=false`:
- После создания staff, создать ресурсы отдельными вызовами API

---

### Фаза 5: Тестирование и обратная совместимость

#### 5.1 Обратная совместимость

- Существующие агенты с `domain_type=beauty_salon` и `domain_type=dental_clinic` **продолжают работать без изменений**
- `_migrate_crm_admin_config()` автоматически подхватывает новые дефолты
- Старые значения `role=master/doctor` и `resource_type=chair/room/equipment` остаются валидными
- CHECK-constraints удалены, но приложение валидирует значения на уровне кода

#### 5.2 Что тестировать

1. **Создание нового агента** для каждого домена (beauty_salon, dental_clinic, auto_service, spa, med_center, custom)
2. **Custom домен**: ввод произвольной роли, произвольных типов ресурсов, кастомной инструкции
3. **resource_linked_to_staff=true**: убедиться, что ресурс создаётся автоматически при создании staff и удаляется при удалении
4. **resource_linked_to_staff=false**: убедиться, что ресурсы управляются отдельно
5. **Миграция существующих агентов**: открыть настройки старого агента — всё должно работать
6. **LLM-поведение**: агент должен правильно использовать терминологию выбранного домена
7. **Booking flow**: полный цикл записи (check_availability → create_appointment → reschedule → cancel) для каждого домена

---

### Порядок реализации (recommended)

| Шаг | Что делать | Файлы |
|-----|-----------|-------|
| 1 | Создать `domains.py` с `DOMAIN_REGISTRY` и `DomainConfig` | `backend/app/services/admin_booking/domains.py` |
| 2 | Alembic-миграция: убрать CHECK-constraints, расширить поля, добавить `linked_staff_id` | `backend/app/alembic/versions/xxx_admin_flexible_domains.py` |
| 3 | Обновить router.py: `CRM_DOMAIN_TYPES`, `_migrate_crm_admin_config()`, `_resolve_admin_agent()`, добавить endpoint `/admin/domain-registry` | `backend/app/router_agents/router.py` |
| 4 | Обновить tool_registry.py: убрать pattern-constraints на role | `backend/app/services/admin_booking/tool_registry.py` |
| 5 | Обновить local.py: логика auto-create/delete ресурса при `resource_linked_to_staff` | `backend/app/services/admin_booking/providers/local.py` |
| 6 | Обновить template_runtime.py: `_crm_admin_domain_instruction()`, системный промпт | `backend/app/services/template_runtime.py` |
| 7 | Обновить createAgent.jsx: убрать дублирование, универсальный UI, загрузка реестра | `frontend/src/pages/createAgent.jsx` |
| 8 | Исправить рассинхронизации: confirm_appointment, find_next_available, list_appointments | `router.py`, `tool_registry.py`, `createAgent.jsx` |
| 9 | Обновить AgentDetailedAnalyticsPage.jsx: динамические resource_type, staff labels | `frontend/src/pages/AgentDetailedAnalyticsPage.jsx` |
| 10 | Тесты и ручная проверка | — |

---

### Краткая сводка изменений по файлам

#### Backend

| Файл | Действие |
|------|----------|
| `backend/app/services/admin_booking/domains.py` | **СОЗДАТЬ** — реестр доменов |
| `backend/app/alembic/versions/xxx_...py` | **СОЗДАТЬ** — миграция БД |
| `backend/app/alembic/models.py` | **ИЗМЕНИТЬ** — убрать CHECK-constraints из метаданных моделей, добавить `linked_staff_id` в `AdminResource`, расширить String(16) → String(32) |
| `backend/app/router_agents/router.py` | **ИЗМЕНИТЬ** — `CRM_DOMAIN_TYPES`, `_migrate_crm_admin_config()`, `_resolve_admin_agent()`, `_default_crm_admin_config()`, новый endpoint |
| `backend/app/services/template_runtime.py` | **ИЗМЕНИТЬ** — `_crm_admin_domain_instruction()`, системный промпт |
| `backend/app/services/admin_booking/tool_registry.py` | **ИЗМЕНИТЬ** — убрать pattern-constraints, условная выдача tool-set |
| `backend/app/services/admin_booking/providers/local.py` | **ИЗМЕНИТЬ** — auto-link ресурсов к staff, скрытие linked ресурсов |
| `backend/app/services/admin_booking/providers/base.py` | **ИЗМЕНИТЬ** — обновить сигнатуры при необходимости |

#### Frontend

| Файл | Действие |
|------|----------|
| `frontend/src/pages/createAgent.jsx` | **ИЗМЕНИТЬ** — унификация UI, загрузка реестра, кастомный домен, убрать дублирование |
| `frontend/src/pages/AgentDetailedAnalyticsPage.jsx` | **ИЗМЕНИТЬ** — вкладка Operations: убрать хардкод `resource_type` select (chair/room/equipment) → динамические типы из домена; адаптировать staff labels |
| `frontend/src/services/agentService.js` | **ИЗМЕНИТЬ** — добавить метод `getAdminDomainRegistry()` для нового API-эндпоинта |

---

### Фаза 6: Исправление рассинхронизаций

При анализе обнаружены рассинхронизации между фронтендом и бэкендом, которые нужно исправить в рамках апгрейда:

#### 6.1 `confirm_appointment` — объявлен, но не реализован

- `DEFAULT_BOOKING_ALLOWED_TOOLS` в `router.py` включает `confirm_appointment`
- Но `_TOOL_MODELS` в `tool_registry.py` **не содержит** этого ключа → tool никогда не отдаётся LLM
- **Решение:** либо реализовать tool (вызов `AdminBookingService.confirm_appointment`), либо убрать из дефолтов

#### 6.2 `find_next_available` — добавляется фронтом, отсутствует в бэкенд-дефолте

- Фронт (`createAgent.jsx`) явно добавляет `find_next_available` в `allowed_booking_tools`
- `DEFAULT_BOOKING_ALLOWED_TOOLS` в `router.py` его **не включает**
- **Решение:** добавить `find_next_available` в `DEFAULT_BOOKING_ALLOWED_TOOLS`

#### 6.3 `list_appointments` — в UI-списке нет, но в бэкенд-дефолте есть

- Фронт передаёт фиксированный список из 7 tools, не включая `list_appointments`
- Бэкенд-дефолт включает 8 tools с `list_appointments`
- **Решение:** при переходе на динамический реестр — синхронизировать tool-списки через `DOMAIN_REGISTRY`

#### 6.4 Operations UI (`AgentDetailedAnalyticsPage.jsx`)

- Dropdown `resource_type` жёстко содержит `chair | room | equipment`
- При добавлении новых доменов (auto_service → `bay`/`lift`) этот dropdown станет невалидным
- **Решение:** загружать допустимые `resource_type` из `DOMAIN_REGISTRY` или из `template_config` агента

---

### Риски и ограничения

1. **Миграция БД** — самый рискованный шаг. Перед запуском в проде нужен бэкап. Alembic-миграция должна быть идемпотентной
2. **LLM-промпт** — новые домены могут потребовать тонкой настройки инструкций. Домен `custom` особенно рискован — пользователь может написать плохую инструкцию
3. **Обратная совместимость** — все API-ответы должны сохранить формат. Клиенты, использующие `domain_type=beauty_salon`, не должны сломаться
4. **CRM-провайдер** — логика CRM (AmoCRM, Bitrix24) не зависит от домена и не затрагивается этим апгрейдом
