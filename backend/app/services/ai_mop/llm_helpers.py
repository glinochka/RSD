"""LLM-хелперы для провижининга и outreach ИИ МОП."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..ai_authoring import ai_client
from ..admin_booking.domains import DOMAIN_REGISTRY

logger = logging.getLogger(__name__)

_DOMAIN_KEYS = sorted(DOMAIN_REGISTRY.keys())

_PROVISION_SCHEMA = """
Верни ТОЛЬКО валидный JSON без markdown:
{
  "domain_type": "<один из: """ + ", ".join(_DOMAIN_KEYS) + """>",
  "business_description": "<2-4 предложения о компании для сайта>",
  "agent_system_prompt": "<системный промпт ИИ-администратора компании, 3-6 предложений>",
  "staff": [{"full_name": "<имя>", "role": "<роль>", "specializations": ["<услуга>"]}],
  "services": [{"name": "<услуга>", "description": "<кратко>", "duration_minutes": 60, "price_rub": 0}]
}
""".strip()

_OUTREACH_SCHEMA = """
Верни ТОЛЬКО валидный JSON без markdown:
{
  "subject": "<тема письма, до 80 символов>",
  "text": "<текст письма plain text, 4-8 предложений>",
  "html_body": "<HTML фрагмент для тела письма: параграфы <p>, без html/head/body>"
}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


async def generate_provision_profile(*, lead_context: str) -> dict[str, Any]:
    prompt = (
        "Ты готовишь демо-аккаунт для малого бизнеса на платформе RSD.\n"
        "По данным компании из холодной базы (без сайта) сгенерируй профиль для:\n"
        "1) ИИ-администратора (crm_admin)\n"
        "2) Услуг и сотрудника\n"
        "3) Описания для генерации сайта\n\n"
        f"Данные компании:\n{lead_context}\n\n"
        f"{_PROVISION_SCHEMA}"
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    data = _extract_json(response.choices[0].message.content or "")
    domain_type = str(data.get("domain_type") or "beauty_salon").strip().lower()
    if domain_type not in DOMAIN_REGISTRY:
        domain_type = "beauty_salon"
    data["domain_type"] = domain_type
    return data


async def compose_outreach_email(
    *,
    lead_context: str,
    website_url: str,
    login_email: str,
    temp_password: str,
    platform_name: str = "RSD",
) -> dict[str, str]:
    prompt = (
        f"Напиши персональное холодное письмо от имени {platform_name}.\n"
        "Контекст: мы заметили, что у компании нет сайта, и БЕСПЛАТНО сделали для них демо:\n"
        "- готовый сайт с ИИ-чатом (ИИ-администратор)\n"
        "- первый месяц обслуживания бесплатно, далее только ежемесячная оплата\n"
        "Тон: дружелюбный, по делу, без спама и капслока. На русском.\n"
        "Обязательно укажи ссылку на сайт и данные для входа в личный кабинет.\n\n"
        f"Компания:\n{lead_context}\n\n"
        f"Сайт: {website_url}\n"
        f"Email для входа: {login_email}\n"
        f"Временный пароль: {temp_password}\n\n"
        f"{_OUTREACH_SCHEMA}"
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
    )
    data = _extract_json(response.choices[0].message.content or "")
    return {
        "subject": str(data.get("subject") or "Мы сделали для вас сайт — посмотрите").strip()[:200],
        "text": str(data.get("text") or "").strip(),
        "html_body": str(data.get("html_body") or "").strip(),
    }


def build_lead_context(
    *,
    org_name: str,
    email: str,
    lpr_name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    category: str | None = None,
) -> str:
    parts = [f"Название: {org_name}", f"Email: {email}"]
    if lpr_name:
        parts.append(f"Контакт: {lpr_name}")
    if phone:
        parts.append(f"Телефон: {phone}")
    if address:
        parts.append(f"Адрес: {address}")
    if category:
        parts.append(f"Категория: {category}")
    parts.append("Сайта у компании нет (или не указан).")
    return "\n".join(parts)
