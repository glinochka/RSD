# RSD: портал цифровизации бизнеса — видение и план рефакторинга

> Переход от «платформы ИИ-агентов» к **единому порталу цифровизации бизнеса**.  
> **1 этап = 1 промпт** для Cursor Agent. Этапы идут последовательно.  
> Статус: **планирование** · Обновлено: июнь 2026

---

## Содержание

1. [Видение продукта](#1-видение-продукта)
2. [Текущее состояние (as-is)](#2-текущее-состояние-as-is)
3. [Целевая архитектура (to-be)](#3-целевая-архитектура-to-be)
4. [UX и навигация](#4-ux-и-навигация)
5. [Создание проекта (AI-first)](#5-создание-проекта-ai-first)
6. [Инструменты проекта — детали](#6-инструменты-проекта--детали)
7. [Модель данных](#7-модель-данных)
8. [Этапы реализации](#8-этапы-реализации)
9. [Глоссарий](#9-глоссарий)

---

## 1. Видение продукта

### 1.1. Что такое RSD

**RSD — единый портал цифровизации бизнеса.** Аналог AmoCRM, но существенно продвинутее: все инструменты для автоматизации, цифровизации и роста продаж — в одном месте, no-code, из коробки, с ИИ в ядре.

Пользователь описывает бизнес → получает **готовый цифровой офис**: команда ИИ-сотрудников, CRM, сайт, контент, каналы. Всё уже настроено, правки — по желанию.

### 1.2. Единица продукта — Проект

**1 проект = 1 малый/средний бизнес** или **1 отдел в крупной компании**.

Примеры:
- Салон красоты «Lumi Beauty» — один проект
- Отдел продаж компании «Феникс Логистик» — один проект
- Филиал стоматологии — один проект

У одного пользователя (аккаунта) может быть несколько проектов.

### 1.3. Инструменты проекта

| Инструмент | Описание |
|------------|----------|
| **Единая CRM** | Одна база клиентов на проект. **Автоматически ведётся ИИ-агентами**: каждый диалог, заявка, запись дополняет карточку клиента. Данные используются всеми агентами при работе с клиентом. |
| **Мультиагентная система** | Несколько ИИ-сотрудников с разными ролями в одном проекте. Пример: **Администратор** принимает входящие заявки и записывает; **МОП** занимается холодными продажами, партизанским маркетингом, рассылками. Агенты делят одну CRM. |
| **ИИ контент-завод** | Полный цикл производства контента. Упор на **короткие вертикальные видео**. Публикация в соцсети. |
| **Каналы — для агентов** | Мессенджеры (Telegram, WhatsApp, MAX…) + телефония. Канал подключается на уровне проекта, **пользователь выбирает, какой агент его обрабатывает**. |
| **Каналы — для контент-завода** | TikTok, Pinterest, YouTube, Instagram. |
| **ИИ конструктор лендингов** | Сайт/лендинг проекта. AI-генерация из брифа + визуальный редактор. |
| **ИИ-менеджер** | Отдельный агент, с которым **владелец бизнеса общается о делах компании**: успехи, показатели, что улучшить. Имеет доступ к метрикам и CRM проекта. |

### 1.4. Процесс создания проекта

1. Пользователь открывает **окно с наводящими вопросами** + пишет **краткий бриф** о бизнесе.
2. Данные передаются **LLM**.
3. LLM создаёт проект **из коробки**:
   - нужные агенты по шаблонам (`crm_admin`, `sales_manager`, `qa`, `content_factory`, `ai_manager`…);
   - системные промпты под нишу;
   - CRM с pipeline под отрасль;
   - черновик лендинга;
   - настройки контент-завода (если уместно).
4. Пользователь видит **preview** → вносит правки → запускает.
5. Каналы и оплата — **после** создания, не блокируют старт.

### 1.5. Позиционирование

| | Было | Стало |
|---|------|-------|
| Категория | No-code платформа для ИИ-агентов | Портал цифровизации бизнеса |
| Hero | «ИИ-агент за 5 минут» | «Цифровой офис вашего бизнеса за 10 минут» |
| Аналог | Chatbot builder | AmoCRM × AI × no-code |
| Единица | Агент | Проект (бизнес / отдел) |

---

## 2. Текущее состояние (as-is)

### 2.1. Архитектура сейчас

```
User
 └── Agent (центральная сущность — нет Project)
      ├── Каналы (per agent)
      ├── CRM Amo/Bitrix (per agent)
      ├── Booking DB (per agent, crm_admin)
      ├── Sales contacts (per agent, sales_manager)
      ├── Website (optional, привязан к agent_id)
      └── content_factory (in_development, per agent)
```

### 2.2. Навигация сейчас

- `/agents` — список агентов
- `/create-agent` — тяжёлый wizard (~3000 строк)
- Сайт — внутри карточки агента
- CRM — разрознена, агенты не делят клиентов

### 2.3. Что уже есть и переиспользуем

| Модуль | Статус | Путь |
|--------|--------|------|
| Шаблоны `qa`, `crm_admin`, `sales_manager` | Production | `createAgent.jsx`, `agent_template_pricing.py` |
| Website builder + AI generation | Production | `frontend/src/website-builder/` |
| Мульти-канальность | Production | `AgentChannelConnection`, bridges |
| Booking / admin | Production | `AdminAppointment`, `admin_booking/` |
| Sales outreach / cold DM | Production | `sales/fsm.py`, `AgentSalesContact` |
| Content factory pipeline | Backend ready, UI blocked | `content_factory_worker.py`, `AgentContentJob` |
| Telephony | Demo | `telephony_bridge/` |
| External CRM Amo/Bitrix | Production | `services/crm/` |
| RAG / KB | Production | Qdrant, `AgentDocument` |

### 2.4. Главные проблемы

1. Agent-first UX не отражает «цифровой офис бизнеса».
2. CRM per agent — мультиагентность на данных не работает.
3. Onboarding слишком сложный — канал обязателен до ценности.
4. Content factory, ai_manager, телефония — не интегрированы в единый portal UX.
5. Нет агента-менеджера для владельца бизнеса.

---

## 3. Целевая архитектура (to-be)

```
User (аккаунт)
 └── Project (бизнес / отдел)
      ├── BusinessProfile (бриф, отрасль, AI-метаданные)
      │
      ├── ProjectCrm                          ← единая CRM
      │    ├── Contacts (авто-заполнение агентами)
      │    ├── Leads / Deals (pipeline)
      │    ├── Appointments
      │    └── Activity Timeline
      │
      ├── Agents[]                            ← мультиагентная команда
      │    ├── Администратор (crm_admin)
      │    ├── МОП (sales_manager)
      │    ├── Консультант (qa)
      │    ├── ИИ-менеджер (ai_manager)       ← для владельца
      │    └── …
      │
      ├── ContentFactory                      ← контент-завод проекта
      │    ├── Jobs pipeline (script → render → publish)
      │    └── Social channels (TikTok, IG, YouTube, Pinterest)
      │
      ├── Channels[]                          ← каналы проекта
      │    ├── type: messenger | telephony | social
      │    └── assigned_agent_id              ← какой агент обрабатывает
      │
      ├── Website                             ← лендинг проекта
      ├── ProjectKnowledge (RAG)              ← общая база знаний
      ├── Integrations (Amo, Bitrix, YooKassa)
      └── Analytics                           ← метрики для ИИ-менеджера и UI
```

### Принципы

- **Project-first** — всё внутри проекта.
- **CRM auto-maintained** — агенты пишут в CRM при каждом значимом действии.
- **AI-first create** — бриф → LLM → готовый проект.
- **Каналы отдельно от агентов** — подключил Telegram → назначил агента.
- **Out of the box** — минимум решений до первой ценности.

---

## 4. UX и навигация

### 4.1. Маршруты

| Маршрут | Назначение |
|---------|------------|
| `/projects` | Список проектов |
| `/projects/create` | AI-first создание (анкета + бриф) |
| `/projects/:id` | Dashboard — обзор проекта |
| `/projects/:id/agents` | ИИ-команда |
| `/projects/:id/agents/:agentId` | Настройки агента |
| `/projects/:id/crm` | CRM |
| `/projects/:id/crm/contacts/:contactId` | Карточка клиента + timeline |
| `/projects/:id/website` | Лендинг |
| `/projects/:id/content` | Контент-завод |
| `/projects/:id/channels` | Каналы (мессengers, телефония, соцсети) |
| `/projects/:id/manager` | Чат с ИИ-менеджером |
| `/projects/:id/analytics` | Аналитика |
| `/projects/:id/settings` | Настройки, интеграции, биллинг |
| `/projects/:id/knowledge` | База знаний |

**Navbar:** Мои проекты · Создать проект · Документация · Цены

**Редиректы:** `/agents` → `/projects`, `/create-agent` → `/projects/create`

### 4.2. Dashboard проекта

```
┌──────────────────────────────────────────────────────────────┐
│  Lumi Beauty                              [⚙] [📊] [💬 Менеджер]│
├───────────┬──────────────────────────────────────────────────┤
│ Обзор     │  Метрики: диалоги · лиды · записи · контент · сайт│
│ ИИ-команда│  ─────────────────────────────────────────────── │
│ CRM       │  ИИ-команда (карточки: Админ ✓ · МОП ✓ · Менеджер)│
│ Сайт      │  ─────────────────────────────────────────────── │
│ Контент   │  CRM: последние клиенты и лиды                   │
│ Каналы    │  ─────────────────────────────────────────────── │
│ Менеджер  │  Быстрые действия                                │
│ Аналитика │                                                  │
│ Настройки │                                                  │
└───────────┴──────────────────────────────────────────────────┘
```

### 4.3. Раздел «Каналы»

Единый экран двух типов каналов:

**Для агентов (коммуникации):**
- Telegram bot / userbot, WhatsApp, MAX, телефония
- При подключении: dropdown «Какой агент обрабатывает этот канал»

**Для контент-завода (публикация):**
- TikTok, Instagram, YouTube, Pinterest
- Привязка к content factory pipeline

---

## 5. Создание проекта (AI-first)

### 5.1. UI анкеты

**Наводящие вопросы (пошагово или одной формой):**

1. Как называется ваш бизнес / отдел?
2. Чем занимаетесь? (свободный текст / бриф)
3. Отрасль / ниша
4. Основные продукты или услуги
5. Кто ваши клиенты?
6. Как сейчас приходят заявки? (мессengers, телефон, сайт, офлайн)
7. Главные задачи (продажи / запись / поддержка / контент / всё сразу)
8. Есть ли сайт или соцсети? (ссылки, опционально)
9. Город / регион (опционально)

Пользователь может дописать **свободный бриф** в конце.

### 5.2. LLM provisioning

```
POST /api/projects/provision
  → LLM анализирует бриф
  → Определяет: какие агенты, промпты, CRM pipeline, нужен ли контент-завод
  → Создаёт Project + Agents + ProjectCrm + Website draft + ContentFactory config
  → Возвращает preview

GET /api/projects/{id}/provision/status
  → прогресс генерации сайта и т.д.
```

### 5.3. Preview и запуск

Пользователь видит:
- Карточки созданных агентов (роль, промпт — можно отредактировать)
- CRM pipeline
- Превью лендинга
- Контент-завод (если создан)

Кнопки: **«Запустить проект»** · **«Изменить»** · **«Добавить агента»**

---

## 6. Инструменты проекта — детали

### 6.1. Единая CRM

- **Single source of truth** для всех клиентских данных в проекте.
- Агенты через CRM tools **создают/обновляют** контакты, лиды, записи, notes.
- Каждое действие → запись в `ProjectCrmActivity` (timeline).
- Карточка клиента: все каналы (telegram id, phone, email), история всех агентов.
- Опционально: sync с AmoCRM / Bitrix24 (одно подключение на проект).
- Identity resolution: merge по phone / email / telegram id.

### 6.2. Мультиагентная система

| Агент | Шаблон | Задача |
|-------|--------|--------|
| Администратор | `crm_admin` | Входящие заявки, запись, расписание |
| МОП | `sales_manager` | Холодные продажи, рассылки, партизанский маркетинг |
| Консультант | `qa` | Ответы на вопросы, база знаний |
| ИИ-менеджер | `ai_manager` | Советник владельца, метрики, стратегия |
| Контент-завод | `content_factory` | Генерация и публикация видео |

Handoff: МОП квалифицировал → лид в CRM → Администратор видит и записывает.

### 6.3. ИИ контент-завод

- Pipeline: тема/бриф → сценарий (LLM) → генерация видео (Kling) → публикация.
- Привязан к **проекту**, не к отдельному агенту.
- Каналы публикации: TikTok, Instagram, YouTube, Pinterest.
- Фокус: **короткие вертикальные видео**.
- Backend уже частично есть: `content_factory_worker.py`, `AgentContentJob`.

### 6.4. ИИ-менеджер

- Шаблон `ai_manager` — агент для **владельца бизнеса**, не для клиентов.
- Доступ к: метрикам проекта, CRM summary, статусу агентов, контент-плану, сайту.
- UI: отдельный раздел `/projects/:id/manager` — чат-интерфейс.
- Отвечает на: «Как дела за неделю?», «Сколько лидов?», «Что улучшить в продажах?»

### 6.5. ИИ конструктор лендингов

- Один основной сайт на проект (landing pages later).
- AI-генерация при provisioning из BusinessProfile.
- Редактор: `frontend/src/website-builder/` (переиспользовать).
- Виджет агента на сайте → пишет в ProjectCrm.

---

## 7. Модель данных

### 7.1. Новые таблицы

```python
Project(id, owner_id, name, slug, industry, status, created_at, updated_at)

ProjectBusinessProfile(project_id, description, services_json, goals_json,
                       region, contacts_json, ai_generation_metadata)

ProjectCrmContact(project_id, name, phone, email, external_ids_json,
                  source, assigned_agent_id, metadata_json, ...)

ProjectCrmLead(project_id, contact_id, pipeline_stage, title, value,
               created_by_agent_id, ...)

ProjectCrmActivity(project_id, contact_id, agent_id, activity_type,
                 payload_json, created_at)

ProjectChannel(id, project_id, channel_type,  # messenger|telephony|social
               provider, assigned_agent_id, credentials, is_active, ...)

ProjectContentFactory(project_id, config_json, is_active)

ProjectDocument(project_id, title, source_type, qdrant_point_ids, ...)
```

### 7.2. Изменения существующих

```python
Agent          + project_id, display_name, role_description, crm_permissions_json
Website        + project_id (primary), agent_id (widget agent)
AgentCrmConnection → project_id (one per project)
Admin* tables  + project_id
AgentContentJob → project_id (via content factory module)
```

### 7.3. API (целевое)

```
/api/projects
/api/projects/provision
/api/projects/{id}/business-profile
/api/projects/{id}/crm/contacts|leads|activities
/api/projects/{id}/agents
/api/projects/{id}/channels
/api/projects/{id}/content
/api/projects/{id}/website
/api/projects/{id}/manager/chat
/api/projects/{id}/analytics
/api/projects/{id}/documents
```

---

## 8. Этапы реализации

> **Как пользоваться:** выполняй этапы по порядку. Копируй текст из блока **Промпт** в Cursor Agent.  
> Не начинай следующий этап, пока не выполнены зависимости.  
> Каждый этап рассчитан на **одну сессию** агента.

---

### Этап 1. Модель Project в БД + миграция данных

**Зависимости:** нет  
**Результат:** таблицы `projects`, `project_business_profiles`; колонка `agents.project_id`; скрипт backfill (1 agent = 1 project).

**Scope:**
- Alembic migration
- SQLAlchemy models
- Скрипт `migrate_agents_to_projects.py`
- Не трогать frontend

**Промпт:**
```
Реализуй Этап 1 из REFACTORING_AND_UX.md:

1. Добавь модели Project и ProjectBusinessProfile в backend/app/alembic/models.py
2. Добавь project_id (nullable сначала) в Agent
3. Создай Alembic migration
4. Напиши backend/scripts/migrate_agents_to_projects.py — для каждого Agent создаёт Project с именем агента и проставляет project_id
5. Добавь relationship User → projects, Project → agents

Не меняй frontend и API роутеры. Не делай project_id NOT NULL — это будет после backfill.
```

---

### Этап 2. Backend API проектов (CRUD)

**Зависимости:** Этап 1  
**Результат:** `GET/POST/PATCH/DELETE /api/projects`, ownership check, список агентов проекта.

**Scope:**
- `backend/app/router_projects/` — router, schemas, service
- Mount в `server.py`
- Тесты базовых endpoints

**Промпт:**
```
Реализуй Этап 2 из REFACTORING_AND_UX.md:

1. Создай backend/app/router_projects/ (router.py, schemas.py, service.py)
2. Endpoints: GET /api/projects (list), POST /api/projects, GET /api/projects/{id}, PATCH /api/projects/{id}, DELETE /api/projects/{id}
3. GET /api/projects/{id}/agents — список агентов проекта
4. Проверка ownership: только owner может управлять проектом
5. Подключи router в server.py
6. Добавь базовые тесты

Не трогай frontend. Существующие /api/agents/* не удаляй.
```

---

### Этап 3. Frontend — маршруты, Navbar, редиректы

**Зависимости:** Этап 2  
**Результат:** `/projects` работает, `/agents` редиректит, Navbar «Мои проекты» / «Создать проект».

**Scope:**
- `App.jsx`, `constants.js`, `Navbar.jsx`, `seo.js`
- `projectService.js` — API client
- Redirects, без полного dashboard

**Промпт:**
```
Реализуй Этап 3 из REFACTORING_AND_UX.md:

1. Добавь NAVIGATION_ROUTES: PROJECTS, PROJECT_CREATE, PROJECT(id)
2. Создай frontend/src/services/projectService.js
3. Обнови Navbar: «Мои проекты» → /projects, «Создать проект» → /projects/create
4. В App.jsx: redirect /agents → /projects, /create-agent → /projects/create
5. Обнови seo.js — private prefixes /projects
6. Пока используй заглушку ProjectsPage (можно временно re-export agentsPage)

Не реализуй dashboard и CRM — только навигация и API client.
```

---

### Этап 4. Страница списка проектов

**Зависимости:** Этап 3  
**Результат:** `/projects` показывает карточки проектов пользователя (не агентов).

**Scope:**
- Новая `ProjectsPage.jsx` или рефакторинг list-view из `agentsPage.jsx`
- Карточка: название, отрасль, кол-во агентов, статус, дата

**Промпт:**
```
Реализуй Этап 4 из REFACTORING_AND_UX.md:

1. Создай frontend/src/pages/ProjectsPage.jsx — список проектов через projectService
2. Карточка проекта: name, industry, agents count, status, created_at
3. Клик → /projects/:id
4. Empty state: «Создайте первый проект» + CTA на /projects/create
5. Подключи в App.jsx вместо заглушки
6. agentsPage.jsx пока не удаляй — используется на следующих этапах

Стиль — в духе существующего agentsPage list view.
```

---

### Этап 5. Shell dashboard проекта (layout + sidebar)

**Зависимости:** Этап 4  
**Результат:** `/projects/:id` с sidebar и nested routes (заглушки разделов).

**Scope:**
- `ProjectLayout.jsx`, `ProjectSidebar.jsx`
- Routes: overview, agents, crm, website, content, channels, manager, analytics, settings
- Overview — базовые метрики-placeholder

**Промпт:**
```
Реализуй Этап 5 из REFACTORING_AND_UX.md:

1. Создай ProjectLayout.jsx + ProjectSidebar.jsx
2. Sidebar пункты: Обзор, ИИ-команда, CRM, Сайт, Контент, Каналы, Менеджер, Аналитика, Настройки
3. Nested routes в App.jsx под /projects/:id/*
4. ProjectDashboardPage.jsx (Обзор) — header с названием проекта, placeholder метрик, placeholder блоков
5. Остальные разделы — placeholder pages с заголовком

Загрузка project по id из API. 404 если не найден / не owner.
```

---

### Этап 6. ИИ-команда внутри проекта

**Зависимости:** Этап 5  
**Результат:** `/projects/:id/agents` — управление агентами проекта (перенос логики из agentsPage).

**Scope:**
- `ProjectAgentsPage.jsx`
- Reuse detail panel из agentsPage
- Фильтрация агентов по project_id

**Промпт:**
```
Реализуй Этап 6 из REFACTORING_AND_UX.md:

1. Создай ProjectAgentsPage.jsx — список агентов проекта (GET /api/projects/{id}/agents)
2. Перенеси/переиспользуй panel управления агентом из agentsPage.jsx (промпт, каналы, документы, billing)
3. URL: /projects/:id/agents и /projects/:id/agents/:agentId
4. Убери зависимость от «глобального» списка агентов — всё в контексте projectId
5. «Добавить агента» — пока ведёт на /create-agent?projectId=X (временно)

Не удаляй agentsPage.jsx — добавь redirect /agents/:id → соответствующий project agent.
```

---

### Этап 7. UI создания проекта — анкета и бриф

**Зависимости:** Этап 3  
**Результат:** `/projects/create` — форма с наводящими вопросами и полем брифа. Submit пока создаёт пустой project или mock.

**Scope:**
- `ProjectCreatePage.jsx` — multi-step или single form
- Вопросы из §5.1 документа
- POST на `/api/projects` с business profile (без LLM)

**Промпт:**
```
Реализуй Этап 7 из REFACTORING_AND_UX.md:

1. Создай ProjectCreatePage.jsx на /projects/create
2. Форма: название, отрась, бриф (textarea), услуги, как приходят клиенты, главные задачи, регион, ссылки (optional)
3. Наводящие подсказки/placeholder к каждому полю
4. Backend: расширь POST /api/projects — принимает business profile fields, сохраняет в ProjectBusinessProfile
5. После submit — redirect на /projects/:id (пока без AI provisioning)

Красивый UX, progress indicator если multi-step. Без LLM на этом этапе.
```

---

### Этап 8. AI Provisioning — LLM создаёт агентов и промпты

**Зависимости:** Этап 7  
**Результат:** `POST /api/projects/provision` — LLM анализирует бриф, создаёт агентов с промптами.

**Scope:**
- `backend/app/services/project_provisioning/`
- Industry templates
- Создание agents с system_prompt, welcome_message, template_config
- Без website и CRM пока

**Промпт:**
```
Реализуй Этап 8 из REFACTORING_AND_UX.md:

1. Создай backend/app/services/project_provisioning/ (service.py, industry_templates.py, prompt_builder.py)
2. POST /api/projects/provision — принимает business profile, вызывает LLM
3. LLM определяет набор агентов (crm_admin, sales_manager, qa, ai_manager, content_factory) по брифу
4. Создаёт Project + BusinessProfile + Agents с generated system_prompt и welcome_message
5. Industry templates: beauty_salon, b2b_sales, generic — defaults для промптов
6. Возвращает preview: список созданных агентов с ролями и промптами

Не генерируй website и CRM на этом этапе. Переиспользуй template runtime и agent creation logic.
```

---

### Этап 9. Preview provisioning + интеграция в create flow

**Зависимости:** Этап 8  
**Результат:** После анкеты — экран preview сгенерированного проекта, редактирование промптов, «Запустить».

**Scope:**
- Frontend preview step после формы
- Polling / synchronous provision
- Edit prompts before launch

**Промпт:**
```
Реализуй Этап 9 из REFACTORING_AND_UX.md:

1. ProjectCreatePage: после формы → вызов POST /api/projects/provision → экран Preview
2. Preview показывает: карточки агентов (display_name, role, system_prompt editable, welcome_message editable)
3. Кнопки: «Запустить проект» → redirect /projects/:id; «Назад» → редактировать анкету
4. PATCH /api/projects/{id}/agents/{agentId} для правок промптов до запуска
5. Loading state во время LLM provisioning (30-60 сек)

UX: пользователь видит что AI создал, может подправить, потом enters dashboard.
```

---

### Этап 10. ProjectCrm — модели и API

**Зависимости:** Этап 1  
**Результат:** таблицы CRM + REST API contacts, leads, activities.

**Scope:**
- Models: ProjectCrmContact, ProjectCrmLead, ProjectCrmActivity
- `backend/app/router_projects/crm.py` или `services/project_crm/`
- CRUD + list with pagination

**Промпт:**
```
Реализуй Этап 10 из REFACTORING_AND_UX.md:

1. Добавь модели ProjectCrmContact, ProjectCrmLead, ProjectCrmActivity в models.py + migration
2. Default pipeline stages per industry (json config)
3. API под /api/projects/{id}/crm/:
   - GET/POST /contacts, GET/PATCH /contacts/{id}
   - GET/POST /leads, PATCH /leads/{id} (stage change)
   - GET /activities?contact_id=, POST /activities
4. Ownership через project_id

Без frontend и без интеграции в agent runtime — только data layer и API.
```

---

### Этап 11. CRM UI — контакты и pipeline

**Зависимости:** Этап 10, Этап 5  
**Результат:** `/projects/:id/crm` — таблица контактов + kanban/list pipeline лидов.

**Scope:**
- `ProjectCrmPage.jsx`
- Contacts table, leads pipeline
- Без timeline detail пока

**Промпт:**
```
Реализуй Этап 11 из REFACTORING_AND_UX.md:

1. Создай ProjectCrmPage.jsx на /projects/:id/crm
2. Tab/section «Контакты» — таблица: имя, телефон, email, источник, assigned agent, дата
3. Tab/section «Сделки» — pipeline лидов (columns by stage), drag или dropdown смены stage
4. projectService или crmService для API из Этапа 10
5. Empty states, loading, error handling

Без карточки контакта и timeline — это Этап 12.
```

---

### Этап 12. CRM UI — карточка клиента и timeline

**Зависимости:** Этап 11  
**Результат:** `/projects/:id/crm/contacts/:contactId` — полная карточка + activity timeline.

**Scope:**
- `ContactDetailPage.jsx`
- Timeline component
- Edit contact fields

**Промпт:**
```
Реализуй Этап 12 из REFACTORING_AND_UX.md:

1. ContactDetailPage.jsx — /projects/:id/crm/contacts/:contactId
2. Header: имя, phone, email, source, assigned agent
3. Связанные лиды
4. Activity Timeline — хронология: сообщения, звонки, смена статуса, записи, notes
5. Клик на контакт в ProjectCrmPage → detail page
6. ActivityTimeline.jsx — reusable component

Timeline пока может быть populated тестовыми/manual данными если agent integration ещё не готова.
```

---

### Этап 13. Agent CRM tools → project-scoped

**Зависимости:** Этап 10  
**Результат:** агенты читают/пишут ProjectCrm вместо isolated per-agent data.

**Scope:**
- Refactor `crm/tool_registry.py`
- Runtime: resolve agent → project_id → ProjectCrm
- Migrate AdminAppointment reads/writes

**Промпт:**
```
Реализуй Этап 13 из REFACTORING_AND_UX.md:

1. Refactor backend/app/services/crm/tool_registry.py — все CRM tools работают через project_id (resolve from agent.project_id)
2. find_contact, create_contact, create_lead, update_lead, add_note → пишут в ProjectCrm* + ProjectCrmActivity
3. Admin booking (AdminAppointment) — добавь project_id, queries через project
4. AgentSalesContact — при создании линкуй к ProjectCrmContact
5. Каждый tool call → activity record с agent_id

Не меняй frontend. Сохрани backward compat: если project_id null — fallback на старую логику.
```

---

### Этап 14. Автозаполнение CRM из диалогов агентов

**Зависимости:** Этап 13  
**Результат:** при каждом значимом взаимодействии агент upsert'ит контакт и пишет activity.

**Scope:**
- Hooks в message processing pipeline
- Auto contact create/update from telegram id, phone
- Identity match

**Промпт:**
```
Реализуй Этап 14 из REFACTORING_AND_UX.md:

1. В agent message pipeline (template_runtime или message handler): при входящем сообщении — upsert ProjectCrmContact по user_external_id / phone
2. При каждом ответе агента — ProjectCrmActivity type=message
3. При вызове CRM tool — activity с tool_name и payload
4. Identity resolution: match by phone > email > telegram id; если match — merge external_ids
5. Обновляй assigned_agent_id при активном диалоге

CRM должна наполняться автоматически без ручного ввода.
```

---

### Этап 15. Каналы проекта — подключение и назначение агента

**Зависимости:** Этап 6  
**Результат:** `/projects/:id/channels` — подключить канал, выбрать агента-обработчика.

**Scope:**
- Model `ProjectChannel` или extend `AgentChannelConnection` with project-level UI
- UI: list channels, add channel, assign agent dropdown
- Reuse channel connection flows from createAgent

**Промпт:**
```
Реализуй Этап 15 из REFACTORING_AND_UX.md:

1. Добавь ProjectChannel model (project_id, provider, channel_type: messenger|telephony, assigned_agent_id, credentials) + migration
2. API: GET/POST/DELETE /api/projects/{id}/channels, PATCH assigned_agent_id
3. ProjectChannelsPage.jsx — список каналов, статус, assigned agent
4. «Добавить канал» — reuse wizard подключения Telegram/WhatsApp из createAgent (extract component)
5. Dropdown «Какой агент обрабатывает» — список агентов проекта
6. Incoming messages route to assigned_agent_id

Telephony — placeholder UI с badge Demo.
```

---

### Этап 16. Website на уровне проекта

**Зависимости:** Этап 5  
**Результат:** `/projects/:id/website` — управление лендингом проекта.

**Scope:**
- `Website.project_id` migration
- ProjectWebsitePage — status, edit, preview, publish
- Reuse website-builder

**Промпт:**
```
Реализуй Этап 16 из REFACTORING_AND_UX.md:

1. Migration: Website.project_id FK → projects.id; backfill from agent.project_id
2. API: GET /api/projects/{id}/website, POST create if not exists
3. ProjectWebsitePage.jsx — статус (draft/published), url, кнопки: редактировать, preview, опубликовать
4. Edit → /projects/:id/website/edit (reuse ConstructorPage с project context)
5. Public /w/:slug — без изменений
6. Widget agent — dropdown выбора агента для виджета

Убери создание сайта только из карточки агента — primary entry point теперь project website section.
```

---

### Этап 17. AI-генерация лендинга при provisioning

**Зависимости:** Этап 8, Этап 16  
**Результат:** при создании проекта автоматически генерируется draft сайта из брифа.

**Scope:**
- Integrate `website_generation_service` into provisioning
- Preview on create flow
- Async generation + polling

**Промпт:**
```
Реализуй Этап 17 из REFACTORING_AND_UX.md:

1. В ProjectProvisioningService после создания agents — queue website generation из BusinessProfile
2. Reuse backend website_generation_service (create-and-generate)
3. Preview step (Этап 9) показывает website generation status + thumbnail/link
4. GET /api/projects/{id}/provision/status — include website status
5. Website привязан к project_id, widget agent = qa agent проекта

Если generation async — polling на preview screen.
```

---

### Этап 18. Контент-завод как модуль проекта

**Зависимости:** Этап 5  
**Результат:** `/projects/:id/content` — UI контент-завода, привязанного к проекту.

**Scope:**
- `ProjectContentFactory` config model
- ProjectContentPage — jobs list, create job, status
- Wire existing content_factory_worker to project

**Промпт:**
```
Реализуй Этап 18 из REFACTORING_AND_UX.md:

1. ProjectContentFactory model (project_id, config_json, is_active) + migration
2. AgentContentJob — добавь project_id; content factory привязан к project, не standalone agent
3. API: GET/POST /api/projects/{id}/content/jobs, GET status
4. ProjectContentPage.jsx — список jobs (status, topic, created, video url), форма «Создать видео» (topic, style)
5. Reuse content_factory_worker — resolve project from job
6. В provisioning: если LLM решил нужен content — создай ProjectContentFactory config

Фокus UI copy: короткие вертикальные видео.
```

---

### Этап 19. Соцсети для контент-завода

**Зависимости:** Этап 18, Этап 15  
**Результат:** каналы TikTok, Instagram, YouTube, Pinterest в разделе Каналы (type=social).

**Scope:**
- Extend ProjectChannel for social providers
- UI connect flow (OAuth placeholder or manual token)
- Publish destination per job

**Промпт:**
```
Реализуй Этап 19 из REFACTORING_AND_UX.md:

1. ProjectChannel.channel_type=social; providers: tiktok, instagram, youtube, pinterest
2. API: POST /api/projects/{id}/channels/social — connect (OAuth scaffold или manual API key storage)
3. В ProjectChannelsPage — секция «Соцсети для контента» отдельно от «Каналы для агентов»
4. При создании content job — выбор куда публиковать (checkboxes connected social channels)
5. Worker placeholder: после генерации видео — mark ready_for_publish + destination channel

Полноценный OAuth можно stub'ить — главное UX flow и data model.
```

---

### Этап 20. ИИ-менеджер — backend и шаблон

**Зависимости:** Этап 8  
**Результат:** `ai_manager` agent создаётся при provisioning; API chat с доступом к метрикам.

**Scope:**
- `ai_manager` template in provisioning
- `POST /api/projects/{id}/manager/chat`
- System prompt with project context injection

**Промпт:**
```
Реализуй Этап 20 из REFACTORING_AND_UX.md:

1. Добавь ai_manager в industry templates provisioning — создаётся для каждого проекта как «ИИ-менеджер»
2. System prompt ai_manager: доступ к метрикам проекта, CRM summary, статус агентов; отвечает владельцу бизнеса
3. POST /api/projects/{id}/manager/chat — messages[], возвращает reply
4. Context builder: aggregate analytics (dialogs count, leads count, appointments, content jobs) + recent CRM summary
5. ai_manager НЕ подключается к messenger channels — только web chat

Template type ai_manager — enable in agent_template_pricing (можно in_development → available).
```

---

### Этап 21. UI чата с ИИ-менеджером

**Зависимости:** Этап 20, Этап 5  
**Результат:** `/projects/:id/manager` — chat UI для владельца.

**Scope:**
- `ProjectManagerPage.jsx`
- Chat interface, suggested questions
- Link from dashboard header

**Промпт:**
```
Реализуй Этап 21 из REFACTORING_AND_UX.md:

1. ProjectManagerPage.jsx — chat UI на /projects/:id/manager
2. Suggested prompts: «Как дела за неделю?», «Сколько новых лидов?», «Что улучшить?»
3. Вызывает POST /api/projects/{id}/manager/chat
4. Кнопка «Менеджер» в header dashboard (Этап 5)
5. Стиль — отличный от client-facing agent chat (бизнес-советник tone)

Reuse chat components если есть (AgentChatShowcase или аналог).
```

---

### Этап 22. Provisioning — CRM pipeline и ai_manager при create

**Зависимости:** Этап 8, Этап 10  
**Результат:** LLM при создании проекта инициализирует CRM pipeline под отрасль.

**Scope:**
- Extend provisioning to create default CRM stages
- Seed pipeline in ProjectCrmLead stages config

**Промпт:**
```
Реализуй Этап 22 из REFACTORING_AND_UX.md:

1. В ProjectProvisioningService: после создания project — init CRM pipeline stages based on industry template
2. Сохрани pipeline config в ProjectBusinessProfile или отдельной project_crm_settings
3. Preview (Этап 9) показывает CRM pipeline stages
4. LLM может customize stage names под бриф (optional)
5. ProjectCrmPage (Этап 11) читает pipeline из project config

Свяжи provisioning end-to-end: бриф → agents + CRM + website + content factory config.
```

---

### Этап 23. Лендинг и SEO — новое позиционирование

**Зависимости:** нет (можно параллельно после Этапа 3)  
**Результат:** Main.jsx, seo.js, pricing — «портал цифровизации бизнеса».

**Scope:**
- Hero, features blocks, CTA «Создать проект»
- All SEO titles/descriptions

**Промпт:**
```
Реализуй Этап 23 из REFACTORING_AND_UX.md:

1. Перепиши frontend/src/pages/Main.jsx — позиционирование «портал цифровизации бизнеса», не «ИИ-агент»
2. Hero: «Цифровой офис вашего бизнеса за 10 минут», CTA → /projects/create
3. Блоки: ИИ-команда, CRM, Сайт, Контент-завод, ИИ-менеджер, мультиагентность
4. Обнови seo.js — все titles/descriptions
5. PriceList.jsx — framing «тарифы проекта», не «шаблоны агентов»
6. Case studies — адаптируй под «проект», не «агент»

Только marketing copy и landing, без backend changes.
```

---

### Этап 24. Биллинг на уровне проекта

**Зависимости:** Этап 2  
**Результат:** subscription привязан к Project; pricing UI в project settings.

**Scope:**
- `Project.subscription_*` fields or mapping table
- Migrate from per-agent billing
- Grandfather existing subs

**Промпт:**
```
Реализуй Этап 24 из REFACTORING_AND_UX.md:

1. Добавь в Project: plan_name, maintenance_paid_until, is_active (или mapping table project_subscriptions)
2. Migration: перенеси billing state с agents на projects (1:1 from backfill)
3. Project settings page — billing section, reuse payment modals from agentsPage
4. project_plan_pricing.py — plans: Старт (free), Бизнес, Про (см. документ §12 старой версии)
5. Grandfather: agents с active sub → project gets same sub

Не ломай существующие YooKassa flows — adapt to project_id.
```

---

### Этап 25. Telegram master bot — проекты

**Зависимости:** Этап 2  
**Результат:** bot навигация по проектам, создание проекта через анкету.

**Scope:**
- `bot/handlers/master/project_*.py`
- Project picker, mirror web provisioning simplified

**Промпт:**
```
Реализуй Этап 25 из REFACTORING_AND_UX.md:

1. bot/handlers/master/ — добавь project list, project picker
2. Flow: /start → мои проекты → выбор проекта → управление агентами проекта
3. «Создать проект» — короткая анкета в чате (3-4 вопроса + бриф) → вызов /api/projects/provision
4. Обнови copy: «проект», не «агент»
5. Сохрани backward compat для пользователей без projects (fallback agents)

Не переписывай весь bot — incremental migration.
```

---

### Этап 26. Cleanup — deprecate legacy routes

**Зависимости:** все предыдущие этапы  
**Результат:** удалены/закрыты `/agents`, `/create-agent`, deprecated API headers.

**Scope:**
- Remove agentsPage as primary (keep redirect)
- Deprecation warnings on old API
- Feature flag removal

**Промпт:**
```
Реализуй Этап 26 из REFACTORING_AND_UX.md:

1. /agents и /create-agent — только redirects на /projects equivalents
2. /api/agents/* — добавь Deprecation header, proxy где возможно на project-scoped endpoints
3. Удали или archive createAgent.jsx если полностью заменён ProjectCreatePage
4. agentsPage.jsx — archive или minimal redirect logic
5. Обнови DocumentationPage — структура docs под project-first UX
6. Remove PROJECTS_UX_ENABLED feature flag если был

Проверь что все links в codebase обновлены. Не ломай management-portal и public website routes.
```

---

## Карта этапов (зависимости)

```
1 Project DB
  └─2 API ──3 Routes ──4 Projects list ──5 Dashboard shell
                          │                    │
                          │                    ├─6 Agents in project
                          │                    ├─11 CRM UI ←10 CRM API ←1
                          │                    ├─12 Contact detail
                          │                    ├─16 Website
                          │                    ├─18 Content factory
                          │                    └─21 Manager UI ←20 Manager backend
                          │
                          └─7 Create form ──8 AI provision ──9 Preview
                                                │
                                                ├─17 Website gen
                                                └─22 CRM pipeline init

10 CRM API ──13 Agent CRM tools ──14 Auto-fill CRM

5 Dashboard ──15 Channels ──19 Social channels

23 Landing (parallel)
24 Billing (after 2)
25 Bot (after 2)
26 Cleanup (last)
```

---

## 9. Глоссарий

| Термин | Значение |
|--------|----------|
| **Проект** | МСБ или отдел в крупной компании — единица продукта |
| **ИИ-сотрудник / Агент** | Роль в проекте (Админ, МОП, Консультант, Менеджер) |
| **ИИ-менеджер** | Агент для владельца бизнеса — метрики, советы, стратегия |
| **CRM** | Единая база клиентов проекта, auto-maintained агентами |
| **Контент-завод** | Pipeline коротких вертикальных видео + публикация |
| **Канал** | Точка входа/выхода: messenger, telephony или social |
| **Provisioning** | AI-сборка проекта из брифа |
| **Бриф** | Описание бизнеса от пользователя |

---

*Каждый этап — один промпт. После выполнения всех 26 этапов RSD становится единым порталом цифровизации бизнеса согласно видению §1.*
