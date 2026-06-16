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
from .website_sanitization_service import get_website_sanitization_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

WEBSITE_CODER_SYSTEM_PROMPT = """\
You are an elite frontend developer and UI/UX designer who creates stunning, \
modern single-page websites. You write production-quality HTML with Tailwind CSS.

TASK: Generate a COMPLETE, UNIQUE, BEAUTIFUL single-page website as raw HTML.

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
10. JAVASCRIPT FOR UI ANIMATIONS IS ALLOWED: You may include inline <script> tags for interactive elements like:
    - Carousels/sliders (touch-friendly, with prev/next buttons)
    - Mobile navigation menu toggle (hamburger menu)
    - Smooth scroll animations on scroll
    - Accordion/FAQ toggles
    - Tab switching
    - Simple hover effects that require JS
    - Counter animations
    IMPORTANT: Keep JavaScript minimal, clean, and self-contained. No external JS libraries.
    NEVER use document.write, eval, or dynamic script injection.
    All JS must be inside the returned HTML body content (at the end, before </body>).
11. CSS animations via Tailwind are preferred where possible (transition, animate-, hover:).

DESIGN PRINCIPLES:
- Hero section: bold, eye-catching, with a strong value proposition
- Typography: use font-weight variety (font-light, font-bold, font-extrabold)
- Spacing: generous whitespace, don't cram content
- Colors: harmonious palette, use gradients where appropriate
- Cards/blocks: rounded corners, subtle shadows, hover effects via Tailwind
- Icons: use inline SVG icons (simple, clean) or Unicode symbols where appropriate
- Sections: each section should have a DIFFERENT visual rhythm and layout
- CTA buttons: prominent, with hover/focus states
- Footer: clean, organized, with social links

STRUCTURE (adapt creatively per industry):
1. Navigation bar (sticky, with backdrop-blur)
2. Hero section (full-width, impactful)
3. 3-5 content sections (services/features, about, testimonials/cases, process/FAQ, etc.)
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
7. Preserve existing <script> tags for animations/interactivity - keep them intact.
8. Preserve section id attributes for navigation.
9. Make ONLY the specific changes the user requested. Don't redesign the whole page.
10. If the user asks to change colors/theme, update Tailwind color classes consistently.
11. If adding new sections, match the existing design language and place them appropriately.
12. When adding a new section, ensure it integrates with existing layout (e.g., footer stays at bottom).

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
7. Preserve all <script> tags, event handlers (but you can modify their content), and interactive elements.
8. Maintain responsive design classes (sm:, md:, lg:).

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

WEBSITE_REFINE_SYSTEM_PROMPT = """\
You are a senior frontend code reviewer. You receive HTML of a landing page and must \
improve it for production quality.

Output ONLY the improved HTML (body content only, no wrappers).

CHECK AND FIX:
- Mobile responsiveness (ensure all sections work on small screens)
- Consistent color palette usage across all sections
- Proper hover/focus states on interactive elements
- Adequate spacing and padding (especially on mobile with px-4, py-8, etc.)
- Section variety (different layouts for different sections)
- Accessibility basics (alt attributes, semantic structure, contrast)
- Remove any empty or placeholder content
- Ensure navigation anchors work correctly
- Fix any Tailwind class typos or conflicts
- Make CTAs stand out visually
- Preserve any existing <script> tags for carousels, animations, interactivity

PRESERVATION RULES:
- Keep ALL existing content sections
- Keep ALL existing JavaScript for animations/interactivity
- Only apply visual/layout improvements
- Do not remove footer, navigation, or any other sections

DO NOT:
- Change the overall design direction
- Remove content sections
- Change language from Russian
- Remove or modify existing scripts unless they are broken
"""

WEBSITE_ADAPTIVE_SYSTEM_PROMPT = """\
You are a frontend specialist focused on responsive adaptation.

You receive already refined HTML for a landing page.
Your task is to improve rendering for tablets and mobile devices without breaking desktop.

Output ONLY adapted HTML (body content only, no wrappers).

ADAPTATION GOALS:
- Improve layout for mobile (<=640px) and tablet (641-1024px) viewports
- Ensure typography scales properly (avoid oversized headings on small screens)
- Improve spacing on smaller viewports (px-4/px-5, sensible vertical rhythm)
- Prevent horizontal scrolling and content overflow
- Make cards/sections stack naturally where needed
- Keep tap targets comfortable on touch devices
- Ensure navigation remains usable on small screens

DESKTOP SAFETY RULES (CRITICAL):
- Do not degrade desktop layout (lg/xl) visual hierarchy
- Keep desktop spacing and section composition close to the original
- Avoid drastic redesign or section reordering
- Preserve business copy and CTA intent
- Preserve ALL existing JavaScript for carousels and interactivity

PRESERVATION RULES:
- Keep ALL content sections exactly as provided
- Keep ALL <script> tags for existing functionality
- Only modify CSS classes for responsive behavior

DO NOT:
- Change language from Russian
- Remove major sections
- Remove or modify existing scripts
"""

WEBSITE_FINAL_QA_SYSTEM_PROMPT = """\
You are a strict frontend QA reviewer for a production landing page.

Output ONLY final HTML (body content only, no wrappers).

CHECKLIST:
- Desktop layout quality remains strong (no regressions after adaptation)
- Tablet and mobile layouts are clean and readable
- No horizontal overflow on common breakpoints
- Navigation anchors still work and ids are preserved
- CTA buttons are visible and accessible on all viewports
- No placeholder/template text or fake contacts
- Tailwind classes look valid and consistent
- ALL content sections from original are present (header, nav, sections, footer)
- Any existing JavaScript for carousels/interactivity is preserved and functional

CRITICAL PRESERVATION:
- Keep ALL content sections exactly as in the input
- Keep ALL <script> tags for carousels, mobile menus, animations
- Do not remove footer, navigation, or any other section

Apply only minimal, targeted fixes needed to pass the checklist.
Do not redesign the page.
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
        self.max_generation_tokens = 16000
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
        max_tokens: int | None = None,
    ) -> str:
        target_model = (model or self.generation_model).strip()
        response = await self.ai_client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens or self.max_generation_tokens,
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
                    max_tokens=self.max_generation_tokens,
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

                # Step 2: Quality refinement pass
                logger.info("[WebsiteGen] Starting refinement pass")
                refine_prompt = (
                    f"Business: {business_name}\n"
                    f"Theme: {'dark' if dark_mode else 'light'}\n"
                    f"Brand color: {primary_color or 'auto'}\n\n"
                    f"Review and improve this HTML:\n\n{html_content}"
                )

                refined_raw = await self._call_ai(
                    system_prompt=WEBSITE_REFINE_SYSTEM_PROMPT,
                    user_prompt=refine_prompt,
                    model=self.generation_model,
                    temperature=0.3,
                    max_tokens=self.max_generation_tokens,
                )

                refined_html = _extract_html_from_response(refined_raw)
                logger.info(f"[WebsiteGen] Refined HTML length: {len(refined_html)} chars")

                if _contains_generic_placeholder_content(refined_html):
                    raise ValueError("Refined HTML contains generic placeholder/template content")

                # Use refined version if it's valid, otherwise keep original
                if len(refined_html) >= len(html_content) * 0.7:
                    html_content = refined_html
                    logger.info("[WebsiteGen] Using refined HTML")
                else:
                    logger.info("[WebsiteGen] Refined HTML too short, using original")

                # Step 3: Adaptive pass for mobile/tablet (desktop-safe)
                logger.info("[WebsiteGen] Starting adaptive pass")
                adaptive_prompt = (
                    f"Business: {business_name}\n"
                    f"Theme: {'dark' if dark_mode else 'light'}\n"
                    f"Brand color: {primary_color or 'auto'}\n\n"
                    f"Adapt this HTML for mobile/tablet without breaking desktop:\n\n{html_content}"
                )
                adaptive_raw = await self._call_ai(
                    system_prompt=WEBSITE_ADAPTIVE_SYSTEM_PROMPT,
                    user_prompt=adaptive_prompt,
                    model=self.generation_model,
                    temperature=0.2,
                    max_tokens=self.max_generation_tokens,
                )
                adaptive_html = _extract_html_from_response(adaptive_raw)
                logger.info(f"[WebsiteGen] Adaptive HTML length: {len(adaptive_html)} chars")

                if _contains_generic_placeholder_content(adaptive_html):
                    raise ValueError("Adaptive HTML contains generic placeholder/template content")

                if len(adaptive_html) >= len(html_content) * 0.75:
                    html_content = adaptive_html
                    logger.info("[WebsiteGen] Using adaptive HTML")
                else:
                    logger.info("[WebsiteGen] Adaptive HTML too short, keeping previous version")

                # Step 4: Final QA pass
                logger.info("[WebsiteGen] Starting final QA pass")
                final_qa_prompt = (
                    f"Business: {business_name}\n"
                    f"Theme: {'dark' if dark_mode else 'light'}\n"
                    f"Brand color: {primary_color or 'auto'}\n\n"
                    f"Run final QA and apply minimal fixes to this HTML:\n\n{html_content}"
                )
                final_qa_raw = await self._call_ai(
                    system_prompt=WEBSITE_FINAL_QA_SYSTEM_PROMPT,
                    user_prompt=final_qa_prompt,
                    model=self.generation_model,
                    temperature=0.15,
                    max_tokens=self.max_generation_tokens,
                )
                final_qa_html = _extract_html_from_response(final_qa_raw)
                logger.info(f"[WebsiteGen] Final QA HTML length: {len(final_qa_html)} chars")

                if _contains_generic_placeholder_content(final_qa_html):
                    raise ValueError("Final QA HTML contains generic placeholder/template content")

                if len(final_qa_html) >= len(html_content) * 0.75:
                    html_content = final_qa_html
                    logger.info("[WebsiteGen] Using final QA HTML")
                else:
                    logger.info("[WebsiteGen] Final QA HTML too short, keeping previous version")

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
                    max_tokens=self.max_generation_tokens,
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
            max_tokens=self.max_generation_tokens,
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
            max_tokens=2000,
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
