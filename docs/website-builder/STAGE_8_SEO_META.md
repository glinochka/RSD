# Этап 8: Управление мета-данными и SEO

## Статус: ✅ Реализован

## Описание

Реализована система управления SEO-метаданными для сайтов: favicon, title, meta-description, OpenGraph-теги, JSON-LD structured data. Сайты выглядят профессионально в поисковиках и соцсетях.

---

## Реализованный функционал

### 1. Поля в модели `Website`

Все SEO-поля уже были добавлены в модель базы данных:

| Поле | Тип | Описание |
|------|-----|----------|
| `title` | VARCHAR(100) | `<title>` страницы (рекомендуется 30-60 символов) |
| `meta_description` | VARCHAR(500) | `<meta name="description">` (рекомендуется 120-160 символов) |
| `og_title` | VARCHAR(100) | OpenGraph title для соцсетей |
| `og_description` | VARCHAR(300) | OpenGraph description для соцсетей |
| `og_image_url` | VARCHAR(1024) | URL превью-изображения 1200x630 |
| `favicon_url` | VARCHAR(1024) | URL favicon (ICO/PNG/SVG) |

### 2. API Endpoints

```
GET  /api/v1/websites/{id}/seo/meta          - Получить SEO метаданные
PUT  /api/v1/websites/{id}/meta               - Обновить SEO данные
POST /api/v1/websites/{id}/favicon            - Загрузить favicon
POST /api/v1/websites/{id}/og-image/upload    - Загрузить OG изображение
POST /api/v1/websites/{id}/og-image/generate  - Сгенерировать OG изображение
GET  /api/v1/websites/{id}/seo/preview        - Получить SEO preview (Google/Telegram)
```

### 3. Сервис `WebsiteSEOService`

**Файл:** `backend/app/services/website_seo_service.py`

#### Favicon конвертация
- Принимает: PNG, JPG, SVG, ICO
- Генерирует размеры: 16x16, 32x32, 48x48, 64x64, 128x128, 180x180, 192x192, 256x256
- Создаёт: favicon.ico с комбинацией 16, 32, 48
- Сохраняет: все размеры как отдельные PNG файлы

#### OG Image генерация
- Размер: 1200x630 пикселей (стандарт OpenGraph)
- Фон: из primary color сайта
- Текст: название бизнеса и описание
- Автоматическая генерация через Pillow

### 4. Frontend компоненты

#### SEOMetaPanel
**Файл:** `frontend/src/website-builder/components/constructor/SEOMetaPanel.jsx`

Вкладки:
- **Basic**: title, meta_description, favicon
- **Social**: og_title, og_description, og_image (upload/generate)
- **Preview**: Google SERP preview, Telegram link preview, SEO warnings

#### WebsiteMetaTags
**Файл:** `frontend/src/website-builder/components/WebsiteMetaTags.jsx`

Использует `react-helmet-async` для управления `<head>`:

```jsx
<Helmet>
  {/* Basic */}
  <title>{title}</title>
  <meta name="description" content={description} />
  
  {/* OpenGraph */}
  <meta property="og:title" content={ogTitle} />
  <meta property="og:description" content={ogDescription} />
  <meta property="og:image" content={ogImageUrl} />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  
  {/* Twitter */}
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={ogTitle} />
  <meta name="twitter:image" content={ogImageUrl} />
  
  {/* Favicon */}
  <link rel="icon" href={faviconUrl} />
  <link rel="apple-touch-icon" sizes="180x180" href={...} />
  
  {/* JSON-LD Structured Data */}
  <script type="application/ld+json">
    {JSON.stringify(localBusinessSchema)}
  </script>
</Helmet>
```

### 5. JSON-LD Structured Data

Автоматически генерируется для каждого сайта:

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Название бизнеса",
  "description": "Описание",
  "url": "https://rsd-ai.ru/slug",
  "image": "https://rsd-ai.ru/og-image.png",
  "telephone": "+7...",
  "email": "..."
}
```

Также генерируется WebSite schema.

### 6. SEO Preview

#### Google SERP Preview
- Показывает title, description, URL
- Предупреждения о длине:
  - Title: хорошо (30-60), предупреждение (<30 или 60-70), ошибка (>70)
  - Description: хорошо (120-160), предупреждение (<120 или 160-180), ошибка (>180)

#### Telegram Link Preview
- Показывает карточку как в Telegram
- Превью изображение, title, description, URL

---

## Интеграция в конструктор

В `ConstructorPage` добавлена вкладка "SEO" в правой панели:

```jsx
<div className="wb-panel-tabs">
  <button onClick={() => setRightPanelTab('settings')}>Styles</button>
  <button onClick={() => setRightPanelTab('seo')}>SEO</button>
</div>

{rightPanelTab === 'seo' && (
  <SEOMetaPanel
    websiteId={websiteId}
    website={website}
    onUpdate={...}
  />
)}
```

---

## Использование на публичных страницах

### WebsitePublicPage
```jsx
<HelmetProvider>
  <WebsiteMetaTags website={mergedSchema} agent={agent} />
  {/* ... renderer ... */}
</HelmetProvider>
```

### PreviewPage
```jsx
<HelmetProvider>
  <PreviewMetaTags title={schema?.title} description="Preview mode" />
  {/* ... renderer ... */}
</HelmetProvider>
```

---

## Зависимости

### Backend
```
pillow>=10.0.0  # Добавлено в requirements.txt
```

### Frontend
```
react-helmet-async@^3.0.0  # Уже было в package.json
```

---

## Проверка работы

1. Открыть конструктор сайта
2. Переключиться на вкладку "SEO" в правой панели
3. Заполнить:
   - Page Title: "Мой бизнес"
   - Meta Description: "Описание для поисковиков..."
4. Загрузить favicon (drag-and-drop или выбор файла)
5. Сгенерировать или загрузить OG Image
6. Посмотреть превью в вкладке Preview
7. Опубликовать сайт
8. Открыть публичный URL - проверить мета-теги в DevTools

---

## Планы на будущее

- [ ] Автогенерация OG изображения через AI (интеграция с DeepSeek для генерации картинки)
- [ ] Поддержка многоязычных сайтов (hreflang)
- [ ] Sitemap.xml генерация
- [ ] Robots.txt настройка
- [ ] SEO аудит (проверка битых ссылок, скорости загрузки)
