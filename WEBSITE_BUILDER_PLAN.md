# План реализации фичи: Сайт для владельцев ИИ-агентов

## Общее описание

Фича позволяет клиентам создавать одностраничные сайты для своих ИИ-агентов. Сайты генерируются с помощью ИИ (DeepSeek), привязываются к услугам агента (для админ-шаблонов), имеют качественный адаптивный дизайн, режим визуального конструктора (по аналогии с Яндекс КИТ), возможность экспорта в ZIP и поддержку кастомных доменов.

---

## Архитектурные решения

### Технологический стек
- **Frontend**: React + Vite + Tailwind CSS (тот же, что в основном проекте)
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **AI Generation**: DeepSeek API (уже используется в проекте)
- **Queue**: Celery + Redis (для фоновой генерации)
- **Storage**: S3/MinIO или локальное хранилище для архивов
- **Domain Management**: Wildcard DNS + Nginx reverse proxy

### Интеграция с существующей системой
- Аутентификация через существующую систему `User` / `Agent`
- Использование `AgentService` для подгрузки услуг
- Встраивание существующего чат-виджета (`main.jsx` widget)
- Интеграция с системой бронирования (`BookingService`, `TimeSlot`)

---

## Этапы реализации

### Этап 1: Проектирование схемы данных и API

**Описание:** Создание моделей БД для хранения сайтов, блоков, настроек и привязки к агентам. Проектирование REST API endpoints.

**Цель:** Иметь структуру данных, которая поддерживает мультитенантность (пользователи → агенты → сайты), версионирование контента и привязку к услугам агента.

**Что нужно сделать:**

1. **Создать модели SQLAlchemy:**
   - `Website` — основная модель сайта
     - `id`, `owner_id`, `agent_id`
     - `slug` — уникальный для поддомена `rsd-ai.ru/{slug}`
     - `title`, `meta_description`, `og_image_url`, `favicon_url`
     - `template_id`, `status` (draft | published | archived)
     - `created_at`, `updated_at`, `published_at`
   - `WebsiteBlock` — блоки контента сайта
     - `id`, `website_id`, `order`
     - `type` (hero | services | about | contacts | cta | footer | custom)
     - `content` (JSONB) — структура данных блока
     - `styles` (JSONB) — кастомные стили
   - `WebsiteTemplate` — предустановленные шаблоны
     - `id`, `name`, `description`, `thumbnail_url`
     - `default_blocks` (JSONB) — структура по умолчанию
     - `default_styles` (JSONB) — цвета, шрифты
   - `WebsiteDomain` — кастомные домены
     - `id`, `website_id`, `domain` (полный домен)
     - `ssl_enabled`, `verification_status` (pending | verified | failed)
     - `verification_token` — для TXT-записи DNS

2. **Миграции Alembic:**
   - Создать миграцию для новых таблиц
   - Индексы: `slug` (unique), `website_id + order`, `domain` (unique)
   - Foreign keys: `owner_id → users.id`, `agent_id → agents.id`

3. **Pydantic схемы для API:**
   - `WebsiteCreateRequest` — создание сайта
   - `WebsiteUpdateRequest` — обновление мета-данных
   - `WebsiteResponse` — полная информация о сайте
   - `WebsiteBlockRequest` / `WebsiteBlockResponse` — CRUD блоков
   - `WebsitePublishRequest` — публикация сайта
   - `WebsiteGenerateRequest` — запрос на AI-генерацию

4. **CRUD endpoints:**
   - `POST /api/v1/websites` — создание сайта
   - `GET /api/v1/websites` — список сайтов пользователя
   - `GET /api/v1/websites/{id}` — детали сайта
   - `PUT /api/v1/websites/{id}` — обновление сайта
   - `DELETE /api/v1/websites/{id}` — удаление сайта
   - `POST /api/v1/websites/{id}/publish` — публикация
   - `POST /api/v1/websites/{id}/unpublish` — снятие с публикации

5. **Валидация и бизнес-логика:**
   - Проверка уникальности `slug` (регулярка: `^[a-z0-9-]+$`, min 3, max 50 символов)
   - Проверка принадлежности сайта пользователю (middleware)
   - Каскадное удаление блоков при удалении сайта
   - Авто-генерация slug из названия агента если не указан

---

### Этап 2: Интеграция с DeepSeek для генерации сайтов

**Описание:** Сервис для генерации React-компонентов через DeepSeek API по описанию пользователя.

**Цель:** Пользователь вводит описание бизнеса → получает готовый одностраничник с текстами, структурой и стилями.

**Что нужно сделать:**

1. **Создать сервис `WebsiteGenerationService`:**
   - Интеграция с существующим DeepSeek API клиентом
   - Настройка retry-логики и таймаутов

2. **Prompt engineering:**
   ```
   Системный промпт:
   Ты — frontend-разработчик. Сгенерируй React-компонент (JSX + Tailwind CSS) 
   для одностраничного сайта бизнеса. 
   
   Входные данные:
   - Название: {business_name}
   - Описание: {business_description}
   - Услуги: [{name, description, price}]
   - Контакты: {phone, email, address}
   - Цветовая схема: {primary_color}
   
   Выходной формат (JSON):
   {
     "meta": {
       "title": "...",
       "description": "..."
     },
     "styles": {
       "primaryColor": "...",
       "secondaryColor": "...",
       "fontFamily": "...",
       "darkMode": false
     },
     "blocks": [
       {
         "type": "hero",
         "order": 1,
         "content": {
           "headline": "...",
           "subheadline": "...",
           "ctaText": "...",
           "ctaLink": "..."
         }
       },
       {
         "type": "services",
         "order": 2,
         "content": {
           "title": "Наши услуги",
           "items": [...]
         }
       },
       ...
     ]
   }
   ```

3. **Парсинг и валидация ответа:**
   - Извлечение JSON из ответа DeepSeek
   - Валидация через Pydantic модели
   - Fallback на default-шаблон при ошибке генерации

4. **Интеграция с данными агента:**
   - Подгрузка `Agent.name`, `Agent.description`
   - Получение услуг из `AgentService` (для агентов с админ-шаблоном)
   - Получение контактов из связанных каналов (Telegram, WhatsApp)

5. **Background task:**
   - Создать Celery task `generate_website_task`
   - Эндпоинт `POST /api/v1/websites/generate` ставит задачу в очередь
   - WebSocket/SSE для уведомления о завершении генерации
   - Статус генерации хранится в `Website.generation_status`

---

### Этап 3: Базовая система шаблонов и адаптивная вёрстка

**Описание:** Создание базовых UI-шаблонов и responsive-контейнера для рендера сайтов.

**Цель:** Сайты выглядят профессионально, адаптируются под мобильные и десктоп, имеют единый дизайн-язык.

**Что нужно сделать:**

1. **Базовые шаблоны (4 шаблона):**
   - `modern-business` — современный корпоративный, градиенты, крупная типографика
   - `minimal-portfolio` — минималистичный, много whitespace, чёрно-белый + акцент
   - `vibrant-service` — яркий, цветные карточки, подходит для услуг
   - `elegant-professional` — элегантный, serif-шрифты, для консалтинга/юруслуг

2. **React-компоненты блоков:**
   - `HeroBlock` — заголовок, подзаголовок, CTA-кнопка, фон (цвет/градиент/изображение)
   - `ServicesBlock` — сетка карточек услуг с иконками/изображениями
   - `AboutBlock` — текст о компании + изображение
   - `ContactBlock` — форма обратной связи + контактная информация
   - `CTABlock` — призыв к действию
   - `FooterBlock` — подвал с копирайтом и ссылками
   - `AgentWidgetBlock` — контейнер для встраивания чат-виджета

3. **Адаптивный дизайн (Tailwind CSS):**
   - Mobile-first подход
   - Breakpoints: `sm:640px`, `md:768px`, `lg:1024px`, `xl:1280px`
   - Responsive typography: `text-3xl md:text-4xl lg:text-5xl`
   - Responsive spacing: `py-12 md:py-16 lg:py-20`
   - Grid адаптация: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`
   - Mobile menu для навигации (если есть)

4. **Preview-режим:**
   - Отдельный роут `/preview/{website_id}`
   - Iframe с рендером сайта
   - Device switcher: mobile (375px), tablet (768px), desktop (100%)
   - Hot reload при редактировании

5. **API для фронтенда:**
   - `GET /api/v1/websites/{id}/schema` — JSON-схема для рендера
   - `GET /api/v1/website-templates` — список доступных шаблонов

---

### Этап 4: Режим конструктора (Visual Constructor Mode)

**Описание:** Интерактивный визуальный редактор блоков по аналогии с Яндекс КИТ — toggles + промпт-редактирование.

**Цель:** Пользователь может визуально редактировать сайт без кода: менять тексты, цвета, порядок блоков, добавлять/удалять секции.

**Что нужно сделать:**

1. **UI режима конструктора:**
   - Левая панель: список блоков с иконками
   - Центральная область: live preview сайта
   - Правая панель: настройки выбранного блока
   - Top bar: заголовок, кнопки сохранить/опубликовать/предпросмотр

2. **Редактирование текста:**
   - Inline editing: клик по тексту → редактирование
   - Rich text: bold, italic, links (tip-tap editor или contenteditable)
   - Placeholders для динамических данных ({{business_name}}, {{phone}})

3. **Редактирование стилей (тoggles):**
   - Цветовая схема: primary color picker, dark/light mode toggle
   - Шрифты: select (Inter, Roboto, Playfair Display, etc.)
   - Отступы: padding/margin sliders
   - Выравнивание: left/center/right
   - Border radius: none/medium/round

4. **Drag-and-drop для блоков:**
   - Библиотека: `@dnd-kit/sortable` или `react-beautiful-dnd`
   - Перетаскивание в списке слева для изменения порядка
   - Визуальный feedback при drag

5. **Добавление/удаление блоков:**
   - Кнопка "+ Добавить блок" → модал с выбором типа
   - Шаблоны для каждого типа блока
   - Duplicate block
   - Delete с подтверждением

6. **Промпт-редактор (AI-ассистент в конструкторе):**
   - Поле ввода в боковой панели
   - Примеры промптов: "Сделай заголовок крупнее", "Добавь иконки к услугам", "Сделай фон темнее"
   - Отправка на DeepSeek с контекстом текущего блока
   - Применение изменений к блоку

7. **Автосохранение:**
   - Debounced сохранение каждые 5 секунд
   - Индикатор "Сохранено" / "Сохранение..."
   - Кнопка "История изменений" (optional)

---

### Этап 5: Интеграция виджета агента и отображение услуг

**Описание:** Встраивание существующего чат-виджета на сайт и динамическое отображение услуг из админ-шаблона агента.

**Цель:** Сайт является полноценным представительством агента с рабочим виджетом и актуальными услугами/записью.

**Что нужно сделать:**

1. **Интеграция чат-виджета:**
   - Переиспользовать существующий `main.jsx` (widget)
   - Компонент `AgentWidget`: обёртка для встраивания
   - Настройка через props: `agentId`, `theme` (цвета сайта), `position`
   - Скрипт-инжект при рендере сайта

2. **Компонент ServicesBlock (динамический):**
   - Автоматическая подгрузка услуг из `AgentService`
   - Для агентов с `AgentTemplateType = admin`
   - Отображение: название, описание, цена, длительность
   - Кнопка "Записаться" → открытие виджета/модалки бронирования

3. **Интеграция системы бронирования:**
   - Блок `BookingBlock` для админ-шаблонов
   - Мини-форма: выбор услуги → дата → время → контакт
   - Интеграция с `BookingService`, `TimeSlot`
   - Подтверждение записи через виджет

4. **Кнопки быстрой связи:**
   - Floating buttons: Telegram, WhatsApp
   - Автоподстановка контактов из `Agent.channels`
   - Deep links: `https://t.me/{username}`, `https://wa.me/{phone}`

5. **Публичный API для данных агента:**
   - `GET /api/v1/agents/{id}/public-data` — без авторизации
   - Возвращает: название, описание, логотип, услуги, контакты
   - Rate limiting: 100 запросов/минуту/IP
   - CORS для публичных доменов

---

### Этап 6: Экспорт сайта в ZIP-архив

**Описание:** Функционал выгрузки готового сайта как статичного HTML/CSS/JS архива для самостоятельного хостинга.

**Цель:** Пользователь может скачать сайт и разместить его на своём хостинге без привязки к платформе.

**Что нужно сделать:**

1. **Сервис `WebsiteExportService`:**
   - SSR/SSG: `ReactDOMServer.renderToString()` для генерации HTML
   - Альтернатива: Puppeteer для скриншота/полной генерации

2. **Генерация статичных файлов:**
   - `index.html` — основной файл с inline стилями и скриптами
   - `styles.css` — критические + полные стили (Tailwind CDN или purged CSS)
   - `script.js` — минимальный JS для интерактивности
   - `assets/` — изображения, favicon

3. **Встраивание виджета:**
   - Inline-скрипт в `<head>` или перед `</body>`
   - Конфигурация через `window.AgentWidgetConfig`
   - Fallback: ссылка на виджет, если скрипт не загрузился

4. **Обработка изображений:**
   - Скачивание внешних изображений
   - Конвертация в base64 для маленьких файлов (< 5KB)
   - Оптимизация: WebP формат с fallback

5. **API endpoint:**
   - `POST /api/v1/websites/{id}/export` — запуск экспорта
   - Background task для сборки архива
   - `GET /api/v1/websites/{id}/export-status` — статус готовности
   - `GET /api/v1/websites/{id}/download` — скачивание ZIP

6. **Хранение архивов:**
   - S3/MinIO для хранения готовых ZIP
   - TTL: 24 часа для временных файлов
   - Квота: 100MB на пользователя

7. **Структура ZIP-архива:**
   ```
   website-{slug}/
   ├── index.html
   ├── css/
   │   └── styles.css
   ├── js/
   │   └── main.js
   ├── assets/
   │   ├── images/
   │   └── favicon/
   └── README.txt (инструкция по развёртыванию)
   ```

---

### Этап 7: Поддержка кастомных доменов и поддоменов

**Описание:** Развёртывание сайтов на поддоменах `rsd-ai.ru/{slug}` и поддержка полностью кастомных доменов пользователей.

**Цель:** Сайты доступны по красивым URL и могут использоваться как полноценные бизнес-сайты.

**Что нужно сделать:**

1. **Поддомены на `rsd-ai.ru`:**
   - Wildcard DNS: `*.rsd-ai.ru → server IP`
   - Nginx конфиг: catch-all server с routing по path или subdomain
   - Alternative: `rsd-ai.ru/{slug}` — проще в реализации

2. **Модель `WebsiteDomain`:**
   - Поля: `domain`, `ssl_enabled`, `verification_status`, `verification_token`
   - Валидация домена: regex для domain name
   - Запрет на system domains: `admin`, `api`, `www`, `mail`, etc.

3. **Верификация кастомного домена:**
   - Генерация unique TXT-записи: `rsd-verification={token}`
   - Инструкция для пользователя (DNS настройки)
   - Периодическая проверка через DNS lookup
   - Статусы: pending → verifying → verified | failed

4. **Nginx / API Gateway:**
   - Dynamic server_name или `map $host $website_id`
   - Reverse proxy на frontend с передачей `X-Website-ID`
   - Fallback на основной сайт при неизвестном домене

5. **SSL/TLS:**
   - Wildcard SSL для `*.rsd-ai.ru` (Let's Encrypt)
   - Автоматический SSL для кастомных доменов (certbot)
   - HTTP → HTTPS redirect

6. **API endpoints:**
   - `POST /api/v1/websites/{id}/domains` — добавление домена
   - `DELETE /api/v1/websites/{id}/domains/{domain_id}` — удаление
   - `POST /api/v1/websites/{id}/domains/{domain_id}/verify` — запуск верификации
   - `GET /api/v1/websites/{id}/domains` — список доменов

7. **Middleware для определения сайта:**
   - Извлечение website_id из `Host` header или URL path
   - Проверка статуса (published)
   - 404 для неопубликованных/несуществующих сайтов

---

### Этап 8: Управление мета-данными и SEO

**Описание:** Настройка favicon, title, meta-description, OpenGraph-тегов для каждого сайта.

**Цель:** Сайты выглядят профессионально в поисковиках и соцсетях, имеют брендированный favicon.

**Что нужно сделать:**

1. **Поля в модели `Website`:**
   - `title` — `<title>` (max 60 символов)
   - `meta_description` — `<meta name="description">` (max 160 символов)
   - `og_title`, `og_description` — OpenGraph
   - `og_image_url` — превью для соцсетей (1200x630)
   - `favicon_url` — favicon (ICO/PNG/SVG)

2. **Загрузка favicon:**
   - Drag-and-drop загрузка
   - Автоконвертация размеров: 16x16, 32x32, 180x180 (apple-touch)
   - Форматы: PNG, ICO, SVG
   - Preview загруженной иконки

3. **Генерация OpenGraph изображения:**
   - Автогенерация из шаблона с названием бизнеса
   - Библиотека: `@vercel/og` или Sharp с шаблоном
   - Custom upload: пользователь может загрузить своё
   - Preview: как будет выглядеть в соцсетях

4. **Head management:**
   - `react-helmet-async` для вставки мета-тегов
   - Динамические теги при смене страниц (если многостраничность)
   - JSON-LD structured data для LocalBusiness

5. **SEO-анализ:**
   - Индикаторы: title length, description length, presence of OG image
   - Предупреждения: "Title слишком длинный"
   - Preview: Google SERP preview, Telegram link preview

6. **API endpoints:**
   - `PUT /api/v1/websites/{id}/meta` — обновление SEO-данных
   - `POST /api/v1/websites/{id}/favicon` — загрузка favicon
   - `POST /api/v1/websites/{id}/og-image` — загрузка OG изображения

---

### Этап 9: Безопасность и изоляция сайтов

**Описание:** Защита от XSS, CSS-инъекций, изоляция пользовательских сайтов друг от друга и от основного приложения.

**Цель:** Пользовательский код не может сломать платформу или украсть данные других пользователей, соблюдение НСД.

**Что нужно сделать:**

1. **Content Security Policy (CSP):**
   ```
   Content-Security-Policy: 
     default-src 'self';
     script-src 'self' 'unsafe-inline' *.rsd-ai.ru;
     style-src 'self' 'unsafe-inline';
     img-src 'self' data: https:;
     font-src 'self' fonts.gstatic.com;
     connect-src 'self' *.rsd-ai.ru;
   ```

2. **Sanitization:**
   - `DOMPurify` для всего пользовательского HTML-контента
   - Запрет опасных тегов: `<script>`, `<iframe>`, `<object>`, `<embed>`
   - Запрет опасных атрибутов: `on*`, `javascript:`
   - CSS sanitization: `@import`, `expression()`, behavior`

3. **CSS Isolation:**
   - Shadow DOM для рендера пользовательских сайтов в preview
   - Scoped CSS с префиксами `.site-{website_id}`
   - CSS-in-JS с уникальными class names

4. **Iframe sandbox (для preview):**
   ```html
   <iframe sandbox="allow-scripts allow-same-origin"></iframe>
   ```

5. **Rate limiting:**
   - Генерация сайтов: 10/час на пользователя
   - Экспорт: 5/час на пользователя
   - Публикация: 20/час на пользователя
   - Redis-based rate limiting

6. **Input validation:**
   - Strict Pydantic validation на всех входах
   - Zod схемы на фронтенде
   - Max length на все текстовые поля
   - Regex на slug, domain, color values

7. **Access control:**
   - Middleware проверки владельца сайта
   - `current_user.id == website.owner_id`
   - 403 Forbidden для чужих ресурсов
   - Логирование подозрительной активности

8. **Separate origin для сайтов (опционально):**
   - Сайты на `sites.rsd-ai.ru` вместо `rsd-ai.ru` — cookie isolation
   - No SameSite cookies для домена сайтов

---

### Этап 10: Публикация, мониторинг и финальное тестирование

**Описание:** Финальная интеграция всех компонентов, нагрузочное тестирование, документация.

**Цель:** Фича готова к продакшену, работает стабильно, есть документация для пользователей.

**Что нужно сделать:**

1. **CI/CD интеграция:**
   - Добавление новых сервисов в `docker-compose.yml`
   - Nginx конфиги в репозиторий
   - Миграции в startup scripts

2. **Мониторинг:**
   - Health checks: `/health/websites`, `/health/generation-queue`
   - Метрики: количество сайтов, время генерации, ошибки генерации
   - Sentry для error tracking
   - Alerting: превышение queue depth, падение генерации

3. **Админ-панель:**
   - Раздел "Все сайты" для модераторов
   - Фильтры: по статусу, по пользователю, по домену
   - Действия: просмотр, блокировка, удаление
   - Логи: кто что генерировал

4. **Документация:**
   - `README.md`: как создать сайт (пошагово)
   - `docs/website-builder/`: подробная документация
   - FAQ: частые вопросы (DNS настройки, как сменить домен, лимиты)
   - Видео-гайды (опционально)

5. **E2E тесты:**
   - Cypress/Playwright сценарии:
     1. Создание сайта из шаблона
     2. Генерация через DeepSeek
     3. Редактирование в конструкторе
     4. Публикация и просмотр
     5. Экспорт в ZIP
     6. Настройка кастомного домена

6. **Performance оптимизации:**
   - Redis кэш для опубликованных сайтов (`website:{id}:rendered`)
   - CDN для статики (Cloudflare или собственный)
   - Image optimization: WebP, lazy loading, blur placeholder
   - Lazy load для виджета агента

7. **Финальная проверка:**
   - Security audit: проверка на XSS, CSRF
   - Load testing: 1000 сайтов, 10000 просмотров/мин
   - Accessibility: WCAG 2.1 AA compliance
   - Cross-browser: Chrome, Firefox, Safari, Edge

---

## Зависимости между этапами

```
Этап 1 (Database & API)
    ↓
Этап 3 (Templates) ← Этап 2 (AI Generation)
    ↓
Этап 4 (Constructor)
    ↓
Этап 5 (Widget Integration) ← Этап 1 (Agent models)
    ↓
Этап 6 (ZIP Export) ← Этап 3 (Components)
    ↓
Этап 7 (Custom Domains) ← Этап 1 (Website model)
    ↓
Этап 8 (Meta & SEO) ← Этап 1 (Website model)
    ↓
Этап 9 (Security) ← Все предыдущие
    ↓
Этап 10 (Deployment)
```

**Параллельные этапы:** 2, 3, 5, 6, 8 могут разрабатываться параллельно после завершения Этапа 1.

---

## Критерии готовности (Definition of Done)

- [ ] Создание сайта через UI работает
- [ ] AI-генерация создаёт валидный сайт за < 30 секунд
- [ ] Конструктор позволяет редактировать все элементы
- [ ] Сайты адаптивны (mobile + desktop)
- [ ] Виджет агента работает на сайте
- [ ] Экспорт в ZIP создаёт рабочий архив
- [ ] Поддомены `rsd-ai.ru/{slug}` работают
- [ ] Кастомные домены проходят верификацию
- [ ] SEO-теги и favicon настраиваются
- [ ] Нет critical security issues
- [ ] E2E тесты проходят
- [ ] Документация написана

---

## Примерная оценка времени

| Этап | Оценка времени |
|------|---------------|
| 1. Database & API | 2-3 дня |
| 2. AI Generation | 3-4 дня |
| 3. Template System | 4-5 дней |
| 4. Visual Constructor | 5-7 дней |
| 5. Widget Integration | 2-3 дня |
| 6. ZIP Export | 2-3 дня |
| 7. Custom Domains | 3-4 дня |
| 8. Meta & SEO | 2-3 дня |
| 9. Security | 2-3 дня |
| 10. Deployment | 3-4 дня |
| **Итого** | **28-39 дней** |

---

*Документ создан: 2026-06-01*
*Последнее обновление: 2026-06-01*
