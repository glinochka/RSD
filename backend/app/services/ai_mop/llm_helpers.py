"""LLM-хелперы для провижининга и outreach ИИ МОП."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..ai_authoring import ai_client
from ..admin_booking.domains import DOMAIN_REGISTRY

logger = logging.getLogger(__name__)

AI_MOP_CONTACT_PHONE = "+79179156670"

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
    domain_options = ", ".join(_DOMAIN_KEYS)
    prompt = (
        "Ты готовишь демо-аккаунт для малого бизнеса на платформе RSD.\n"
        "По данным компании из холодной базы (Яндекс Карты / 2GIS, часто без сайта) сгенерируй профиль для:\n"
        "1) ИИ-администратора (crm_admin)\n"
        "2) Услуг и сотрудника\n"
        "3) Описания для генерации сайта\n\n"
        "КРИТИЧЕСКИ ВАЖНО:\n"
        "- Определи нишу строго по рубрикам/категории и названию компании из данных ниже.\n"
        "- domain_type выбирай только из списка; если ни один не подходит — используй custom.\n"
        "- НЕ подставляй нерелевантные ниши (салон красоты, ремонт ноутбуков, стоматология и т.д.), "
        "если они не следуют из рубрик.\n"
        "- business_description и services должны отражать реальный вид деятельности компании.\n\n"
        f"Данные компании:\n{lead_context}\n\n"
        f"Доступные domain_type: {domain_options}\n\n"
        f"{_PROVISION_SCHEMA}"
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    data = _extract_json(response.choices[0].message.content or "")
    domain_type = str(data.get("domain_type") or "custom").strip().lower()
    if domain_type not in DOMAIN_REGISTRY:
        domain_type = "custom"
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
        f"Напиши персональное холодное письмо от имени {platform_name}.\n\n"
        "Контекст: мы нашли компанию на Яндекс Картах, у неё нет сайта (или он не работает). "
        "Мы бесплатно сделали для них готовый демо-сайт с ИИ-чатом — виртуальным администратором.\n\n"
        "Структура (своими словами, не копируй шаблон дословно):\n"
        "1) Короткое деловое приветствие с названием компании.\n"
        "2) Почему написали: нет сайта, клиенты из поиска уходят к конкурентам.\n"
        "3) Что уже готово: демо-сайт с информацией о компании, ИИ-чат работает — дай ссылку.\n"
        "4) Условия: разработка бесплатно, далее только ежемесячная подписка, первый месяц бесплатно.\n"
        "5) Приглашение посмотреть демо; если есть вопросы или правки — ответить на письмо.\n"
        f"6) Контакт для связи: {AI_MOP_CONTACT_PHONE} — МАКС, Telegram или WhatsApp.\n\n"
        "Запрещено: логин, пароль, личный кабинет, «отправлю доступ» — это отпугивает.\n"
        "Тон: уверенный, по делу, без спама, капслока и панибратского «Привет!». На русском.\n\n"
        f"Компания:\n{lead_context}\n\n"
        f"Ссылка на демо: {website_url}\n\n"
        f"{_OUTREACH_SCHEMA}"
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    data = _extract_json(response.choices[0].message.content or "")
    return {
        "subject": str(data.get("subject") or "Мы сделали для вас сайт — посмотрите").strip()[:200],
        "text": str(data.get("text") or "").strip(),
        "html_body": str(data.get("html_body") or "").strip(),
    }


async def compose_outreach_dm(
    *,
    lead_context: str,
    website_url: str,
    org_name: str,
) -> str:
    """Первое холодное сообщение в мессенджер для ИИ МОП."""
    prompt = (
        "Напиши первое холодное сообщение в мессенджер (Telegram, WhatsApp или MAX) от имени менеджера RSD.\n\n"
        "Структура (своими словами, каждый раз разные формулировки):\n"
        "1) Приветствие + увидели компанию на Яндекс Картах + заметили, что нет сайта.\n"
        "2) Конкретный аргумент про упущенный спрос: люди ищут услуги этой ниши в интернете "
        "(можно упомянуть поисковые запросы / Вордстат в общих чертах; не выдумывай точные цифры).\n"
        "3) Мы специально для них сделали готовый сайт с ИИ-агентом для обработки заявок — ссылка.\n"
        "4) Разработка бесплатно, работаем по ежемесячной подписке, первый месяц бесплатно.\n"
        "5) Если нужны правки — напишите здесь, в этом чате, сделаем.\n\n"
        "Правила:\n"
        "- Тон: живой, уверенный, продающий, но без агрессии и шаблонных фраз.\n"
        "- Персонализируй под компанию и рубрику.\n"
        "- НЕ указывай логин, пароль, личный кабинет.\n"
        "- НЕ предлагай «связаться в мессенджере», «написать в Telegram/WhatsApp/МАКС» "
        "и НЕ указывай телефон для связи — получатель уже в мессенджере, ответит в этом чате.\n"
        "- 4–7 предложений, только чистый текст без markdown.\n"
        "- Верни только текст сообщения, без пояснений.\n\n"
        f"Компания «{org_name}»:\n{lead_context}\n\n"
        f"Ссылка на демо: {website_url}\n"
    )
    response = await ai_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.95,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Пустой текст сообщения для outreach DM")
    return text[:1200]


def build_lead_context(
    *,
    org_name: str,
    email: str,
    lpr_name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    category: str | None = None,
    region: str | None = None,
    city: str | None = None,
    working_hours: str | None = None,
    website_existing: str | None = None,
    yandex_url: str | None = None,
    extra_notes: str | None = None,
) -> str:
    parts = [f"Название: {org_name}", f"Email: {email}"]
    if lpr_name:
        parts.append(f"Контакт: {lpr_name}")
    if phone:
        parts.append(f"Телефон: {phone}")
    if region:
        parts.append(f"Регион: {region}")
    if city:
        parts.append(f"Город: {city}")
    if address:
        parts.append(f"Адрес: {address}")
    if category:
        parts.append(f"Рубрика / ниша: {category}")
    if working_hours:
        parts.append(f"Время работы: {working_hours}")
    if website_existing:
        parts.append(f"Сайт в карточке: {website_existing}")
    if yandex_url:
        parts.append(f"Карточка Яндекс: {yandex_url}")
    if extra_notes:
        parts.append(extra_notes)
    parts.append("Сайта у компании нет (или не указан) — делаем демо с нуля.")
    return "\n".join(parts)


def parse_lead_extra_json(lead) -> dict[str, Any]:
    raw = getattr(lead, "extra_json", None)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def build_lead_context_from_lead(lead) -> str:
    extra = parse_lead_extra_json(lead)
    notes: list[str] = []
    for key in ("subrubric", "подрубрика", "payment_methods", "rating", "reviews_count"):
        val = extra.get(key)
        if val and str(val).strip():
            label = {
                "subrubric": "Подрубрика",
                "подрубрика": "Подрубрика",
                "payment_methods": "Способы оплаты",
                "rating": "Рейтинг",
                "reviews_count": "Отзывы",
            }.get(key, key)
            notes.append(f"{label}: {val}")
    contact_email = str(extra.get("contact_email") or lead.email or "").strip()
    return build_lead_context(
        org_name=lead.org_name,
        email=contact_email or str(lead.email or ""),
        lpr_name=lead.lpr_name,
        phone=lead.phone,
        address=lead.address,
        category=lead.category,
        region=extra.get("region"),
        city=extra.get("city"),
        working_hours=extra.get("working_hours"),
        website_existing=extra.get("сайт") or extra.get("website"),
        yandex_url=getattr(lead, "yandex_url", None),
        extra_notes="\n".join(notes) if notes else None,
    )


_GENERATION_BRIEF_MAX_LEN = 5000


def extract_lead_social_links(lead) -> dict[str, str]:
    """Соцсети из базы лида — только реально указанные ссылки."""
    extra = parse_lead_extra_json(lead)
    links: dict[str, str] = {}

    def _put(label: str, raw: str | None) -> None:
        val = str(raw or "").strip()
        if not val or val in ("—", "-", "нет"):
            return
        if not val.startswith("http") and label in {"ВКонтакте", "YouTube"} and " " in val:
            return
        links[label] = val[:512]

    _put("Telegram", lead.telegram or extra.get("telegram"))
    _put("WhatsApp", lead.whatsapp or extra.get("whatsapp"))
    _put("MAX", extra.get("messenger_max") or extra.get("max") or extra.get("макс"))

    for key, val in extra.items():
        if not val or not isinstance(key, str):
            continue
        nk = key.casefold().replace(" ", "")
        text = str(val).strip()
        if not text:
            continue
        if nk in {"vk", "вконтакте", "vkontakte"} or "вконтакт" in nk:
            _put("ВКонтакте", text)
        elif nk in {"youtube", "ютуб"} or "youtube" in nk:
            _put("YouTube", text)
        elif nk in {"telegram", "телеграм"}:
            _put("Telegram", text)
        elif nk in {"whatsapp"}:
            _put("WhatsApp", text)
        elif nk in {"messenger_max", "max", "макс"}:
            _put("MAX", text)

    return links


def _fit_generation_brief(text: str, *, max_len: int = _GENERATION_BRIEF_MAX_LEN) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def build_website_generation_brief(*, lead, business_description: str) -> str:
    extra = parse_lead_extra_json(lead)
    region = extra.get("region") or "—"
    city = extra.get("city") or "—"
    hours = extra.get("working_hours") or "—"
    rubric = lead.category or extra.get("rubric") or extra.get("рубрика") or "—"
    subrubric = extra.get("subrubric") or extra.get("подрубрика") or ""
    social = extract_lead_social_links(lead)
    parts = [
        f"Сайт для компании «{lead.org_name}».",
        f"Описание бизнеса: {business_description}",
        f"Рубрика / ниша (Яндекс Карты): {rubric}{f' — {subrubric}' if subrubric else ''}.",
        f"Регион: {region}, город: {city}. Адрес: {lead.address or 'не указан'}. Время работы: {hours}.",
        "Дизайн, тексты и услуги должны соответствовать рубрике и названию компании. "
        "Не используй шаблоны других отраслей, если они не указаны в рубрике.",
        "НЕ добавляй чат, мессенджер или секцию «онлайн-консультант» — виджет подключит платформа.",
    ]
    if social:
        social_text = "; ".join(f"{name}: {url}" for name, url in social.items())
        parts.append(
            f"Соцсети в футере ТОЛЬКО эти (без Facebook/Twitter/Instagram): {social_text}."
        )
    else:
        parts.append("Соцсети в футере не добавляй — в базе нет ссылок.")
    return _fit_generation_brief("\n".join(parts))
