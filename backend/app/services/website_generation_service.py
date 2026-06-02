"""Website Generation Service — AI-powered website generation via DeepSeek API."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..alembic.database import async_session_maker
from ..alembic.models import AdminService, Agent, AgentChannelConnection, Website, WebsiteBlock
from ..router_websites.dao import WebsiteBlockDAO, WebsiteDAO
from ..config import settings
from .ai_authoring import ai_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic Models for AI Response Parsing
# ---------------------------------------------------------------------------

class HeroContent(BaseModel):
    headline: str = Field(..., max_length=200)
    subheadline: str | None = Field(default=None, max_length=500)
    cta_text: str | None = Field(default=None, max_length=100)
    cta_link: str | None = Field(default=None, max_length=1024)
    background_image_url: str | None = Field(default=None, max_length=1024)
    nav_links: list[dict[str, str]] = Field(default_factory=list)


class ServiceItem(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(default=None, max_length=500)
    price: str | None = Field(default=None, max_length=100)
    icon: str | None = Field(default=None, max_length=100)
    image_url: str | None = Field(default=None, max_length=1024)


class ServicesContent(BaseModel):
    title: str = Field(default="Наши услуги", max_length=100)
    items: list[ServiceItem] = Field(default_factory=list)


class AboutContent(BaseModel):
    title: str = Field(default="О нас", max_length=100)
    text: str = Field(..., max_length=5000)
    image_url: str | None = Field(default=None, max_length=1024)


class ContactInfo(BaseModel):
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    telegram: str | None = Field(default=None, max_length=100)
    whatsapp: str | None = Field(default=None, max_length=100)
    working_hours: str | None = Field(default=None, max_length=200)


class ContactsContent(BaseModel):
    title: str = Field(default="Контакты", max_length=100)
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    show_form: bool = True


class CTAContent(BaseModel):
    title: str = Field(..., max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    button_text: str = Field(default="Связаться", max_length=100)
    button_link: str | None = Field(default=None, max_length=1024)


class FooterContent(BaseModel):
    company_name: str | None = Field(default=None, max_length=100)
    copyright_text: str | None = Field(default=None, max_length=500)
    social_links: dict[str, str] = Field(default_factory=dict)
    privacy_policy_url: str | None = Field(default=None, max_length=1024)
    terms_url: str | None = Field(default=None, max_length=1024)


class MetaInfo(BaseModel):
    title: str = Field(..., max_length=100)
    description: str = Field(..., max_length=500)


class GeneratedStyles(BaseModel):
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str | None = Field(default=None, max_length=64)
    dark_mode: bool = False
    border_radius: str | None = Field(default=None, max_length=20)


class GeneratedBlock(BaseModel):
    type: str = Field(..., pattern=r"^(hero|services|about|contacts|cta|footer|custom)$")
    order: int = Field(..., ge=0)
    content: dict[str, Any] = Field(default_factory=dict)
    styles: dict[str, Any] = Field(default_factory=dict)


class GeneratedWebsiteSchema(BaseModel):
    meta: MetaInfo
    styles: GeneratedStyles
    blocks: list[GeneratedBlock]

    @field_validator("blocks")
    @classmethod
    def validate_block_orders(cls, blocks: list[GeneratedBlock]) -> list[GeneratedBlock]:
        """Ensure block orders are sequential starting from 1."""
        if not blocks:
            return blocks
        sorted_blocks = sorted(blocks, key=lambda b: b.order)
        for i, block in enumerate(sorted_blocks, 1):
            block.order = i
        return sorted_blocks


MIN_REQUIRED_BLOCK_TYPES = ("hero", "footer")


def normalize_generated_schema(
    schema: GeneratedWebsiteSchema,
    *,
    business_name: str,
    business_description: str,
    primary_color: str | None = None,
    dark_mode: bool = False,
) -> GeneratedWebsiteSchema:
    """Normalize AI-generated schema without template substitution."""
    if not schema.meta.title:
        schema.meta.title = (business_name or "Сайт компании").strip()[:100]
    if not schema.meta.description:
        schema.meta.description = (
            (business_description or "Профессиональные услуги").strip()[:500]
        )

    default_styles = {
        "primary_color": primary_color or "#2563EB",
        "secondary_color": "#1E40AF" if not dark_mode else "#1D4ED8",
        "background_color": "#FFFFFF" if not dark_mode else "#0F172A",
        "text_color": "#1F2937" if not dark_mode else "#E5E7EB",
        "accent_color": "#3B82F6",
        "font_family": "Inter",
        "dark_mode": dark_mode,
        "border_radius": "medium",
    }
    current_styles = schema.styles.model_dump(exclude_none=True)
    schema.styles = GeneratedStyles.model_validate({**default_styles, **current_styles})

    if not schema.blocks:
        raise ValueError("Generated schema has no blocks")

    block_types = {block.type for block in schema.blocks}
    missing_mandatory = [t for t in MIN_REQUIRED_BLOCK_TYPES if t not in block_types]
    if missing_mandatory:
        raise ValueError(f"Generated schema missing mandatory blocks: {', '.join(missing_mandatory)}")

    hero_blocks = [b for b in schema.blocks if b.type == "hero"]
    non_hero_blocks = [b for b in schema.blocks if b.type != "hero"]
    ordered_blocks = hero_blocks[:1] + non_hero_blocks
    for idx, block in enumerate(ordered_blocks, start=1):
        block.order = idx
    schema.blocks = ordered_blocks

    has_content_between = any(
        b.type in {"services", "about", "contacts", "cta", "custom"} for b in schema.blocks[1:]
    )
    if not has_content_between:
        raise ValueError("Generated schema is too sparse and has no meaningful content sections")

    return schema


# ---------------------------------------------------------------------------
# System Prompt for Website Generation
# ---------------------------------------------------------------------------

WEBSITE_GENERATION_SYSTEM_PROMPT = """Ты — senior frontend engineer + UI/UX designer + conversion copywriter. Твоя задача — создать уникальный одностраничный сайт под конкретный бизнес.

ВАЖНО: Ответь ТОЛЬКО в формате JSON. Никаких пояснений до или после JSON.

Структура ответа должна соответствовать следующей схеме:

```json
{
  "meta": {
    "title": "Заголовок сайта (до 60 символов, SEO-оптимизированный)",
    "description": "Описание для SEO (до 160 символов)"
  },
  "styles": {
    "primary_color": "#XXXXXX",
    "secondary_color": "#XXXXXX",
    "background_color": "#FFFFFF",
    "text_color": "#1F2937",
    "accent_color": "#XXXXXX",
    "font_family": "Inter",
    "dark_mode": false,
    "border_radius": "medium"
  },
  "blocks": [
    {
      "type": "hero",
      "order": 1,
      "content": {
        "headline": "Главный заголовок (убедительный, яркий)",
        "subheadline": "Подзаголовок (ценностное предложение)",
        "cta_text": "Текст кнопки (2-3 слова)",
        "cta_link": "#contacts"
      },
      "styles": {}
    },
    // После hero используй вариативный набор секций:
    // services/about/contacts/cta/footer и/или custom.
    // Для нестандартных секций (кейсы, FAQ, отзывы, карусель, этапы, тарифы и т.д.) используй type="custom" и content.html.
    // Минимум: hero в начале и footer в конце.
  ]
}
```

ПРАВИЛА:
1. Используй цвета из переданной цветовой схемы
2. Текст должен быть на русском языке, профессиональным, продающим
3. Для каждого блока создавай осмысленный, качественный контент
4. Заголовки должны быть цепляющими, конкретными, отраслевыми
5. Не используй повторяющиеся иконки и одинаковые паттерны карточек на всех сайтах
6. Если формируешь custom-блок, генерируй безопасный семантический HTML без inline script/style
7. Если информация не предоставлена — используй реалистичные placeholder-значения
8. Структура должна следовать стандарту: navbar + hero + контентные секции + контакты/CTA + footer
9. hero должен быть первым, footer последним, order строго по возрастанию
10. Только валидный JSON, без markdown-разметки вне JSON
"""


def build_generation_prompt(
    business_name: str,
    business_description: str,
    services: list[dict] | None = None,
    contacts: dict[str, str] | None = None,
    primary_color: str | None = None,
    dark_mode: bool = False,
) -> str:
    """Build the user prompt for website generation."""
    prompt_parts = [
        f"Название бизнеса: {business_name}",
        f"Описание: {business_description}",
    ]

    if services:
        prompt_parts.append("Услуги:")
        for svc in services:
            name = svc.get("name", "")
            desc = svc.get("description", "")
            price = svc.get("price", "")
            prompt_parts.append(f"  - {name}: {desc} (Цена: {price})")

    if contacts:
        prompt_parts.append("Контакты:")
        for key, value in contacts.items():
            if value:
                prompt_parts.append(f"  {key}: {value}")

    if primary_color:
        prompt_parts.append(f"Основной цвет бренда: {primary_color}")
        prompt_parts.append(
            "Цветовая схема: используй этот цвет как primary_color, "
            "подбери гармоничные secondary, accent и background цвета"
        )

    if dark_mode:
        prompt_parts.append("Тема: ТЁМНАЯ (dark mode). Используй тёмные фоны и светлый текст.")
    else:
        prompt_parts.append("Тема: СВЕТЛАЯ (light mode). Используй светлые фоны и тёмный текст.")

    prompt_parts.append("\nСгенерируй полный JSON с сайтом для этого бизнеса.")

    return "\n".join(prompt_parts)


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------

def extract_json_from_response(raw_response: str) -> str:
    """Extract JSON from markdown code blocks or raw text."""
    if not raw_response:
        raise ValueError("Empty response from AI")

    # Try to find JSON in code blocks
    json_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(json_block_pattern, raw_response, re.DOTALL)

    if matches:
        # Return the longest match (most likely to be the full JSON)
        return max(matches, key=len).strip()

    # If no code blocks, try to find JSON object directly
    json_start = raw_response.find("{")
    json_end = raw_response.rfind("}")

    if json_start != -1 and json_end != -1 and json_end > json_start:
        return raw_response[json_start : json_end + 1].strip()

    raise ValueError("No JSON found in response")


def parse_generated_schema(raw_response: str) -> GeneratedWebsiteSchema:
    """Parse and validate AI response into GeneratedWebsiteSchema."""
    try:
        json_str = extract_json_from_response(raw_response)
        data = json.loads(json_str)
        return GeneratedWebsiteSchema.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"Failed to parse AI response: {e}")
        raise


# ---------------------------------------------------------------------------
# Generation Service
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    success: bool
    schema: GeneratedWebsiteSchema | None
    error_message: str | None
    raw_response: str | None


class WebsiteGenerationService:
    """Service for AI-powered website generation using DeepSeek API."""

    def __init__(self):
        self.ai_client = ai_client
        self.model = (settings.WEBSITE_GENERATION_MODEL or "deepseek-coder").strip()
        self.max_retries = 3
        self.timeout_seconds = 60.0
        self.max_generation_tokens = 7000

    async def _chat_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = await self.ai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw_response = response.choices[0].message.content
        if not raw_response:
            raise ValueError("Empty response from AI")
        return raw_response

    async def _generate_structure_plan(
        self,
        *,
        business_name: str,
        business_description: str,
        services: list[dict] | None,
        contacts: dict[str, str] | None,
        dark_mode: bool,
    ) -> dict[str, Any]:
        """Step 1: create structure plan with unique section architecture."""
        system_prompt = (
            "Ты principal UX-архитектор и CRO-стратег лендингов. "
            "Верни ТОЛЬКО валидный JSON. Никакого markdown.\n"
            "Сконструируй УНИКАЛЬНУЮ структуру сайта по индустрии бизнеса и входным данным.\n"
            "Формат:\n"
            "{\n"
            '  "industry": "string",\n'
            '  "tone": "string",\n'
            '  "positioning": "string",\n'
            '  "sections": [\n'
            '    {"type":"hero","anchor":"top","goal":"...", "style_hint":"..."},\n'
            '    {"type":"custom","anchor":"cases","goal":"...", "kind":"cases-grid"},\n'
            '    {"type":"services","anchor":"services","goal":"...", "style_hint":"..."}\n'
            "  ],\n"
            '  "nav_links": [\n'
            '    {"label":"Услуги","anchor":"#services"},\n'
            '    {"label":"О нас","anchor":"#about"},\n'
            '    {"label":"Контакты","anchor":"#contacts"}\n'
            "  ],\n"
            '  "visual_direction": {"layout":"...", "density":"...", "icon_style":"..."},\n'
            '  "image_guidelines": {"max_height_px": 520, "object_fit": "cover"},\n'
            '  "mobile_notes": ["...", "..."]\n'
            "}\n"
            "Обязательные правила:\n"
            "- Всегда включай стандарт лендинга: nav + hero + контентные секции + контакты/CTA + footer.\n"
            "- hero должен быть первым, footer последним.\n"
            "- Между hero и footer должно быть не менее 3 контентных секций.\n"
            "- Разрешены стандартные type (services/about/contacts/cta) и custom.\n"
            "- Для custom указывай kind: faq|testimonials|cases-grid|stats|timeline|pricing|carousel|comparison|team|process.\n"
            "- Избегай однотипной структуры между разными индустриями."
        )

        user_prompt = json.dumps(
            {
                "business_name": business_name,
                "business_description": business_description,
                "services": services or [],
                "contacts": contacts or {},
                "theme": "dark" if dark_mode else "light",
                "hard_rules": [
                    "Не путай индустрию бизнеса",
                    "Если это стоматология/клиника — копирайт и услуги должны быть медицинскими",
                    "Никаких generic-текстов про консалтинг, если это не консалтинг",
                    "Структура не должна выглядеть как единый шаблон для всех сайтов",
                ],
            },
            ensure_ascii=False,
        )

        raw = await self._chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=1800,
        )
        plan = json.loads(extract_json_from_response(raw))
        if not isinstance(plan, dict):
            raise ValueError("AI structure plan is invalid")
        return plan

    async def _generate_schema_from_plan(
        self,
        *,
        plan: dict[str, Any],
        business_name: str,
        business_description: str,
        services: list[dict] | None,
        contacts: dict[str, str] | None,
        primary_color: str | None,
        dark_mode: bool,
    ) -> str:
        """Step 2: generate detailed website schema and content from structure plan."""
        system_prompt = WEBSITE_GENERATION_SYSTEM_PROMPT + (
            "\n\n"
            "Дополнительные требования:\n"
            "1) Сначала сформируй navbar внутри блока hero (nav_links).\n"
            "2) Строго учитывай индустрию из structure_plan.industry.\n"
            "3) Избегай шаблонных общих формулировок; текст должен быть отраслевым.\n"
            "4) Для секции услуг делай карточки с конкретной пользой и понятной ценностью.\n"
            "5) Для медицинских ниш добавляй маркеры доверия и безопасности.\n"
            "6) Для каждого custom блока заполняй content.html качественной, семантической, безопасной разметкой.\n"
            "7) Не дублируй один и тот же паттерн карточек/иконок в нескольких секциях без причины.\n"
            "8) Изображения: учитывай max_height_px=520, object-fit=cover.\n"
            "9) hero должен быть первым блоком, footer последним.\n"
        )
        user_prompt = json.dumps(
            {
                "business_name": business_name,
                "business_description": business_description,
                "services": services or [],
                "contacts": contacts or {},
                "primary_color": primary_color,
                "dark_mode": dark_mode,
                "structure_plan": plan,
                "required_layout": "navbar -> hero -> content sections -> contacts/cta -> footer",
                "must_avoid": [
                    "single universal template look",
                    "generic repeated icon set",
                    "identical section rhythm for all niches",
                ],
            },
            ensure_ascii=False,
        )
        return await self._chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.55,
            max_tokens=self.max_generation_tokens,
        )

    async def _refine_schema_for_quality(
        self,
        *,
        raw_schema: str,
        business_name: str,
        business_description: str,
        plan: dict[str, Any],
    ) -> str:
        """Step 3: quality pass for mobile-first and style consistency."""
        system_prompt = (
            "Ты lead frontend ревьюер. Верни ТОЛЬКО валидный JSON той же схемы сайта.\n"
            "Сделай финальный pass качества:\n"
            "- mobile-first читабельность и плотность контента\n"
            "- единый визуальный ритм секций\n"
            "- корректные CTA и якорные ссылки\n"
            "- осмысленные тексты строго в индустрии бизнеса\n"
            "- избегай неуместной лексики (например, консалтинг для клиники)\n"
            "- изображения должны быть безопасного размера для лендинга\n"
            "- hero в начале и footer в конце, правильная последовательность блоков\n"
            "- custom-блоки должны быть семантическими и безопасными (без script/style)\n"
        )
        user_prompt = json.dumps(
            {
                "business_name": business_name,
                "business_description": business_description,
                "structure_plan": plan,
                "candidate_schema": json.loads(extract_json_from_response(raw_schema)),
            },
            ensure_ascii=False,
        )
        return await self._chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.35,
            max_tokens=5500,
        )

    async def _deep_style_and_variation_pass(
        self,
        *,
        schema_raw: str,
        plan: dict[str, Any],
        dark_mode: bool,
    ) -> str:
        """Step 4: enforce unique visual language and section diversity."""
        system_prompt = (
            "Ты арт-директор digital-продуктов и frontend-дизайнер.\n"
            "Верни ТОЛЬКО валидный JSON той же схемы сайта.\n"
            "Сделай сильную стилизацию и вариативность:\n"
            "- выровняй визуальный язык между секциями\n"
            "- добавь разные паттерны представления контента (карточки, таймлайн, FAQ, сравнение, карусель через custom html)\n"
            "- оставь сайт современным и читабельным\n"
            "- mobile-first: размеры, отступы, длина строк\n"
            "- не ломай SEO meta и базовые контактные данные\n"
        )
        user_prompt = json.dumps(
            {
                "theme": "dark" if dark_mode else "light",
                "structure_plan": plan,
                "candidate_schema": json.loads(extract_json_from_response(schema_raw)),
                "goal": "Maximum visual individuality while keeping clean UX conventions",
            },
            ensure_ascii=False,
        )
        return await self._chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.65,
            max_tokens=6500,
        )

    async def _final_validation_pass(
        self,
        *,
        schema_raw: str,
        plan: dict[str, Any],
    ) -> str:
        """Step 5: final validation and correction pass."""
        system_prompt = (
            "Ты финальный QA-валидатор лендингов.\n"
            "Верни ТОЛЬКО валидный JSON той же схемы сайта.\n"
            "Проверь и исправь:\n"
            "- валидность JSON и обязательных полей\n"
            "- порядок блоков order\n"
            "- hero первый, footer последний\n"
            "- якоря навигации и CTA ссылки\n"
            "- отсутствие пустых/бессмысленных секций\n"
            "- корректность custom html (без script/style, семантический контент)\n"
        )
        user_prompt = json.dumps(
            {
                "structure_plan": plan,
                "candidate_schema": json.loads(extract_json_from_response(schema_raw)),
            },
            ensure_ascii=False,
        )
        return await self._chat_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=6000,
        )

    async def generate_website(
        self,
        business_name: str,
        business_description: str,
        services: list[dict] | None = None,
        contacts: dict[str, str] | None = None,
        primary_color: str | None = None,
        dark_mode: bool = False,
    ) -> GenerationResult:
        """Generate a complete website using AI.

        Args:
            business_name: Name of the business
            business_description: Business description
            services: List of services with name, description, price
            contacts: Dict with phone, email, address, etc.
            primary_color: Primary brand color (hex)
            dark_mode: Whether to use dark mode theme

        Returns:
            GenerationResult with success status and schema
        """
        last_error = None
        raw_response = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "Generation attempt %s/%s (model=%s)",
                    attempt,
                    self.max_retries,
                    self.model,
                )

                structure_plan = await self._generate_structure_plan(
                    business_name=business_name,
                    business_description=business_description,
                    services=services,
                    contacts=contacts,
                    dark_mode=dark_mode,
                )
                primary_schema_raw = await self._generate_schema_from_plan(
                    plan=structure_plan,
                    business_name=business_name,
                    business_description=business_description,
                    services=services,
                    contacts=contacts,
                    primary_color=primary_color,
                    dark_mode=dark_mode,
                )
                quality_schema_raw = await self._refine_schema_for_quality(
                    raw_schema=primary_schema_raw,
                    business_name=business_name,
                    business_description=business_description,
                    plan=structure_plan,
                )
                styled_schema_raw = await self._deep_style_and_variation_pass(
                    schema_raw=quality_schema_raw,
                    plan=structure_plan,
                    dark_mode=dark_mode,
                )
                raw_response = await self._final_validation_pass(
                    schema_raw=styled_schema_raw,
                    plan=structure_plan,
                )

                schema = parse_generated_schema(raw_response)
                schema = normalize_generated_schema(
                    schema,
                    business_name=business_name,
                    business_description=business_description,
                    primary_color=primary_color,
                    dark_mode=dark_mode,
                )

                return GenerationResult(
                    success=True,
                    schema=schema,
                    error_message=None,
                    raw_response=raw_response,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt} failed: {e}")
                continue

        # All retries failed
        logger.error(f"All generation attempts failed: {last_error}")
        return GenerationResult(
            success=False,
            schema=None,
            error_message=last_error,
            raw_response=raw_response,
        )

    async def apply_generated_schema(
        self,
        website_id: int,
        schema: GeneratedWebsiteSchema,
    ) -> bool:
        """Apply generated schema to a website in the database.

        Args:
            website_id: Website ID to update
            schema: Generated website schema

        Returns:
            True if successful
        """
        async with async_session_maker() as session:
            async with session.begin():
                website_dao = WebsiteDAO(session)
                block_dao = WebsiteBlockDAO(session)

                # Get website
                website = await website_dao.find_one_by_filter(id=website_id)
                if not website:
                    logger.error(f"Website not found: {website_id}")
                    return False

                # Update website metadata and styles
                updates = {
                    "title": schema.meta.title,
                    "meta_description": schema.meta.description,
                    "og_title": schema.meta.title,
                    "og_description": schema.meta.description,
                    "custom_styles": schema.styles.model_dump(exclude_none=True),
                    "generation_status": "completed",
                    "updated_at": datetime.utcnow(),
                }
                await website_dao.update(website, updates)

                # Clear existing blocks (if regenerating)
                existing_blocks = await block_dao.list_by_website(
                    website_id, only_visible=False
                )
                for block in existing_blocks:
                    await block_dao.delete(block)

                # Create new blocks
                for block_data in schema.blocks:
                    block = WebsiteBlock(
                        website_id=website_id,
                        type=block_data.type,
                        order=block_data.order,
                        content=block_data.content,
                        styles=block_data.styles,
                        is_visible=True,
                    )
                    session.add(block)

                return True

    async def edit_block_with_prompt(
        self,
        *,
        block_type: str,
        content: dict[str, Any],
        block_styles: dict[str, Any],
        global_styles: dict[str, Any],
        prompt: str,
    ) -> dict[str, Any]:
        """Edit a single block's content/styles via natural-language prompt."""
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

        json_str = extract_json_from_response(raw)
        data = json.loads(json_str)

        if not isinstance(data.get("content"), dict):
            raise ValueError("AI вернул некорректный content")

        return {
            "content": data["content"],
            "styles": data.get("styles") if isinstance(data.get("styles"), dict) else block_styles,
        }


# Singleton instance
_website_generation_service: WebsiteGenerationService | None = None


def get_website_generation_service() -> WebsiteGenerationService:
    """Get or create singleton instance of WebsiteGenerationService."""
    global _website_generation_service
    if _website_generation_service is None:
        _website_generation_service = WebsiteGenerationService()
    return _website_generation_service
