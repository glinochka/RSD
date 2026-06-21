"""Website Generation Service — AI-powered website code generation.

Instead of generating structured JSON that feeds into fixed templates,
this service acts as an AI frontend coder that produces complete,
unique HTML+CSS pages with Tailwind CSS.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..alembic.database import async_session_maker
from ..alembic.models import WebsiteBlock
from ..router_websites.dao import WebsiteBlockDAO, WebsiteDAO
from ..config import settings
from .ai_authoring import ai_client
from .website_html_cleanup import strip_decorative_chat_widgets
from .website_interactivity import inject_landing_interactivity_runtime
from .website_sanitization_service import get_website_sanitization_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

WEBSITE_INTERACTIVITY_INSTRUCTIONS = """\
INTERACTIVITY (MANDATORY — page must be fully functional on first load, no manual fixes):
The platform automatically injects a JavaScript runtime that activates elements \
with data-* attributes. The platform also injects a floating AI chat widget after publish — \
never add chat sections, messenger mockups, or chat input fields to the HTML. \
Use ONLY these patterns — do NOT write custom <script> \
for menus, carousels, FAQ, or tabs. Do NOT use onclick/onchange/on* handlers \
(they are stripped by security sanitization).

1. MOBILE BURGER MENU (required on every page):
   <button type="button" data-menu-toggle aria-label="Открыть меню" aria-expanded="false">...</button>
   <div data-mobile-menu class="hidden md:hidden">...nav links...</div>
   On desktop (md+): show horizontal nav. On mobile: hide data-mobile-menu by default (class="hidden").

2. TESTIMONIALS / REVIEWS CAROUSEL (required when testimonials section exists):
   <div data-carousel class="relative">
     <div data-slide>...review 1...</div>
     <div data-slide class="hidden">...review 2...</div>
     <div data-slide class="hidden">...review 3...</div>
     <button type="button" data-carousel-prev aria-label="Предыдущий">←</button>
     <button type="button" data-carousel-next aria-label="Следующий">→</button>
   </div>
   Only the first slide is visible initially; others have class="hidden".

3. FAQ ACCORDION (required when FAQ section exists — pick ONE approach):
   Option A (preferred):
   <div data-accordion>
     <div data-accordion-item>
       <button type="button" data-accordion-trigger aria-expanded="false">Вопрос?</button>
       <div data-accordion-panel class="hidden">Ответ.</div>
     </div>
     ...more items...
   </div>
   Option B (native HTML, no JS needed):
   <details><summary>Вопрос?</summary><p>Ответ.</p></details>

4. TABS (optional, when tabbed content exists):
   <div data-tabs>
     <button type="button" data-tab-trigger aria-selected="true">Tab 1</button>
     <button type="button" data-tab-trigger aria-selected="false">Tab 2</button>
     <div data-tab-panel>Content 1</div>
     <div data-tab-panel class="hidden">Content 2</div>
   </div>

5. SMOOTH SCROLL: use anchor links href="#section-id" — works without JS.

Every interactive element you add MUST use the data-* patterns above or native \
<details>/<summary>. Never leave decorative-only buttons that do nothing.
"""

WEBSITE_CODER_SYSTEM_PROMPT = """\
You are an elite frontend developer and UI/UX designer who creates stunning, \
modern single-page websites. You write production-quality HTML with Tailwind CSS.

TASK: Generate a COMPLETE, UNIQUE, BEAUTIFUL, FULLY FUNCTIONAL single-page website as raw HTML.

CRITICAL RULES:
1. Output ONLY the HTML code inside <body>. No <!DOCTYPE>, <html>, <head>, or <body> tags.
2. Use Tailwind CSS classes exclusively for styling (CDN is already loaded).
3. The design must be UNIQUE and INDIVIDUAL — not a generic template.
4. Use modern design patterns: glassmorphism, gradients, subtle animations, asymmetric layouts.
5. Language: ALL visible text must be in RUSSIAN.
6. Mobile-first responsive design (sm:, md:, lg: breakpoints).
7. Include smooth scroll behavior via anchor links.
8. Use semantic HTML5 elements (header, nav, main, section, footer).
9. Include proper id attributes on sections for navigation anchors.
10. CSS animations via Tailwind are preferred (transition, animate-, hover:).

""" + WEBSITE_INTERACTIVITY_INSTRUCTIONS + """

DESIGN PRINCIPLES:
- Hero section: bold, eye-catching, with a strong value proposition
- Typography: use font-weight variety (font-light, font-bold, font-extrabold)
- Spacing: generous whitespace, don't cram content
- Colors: harmonious palette, use gradients where appropriate
- Cards/blocks: rounded corners, subtle shadows, hover effects via Tailwind
- Icons: use inline SVG icons (simple, clean) or Unicode symbols where appropriate
- Sections: each section should have a DIFFERENT visual rhythm and layout
- CTA buttons: prominent, with hover/focus states
- Footer: clean, organized; social links ONLY when explicitly listed in the brief (see SOCIAL LINKS rules)

SOCIAL LINKS (footer and contact sections):
- Use ONLY links explicitly provided in INDIVIDUAL BRIEF or CONTACT INFO
- Allowed platforms for Russia: VK (ВКонтакте), Telegram, WhatsApp, MAX, YouTube
- Do NOT add Facebook, Twitter/X, Instagram, LinkedIn, TikTok icons or links unless explicitly provided
- If no social links are provided, omit the social icons block entirely — do not invent placeholder icons

STRUCTURE (adapt creatively per industry):
1. Navigation bar (sticky, with backdrop-blur) — MUST include working mobile burger menu
2. Hero section (full-width, impactful)
3. 3-5 content sections (services/features, about, testimonials/cases, process/FAQ, etc.)
   - If testimonials section exists → MUST include working data-carousel
   - If FAQ section exists → MUST include working data-accordion or <details>/<summary>
4. Call-to-action section
5. Contact section
6. Footer

AVOID:
- Generic "Lorem ipsum" text
- Identical card layouts repeated across all sections
- Plain white backgrounds for everything
- Boring symmetric grids without variation
- Cookie-cutter template look
- Placeholder contacts and fake data (e.g., +7 (999) 999-99-99, hello@example.com, "Иван Иванов")
- Generic service names ("Услуга 1", "Базовая услуга") when business context is available
- Branding that does not match provided business name/description
- Floating chat buttons, messenger bubbles, live-chat icons (platform injects a real chat widget automatically)
- Decorative fixed-position chat FABs in corners
- Embedded chat interfaces of ANY kind: full chat sections, messenger mockups, message-bubble UIs,
  fake "online consultant" panels, chat input fields, or a "Чат" / "Написать нам" block in page content
- Do NOT build chat UI in the landing HTML — the platform adds a floating widget after publish;
  duplicating chat on the page is forbidden

FORMS (contact / lead capture):
- Use real HTML <form> elements (not fake buttons) in contact/CTA sections
- REQUIRED fields only: fio (text), phone (tel)
- Optional: message (textarea) — include only if there is a clear reason; otherwise omit
- Add data-rsd-form="lead" on the form tag
- Use name attributes on inputs: name="fio" and name="phone" (type="tel" for phone)
- Do NOT add action/method to external URLs — submission is handled automatically by the platform
- Labels in Russian: «ФИО», «Телефон»; optional message label: «Комментарий (необязательно)»
- Do NOT add a separate booking widget or service/date picker — the contact form is enough
"""

WEBSITE_EDIT_SYSTEM_PROMPT = """\
You are an expert frontend developer editing an existing website's HTML code.

The user will describe desired changes in natural language.
You receive the current HTML and must return the MODIFIED HTML with the requested changes applied.

CRITICAL RULES - PRESERVATION IS KEY:
1. Output ONLY the modified HTML (the body content, no DOCTYPE/html/head/body wrappers).
2. Keep ALL existing structure, sections, and content unless EXPLICITLY asked to remove them.
3. NEVER remove existing sections like footer, navigation, header, contact sections, etc.
4. NEVER modify sections that the user didn't ask to change.
5. Maintain responsive design (sm:, md:, lg: breakpoints).
6. All text must remain in RUSSIAN.
7. Preserve existing data-* attributes for interactivity (data-menu-toggle, data-carousel, data-accordion, etc.).
8. Preserve section id attributes for navigation.
9. Make ONLY the specific changes the user requested. Don't redesign the whole page.
10. If the user asks to change colors/theme, update Tailwind color classes consistently.
11. If adding new sections, match the existing design language and place them appropriately.
12. When adding a new section, ensure it integrates with existing layout (e.g., footer stays at bottom).
13. Do NOT add embedded chat UIs, messenger mockups, or fake online-consultant panels — the platform injects a floating chat widget automatically.

""" + WEBSITE_INTERACTIVITY_INSTRUCTIONS + """

IMAGES AND MEDIA:
- If user references uploaded images, insert them using proper <img> tags with the image as base64 data URL.
- Replace placeholder images/gray boxes with actual images when provided.
- Use object-fit: cover for consistent image sizing with Tailwind's object-cover class.
- Add proper alt attributes to all images in Russian.

YANDEX MAPS INTEGRATION:
- When user asks to add a map, use the official Yandex Maps Embed API:
  <iframe src="https://yandex.ru/map-widget/v1/?ll=LONGITUDE%2CLATITUDE&z=16&pt=LONGITUDE%2CLATITUDE" 
         width="100%" height="400" frameborder="0" allowfullscreen></iframe>
- Or for JavaScript API (more control), use:
  <div id="map" style="width:100%;height:400px;"></div>
  <script src="https://api-maps.yandex.ru/2.1/?lang=ru_RU"></script>
  <script>
    ymaps.ready(function() {
      var myMap = new ymaps.Map("map", { center: [LATITUDE, LONGITUDE], zoom: 16 });
      var placemark = new ymaps.Placemark([LATITUDE, LONGITUDE], { hintContent: "COMPANY_NAME" });
      myMap.geoObjects.add(placemark);
    });
  </script>
- If address is provided but not coordinates, use descriptive placeholder with the address text.

EXAMPLE SCENARIOS:
- User says "add testimonials section" → Add the section but keep ALL existing content including footer.
- User says "change hero color to blue" → Only update hero background color, preserve everything else.
- User says "make text larger" → Only update font sizes in appropriate sections, preserve all sections.
- User says "add this image to hero" → Replace hero background or add image with the provided image data.
- User says "add Yandex map with our address" → Add map section with iframe or JS API before footer.

OUTPUT: Complete HTML body content with ALL original sections + requested modifications.
"""

WEBSITE_EDIT_PROMPT_IMPROVEMENT = """\
Ты помогаешь обычным людям (не программистам) редактировать лендинг через AI-конструктор.

Пользователь написал запрос своими словами. Переформулируй его в чёткую техническую инструкцию \
для frontend-разработчика, который будет менять HTML.

Правила:
1. Сохрани исходное намерение пользователя — не добавляй новых пожеланий.
2. Если запрос расплывчатый — выбери наиболее вероятную интерпретацию и сформулируй явно.
3. Укажи конкретику: какие секции, цвета, тексты, элементы затронуть.
4. Пиши по-русски, 1–3 коротких предложения.
5. Только текст инструкции, без markdown и пояснений.
"""

WEBSITE_EDIT_SMART_MERGE_PROMPT = """\
You are an expert frontend developer performing surgical edits to website HTML.

TASK: Apply the user's requested changes using SEARCH/REPLACE blocks. This is similar to how modern IDEs like Cursor or Copilot apply code changes.

CRITICAL RULES:
1. Identify the EXACT sections of HTML that need to be modified.
2. For each change, provide a SEARCH/REPLACE block.
3. SEARCH must match the original HTML exactly (including whitespace, but you can use flexible matching for class order).
4. If creating NEW content, use SEARCH with a nearby anchor element and REPLACE with the anchor + new content.
5. NEVER omit sections - if you're unsure about a section, leave it unchanged (don't include in any SEARCH/REPLACE).
6. All text must remain in RUSSIAN unless adding new content.
7. Preserve all data-* interactivity attributes and interactive markup.
8. Maintain responsive design classes (sm:, md:, lg:).

""" + WEBSITE_INTERACTIVITY_INSTRUCTIONS + """

SEARCH/REPLACE FORMAT:
```html
<<<<<<< SEARCH
[exact original HTML to find]
=======
[new/modified HTML to replace with]
>>>>>>> REPLACE
```

EXAMPLES:

Example 1 - Adding a testimonials section after services:
```html
<<<<<<< SEARCH
  </section>
  <!-- End Services -->
  
  <footer class="bg-gray-900">
=======
  </section>
  <!-- End Services -->
  
  <!-- Testimonials Section -->
  <section id="testimonials" class="py-20 bg-white">
    <div class="container mx-auto px-4">
      <h2 class="text-3xl font-bold text-center mb-12">Отзывы клиентов</h2>
      <!-- testimonials content -->
    </div>
  </section>
  
  <footer class="bg-gray-900">
>>>>>>> REPLACE
```

Example 2 - Changing hero background color:
```html
<<<<<<< SEARCH
  <section id="hero" class="relative bg-blue-600 text-white">
=======
  <section id="hero" class="relative bg-green-600 text-white">
>>>>>>> REPLACE
```

Example 3 - Modifying navigation text:
```html
<<<<<<< SEARCH
      <a href="#services" class="text-white hover:text-blue-200">Услуги</a>
=======
      <a href="#services" class="text-white hover:text-blue-200">Наши услуги</a>
>>>>>>> REPLACE
```

GUIDANCE:
- Use multiple SEARCH/REPLACE blocks for multiple independent changes
- Each SEARCH should find enough context to be unique (include parent element or siblings)
- If adding new section, place it logically (e.g., after hero, before footer)
- Keep all original sections unless explicitly asked to remove them

OUTPUT FORMAT:
Provide ONLY the SEARCH/REPLACE blocks, no other text or explanations.
"""

WEBSITE_POLISH_SYSTEM_PROMPT = """\
You are a senior frontend specialist performing a single production polish pass on a \
landing page HTML.

Output ONLY the polished HTML (body content only, no wrappers).

VISUAL QUALITY:
- Consistent color palette across all sections
- Proper hover/focus states on interactive elements
- Adequate spacing and padding (px-4, py-8, etc.)
- Section variety (different layouts for different sections)
- Accessibility basics (alt attributes, semantic structure, contrast)
- Remove any empty or placeholder content
- Ensure navigation anchors work correctly
- Fix any Tailwind class typos or conflicts
- Make CTAs stand out visually

RESPONSIVE (mobile <=640px, tablet 641-1024px, preserve desktop lg/xl):
- All sections work on small screens; typography scales (no oversized headings on mobile)
- Sensible vertical rhythm; prevent horizontal scrolling and content overflow
- Cards/sections stack naturally where needed; comfortable tap targets
- Do not degrade desktop layout, spacing, or section composition
- Avoid drastic redesign or section reordering

INTERACTIVITY QA:
- Burger menu: data-menu-toggle + data-mobile-menu present and correct
- Carousel (if testimonials exist): data-carousel + data-slide + prev/next buttons
- FAQ (if FAQ section exists): data-accordion or native <details>/<summary>
- If interactive markup is missing but the section implies it, ADD data-* patterns
- No placeholder/template text or fake contacts

PRESERVATION (CRITICAL):
- Keep ALL content sections exactly as provided (header, nav, sections, footer)
- Keep ALL data-* interactivity attributes intact
- Preserve business copy and CTA intent
- Only apply targeted visual/layout/responsive fixes — do not redesign the page
- Do not change language from Russian
- Do not replace data-* patterns with onclick handlers or non-functional buttons
"""


def _build_generation_user_prompt(
    business_name: str,
    business_description: str,
    services: list[dict] | None = None,
    contacts: dict[str, str] | None = None,
    primary_color: str | None = None,
    dark_mode: bool = False,
    generation_brief: str | None = None,
) -> str:
    """Build the detailed user prompt for website generation."""
    parts = [
        f"Create a stunning landing page for this business:\n",
        f"BUSINESS NAME: {business_name}",
        f"DESCRIPTION: {business_description}",
    ]

    if services:
        parts.append("\nSERVICES:")
        for svc in services:
            name = svc.get("name", "")
            desc = svc.get("description", "")
            price = svc.get("price", "")
            line = f"  - {name}"
            if desc:
                line += f": {desc}"
            if price:
                line += f" ({price})"
            parts.append(line)

    if contacts:
        parts.append("\nCONTACT INFO (include on the page):")
        for key, value in contacts.items():
            if value:
                parts.append(f"  {key}: {value}")

    parts.append(f"\nTHEME: {'DARK (use dark backgrounds like slate-900/gray-900, light text)' if dark_mode else 'LIGHT (use white/light backgrounds, dark text)'}")

    if primary_color:
        parts.append(f"BRAND COLOR: {primary_color} — use this as the accent/primary color throughout.")
        parts.append("Build a harmonious color scheme around this brand color.")
    else:
        parts.append("Choose a modern, appropriate color scheme for this industry.")

    if generation_brief:
        parts.append(f"\nINDIVIDUAL BRIEF (must be reflected in design and copy): {generation_brief}")

    parts.append(
        "\nPAGE STRUCTURE REQUIREMENT: Build clear structure as "
        "Navbar -> Header (hero) -> multiple content sections -> contact section -> footer."
    )
    parts.append(
        "Sections must be tailored to this exact business context (problem, offer, process, trust, CTA)."
    )
    parts.append("\nREMEMBER: All visible text on the page must be in RUSSIAN. Make it professional, compelling, and conversion-focused.")
    parts.append("The design must feel CUSTOM-MADE for this specific business, not a generic template.")
    parts.append("\nOutput ONLY the HTML code (body content). No markdown fences, no explanations.")

    return "\n".join(parts)


def _build_polish_user_prompt(
    *,
    html_content: str,
    business_name: str,
    dark_mode: bool,
    primary_color: str | None,
) -> str:
    """User prompt for the single post-generation polish pass."""
    return (
        f"Business: {business_name}\n"
        f"Theme: {'dark' if dark_mode else 'light'}\n"
        f"Brand color: {primary_color or 'auto'}\n\n"
        f"Polish this landing page HTML for production quality, responsive layout, "
        f"and interactive QA:\n\n{html_content}"
    )


def _edit_prompt_needs_clarification(raw_prompt: str) -> bool:
    """Return True when a casual edit request should be clarified via LLM."""
    text = raw_prompt.strip()
    if not text:
        return False
    if len(text) < 25:
        return True
    vague_patterns = (
        "красивее",
        "лучше",
        "улучш",
        "поправь",
        "сделай нормально",
        "не нравится",
        "как-то",
        "плохо выглядит",
        "пофикси",
        "fix it",
        "make it better",
    )
    lower = text.lower()
    if any(pattern in lower for pattern in vague_patterns) and len(text) < 80:
        return True
    return False


def _extract_html_from_response(raw: str) -> str:
    """Extract HTML from AI response, handling markdown fences."""
    if not raw:
        raise ValueError("Empty response from AI")

    # Remove markdown code fences if present
    html_block = re.search(r"```(?:html)?\s*\n(.*?)```", raw, re.DOTALL)
    if html_block:
        return html_block.group(1).strip()

    # If it starts with a tag, it's raw HTML
    stripped = raw.strip()
    if stripped.startswith("<"):
        return stripped

    # Try to find the first HTML tag
    first_tag = re.search(r"<(?:header|nav|div|section|main|!--)", stripped)
    if first_tag:
        return stripped[first_tag.start():].strip()

    return stripped


def _parse_search_replace_blocks(response: str) -> list[dict]:
    """Parse SEARCH/REPLACE blocks from AI response.
    
    Returns list of dicts with 'search' and 'replace' keys.
    Format:
    <<<<<<< SEARCH
    [original]
    =======
    [replacement]
    >>>>>>> REPLACE
    """
    blocks = []
    # Pattern to match search/replace blocks
    pattern = r'<<<<<<<\s*SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>>\s*REPLACE'
    
    for match in re.finditer(pattern, response, re.DOTALL):
        search_content = match.group(1).strip()
        replace_content = match.group(2).strip()
        if search_content:  # Only add if search is not empty
            blocks.append({
                'search': search_content,
                'replace': replace_content,
            })
    
    return blocks


def _apply_search_replace_blocks(original_html: str, blocks: list[dict]) -> str:
    """Apply search/replace blocks to HTML.
    
    Args:
        original_html: The original HTML content
        blocks: List of search/replace blocks from AI
        
    Returns:
        Modified HTML with all replacements applied
        
    Raises:
        ValueError: If a search block cannot be found in the original
    """
    result = original_html
    applied_count = 0
    failed_searches = []
    
    for i, block in enumerate(blocks):
        search = block['search']
        replace = block['replace']
        
        # Try exact match first
        if search in result:
            result = result.replace(search, replace, 1)
            applied_count += 1
            continue
        
        # Try flexible matching (normalize whitespace)
        # Create a pattern that allows for variable whitespace
        search_normalized = re.sub(r'\s+', r'\\s+', re.escape(search))
        
        # Try to find a match with flexible whitespace
        match = re.search(search_normalized, result, re.DOTALL)
        if match:
            result = result[:match.start()] + replace + result[match.end():]
            applied_count += 1
        else:
            failed_searches.append({
                'index': i,
                'search_preview': search[:100] + '...' if len(search) > 100 else search
            })
    
    if failed_searches:
        logger.warning(f"[SmartMerge] {len(failed_searches)} search blocks could not be applied")
        for f in failed_searches:
            logger.warning(f"  - Block {f['index']}: {f['search_preview']}")
    
    logger.info(f"[SmartMerge] Applied {applied_count}/{len(blocks)} changes")
    return result


def _validate_html_preservation(original: str, modified: str, threshold: float = 0.5) -> dict:
    """Validate that the modified HTML preserves the structure of the original.
    
    Args:
        original: Original HTML
        modified: Modified HTML
        threshold: Minimum acceptable similarity ratio (0-1)
        
    Returns:
        Dict with validation results
    """
    import difflib
    
    # Calculate similarity ratio
    similarity = difflib.SequenceMatcher(None, original, modified).ratio()
    
    # Count sections in both
    original_sections = len(re.findall(r'<section', original, re.IGNORECASE))
    modified_sections = len(re.findall(r'<section', modified, re.IGNORECASE))
    
    original_headers = len(re.findall(r'<header', original, re.IGNORECASE))
    modified_headers = len(re.findall(r'<header', modified, re.IGNORECASE))
    
    original_footers = len(re.findall(r'<footer', original, re.IGNORECASE))
    modified_footers = len(re.findall(r'<footer', modified, re.IGNORECASE))
    
    issues = []
    
    if modified_sections < original_sections:
        issues.append(f"Lost {original_sections - modified_sections} section(s)")
    
    if modified_headers < original_headers:
        issues.append(f"Lost {original_headers - modified_headers} header(s)")
    
    if modified_footers < original_footers:
        issues.append(f"Lost {original_footers - modified_footers} footer(s)")
    
    # Check if similarity is too low
    if similarity < threshold:
        issues.append(f"High divergence detected (similarity: {similarity:.2f})")
    
    return {
        'is_valid': len(issues) == 0,
        'similarity': similarity,
        'sections_original': original_sections,
        'sections_modified': modified_sections,
        'issues': issues,
        'suspicious_change': similarity < 0.3,  # Very different - likely complete rewrite
    }


def _smart_merge_html(original_html: str, ai_modified_html: str) -> str:
    """Intelligently merge AI changes with original HTML.
    
    This function implements a hybrid approach:
    1. If AI returned SEARCH/REPLACE blocks → apply them
    2. If AI returned complete HTML with high similarity → use AI version
    3. If AI returned complete HTML with low similarity → merge carefully
    
    Args:
        original_html: Original HTML content
        ai_modified_html: AI's response (may be complete HTML or search/replace blocks)
        
    Returns:
        Best merged result
    """
    # First, try to parse as search/replace blocks
    search_replace_blocks = _parse_search_replace_blocks(ai_modified_html)
    
    if search_replace_blocks:
        logger.info(f"[SmartMerge] Found {len(search_replace_blocks)} SEARCH/REPLACE blocks")
        
        # Apply the search/replace blocks
        result = _apply_search_replace_blocks(original_html, search_replace_blocks)
        
        # Validate the result
        validation = _validate_html_preservation(original_html, result)
        
        if validation['is_valid']:
            logger.info("[SmartMerge] Changes applied successfully via search/replace")
            return result
        else:
            logger.warning(f"[SmartMerge] Validation issues after search/replace: {validation['issues']}")
            # Fall through to check if AI also provided complete HTML
    
    # Check if AI returned complete HTML
    extracted_html = _extract_html_from_response(ai_modified_html)
    
    if len(extracted_html) > 500 and '<section' in extracted_html:
        # AI returned complete HTML
        validation = _validate_html_preservation(original_html, extracted_html)
        
        if validation['is_valid']:
            logger.info(f"[SmartMerge] Using AI complete HTML (similarity: {validation['similarity']:.2f})")
            return extracted_html
        elif validation['similarity'] > 0.7:
            # High similarity but some issues - trust AI with warning
            logger.warning(f"[SmartMerge] Using AI HTML despite minor issues: {validation['issues']}")
            return extracted_html
        else:
            # Low similarity - AI may have rewritten too much
            logger.error(f"[SmartMerge] AI HTML too different, rejecting: {validation['issues']}")
            raise ValueError(f"AI made too many changes. Issues: {', '.join(validation['issues'])}")
    
    # No valid output found
    raise ValueError("AI did not return valid HTML or search/replace blocks")


def _contains_generic_placeholder_content(html: str) -> bool:
    """Placeholder filtering is intentionally disabled by product decision."""
    return False


def _inject_tailwind_color(html: str, primary_color: str | None) -> str:
    """If a brand color is specified but AI used generic colors, this is a safety net."""
    if not primary_color:
        return html
    return html


# Website model column limits (websites.title, meta_description, og_*)
_WEBSITE_TITLE_MAX_LEN = 100
_WEBSITE_META_DESCRIPTION_MAX_LEN = 500
_WEBSITE_OG_DESCRIPTION_MAX_LEN = 300


def _normalize_website_meta(meta: dict | None) -> dict[str, str]:
    """Clamp meta fields to DB column sizes."""
    meta = meta or {}
    title = str(meta.get("title") or "")[:_WEBSITE_TITLE_MAX_LEN]
    description = str(meta.get("description") or "")[:_WEBSITE_META_DESCRIPTION_MAX_LEN]
    og_description = str(meta.get("og_description") or description)[
        :_WEBSITE_OG_DESCRIPTION_MAX_LEN
    ]
    return {
        "title": title,
        "description": description,
        "og_title": str(meta.get("og_title") or title)[:_WEBSITE_TITLE_MAX_LEN],
        "og_description": og_description,
    }


def _prepare_html_for_db_storage(html: str) -> str:
    """Remove characters that PostgreSQL JSON/text columns reject."""
    if not html:
        return ""
    return "".join(
        ch
        for ch in html
        if ch != "\x00" and (ch in "\t\n\r" or ord(ch) >= 32)
    )


def _build_meta_from_html(html: str, business_name: str, business_description: str) -> dict:
    """Extract meta info from the generated HTML content."""
    return _normalize_website_meta(
        {
            "title": business_name,
            "description": business_description,
        }
    )


# ---------------------------------------------------------------------------
# Generation Result
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    success: bool
    html_content: str | None
    meta: dict | None
    error_message: str | None
    raw_response: str | None


# ---------------------------------------------------------------------------
# Main Service
# ---------------------------------------------------------------------------

class WebsiteGenerationService:
    """AI-powered website code generator — produces complete HTML pages."""

    def __init__(self):
        self.ai_client = ai_client
        # Use separate models for generation and editing:
        # - generation: creative full-page layout synthesis
        # - editing: precise surgical HTML modifications
        configured_generation_model = settings.WEBSITE_GENERATION_MODEL or "deepseek-chat"
        configured_edit_model = (
            settings.WEBSITE_EDIT_MODEL
            or configured_generation_model
            or "deepseek-chat"
        )
        self.generation_model = configured_generation_model.strip()
        self.edit_model = configured_edit_model.strip()
        self.max_retries = 2
        logger.info(
            "[WebsiteGenService] Initialized models: generation=%s, edit=%s",
            self.generation_model,
            self.edit_model,
        )

    async def _call_ai(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> str:
        target_model = (model or self.generation_model).strip()
        response = await self.ai_client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from AI")
        return content

    async def generate_website(
        self,
        business_name: str,
        business_description: str,
        services: list[dict] | None = None,
        contacts: dict[str, str] | None = None,
        primary_color: str | None = None,
        dark_mode: bool = False,
        generation_brief: str | None = None,
    ) -> GenerationResult:
        """Generate a complete website as HTML code.

        The AI acts as a frontend coder, producing unique HTML+Tailwind
        that is rendered in a sandboxed iframe on the frontend.
        """
        last_error = None
        raw_response = None

        logger.info(
            "[WebsiteGen] Starting generate_website for '%s' (model=%s)",
            business_name,
            self.generation_model,
        )
        logger.info(f"[WebsiteGen] Params: dark_mode={dark_mode}, color={primary_color}")
        logger.info(f"[WebsiteGen] Services count: {len(services) if services else 0}")

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "[WebsiteGen] Generation attempt %s/%s (model=%s)",
                    attempt, self.max_retries, self.generation_model,
                )

                # Step 1: Generate the website HTML
                user_prompt = _build_generation_user_prompt(
                    business_name=business_name,
                    business_description=business_description,
                    services=services,
                    contacts=contacts,
                    primary_color=primary_color,
                    dark_mode=dark_mode,
                    generation_brief=generation_brief,
                )
                logger.debug(f"[WebsiteGen] User prompt length: {len(user_prompt)} chars")

                raw_response = await self._call_ai(
                    system_prompt=WEBSITE_CODER_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    model=self.generation_model,
                    temperature=0.75,
                )
                logger.info(f"[WebsiteGen] AI response received, length: {len(raw_response or '')} chars")

                html_content = _extract_html_from_response(raw_response)
                logger.info(f"[WebsiteGen] Extracted HTML length: {len(html_content)} chars")

                # Validate minimum quality
                if len(html_content) < 500:
                    raise ValueError(f"Generated HTML too short ({len(html_content)} chars)")

                if "<section" not in html_content and "<div" not in html_content:
                    raise ValueError("Generated content doesn't contain valid HTML sections")

                # Soft warning for nav/header - AI sometimes uses div-based navigation
                if "<nav" not in html_content and "<header" not in html_content:
                    logger.warning("[WebsiteGen] Generated HTML missing explicit nav/header tags, checking for navigation patterns")
                    # Check for navigation-like patterns (menu, navbar classes, etc.)
                    nav_patterns = ['navbar', 'menu', 'navigation', 'nav-', 'role="navigation"']
                    has_nav_pattern = any(p in html_content.lower() for p in nav_patterns)
                    if not has_nav_pattern:
                        raise ValueError("Generated HTML must include navigation structure (nav, header, or navbar pattern)")

                if _contains_generic_placeholder_content(html_content):
                    raise ValueError("Generated HTML contains generic placeholder/template content")

                logger.info("[WebsiteGen] HTML validation passed")

                # Step 2: Single polish pass (visual quality + responsive + interactivity QA)
                logger.info("[WebsiteGen] Starting polish pass")
                polish_prompt = _build_polish_user_prompt(
                    html_content=html_content,
                    business_name=business_name,
                    dark_mode=dark_mode,
                    primary_color=primary_color,
                )
                polish_raw = await self._call_ai(
                    system_prompt=WEBSITE_POLISH_SYSTEM_PROMPT,
                    user_prompt=polish_prompt,
                    model=self.generation_model,
                    temperature=0.25,
                )
                polished_html = _extract_html_from_response(polish_raw)
                logger.info(f"[WebsiteGen] Polished HTML length: {len(polished_html)} chars")

                if _contains_generic_placeholder_content(polished_html):
                    raise ValueError("Polished HTML contains generic placeholder/template content")

                if len(polished_html) >= len(html_content) * 0.7:
                    html_content = polished_html
                    logger.info("[WebsiteGen] Using polished HTML")
                else:
                    logger.info("[WebsiteGen] Polished HTML too short, using original")

                # Apply brand color safety net
                html_content = _inject_tailwind_color(html_content, primary_color)

                # Extract meta
                meta = _build_meta_from_html(html_content, business_name, business_description)
                logger.info(f"[WebsiteGen] Meta extracted: title='{meta.get('title', '')[:50]}...'")

                logger.info("[WebsiteGen] Generation completed successfully")
                return GenerationResult(
                    success=True,
                    html_content=html_content,
                    meta=meta,
                    error_message=None,
                    raw_response=raw_response,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[WebsiteGen] Generation attempt {attempt} failed: {e}")
                continue

        logger.error(f"[WebsiteGen] All website generation attempts failed: {last_error}")
        return GenerationResult(
            success=False,
            html_content=None,
            meta=None,
            error_message=last_error,
            raw_response=raw_response,
        )

    async def apply_generated_html(
        self,
        website_id: int,
        html_content: str,
        meta: dict,
    ) -> tuple[bool, str | None]:
        """Save generated HTML to the website as a fullpage block."""
        logger.info(f"[WebsiteGenService] apply_generated_html called for website_id={website_id}")
        logger.info(f"[WebsiteGenService] HTML content size: {len(html_content)} chars")
        normalized_meta = _normalize_website_meta(meta)
        logger.info(
            "[WebsiteGenService] Meta: title='%s...', description_len=%s, og_description_len=%s",
            normalized_meta["title"][:50],
            len(normalized_meta["description"]),
            len(normalized_meta["og_description"]),
        )

        try:
            sanitization_service = get_website_sanitization_service()
            try:
                sanitized_html = sanitization_service.sanitize_fullpage_html(html_content)
            except Exception as sanitize_exc:
                logger.warning(
                    "[WebsiteGenService] Fullpage sanitization failed for website_id=%s, "
                    "storing normalized HTML only: %s",
                    website_id,
                    sanitize_exc,
                )
                sanitized_html = _prepare_html_for_db_storage(html_content)
            else:
                sanitized_html = _prepare_html_for_db_storage(sanitized_html)
            sanitized_html = strip_decorative_chat_widgets(sanitized_html)
            sanitized_html = inject_landing_interactivity_runtime(sanitized_html)
            logger.info(
                "[WebsiteGenService] HTML sanitized: %s -> %s chars",
                len(html_content),
                len(sanitized_html),
            )

            async with async_session_maker() as session:
                async with session.begin():
                    website_dao = WebsiteDAO(session)
                    block_dao = WebsiteBlockDAO(session)

                    website = await website_dao.find_one_by_filter(id=website_id)
                    if not website:
                        logger.error(f"[WebsiteGenService] Website not found: {website_id}")
                        return False, "Website not found"

                    logger.info(f"[WebsiteGenService] Found website '{website.title}', updating metadata")

                    # Update website metadata
                    updates = {
                        "title": normalized_meta["title"],
                        "meta_description": normalized_meta["description"],
                        "og_title": normalized_meta["og_title"],
                        "og_description": normalized_meta["og_description"],
                        "custom_styles": {
                            **(website.custom_styles or {}),
                            "rendering_mode": "fullpage",
                        },
                        "generation_status": "completed",
                        "updated_at": datetime.utcnow(),
                    }
                    await website_dao.update(website, updates)
                    logger.info(f"[WebsiteGenService] Website metadata updated for website_id={website_id}")

                    # Clear existing blocks
                    existing_blocks = await block_dao.list_by_website(
                        website_id, only_visible=False
                    )
                    blocks_count = len(existing_blocks)
                    logger.info(f"[WebsiteGenService] Clearing {blocks_count} existing blocks")
                    for block in existing_blocks:
                        await block_dao.delete(block)
                    logger.info(f"[WebsiteGenService] Cleared {blocks_count} existing blocks")

                    # Create single fullpage block
                    logger.info(f"[WebsiteGenService] Creating fullpage block for website_id={website_id}")
                    block = WebsiteBlock(
                        website_id=website_id,
                        type="fullpage",
                        order=1,
                        content={"html": sanitized_html},
                        styles={},
                        is_visible=True,
                    )
                    session.add(block)
                    logger.info(f"[WebsiteGenService] Fullpage block added to session for website_id={website_id}")

                    logger.info(f"[WebsiteGenService] apply_generated_html completed successfully for website_id={website_id}")
                    return True, None
        except Exception as e:
            logger.exception(f"[WebsiteGenService] Error in apply_generated_html for website_id={website_id}: {e}")
            return False, str(e)

    async def improve_edit_prompt(
        self,
        *,
        raw_prompt: str,
        business_name: str = "",
    ) -> str:
        """Clarify a casual user edit request before applying it to HTML."""
        cleaned_input = raw_prompt.strip()
        if not _edit_prompt_needs_clarification(cleaned_input):
            logger.info("[EditWebsite] Skipping prompt clarification — request is specific enough")
            return cleaned_input

        user_message = (
            f"Название бизнеса: {business_name or 'не указано'}\n\n"
            f"Запрос пользователя:\n{cleaned_input}"
        )
        improved = await self._call_ai(
            system_prompt=WEBSITE_EDIT_PROMPT_IMPROVEMENT,
            user_prompt=user_message,
            model=self.edit_model,
            temperature=0.3,
        )
        cleaned = (improved or "").strip()
        return cleaned or raw_prompt.strip()

    async def edit_website_with_prompt(
        self,
        *,
        current_html: str,
        prompt: str,
        business_name: str = "",
    ) -> str:
        """Edit the website HTML based on a natural-language prompt.

        Uses a hybrid approach for reliability:
        1. First attempt: Smart merge with SEARCH/REPLACE blocks (like Cursor/Codex)
        2. Fallback: Complete HTML regeneration with validation
        
        This ensures that even if AI's context is limited, we preserve existing content.
        """
        logger.info(f"[EditWebsite] Starting edit with prompt: {prompt[:100]}...")
        logger.info(f"[EditWebsite] Original HTML length: {len(current_html)} chars")
        
        # Calculate complexity score to decide on approach
        # Simple changes: color, text, minor class changes → use smart merge
        # Complex changes: add sections, redesign → use complete HTML
        complexity_indicators = [
            'добавь', 'добавить', 'add', 'new section', 'новая секция',
            'создай', 'создать', 'create', 'переделай', 'redesign',
            'перемести', 'move', 'удали', 'remove', 'delete'
        ]
        prompt_lower = prompt.lower()
        is_complex_change = any(ind in prompt_lower for ind in complexity_indicators)
        
        # For simple changes, try smart merge with search/replace
        if not is_complex_change and len(current_html) < 10000:
            logger.info("[EditWebsite] Using SMART MERGE approach (search/replace blocks)")
            
            user_message_smart = (
                f"CURRENT WEBSITE HTML (length: {len(current_html)} chars):\n\n"
                f"```html\n{current_html}\n```\n\n"
                f"---\n\n"
                f"USER REQUEST: {prompt}\n\n"
                f"Apply the requested changes using SEARCH/REPLACE blocks. "
                f"Each SEARCH must match the original HTML exactly. "
                f"Provide ONLY the SEARCH/REPLACE blocks, no explanations."
            )
            
            try:
                raw_smart = await self._call_ai(
                    system_prompt=WEBSITE_EDIT_SMART_MERGE_PROMPT,
                    user_prompt=user_message_smart,
                    model=self.edit_model,
                    temperature=0.2,  # Lower temperature for precise edits
                )
                
                # Try to apply smart merge
                merged_html = _smart_merge_html(current_html, raw_smart)
                
                # Validate the result
                validation = _validate_html_preservation(current_html, merged_html)
                
                if validation['is_valid']:
                    logger.info(f"[EditWebsite] Smart merge successful (similarity: {validation['similarity']:.2f})")
                    return merged_html
                else:
                    logger.warning(f"[EditWebsite] Smart merge validation issues: {validation['issues']}")
                    # Fall through to complete HTML approach
            except Exception as e:
                logger.warning(f"[EditWebsite] Smart merge failed: {e}, trying complete HTML")
                # Fall through to complete HTML approach
        
        # For complex changes or if smart merge failed: use complete HTML approach
        logger.info("[EditWebsite] Using COMPLETE HTML approach")
        
        user_message = (
            f"CURRENT WEBSITE HTML:\n\n{current_html}\n\n"
            f"---\n\n"
            f"USER REQUEST: {prompt}\n\n"
            f"Apply the requested changes and output the COMPLETE modified HTML. "
            f"Keep ALL existing sections unless explicitly asked to remove them. "
            f"No markdown fences, no explanations — only the HTML code."
        )

        raw = await self._call_ai(
            system_prompt=WEBSITE_EDIT_SYSTEM_PROMPT,
            user_prompt=user_message,
            model=self.edit_model,
            temperature=0.4,
        )

        # Use smart merge to validate and potentially fix the AI output
        try:
            final_html = _smart_merge_html(current_html, raw)
            
            # Additional validation
            validation = _validate_html_preservation(current_html, final_html)
            
            if len(final_html) < 200:
                raise ValueError("AI returned too short HTML after editing")
            
            if validation['suspicious_change']:
                logger.warning(f"[EditWebsite] AI made suspicious changes: {validation['issues']}")
                # Still return but log the issue for monitoring
            
            logger.info(f"[EditWebsite] Edit complete. Similarity: {validation['similarity']:.2f}, "
                       f"Original sections: {validation['sections_original']}, "
                       f"Modified sections: {validation['sections_modified']}")
            
            return final_html
            
        except ValueError as e:
            logger.error(f"[EditWebsite] Smart merge rejected AI output: {e}")
            # As last resort, try to extract HTML directly
            edited_html = _extract_html_from_response(raw)
            if len(edited_html) >= 200:
                logger.warning("[EditWebsite] Falling back to direct extraction (may have issues)")
                return edited_html
            raise

    # -----------------------------------------------------------------------
    # Legacy compatibility: edit_block_with_prompt for old block-based sites
    # -----------------------------------------------------------------------

    async def edit_block_with_prompt(
        self,
        *,
        block_type: str,
        content: dict[str, Any],
        block_styles: dict[str, Any],
        global_styles: dict[str, Any],
        prompt: str,
    ) -> dict[str, Any]:
        """Edit a single block's content/styles via natural-language prompt.

        Legacy method for backward compatibility with old JSON-based sites.
        """
        system_prompt = (
            "Ты — редактор блоков одностраничного сайта. "
            "Пользователь описывает желаемые изменения. "
            "Верни ТОЛЬКО валидный JSON без markdown:\n"
            '{"content": {...}, "styles": {...}}\n'
            "Сохраняй структуру content (те же ключи), меняй только то, что просит пользователь. "
            "styles — стили блока (padding, textAlign, borderRadius и т.д.), можно оставить пустым {}."
        )
        user_message = json.dumps(
            {
                "block_type": block_type,
                "current_content": content,
                "current_block_styles": block_styles,
                "global_styles": global_styles,
                "instruction": prompt,
            },
            ensure_ascii=False,
        )

        response = await self.ai_client.chat.completions.create(
            model=self.edit_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
        )

        raw = response.choices[0].message.content
        if not raw:
            raise ValueError("Пустой ответ от AI")

        json_str = self._extract_json(raw)
        data = json.loads(json_str)

        if not isinstance(data.get("content"), dict):
            raise ValueError("AI вернул некорректный content")

        return {
            "content": data["content"],
            "styles": data.get("styles") if isinstance(data.get("styles"), dict) else block_styles,
        }

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Extract JSON from AI response."""
        json_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if json_block:
            return json_block.group(1).strip()

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            return raw[start:end + 1]

        raise ValueError("No JSON found in response")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_website_generation_service: WebsiteGenerationService | None = None


def get_website_generation_service() -> WebsiteGenerationService:
    """Get or create singleton instance of WebsiteGenerationService."""
    global _website_generation_service
    if _website_generation_service is None:
        _website_generation_service = WebsiteGenerationService()
    return _website_generation_service
