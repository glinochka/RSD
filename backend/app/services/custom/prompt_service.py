"""CustomPrompt management: defaults, versioning, testing."""
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomAutomation, CustomPrompt, PromptType
from ...services.ai_authoring import ai_client


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DEFAULT_PROMPTS: dict[str, dict[str, Any]] = {
    PromptType.CHAT_MONITORING_TRIGGER.value: {
        "name": "Chat Monitoring Trigger",
        "content": """Ты анализируешь сообщение в Telegram-чате.
Определи, является ли это сообщение заявкой или запросом на услуги (SEO, маркетинг, сайт, автоматизация, CRM, чат-боты и т.п.).

Верни ТОЛЬКО валидный JSON без markdown:
{
  "is_lead": true/false,
  "confidence": 0.0-1.0,
  "reason": "краткое объяснение",
  "contact_type": "telegram",
  "contact_value": "username или id отправителя, если видно"
}

Сообщение:
{text}""",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 300,
        "response_format": "json",
    },
    PromptType.CHAT_MONITORING_RESPONSE.value: {
        "name": "Chat Monitoring Response",
        "content": """Напиши короткое дружелюбное сообщение в Telegram ЛС от имени представителя компании.
Ответь на вопрос или предложи помощь по услугам (SEO, маркетинг, сайт, автоматизация, CRM).

Сообщение из чата:
{text}

Верни ТОЛЬКО JSON:
{
  "message": "текст ответа"
}""",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 300,
        "response_format": "json",
    },
    PromptType.NEUROCOMMENTING.value: {
        "name": "Neurocommenting",
        "content": """Ты — участник Telegram-чата/канала. Тебе показали пост.
Напиши короткий, естественный, релевантный комментарий (1-2 предложения), который продолжает дискуссию или добавляет ценность.
Не спами, не используй хештеги, не предлагай ссылки.

Пост:
{post_text}

Контекст чата:
{chat_title}

Верни ТОЛЬКО JSON:
{
  "comment": "текст комментария"
}""",
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": 200,
        "response_format": "json",
    },
    PromptType.DISCUSSION_REPLY.value: {
        "name": "Discussion Reply",
        "content": """Ты — обычный участник Telegram-чата. К тебе обратились или задали вопрос в сообщении.
Напиши короткий, естественный, дружелюбный ответ (1-3 предложения). Мягко поделись мнением или опытом, если уместно, но не навязывай продукт и не используй ссылки.

Сообщение:
{message_text}

Контекст чата:
{chat_title}

Верни ТОЛЬКО JSON:
{
  "reply": "текст ответа"
}""",
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": 250,
        "response_format": "json",
    },
    PromptType.DMP_OUTREACH.value: {
        "name": "DMP Outreach",
        "content": """Ты — живой человек в Telegram, пишешь первое сообщение посетителю сайта.
Коротко, по-человечески, без рекламного тона и без признания, что человека «вычислили».
Если есть промокод или ссылка — мягко предложи ими воспользоваться. Не вставляй ссылку, если поле пустое.

Имя: {name}
Компания: {company}
Сайт: {website}
Страница: {page}
Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}
Уже регистрировался: {registered}

Верни ТОЛЬКО JSON:
{
  "message": "текст первого сообщения"
}""",
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": 250,
        "response_format": "json",
    },
    PromptType.CHAT_RELEVANCE.value: {
        "name": "Chat Relevance",
        "content": """Ты оцениваешь релевантность Telegram-чата или канала для кампании.

Кампания: {query}

Название: {title}
Описание: {description}
Тип: {chat_type}
Участников: {participants_count}

Оцени релевантность от 0 до 1, где 1 — идеально подходит, 0 — не подходит.
Верни ТОЛЬКО JSON:
{
  "score": 0.0-1.0,
  "reason": "краткое объяснение",
  "relevant": true/false
}""",
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 300,
        "response_format": "json",
    },
    PromptType.LEAD_QUALIFICATION.value: {
        "name": "Lead Qualification",
        "content": """Ты квалифицируешь лид в Telegram-переписке.

История переписки:
{history}

Последнее сообщение лида:
{last_incoming}

Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}

Верни ТОЛЬКО JSON:
{
  "qualified": true/false,
  "lost": true/false,
  "continue": true/false,
  "reply": "следующее короткое сообщение, если continue=true"
}""",
        "model": "deepseek-chat",
        "temperature": 0.4,
        "max_tokens": 400,
        "response_format": "json",
    },
    PromptType.PROFILE_BIO.value: {
        "name": "Profile Bio",
        "content": """Ты — копирайтер. Напиши уникальное, короткое, естественное описание профиля Telegram (bio) на русском языке.

Тематика: {industry}
Имя/ник: {name}

Верни ТОЛЬКО JSON:
{
  "bio": "текст bio"
}""",
        "model": "deepseek-chat",
        "temperature": 0.9,
        "max_tokens": 200,
        "response_format": "json",
    },
    PromptType.SHILLING.value: {
        "name": "Шиллинг: вопрос и ответ",
        "content": json.dumps(
            {
                "setup": "Кто-нибудь уже пробовал сервис, о котором тут пишут? Не хочу влететь.",
                "reply": "Пользуюсь сам уже какое-то время, по работе зашёл. Если надо — могу в личке набросать, как подключался.",
            },
            ensure_ascii=False,
        ),
        "model": "deepseek-chat",
        "temperature": 0.0,
        "max_tokens": 200,
        "response_format": "json",
    },
    PromptType.INBOUND_DM.value: {
        "name": "Inbound DM",
        "content": """Ты отвечаешь в личных сообщениях Telegram от имени живого человека.

Входящее сообщение:
{incoming}

Контекст продукта/сервиса:
{product_context}

Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}

Дай короткий нативный ответ (1–3 предложения). Если спрашивают ссылку или промокод — дай их, если поля не пустые.
Верни ТОЛЬКО текст ответа без кавычек и JSON.""",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 350,
        "response_format": None,
    },
}


PROMPT_VARIABLES: dict[str, list[str]] = {
    PromptType.CHAT_MONITORING_TRIGGER.value: ["text"],
    PromptType.CHAT_MONITORING_RESPONSE.value: ["text"],
    PromptType.NEUROCOMMENTING.value: ["post_text", "chat_title"],
    PromptType.DISCUSSION_REPLY.value: ["message_text", "chat_title"],
    PromptType.DMP_OUTREACH.value: [
        "name",
        "company",
        "website",
        "page",
        "partner_utm_url",
        "partner_promo_code",
        "registered",
    ],
    PromptType.CHAT_RELEVANCE.value: ["query", "title", "description", "chat_type", "participants_count"],
    PromptType.LEAD_QUALIFICATION.value: ["history", "last_incoming", "partner_utm_url", "partner_promo_code"],
    PromptType.PROFILE_BIO.value: ["industry", "name"],
    PromptType.SHILLING.value: [],
    PromptType.INBOUND_DM.value: ["incoming", "product_context", "partner_utm_url", "partner_promo_code"],
}

SOLUTION_PROMPT_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "fulfillment": {
        PromptType.CHAT_MONITORING_TRIGGER.value: {
            "name": "Перехват заявок: триггер",
            "content": """Ты анализируешь сообщение в Telegram-чате.
Это заявка, если человек ищет фулфилмент, склад, упаковку, отгрузки, логистику для ecom, хранение товара.

Верни ТОЛЬКО валидный JSON без markdown:
{
  "is_lead": true/false,
  "confidence": 0.0-1.0,
  "reason": "краткое объяснение",
  "contact_type": "telegram",
  "contact_value": "username или id отправителя, если видно"
}

Сообщение:
{text}""",
        },
        PromptType.CHAT_MONITORING_RESPONSE.value: {
            "name": "Перехват заявок: ответ",
            "content": """Напиши короткое ЛС от живого человека с опытом отгрузок/склада.
Ответь по делу. Не закрывай сделку сам — цель позже передать менеджеру.

Сообщение из чата:
{text}

Верни ТОЛЬКО JSON:
{
  "message": "текст ответа"
}""",
        },
        PromptType.DMP_OUTREACH.value: {
            "name": "DMP: первое сообщение",
            "content": """Ты — доверенный аккаунт. Пишешь человеку, который смотрел сайт фулфилмента.
Прогрей интерес к складу/отгрузкам. Не закрывай сделку и не зови сразу «оставить заявку менеджеру».
Если есть промокод или ссылка — можно мягко упомянуть. Не признавайся в пикселе.

Имя: {name}
Компания: {company}
Сайт: {website}
Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}
Уже регистрировался: {registered}

Верни ТОЛЬКО JSON:
{
  "message": "текст первого сообщения"
}""",
        },
        PromptType.LEAD_QUALIFICATION.value: {
            "name": "Квалификация лида",
            "content": """Ты прогреваешь лида фулфилмента в Telegram.
Когда человек проявил интерес и готов обсуждать объёмы/условия — qualified=true, его передадут МОПу.
Не обещай цены сам.

История переписки:
{history}

Последнее сообщение лида:
{last_incoming}

Ссылка с UTM: {partner_utm_url}
Промокод: {partner_promo_code}

lost=true при отказе или спаме.
continue=true, если нужно ещё одно короткое сообщение.

Верни ТОЛЬКО JSON:
{
  "qualified": true/false,
  "lost": true/false,
  "continue": true/false,
  "reply": "следующее короткое сообщение, если continue=true"
}""",
        },
    },
}


def render_prompt(template: str, variables: dict[str, Any] | None = None) -> str:
    rendered = template or ""
    for key, value in (variables or {}).items():
        rendered = rendered.replace("{" + str(key) + "}", "" if value is None else str(value))
    return rendered


def prompts_for_kind(kind: str | None) -> dict[str, dict[str, Any]]:
    catalog = {key: dict(value) for key, value in DEFAULT_PROMPTS.items()}
    kind_key = (kind or "generic").strip().lower()
    if kind_key == "seo_saas":
        from ...alembic.prompt_data.seo_saas_prompts import SEO_SAAS_PROMPTS

        for prompt_type, override in SEO_SAAS_PROMPTS.items():
            catalog[prompt_type] = {**catalog.get(prompt_type, {}), **override}
    overrides = SOLUTION_PROMPT_OVERRIDES.get(kind_key, {})
    for prompt_type, override in overrides.items():
        catalog[prompt_type] = {**catalog.get(prompt_type, {}), **override}
    return catalog


async def create_default_prompts(session: AsyncSession, automation_id: int) -> None:
    automation = await session.get(CustomAutomation, automation_id)
    kind = (automation.solution_kind if automation else None) or "generic"
    catalog = prompts_for_kind(kind)
    for prompt_type, defaults in catalog.items():
        existing = await session.scalar(
            select(CustomPrompt).where(
                CustomPrompt.custom_automation_id == automation_id,
                CustomPrompt.prompt_type == prompt_type,
            )
        )
        if existing:
            continue
        prompt = CustomPrompt(
            custom_automation_id=automation_id,
            prompt_type=prompt_type,
            name=defaults["name"],
            content=defaults["content"],
            model=defaults["model"],
            temperature=defaults["temperature"],
            max_tokens=defaults["max_tokens"],
            response_format=defaults.get("response_format"),
            is_active=True,
            version=1,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        session.add(prompt)
    await session.commit()


async def list_prompts(session: AsyncSession, automation_id: int) -> list[CustomPrompt]:
    await create_default_prompts(session, automation_id)
    result = await session.execute(
        select(CustomPrompt).where(
            CustomPrompt.custom_automation_id == automation_id,
        ).order_by(CustomPrompt.prompt_type.asc(), CustomPrompt.version.desc())
    )
    return list(result.scalars().all())


async def get_prompt(session: AsyncSession, automation_id: int, prompt_id: int) -> CustomPrompt | None:
    prompt = await session.get(CustomPrompt, prompt_id)
    if not prompt or prompt.custom_automation_id != automation_id:
        return None
    return prompt


async def update_prompt(
    session: AsyncSession,
    automation_id: int,
    prompt_id: int,
    *,
    content: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    is_active: bool | None = None,
) -> CustomPrompt:
    prompt = await get_prompt(session, automation_id, prompt_id)
    if not prompt:
        raise ValueError("Prompt not found")

    new_prompt = CustomPrompt(
        custom_automation_id=automation_id,
        prompt_type=prompt.prompt_type,
        name=prompt.name,
        content=content if content is not None else prompt.content,
        model=model if model is not None else prompt.model,
        temperature=temperature if temperature is not None else prompt.temperature,
        max_tokens=max_tokens if max_tokens is not None else prompt.max_tokens,
        response_format=prompt.response_format,
        is_active=True if is_active is None else is_active,
        version=prompt.version + 1,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    prompt.is_active = False
    prompt.updated_at = _utc_now()
    session.add(new_prompt)
    await session.commit()
    await session.refresh(new_prompt)
    return new_prompt


async def toggle_prompt(session: AsyncSession, automation_id: int, prompt_id: int) -> CustomPrompt:
    prompt = await get_prompt(session, automation_id, prompt_id)
    if not prompt:
        raise ValueError("Prompt not found")
    prompt.is_active = not prompt.is_active
    prompt.updated_at = _utc_now()
    await session.commit()
    await session.refresh(prompt)
    return prompt


async def test_prompt(
    session: AsyncSession,
    automation_id: int,
    prompt_id: int,
    variables: dict[str, str],
) -> dict[str, Any]:
    prompt = await get_prompt(session, automation_id, prompt_id)
    if not prompt:
        raise ValueError("Prompt not found")

    rendered = prompt.content
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))

    missing = [v for v in PROMPT_VARIABLES.get(prompt.prompt_type, []) if f"{{{v}}}" in rendered]

    if prompt.prompt_type == PromptType.SHILLING.value:
        from .shilling_service import parse_shilling_lines

        setup, reply = parse_shilling_lines(prompt.content)
        return {
            "rendered": prompt.content,
            "output": f"{setup}\n---\n{reply}".strip(),
            "missing_variables": [] if setup and reply else ["setup", "reply"],
        }

    try:
        response = await ai_client.chat.completions.create(
            model=prompt.model,
            messages=[{"role": "user", "content": rendered}],
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens,
        )
        output = response.choices[0].message.content or ""
        return {
            "rendered": rendered,
            "output": output,
            "missing_variables": missing,
        }
    except Exception as exc:
        return {
            "rendered": rendered,
            "output": "",
            "error": str(exc),
            "missing_variables": missing,
        }


def extract_variables(content: str) -> list[str]:
    return list(set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", content)))
