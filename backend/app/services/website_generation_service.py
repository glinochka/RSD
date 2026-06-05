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
8. No <script> tags, no inline JavaScript, no external resources except Tailwind.
9. Use semantic HTML5 elements (header, nav, main, section, footer).
10. Include proper id attributes on sections for navigation anchors.

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

RULES:
1. Output ONLY the modified HTML (the body content, no DOCTYPE/html/head/body wrappers).
2. Keep all existing Tailwind CSS classes and structure intact unless the change requires modification.
3. Maintain responsive design (sm:, md:, lg: breakpoints).
4. All text must remain in RUSSIAN.
5. No <script> tags, no inline JavaScript.
6. Preserve section id attributes for navigation.
7. Make ONLY the changes the user requested. Don't redesign the whole page unnecessarily.
8. If the user asks to change colors/theme, update Tailwind color classes consistently.
9. If adding new sections, match the existing design language.
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

DO NOT:
- Add scripts
- Change the overall design direction
- Remove content sections
- Change language from Russian
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

DO NOT:
- Add scripts
- Change language from Russian
- Remove major sections
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


def _contains_generic_placeholder_content(html: str) -> bool:
    """Detect obvious template/placeholder content that should be rejected."""
    text = (html or "").lower()
    generic_markers = (
        "hello@example.com",
        "+7 (999) 999-99-99",
        "иван иванов",
        "базовая услуга",
        "расширенное сопровождение",
        "индивидуальное решение",
        "создано с помощью rsd ai",
        "ваш бизнес",
        "заголовок вашего сайта",
        "краткое описание предложения",
        "услуга 1",
        "услуга 2",
    )
    return any(marker in text for marker in generic_markers)


def _inject_tailwind_color(html: str, primary_color: str | None) -> str:
    """If a brand color is specified but AI used generic colors, this is a safety net."""
    if not primary_color:
        return html
    return html


def _build_meta_from_html(html: str, business_name: str, business_description: str) -> dict:
    """Extract meta info from the generated HTML content."""
    title = business_name[:100]
    description = business_description[:500]
    return {"title": title, "description": description}


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
        # Use deepseek-chat for HTML generation (better creative/design capabilities)
        # deepseek-coder is optimized for code completion, not full page design
        configured_model = settings.WEBSITE_GENERATION_MODEL or "deepseek-chat"
        self.model = configured_model.strip()
        self.max_retries = 2
        self.max_generation_tokens = 16000
        logger.info(f"[WebsiteGenService] Initialized with model: {self.model}")

    async def _call_ai(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        response = await self.ai_client.chat.completions.create(
            model=self.model,
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

        logger.info(f"[WebsiteGen] Starting generate_website for '{business_name}' (model={self.model})")
        logger.info(f"[WebsiteGen] Params: dark_mode={dark_mode}, color={primary_color}")
        logger.info(f"[WebsiteGen] Services count: {len(services) if services else 0}")

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "[WebsiteGen] Generation attempt %s/%s (model=%s)",
                    attempt, self.max_retries, self.model,
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

                if "<nav" not in html_content or "<header" not in html_content:
                    raise ValueError("Generated HTML must include nav and header structure")

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
    ) -> bool:
        """Save generated HTML to the website as a fullpage block."""
        logger.info(f"[WebsiteGenService] apply_generated_html called for website_id={website_id}")
        logger.info(f"[WebsiteGenService] HTML content size: {len(html_content)} chars")
        logger.info(f"[WebsiteGenService] Meta: title='{meta.get('title', 'N/A')[:50]}...'")

        try:
            async with async_session_maker() as session:
                async with session.begin():
                    website_dao = WebsiteDAO(session)
                    block_dao = WebsiteBlockDAO(session)

                    website = await website_dao.find_one_by_filter(id=website_id)
                    if not website:
                        logger.error(f"[WebsiteGenService] Website not found: {website_id}")
                        return False

                    logger.info(f"[WebsiteGenService] Found website '{website.title}', updating metadata")

                    # Update website metadata
                    updates = {
                        "title": meta.get("title", ""),
                        "meta_description": meta.get("description", ""),
                        "og_title": meta.get("title", ""),
                        "og_description": meta.get("description", ""),
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
                        content={"html": html_content},
                        styles={},
                        is_visible=True,
                    )
                    session.add(block)
                    logger.info(f"[WebsiteGenService] Fullpage block added to session for website_id={website_id}")

                    # File creation is logged at the DB level
                    logger.info(f"[WebsiteGenService] apply_generated_html completed successfully for website_id={website_id}")
                    return True
        except Exception as e:
            logger.exception(f"[WebsiteGenService] Error in apply_generated_html for website_id={website_id}: {e}")
            return False

    async def edit_website_with_prompt(
        self,
        *,
        current_html: str,
        prompt: str,
        business_name: str = "",
    ) -> str:
        """Edit the website HTML based on a natural-language prompt.

        This is the core editing capability — the AI modifies existing HTML
        according to user instructions, similar to how Cursor edits code.
        """
        user_message = (
            f"CURRENT WEBSITE HTML:\n\n{current_html}\n\n"
            f"---\n\n"
            f"USER REQUEST: {prompt}\n\n"
            f"Apply the requested changes and output the COMPLETE modified HTML. "
            f"No markdown fences, no explanations — only the HTML code."
        )

        raw = await self._call_ai(
            system_prompt=WEBSITE_EDIT_SYSTEM_PROMPT,
            user_prompt=user_message,
            temperature=0.4,
            max_tokens=self.max_generation_tokens,
        )

        edited_html = _extract_html_from_response(raw)

        if len(edited_html) < 200:
            raise ValueError("AI returned too short HTML after editing")

        return edited_html

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
            model=self.model,
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
