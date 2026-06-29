# AI-генерация лендингов (fullpage)

Первичная генерация: AI выдаёт HTML body с Tailwind CSS; платформа сохраняет один блок `fullpage`, санитизирует и подключает JS-runtime для меню, каруселей, FAQ и форм.

## Пайплайн (4 LLM-прохода)

Сервис: `backend/app/services/website_generation_service.py`, метод `generate_website()`.

| Шаг | System prompt | Назначение |
|-----|---------------|------------|
| 1 | `WEBSITE_CODER_SYSTEM_PROMPT` | Уникальный HTML + обязательные `data-*` паттерны |
| 2 | `WEBSITE_REFINE_SYSTEM_PROMPT` | Визуальное качество; **добавить** отсутствующие `data-*` |
| 3 | `WEBSITE_ADAPTIVE_SYSTEM_PROMPT` | Адаптив (mobile/tablet), **не ломать** `data-*` |
| 4 | `WEBSITE_FINAL_QA_SYSTEM_PROMPT` | Финальный чеклист интерактивности и формы |

После генерации: `apply_generated_html()`:

1. `sanitize_fullpage_html()` — XSS, удаление `onclick` / опасных `<script>`
2. `strip_decorative_chat_widgets()` — убрать фейковые чат-FAB (реальный виджет — от платформы)
3. `inject_landing_interactivity_runtime()` — `<script data-rsd-landing-runtime>` в HTML

Тот же постпроцесс применяется при сохранении/редактировании fullpage-блока в `router_websites/router.py`.

## Интерактивность: почему только `data-*`

| Подход | Результат |
|--------|-----------|
| `onclick="..."` | **Удаляется** санитайзером |
| Кастомный `<script>` с `fetch` / `eval` | **Блокируется** санитайзером |
| `data-menu-toggle`, `data-carousel`, `data-accordion`, … | **Работает** через платформенный runtime |

Обязательные паттерны (см. `WEBSITE_INTERACTIVITY_INSTRUCTIONS` в коде):

- **Бургер:** `data-menu-toggle` + `data-mobile-menu` (`class="hidden md:hidden"` на мобиле)
- **Отзывы:** `data-carousel` + `data-slide` + `data-carousel-prev` / `data-carousel-next`
- **FAQ:** `data-accordion` + `data-accordion-trigger` + `data-accordion-panel`
- **Форма:** `data-rsd-form="lead"`, `name="fio"`, `name="phone"` — см. [PUBLIC_FORMS.md](./PUBLIC_FORMS.md)

В user prompt первичной генерации (`_build_generation_user_prompt`) дублируется блок **MANDATORY INTERACTIVITY — VERIFY BEFORE OUTPUT**.

## Где подключается JS-runtime

| Контекст | Источник runtime |
|----------|------------------|
| Сохранённый HTML в БД | Бэкенд: `inject_landing_interactivity_runtime()` |
| Превью в конструкторе (iframe) | Фронт: `FullpageRenderer` → `LANDING_MENU_CAROUSEL_RUNTIME` если маркера ещё нет |
| Формы на лендинге | Фронт: `LANDING_FORM_RUNTIME` + `window.__RSD_LANDING__` при `agent_id` |

Исходники runtime (должны быть синхронны):

- `backend/app/services/website_interactivity.py`
- `frontend/src/website-builder/utils/landingInteractivity.js`

Runtime также содержит **fallback-эвристики** (секции `faq` / `testimonial`, кнопки меню без явного `data-menu-toggle`) — страховка, если модель пропустила атрибуты. Основной путь — корректная разметка с `data-*` из промптов.

## Редактирование после генерации

- **Промпт в конструкторе:** `edit_block_with_prompt` → `edit_website_with_prompt` (smart merge SEARCH/REPLACE или полный HTML).
- Промпты редактирования сохраняют `data-*` (`WEBSITE_EDIT_SYSTEM_PROMPT`, `WEBSITE_EDIT_SMART_MERGE_PROMPT`).
- После edit — тот же sanitize + inject runtime.

## Модели и лимиты

- `WEBSITE_GENERATION_MODEL` / `WEBSITE_EDIT_MODEL` — из settings (по умолчанию deepseek-chat).
- Первичная генерация: до `_PRIMARY_GENERATION_MAX_OUTPUT_TOKENS` (384K) на проход.
- Редактирование: `_EDIT_MAX_OUTPUT_TOKENS` (16K).

## История регрессии (2026-06-21)

Коммит `c820034` временно свёл генерацию к 2 проходам и ослабил чеклист интерактивности в user prompt — из-за этого AI чаще отдавал разметку без `data-*`, элементы выглядели кликабельными, но не работали после санитизации.

**Восстановлено:** 4 прохода + жёсткие промпты на `data-*` на всех этапах + усиленный runtime (2026-06-29).

## Тесты

```bash
python -m pytest backend/app/tests/test_website_interactivity.py -q
python -m pytest backend/app/tests/test_website_generation_save.py -q
```
