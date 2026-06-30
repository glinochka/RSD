# E2E Чеклист - Портал Цифровизации

> Последнее обновление: 2026-06-30

## ✅ Backend API Endpoints

### Проекты (Projects)
- [x] `GET /api/projects` - Список проектов пользователя
- [x] `POST /api/projects` - Создание проекта
- [x] `GET /api/projects/{id}` - Получение проекта
- [x] `PATCH /api/projects/{id}` - Обновление проекта
- [x] `DELETE /api/projects/{id}` - Архивация проекта
- [x] `GET /api/projects/{id}/dashboard` - Дашборд проекта

### AI Генерация
- [x] `POST /api/projects/ai/generate-plan` - Генерация плана AI
- [x] `POST /api/projects/ai/apply-plan` - Применение плана (создание агентов/сайта)

### Документы (Knowledge Base)
- [x] `GET /api/projects/{id}/documents` - Список документов
- [x] `POST /api/projects/{id}/documents` - Загрузка файла/ссылки
- [x] `DELETE /api/projects/{id}/documents/{doc_id}` - Удаление документа
- [x] `POST /api/projects/{id}/documents/{doc_id}/reindex` - Переиндексация

### CRM
- [x] `GET /api/projects/{id}/crm/summary` - Сводка CRM (записи, контакты, лиды)

### Сайт
- [x] `GET /api/projects/{id}/website` - Информация о сайте проекта

### Контент и AI Manager
- [x] `GET /api/projects/{id}/content` - Данные content_factory агентов
- [x] `GET /api/projects/{id}/ai-manager` - Данные ai_manager агентов

### Агенты (фильтрация)
- [x] `GET /api/agents/allBy_tgID?project_id={id}` - Агенты проекта
- [x] `POST /api/agents` - Создание агента с project_id

---

## ✅ Frontend Страницы

### Публичные
- [x] `/` - Главная (landing)
- [x] `/pricing` - Тарифы
- [x] `/documentation` - Документация
- [x] `/auth` - Авторизация

### Проекты
- [x] `/projects` - Список проектов
- [x] `/projects/create` - Создание проекта (AI-first wizard)
- [x] `/projects/{id}` - Дашборд проекта
- [x] `/projects/{id}/agents` - Агенты проекта
- [x] `/projects/{id}/knowledge` - База знаний
- [x] `/projects/{id}/crm` - CRM
- [x] `/projects/{id}/website` - Управление сайтом
- [x] `/projects/{id}/content` - Контент-завод
- [x] `/projects/{id}/manager` - AI-менеджер
- [x] `/projects/{id}/settings` - Настройки проекта

### Агенты (legacy + интеграция)
- [x] `/agents` → редирект на `/projects` или `/projects/{lastId}/agents`
- [x] `/create-agent?projectId={id}` - Создание агента в контексте проекта
- [x] `/agents/{id}/analytics` - Аналитика агента (без изменений)
- [x] `/agents/{id}/edit` - Редактирование агента (без изменений)

### Сайты (без изменений)
- [x] `/websites/{id}/edit` - Конструктор сайта
- [x] `/preview/{id}` - Превью
- [x] `/w/{slug}` - Публичный сайт

---

## ✅ Компоненты

- [x] `CreateChoiceModal` - Модальное окно выбора (ИИ-агент / Проект)
- [x] `useCreateChoice` - Хук для управления модалкой
- [x] `ProjectLayout` - Layout проекта с сайдбаром
- [x] `ProjectErrorBoundary` - Обработка ошибок в проекте

---

## ✅ Интеграции

### Модалка выбора подключена в:
- [x] `Main.jsx` - Hero CTA, Footer CTA
- [x] `agentsPage.jsx` - "+ Новый агент"
- [x] `Navbar.jsx` - "Создать"
- [x] `PriceList.jsx` - Кнопки тарифов

### Редиректы
- [x] `/agents` → `/projects/{lastProjectId}/agents` или `/projects`
- [x] После создания агента с `?projectId=` → возврат в проект

### SEO
- [x] `seo.js` - Обновлены title/description для портала
- [x] `robots.txt` - `/projects/*` в Disallow
- [x] `llms.txt` - Обновлено описание продукта

---

## 🧪 E2E Сценарий Тестирования

### 1. Регистрация и вход
```
1. Открыть https://rsd-ai.ru/
2. Нажать "Начать" → redirect на /auth
3. Зарегистрироваться / войти
4. После входа → redirect на /projects
```

### 2. Создание проекта через AI
```
1. На /projects нажать "Новый проект"
2. ИЛИ нажать "Создать" в Navbar → выбрать "Проект"
3. Заполнить бриф:
   - Название: "Тестовый салон"
   - Отрасль: "Салон красоты"
   - Что автоматизируем: поддержка, запись, сайт
   - Описание: (минимум 50 символов)
4. Нажать "Далее" → ожидание генерации плана AI
5. На экране превью:
   - Проверить предложенных агентов (2-3 агента)
   - Проверить предложенный сайт
   - Можно отключить ненужное
6. Нажать "Запустить проект"
7. Редирект на `/projects/{id}` (дашборд)
```

### 3. Дашборд проекта
```
1. Проверить виджеты:
   - Количество агентов (N)
   - Диалогов за 7 дней (0 для нового)
   - Статус сайта
2. Чеклист онбординга:
   - "Подключить Telegram" → должен вести в агенты
   - "Загрузить базу знаний" → в knowledge
   - "Опубликовать сайт" → в website
3. Быстрые действия:
   - "Добавить агента" → открыть модалку
   - "Загрузить документ" → в knowledge
```

### 4. Добавление агента из проекта
```
1. На дашборде нажать "Добавить агента"
2. ИЛИ в сайдбаре "Агенты" → "Добавить агента"
3. Модалка выбора → выбрать "ИИ-агент"
4. Создать агента (выбрать шаблон, заполнить поля)
5. После сохранения → редирект на `/projects/{id}/agents`
6. Новый агент должен быть в списке
```

### 5. База знаний
```
1. В сайдбаре "База знаний"
2. Загрузить PDF файл
3. Проверить что файл появился в списке со статусом
4. Проверить "Рекомендуем загрузить" (из AI плана)
5. Удалить файл → файл исчезает из списка
```

### 6. CRM
```
1. В сайдбаре "CRM"
2. Таб "Записи" - пока пусто (если нет crm_admin агента)
3. Таб "Контакты" - пока пусто (если нет sales_manager агента)
4. Добавить агента типа "crm_admin" → вернуться в CRM
5. Таб "Записи" должен показывать данные
```

### 7. Настройки проекта
```
1. В сайдбаре "Настройки"
2. Изменить название проекта
3. Изменить описание
4. Сохранить → проверить обновление в шапке
5. "Архивировать проект" → подтвердить
6. Проверить что проект скрыт из списка
```

### 8. Legacy URL
```
1. Открыть /agents (старое)
2. Должен быть редирект на /projects/{lastId}/agents
3. Если нет lastId → /projects
```

---

## ⚠️ Known Limitations (Вне MVP)

- Диалоги за 7 дней на дашборде: пока заглушка (0)
- Новые лиды за 7 дней: пока заглушка (0)
- AI Manager аналитика: заглушки (0)
- Content Factory: только отображение агентов, не полный dashboard
- Настоящая обработка документов (indexing) - требует background worker
- Создание сайта через apply-plan требует настроенного website generation

---

## 📦 Файлы для коммита

### Backend
```
backend/app/alembic/models.py
backend/app/alembic/migration/versions/a2b3c4d5e6f7_add_projects_table.py
backend/app/alembic/migration/versions/b3c4d5e6f7g8_add_project_documents.py
backend/app/dao/project_dao.py
backend/app/prompts/project_plan.py
backend/app/router_projects/router.py
backend/app/router_projects/schemas.py
backend/app/services/project_plan_service.py
backend/app/services/project_provisioning_service.py
backend/app/tests/test_projects_router.py
backend/app/tests/test_project_plan_service.py
backend/app/tests/test_project_provisioning_service.py
backend/server.py
```

### Frontend
```
frontend/src/App.jsx
frontend/src/components/CreateChoiceModal.jsx
frontend/src/components/Navbar.jsx
frontend/src/components/projects/ProjectErrorBoundary.jsx
frontend/src/components/projects/ProjectLayout.jsx
frontend/src/config/constants.js
frontend/src/config/seo.js
frontend/src/hooks/useCreateChoice.js
frontend/src/mocks/projectPlanMock.js
frontend/src/pages/AgentsRedirect.jsx
frontend/src/pages/Main.jsx
frontend/src/pages/agentsPage.jsx
frontend/src/pages/createAgent.jsx
frontend/src/pages/PriceList.jsx
frontend/src/pages/projects/*.jsx
frontend/src/services/projectService.js
frontend/src/styles/*.css
frontend/public/robots.txt
frontend/public/llms.txt
```

---

## 🚀 Следующие шаги

1. **Протестировать локально**:
   ```bash
   cd backend
   pytest app/tests/test_projects_router.py -v
   pytest app/tests/test_project_plan_service.py -v
   pytest app/tests/test_project_provisioning_service.py -v
   ```

2. **Запустить миграции**:
   ```bash
   alembic upgrade head
   ```

3. **Протестировать фронтенд**:
   ```bash
   cd frontend
   npm run dev
   ```

4. **Проверить E2E** по сценариям выше

5. **Закоммитить** все изменения

6. **Деплой** на VPS с проверкой:
   - Миграции применены
   - Все контейнеры подняты
   - API доступно
