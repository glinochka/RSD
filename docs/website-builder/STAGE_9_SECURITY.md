# Этап 9: Безопасность и изоляция сайтов

## Статус: ✅ Реализован

## Описание

Реализована комплексная система безопасности: CSP заголовки, санитизация HTML/CSS, CSS isolation, rate limiting, iframe sandbox, security audit logging. Пользовательский код изолирован от платформы и друг от друга.

---

## Реализованный функционал

### 1. Content Security Policy (CSP)

**Файл:** `backend/app/middleware/security.py` - `CSPMiddleware`

Добавляет security headers ко всем website-related endpoints:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' *.rsd-ai.ru rsd-ai.ru;
  style-src 'self' 'unsafe-inline' *.rsd-ai.ru rsd-ai.ru fonts.googleapis.com;
  img-src 'self' data: https: blob:;
  font-src 'self' fonts.gstatic.com data:;
  connect-src 'self' *.rsd-ai.ru rsd-ai.ru;
  frame-src 'self';
  object-src 'none';
  base-uri 'self';
  form-action 'self';
  frame-ancestors 'none';
  upgrade-insecure-requests;

X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

Применяется к путям:
- `/api/v1/websites/*`
- `/public-website/*`
- `/w/*`
- `/preview/*`

### 2. HTML/CSS Sanitization

**Файл:** `backend/app/services/website_sanitization_service.py`

#### HTML Sanitization (bleach)

Разрешённые теги:
```python
ALLOWED_TAGS = {
    'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'b', 'em', 'i', 'u', 'strike', 'del', 's',
    'a', 'img', 'ul', 'ol', 'li',
    'blockquote', 'code', 'pre', 'hr',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
}
```

Запрещённые теги:
- `<script>`, `<iframe>`, `<object>`, `<embed>`, `<applet>`, `<form>`

Запрещённые атрибуты:
- `onerror`, `onload`, `onclick`, и все `on*` event handlers
- `javascript:` URLs

#### CSS Sanitization

Запрещённые CSS правила:
- `@import` - предотвращает загрузку внешних стилей
- `expression()` - IE CSS expressions
- `behavior`, `-moz-binding` - HTC/XBL behaviors

Разрешённые CSS свойства (полный список в файле сервиса):
- Typography, colors, spacing, layout, flexbox/grid
- NO: animations, transforms с опасными значениями

#### Frontend Sanitization

**Файл:** `frontend/src/website-builder/utils/security.js`

```javascript
import { sanitizeHTML, sanitizeCSS, sanitizeURL } from './security';

// Sanitize user content
const clean = sanitizeHTML(dirtyHtml, isBlockContent);
const cleanCSS = sanitizeCSS(userCSS);
const safeUrl = sanitizeURL(userUrl);

// Validate content
const check = checkSuspiciousContent(content);
// Returns: { safe: boolean, issues: string[] }
```

### 3. CSS Isolation

**Файлы:**
- `backend/app/services/website_css_isolation.py`
- `frontend/src/website-builder/utils/security.js` - `scopeCSS()`

Техника: **Class Prefixing**

```css
/* Original */
.header { color: red; }
.btn:hover { background: blue; }

/* Scoped for website ID 123 */
.site-123 .header { color: red; }
.site-123 .btn:hover { background: blue; }
```

В `WebsiteRenderer` все стили обёрнуты в scope class:

```jsx
<div className={`site-${websiteId}`}>
  <style>{scopedCSS}</style>
  {/* content */}
</div>
```

Это гарантирует, что стили одного сайта не влияют на другие.

### 4. Rate Limiting

**Файл:** `backend/app/middleware/security.py` - `RateLimitMiddleware`

Конфигурация:
```python
RATE_LIMITS = {
    "website_generate": (10, 3600),      # 10 per hour
    "website_export": (5, 3600),         # 5 per hour
    "website_publish": (20, 3600),       # 20 per hour
    "website_domain_verify": (10, 300),  # 10 per 5 minutes
}
```

Использует Redis если доступен, иначе in-memory fallback.

Ответ при превышении:
```json
{
  "detail": "Rate limit exceeded. Please try again later.",
  "retry_after": 3600
}
```

### 5. Security Audit Logging

**Файл:** `backend/app/middleware/security.py` - `SecurityAuditMiddleware`

Обнаруживает подозрительные паттерны:
- XSS attempts: `<script`, `javascript:`, `onerror=`, etc.
- SQL injection: `' OR `, `UNION SELECT`, `; DROP `
- Path traversal: `../`, `..\`, URL-encoded variants

Логирует:
- Тип атаки
- URL и метод запроса
- IP адрес
- User agent

Для критических атак (XSS, SQLi) - немедленный 403 Forbidden.

### 6. Iframe Sandbox (Preview)

**Файл:** `frontend/src/website-builder/components/SecurePreview.jsx`

Sandbox permissions:
```
allow-same-origin
allow-scripts
allow-popups
allow-popups-to-escape-sandbox
allow-forms
```

Встроенная CSP в iframe document:
```javascript
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https: blob:",
  "object-src 'none'",
].join('; ');
```

Дополнительная защита в iframe:
- `window.parent = null`
- `window.open()` disabled
- Scope wrapper для CSS isolation

### 7. Input Validation

**Backend (Pydantic):**
- `schemas.py` - strict validation на всех endpoints
- Max length: title (100), description (500), slug (50), domain (253)
- Regex patterns: slug, domain, color hex values

**Frontend:**
- Zod-like validation через Pydantic schemas
- Max length на все текстовые поля
- URL sanitization

### 8. Access Control

**Уже реализовано в router:**
- `get_current_user` dependency
- Проверка `website.owner_id == current_user.id`
- 403 Forbidden для чужих ресурсов

**Декоратор для дополнительной защиты:**
```python
from app.middleware import require_website_owner

@router.get("/{website_id}/...")
@require_website_owner()
async def endpoint(website_id: int, current_user: User = Depends(...)):
    ...
```

---

## Структура файлов

```
backend/
├── app/
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── security.py          # CSP, RateLimit, SecurityAudit
│   └── services/
│       ├── website_sanitization_service.py  # HTML/CSS sanitization
│       └── website_css_isolation.py          # CSS scoping
│
frontend/
└── src/website-builder/
    ├── components/
    │   ├── SecurePreview.jsx    # Iframe sandbox
    │   └── WebsiteRenderer.jsx  # CSS isolation wrapper
    └── utils/
        └── security.js          # Frontend sanitization
```

---

## Зависимости

### Backend
```
bleach[css]>=6.1.0  # Added to requirements.txt
```

### Frontend
```
dompurify@^3.0.8   # Added to package.json
```

---

## Интеграция

### server.py
```python
from app.middleware import (
    CSPMiddleware,
    RateLimitMiddleware,
    SecurityAuditMiddleware,
)

app.add_middleware(SecurityAuditMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CSPMiddleware)
```

### WebsiteRenderer (CSS Isolation)
```jsx
// Scope class for isolation
const scopeClass = id ? `site-${id}` : 'site-preview';

// Scoped wrapper
<div className={scopeClass} style={{ all: 'initial' }}>
  <style>{scopedCSS}</style>
  {/* Website content */}
</div>
```

### SecurePreview (Iframe Sandbox)
```jsx
import { SecurePreview } from './components';

<SecurePreview
  websiteId={websiteId}
  html={htmlContent}
  css={cssContent}
  allowScripts={true}
  sandbox="allow-scripts allow-same-origin"
/>
```

---

## Тестирование безопасности

1. **XSS Test:**
   ```html
   <script>alert('xss')</script>
   ```
   Ожидаемый результат: теги удалены или экранированы

2. **CSS Injection Test:**
   ```css
   @import url('https://evil.com/malicious.css');
   ```
   Ожидаемый результат: `@import` удалён

3. **Rate Limit Test:**
   Быстро вызвать API endpoint 11+ раз
   Ожидаемый результат: HTTP 429 Too Many Requests

4. **CSP Test:**
   Проверить response headers в DevTools
   Ожидаемый результат: CSP заголовки присутствуют

5. **CSS Isolation Test:**
   Открыть 2 сайта в разных вкладках
   Ожидаемый результат: стили первого не влияют на второй

---

## Планы на будущее

- [ ] Separate origin для сайтов (`sites.rsd-ai.ru`)
- [ ] Cookie isolation (SameSite=None для сайтов)
- [ ] Shadow DOM для рендера (alternative to CSS scoping)
- [ ] CSP nonce для inline scripts
- [ ] HSTS (Strict-Transport-Security) headers
- [ ] Security.txt для security researchers
