"""Built-in /custom solution pipelines: SEO SaaS, fulfillment, DMP-bot."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...alembic.models import CustomAutomation

KIND_GENERIC = "generic"
KIND_SEO_SAAS = "seo_saas"
KIND_FULFILLMENT = "fulfillment"
KIND_DMP_BOT = "dmp_bot"

SLUG_SEO_SAAS = "seo-saas"
SLUG_FULFILLMENT = "fulfillment"
SLUG_DMP_BOT = "dmp-bot"

KNOWN_KINDS = {KIND_GENERIC, KIND_SEO_SAAS, KIND_FULFILLMENT, KIND_DMP_BOT}

BUILTIN_SOLUTIONS: list[dict[str, Any]] = [
    {
        "slug": SLUG_SEO_SAAS,
        "kind": KIND_SEO_SAAS,
        "name": "SEO SaaS",
        "client_name": "SEO SaaS",
        "industry": "seo_saas",
        "description": (
            "Партизанский маркетинг и DMP для SaaS SEO-продвижения. "
            "Без отдела продаж: доверенный аккаунт закрывает регистрацию по UTM/промокоду."
        ),
        "is_amocrm_enabled": False,
    },
    {
        "slug": SLUG_FULFILLMENT,
        "kind": KIND_FULFILLMENT,
        "name": "Фулфилмент",
        "client_name": "Фулфилмент",
        "industry": "fulfillment",
        "description": (
            "Партизанский маркетинг, DMP и прогрев доверенным аккаунтом "
            "с передачей в отдел продаж и AmoCRM."
        ),
        "is_amocrm_enabled": True,
    },
    {
        "slug": SLUG_DMP_BOT,
        "kind": KIND_DMP_BOT,
        "name": "DMP-бот",
        "client_name": "DMP-бот",
        "industry": "dmp_bot",
        "description": (
            "Связка DMP.one с Telegram-ботом и Google Таблицей. "
            "Без ИИ-агентов: лид приходит вебхуком, уходит в бот и в строку таблицы."
        ),
        "is_amocrm_enabled": False,
    },
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_solution_kind(value: str | None) -> str:
    kind = (value or KIND_GENERIC).strip().lower().replace("-", "_")
    if kind in KNOWN_KINDS:
        return kind
    return KIND_GENERIC


def is_dmp_notify_pipeline(automation: CustomAutomation) -> bool:
    return normalize_solution_kind(getattr(automation, "solution_kind", None)) == KIND_DMP_BOT


def qualification_enabled(automation: CustomAutomation) -> bool:
    """DMP-bot qualifies only if the toggle is on. Other pipelines always warm up."""
    if is_dmp_notify_pipeline(automation):
        return bool(getattr(automation, "is_lead_qualification_enabled", False))
    return True


def uses_sales_handoff(automation: CustomAutomation) -> bool:
    """SEO SaaS closes in-chat; DMP-bot notifies bot/sheets; fulfillment/generic hand off to sales."""
    kind = normalize_solution_kind(automation.solution_kind)
    return kind not in {KIND_SEO_SAAS, KIND_DMP_BOT}


def apply_solution_kind(automation: CustomAutomation, kind: str | None) -> None:
    kind = normalize_solution_kind(kind)
    automation.solution_kind = kind
    if kind == KIND_GENERIC:
        return
    automation.industry = automation.industry or kind
    if kind == KIND_DMP_BOT:
        automation.is_chat_monitoring_enabled = False
        automation.is_neurocommenting_enabled = False
        automation.is_digital_footprint_enabled = False
        automation.is_shilling_enabled = False
        automation.is_dmp_one_enabled = True
        automation.is_amocrm_enabled = False
        automation.is_lead_qualification_enabled = False
        automation.lead_warmup_enabled = False
        automation.status = "active" if automation.status == "draft" else automation.status
        return
    automation.is_chat_monitoring_enabled = True
    automation.is_neurocommenting_enabled = True
    automation.is_digital_footprint_enabled = True
    automation.is_shilling_enabled = True
    automation.is_dmp_one_enabled = True
    automation.is_amocrm_enabled = kind == KIND_FULFILLMENT
    automation.lead_warmup_enabled = True
    automation.status = "active" if automation.status == "draft" else automation.status


def lock_dmp_bot_modules(automation: CustomAutomation) -> None:
    if not is_dmp_notify_pipeline(automation):
        return
    automation.is_chat_monitoring_enabled = False
    automation.is_neurocommenting_enabled = False
    automation.is_digital_footprint_enabled = False
    automation.is_shilling_enabled = False
    automation.is_amocrm_enabled = False
    automation.lead_warmup_enabled = bool(automation.is_lead_qualification_enabled)


async def ensure_builtin_solutions(session: AsyncSession) -> list[int]:
    """Create the product pipelines if they are missing. Do not overwrite existing rows."""
    from ..account_pool_service import get_or_create_default_pool
    from .dmp_one_service import ensure_dmp_webhook_secret
    from .prompt_service import create_default_prompts

    ids: list[int] = []
    now = _utc_now()
    for spec in BUILTIN_SOLUTIONS:
        existing = await session.scalar(
            select(CustomAutomation).where(CustomAutomation.solution_slug == spec["slug"])
        )
        if existing:
            await get_or_create_default_pool(session, existing.id)
            if existing.is_dmp_one_enabled:
                ensure_dmp_webhook_secret(existing)
            if not is_dmp_notify_pipeline(existing):
                await create_default_prompts(session, existing.id)
            ids.append(existing.id)
            continue

        automation = CustomAutomation(
            name=spec["name"],
            client_name=spec["client_name"],
            industry=spec["industry"],
            description=spec["description"],
            status="active",
            solution_kind=spec["kind"],
            solution_slug=spec["slug"],
            created_at=now,
            updated_at=now,
        )
        apply_solution_kind(automation, spec["kind"])
        session.add(automation)
        await session.flush()
        await get_or_create_default_pool(session, automation.id)
        ensure_dmp_webhook_secret(automation)
        if spec["kind"] != KIND_DMP_BOT:
            await create_default_prompts(session, automation.id)
        ids.append(automation.id)
    await session.commit()
    return ids
