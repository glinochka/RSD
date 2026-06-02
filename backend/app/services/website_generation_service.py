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


# ---------------------------------------------------------------------------
# Default / Fallback Templates
# ---------------------------------------------------------------------------

DEFAULT_FALLBACK_SCHEMA = GeneratedWebsiteSchema(
    meta=MetaInfo(
        title="Мой бизнес",
        description="Профессиональные услуги для ваших нужд",
    ),
    styles=GeneratedStyles(
        primary_color="#2563EB",
        secondary_color="#1E40AF",
        background_color="#FFFFFF",
        text_color="#1F2937",
        accent_color="#3B82F6",
        font_family="Inter",
        dark_mode=False,
        border_radius="medium",
    ),
    blocks=[
        GeneratedBlock(
            type="hero",
            order=1,
            content=HeroContent(
                headline="Добро пожаловать",
                subheadline="Мы предлагаем качественные услуги",
                cta_text="Узнать больше",
            ).model_dump(),
        ),
        GeneratedBlock(
            type="contacts",
            order=2,
            content=ContactsContent(
                title="Свяжитесь с нами",
                contact_info=ContactInfo(
                    phone="+7 (XXX) XXX-XX-XX",
                ),
            ).model_dump(),
        ),
        GeneratedBlock(
            type="footer",
            order=3,
            content=FooterContent(
                company_name="Моя компания",
                copyright_text="© 2026 Все права защищены",
            ).model_dump(),
        ),
    ],
)


# ---------------------------------------------------------------------------
# System Prompt for Website Generation
# ---------------------------------------------------------------------------

WEBSITE_GENERATION_SYSTEM_PROMPT = """Ты — опытный frontend-разработчик и UX/UI дизайнер. Твоя задача — создать профессиональный одностраничный сайт для бизнеса.

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
    {
      "type": "services",
      "order": 2,
      "content": {
        "title": "Наши услуги",
        "items": [
          {
            "name": "Название услуги",
            "description": "Описание 1-2 предложения",
            "price": "Цена (опционально)",
            "icon": "имя_иконки"
          }
        ]
      },
      "styles": {}
    },
    {
      "type": "about",
      "order": 3,
      "content": {
        "title": "О нас",
        "text": "Рассказ о компании (3-5 предложений)",
        "image_url": null
      },
      "styles": {}
    },
    {
      "type": "contacts",
      "order": 4,
      "content": {
        "title": "Контакты",
        "contact_info": {
          "phone": "телефон",
          "email": "email",
          "address": "адрес",
          "working_hours": "часы работы"
        },
        "show_form": true
      },
      "styles": {}
    },
    {
      "type": "cta",
      "order": 5,
      "content": {
        "title": "Призыв к действию",
        "subtitle": "Подзаголовок",
        "button_text": "Заказать сейчас",
        "button_link": "#contacts"
      },
      "styles": {}
    },
    {
      "type": "footer",
      "order": 6,
      "content": {
        "company_name": "Название компании",
        "copyright_text": "© 2026 Все права защищены",
        "social_links": {},
        "privacy_policy_url": null,
        "terms_url": null
      },
      "styles": {}
    }
  ]
}
```

ПРАВИЛА:
1. Используй цвета из переданной цветовой схемы
2. Текст должен быть на русском языке, профессиональным, продающим
3. Для каждого блока создавай осмысленный, качественный контент
4. Заголовки должны быть цепляющими и конкретными
5. Описание услуг — с акцентом на выгоды для клиента
6. ЦТА-кнопки должны быть действием ("Записаться", "Получить консультацию", "Узнать цену")
7. Если информация не предоставлена — используй реалистичные placeholder-значения
8. Всегда включай все 6 типов блоков (hero, services, about, contacts, cta, footer)
9. order должен начинаться с 1 и идти последовательно
10. Только валидный JSON, без markdown-разметки вне JSON
"""


def build_generation_prompt(
    business_name: str,
    business_description: str,
    services: list[dict] | None = None,
    contacts: dict[str, str] | None = None,
    primary_color: str | None = None,
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
        self.model = "deepseek-chat"
        self.max_retries = 3
        self.timeout_seconds = 60.0

    async def generate_website(
        self,
        business_name: str,
        business_description: str,
        services: list[dict] | None = None,
        contacts: dict[str, str] | None = None,
        primary_color: str | None = None,
    ) -> GenerationResult:
        """Generate a complete website using AI.

        Args:
            business_name: Name of the business
            business_description: Business description
            services: List of services with name, description, price
            contacts: Dict with phone, email, address, etc.
            primary_color: Primary brand color (hex)

        Returns:
            GenerationResult with success status and schema
        """
        user_prompt = build_generation_prompt(
            business_name=business_name,
            business_description=business_description,
            services=services,
            contacts=contacts,
            primary_color=primary_color,
        )

        last_error = None
        raw_response = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Generation attempt {attempt}/{self.max_retries}")

                response = await self.ai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": WEBSITE_GENERATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )

                raw_response = response.choices[0].message.content

                if not raw_response:
                    raise ValueError("Empty response from AI")

                schema = parse_generated_schema(raw_response)

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

    async def apply_fallback_template(self, website_id: int) -> bool:
        """Apply default fallback template when generation fails.

        Args:
            website_id: Website ID to update

        Returns:
            True if successful
        """
        return await self.apply_generated_schema(website_id, DEFAULT_FALLBACK_SCHEMA)

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
