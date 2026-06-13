from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

MAINTENANCE_GRACE_DAYS = 3

AGENT_CONTRACT_DURATION_MONTHS = (1, 3, 6)
AGENT_DURATION_DISCOUNT_BY_MONTHS: dict[int, int] = {
    1: 0,
    3: 15,
    6: 25,
}

# Шаблоны на странице /pricing (без «под ключ» и без content_factory).
PRICING_PAGE_TEMPLATE_CODES: tuple[str, ...] = ("qa", "crm_admin", "sales_manager")

PRICING_CARD_TITLES: dict[str, str] = {
    "qa": "ИИ консультант",
    "crm_admin": "ИИ Администратор",
    "sales_manager": "ИИ МОП",
}


@dataclass(frozen=True)
class AgentTemplatePricing:
    code: str
    title: str
    setup_rub_min: int
    monthly_maintenance_rub_min: int
    is_free: bool
    selectable: bool
    status: str  # available | in_development
    description: str = ""

    def to_public_dict(self, *, card_title: str | None = None) -> dict[str, Any]:
        data = asdict(self)
        data["card_title"] = card_title or self.title
        data["llm_tokens_note"] = (
            "Токены LLM включены в подписку — расходы на модели покрывает платформа."
        )
        return data


_DEFAULT_PRICING_CARD_TITLES: dict[str, str] = dict(PRICING_CARD_TITLES)

_DEFAULT_AGENT_TEMPLATE_PRICING: dict[str, AgentTemplatePricing] = {
    "qa": AgentTemplatePricing(
        code="qa",
        title="ИИ консультант",
        setup_rub_min=0,
        monthly_maintenance_rub_min=0,
        is_free=True,
        selectable=True,
        status="available",
        description=(
            "Бесплатный пробный шаблон: ответы по базе знаний для поддержки и консультаций. "
            "Подходит, чтобы попробовать платформу без оплаты."
        ),
    ),
    "crm_admin": AgentTemplatePricing(
        code="crm_admin",
        title="ИИ Администратор",
        setup_rub_min=0,
        monthly_maintenance_rub_min=990,
        is_free=False,
        selectable=True,
        status="available",
        description=(
            "Запись, расписание и интеграции с CRM/ERP. Подписка 990 ₽/мес; "
            "первые 3 дня после создания бесплатно. Сложные интеграции — отдельно."
        ),
    ),
    "sales_manager": AgentTemplatePricing(
        code="sales_manager",
        title="ИИ МОП",
        setup_rub_min=0,
        monthly_maintenance_rub_min=1_990,
        is_free=False,
        selectable=True,
        status="available",
        description=(
            "Исходящие и входящие продажи в мессенджерах. Подписка 1 990 ₽/мес; "
            "первые 3 дня после создания бесплатно."
        ),
    ),
    "content_factory": AgentTemplatePricing(
        code="content_factory",
        title="Контент‑завод",
        setup_rub_min=0,
        monthly_maintenance_rub_min=0,
        is_free=False,
        selectable=False,
        status="in_development",
        description="Шаблон в разработке. Создание и переключение на него временно недоступны.",
    ),
    "ai_logist": AgentTemplatePricing(
        code="ai_logist",
        title="ИИ Логист",
        setup_rub_min=0,
        monthly_maintenance_rub_min=0,
        is_free=False,
        selectable=False,
        status="in_development",
        description="Логистика и статусы заказов — шаблон в разработке.",
    ),
    "ai_manager": AgentTemplatePricing(
        code="ai_manager",
        title="ИИ менеджер",
        setup_rub_min=0,
        monthly_maintenance_rub_min=0,
        is_free=False,
        selectable=False,
        status="in_development",
        description="Телефония и входящие звонки — шаблон в разработке.",
    ),
}

# Legacy alias kept for stored agents; not offered in UI.
_DEFAULT_AGENT_TEMPLATE_PRICING["lead_generation"] = AgentTemplatePricing(
    code="lead_generation",
    title="Генерация лидов (legacy)",
    setup_rub_min=0,
    monthly_maintenance_rub_min=1_990,
    is_free=False,
    selectable=False,
    status="in_development",
    description="Устаревший шаблон, используйте «ИИ МОП».",
)

_ADMIN_EDITABLE_TEMPLATE_CODES = frozenset(
    code for code in _DEFAULT_AGENT_TEMPLATE_PRICING if code != "lead_generation"
)

_OVERRIDE_FILE_PATH = Path(__file__).with_name("agent_template_pricing.override.json")

AGENT_TEMPLATE_PRICING: dict[str, AgentTemplatePricing] = {}
TEMPLATE_TYPES_IN_DEVELOPMENT: set[str] = set()


def _read_pricing_overrides() -> dict[str, dict[str, Any]]:
    if not _OVERRIDE_FILE_PATH.exists():
        return {}
    try:
        raw = json.loads(_OVERRIDE_FILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    overrides: dict[str, dict[str, Any]] = {}
    for code, data in raw.items():
        if code in _ADMIN_EDITABLE_TEMPLATE_CODES and isinstance(data, dict):
            overrides[str(code)] = data
    return overrides


def _merge_template_pricing(
    base: AgentTemplatePricing,
    upd: dict[str, Any],
    *,
    card_titles: dict[str, str],
) -> AgentTemplatePricing:
    code = base.code
    title = str(upd.get("title", base.title) or base.title)
    setup_rub_min = int(upd.get("setup_rub_min", base.setup_rub_min) or 0)
    monthly_maintenance_rub_min = int(
        upd.get("monthly_maintenance_rub_min", base.monthly_maintenance_rub_min) or 0
    )
    is_free = bool(upd.get("is_free", base.is_free))
    selectable = bool(upd.get("selectable", base.selectable))
    status = str(upd.get("status", base.status) or base.status)
    if status not in ("available", "in_development"):
        status = base.status
    description = str(upd.get("description", base.description) or "")
    if "card_title" in upd:
        card_title = str(upd.get("card_title") or "").strip()
        if card_title:
            card_titles[code] = card_title
        elif code in card_titles:
            del card_titles[code]
    return AgentTemplatePricing(
        code=code,
        title=title,
        setup_rub_min=setup_rub_min,
        monthly_maintenance_rub_min=monthly_maintenance_rub_min,
        is_free=is_free,
        selectable=selectable,
        status=status,
        description=description,
    )


def _apply_pricing_overrides(overrides: dict[str, dict[str, Any]]) -> tuple[dict[str, AgentTemplatePricing], dict[str, str]]:
    card_titles = dict(_DEFAULT_PRICING_CARD_TITLES)
    pricing: dict[str, AgentTemplatePricing] = {}
    for code, base in _DEFAULT_AGENT_TEMPLATE_PRICING.items():
        upd = overrides.get(code, {})
        if upd:
            pricing[code] = _merge_template_pricing(base, upd, card_titles=card_titles)
        else:
            pricing[code] = base
    return pricing, card_titles


def _reload_agent_template_pricing() -> None:
    global AGENT_TEMPLATE_PRICING, TEMPLATE_TYPES_IN_DEVELOPMENT, PRICING_CARD_TITLES
    AGENT_TEMPLATE_PRICING, PRICING_CARD_TITLES = _apply_pricing_overrides(_read_pricing_overrides())
    TEMPLATE_TYPES_IN_DEVELOPMENT = {
        code for code, row in AGENT_TEMPLATE_PRICING.items() if row.status == "in_development"
    }


_reload_agent_template_pricing()


def get_paid_agent_template_types() -> tuple[str, ...]:
    return tuple(
        code
        for code, pricing in AGENT_TEMPLATE_PRICING.items()
        if pricing.monthly_maintenance_rub_min > 0
    )


def get_all_agent_template_pricing_admin() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for code in sorted(_ADMIN_EDITABLE_TEMPLATE_CODES):
        row = AGENT_TEMPLATE_PRICING.get(code)
        if not row:
            continue
        data = row.to_public_dict(card_title=PRICING_CARD_TITLES.get(code))
        data["on_pricing_page"] = code in PRICING_PAGE_TEMPLATE_CODES
        items.append(data)
    return items


def update_agent_template_pricing_overrides(*, template_updates: list[dict[str, Any]]) -> None:
    overrides = _read_pricing_overrides()
    for upd in template_updates:
        code = upd.get("code")
        if code not in _ADMIN_EDITABLE_TEMPLATE_CODES:
            continue
        base = _DEFAULT_AGENT_TEMPLATE_PRICING[code]
        entry: dict[str, Any] = {
            "title": str(upd.get("title", base.title) or base.title),
            "setup_rub_min": int(upd.get("setup_rub_min", base.setup_rub_min) or 0),
            "monthly_maintenance_rub_min": int(
                upd.get("monthly_maintenance_rub_min", base.monthly_maintenance_rub_min) or 0
            ),
            "is_free": bool(upd.get("is_free", base.is_free)),
            "selectable": bool(upd.get("selectable", base.selectable)),
            "status": str(upd.get("status", base.status) or base.status),
            "description": str(upd.get("description", base.description) or ""),
        }
        card_title = upd.get("card_title")
        if card_title is not None:
            card_title_str = str(card_title).strip()
            if card_title_str:
                entry["card_title"] = card_title_str
        overrides[str(code)] = entry

    tmp_path = _OVERRIDE_FILE_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(_OVERRIDE_FILE_PATH)
    _reload_agent_template_pricing()

PAYMENT_KIND_SUBSCRIPTION = "subscription"
PAYMENT_KIND_AGENT_ACTIVATION = "agent_activation"
PAYMENT_KIND_AGENT_MAINTENANCE = "agent_maintenance"

AGENT_PAYMENT_PLAN_PREFIX = "__agent__:"


def list_public_agent_template_pricing() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for code in PRICING_PAGE_TEMPLATE_CODES:
        row = AGENT_TEMPLATE_PRICING.get(code)
        if not row:
            continue
        items.append(row.to_public_dict(card_title=PRICING_CARD_TITLES.get(code)))
    return items


def _agent_registered_date(agent) -> date:
    registered = getattr(agent, "registered", None)
    if registered is None:
        return date.today()
    if isinstance(registered, datetime):
        return registered.date()
    return registered


def maintenance_grace_until(agent) -> date | None:
    pricing = get_agent_template_pricing(getattr(agent, "template_type", None))
    if not pricing or pricing.monthly_maintenance_rub_min <= 0:
        return None
    return _agent_registered_date(agent) + timedelta(days=MAINTENANCE_GRACE_DAYS)


def is_maintenance_grace_active(agent, *, today: date | None = None) -> bool:
    grace_until = maintenance_grace_until(agent)
    if grace_until is None:
        return False
    ref = today or date.today()
    return ref <= grace_until


def initial_maintenance_paid_until_for_template(template_type: str, *, from_date: date | None = None) -> date | None:
    pricing = get_agent_template_pricing(template_type)
    if not pricing or pricing.monthly_maintenance_rub_min <= 0:
        return None
    base = from_date or date.today()
    return base + timedelta(days=MAINTENANCE_GRACE_DAYS)


def get_agent_template_pricing(template_type: str | None) -> AgentTemplatePricing | None:
    raw = (template_type or "qa").strip().lower()
    return AGENT_TEMPLATE_PRICING.get(raw)


def assert_template_selectable(template_type: str | None) -> AgentTemplatePricing:
    pricing = get_agent_template_pricing(template_type)
    if pricing is None:
        raise ValueError(f"Unknown template_type: {template_type}")
    if not pricing.selectable or pricing.status == "in_development":
        raise ValueError(f"Template {pricing.code} is not available for new agents")
    return pricing


def requires_activation_payment(template_type: str | None) -> bool:
    pricing = get_agent_template_pricing(template_type)
    if not pricing:
        return False
    return pricing.setup_rub_min > 0


def user_has_free_agent_activation(user) -> bool:
    return bool(user and getattr(user, "free_agent_activation", False))


def is_activation_paid(agent, *, user=None) -> bool:
    if user_has_free_agent_activation(user):
        return True
    pricing = get_agent_template_pricing(getattr(agent, "template_type", None))
    if not pricing or pricing.setup_rub_min <= 0:
        return True
    paid_at = getattr(agent, "activation_paid_at", None)
    return paid_at is not None


def round_contract_total_rub(value: int) -> int:
    normalized = int(value or 0)
    if normalized <= 0:
        return 0
    return max(90, round((normalized - 90) / 100) * 100 + 90)


def calculate_contract_total_rub(monthly_rub: int, duration_months: int) -> int:
    months = int(duration_months or 1)
    if months not in AGENT_CONTRACT_DURATION_MONTHS:
        months = 1
    discount_percent = AGENT_DURATION_DISCOUNT_BY_MONTHS.get(months, 0)
    base_total = int(monthly_rub) * months
    discounted = round(base_total * (1 - discount_percent / 100))
    return round_contract_total_rub(discounted)


def calculate_contract_amount_kopecks(monthly_rub: int, duration_months: int) -> int:
    return calculate_contract_total_rub(monthly_rub, duration_months) * 100


def is_maintenance_current(agent, *, today: date | None = None) -> bool:
    pricing = get_agent_template_pricing(getattr(agent, "template_type", None))
    if not pricing or pricing.monthly_maintenance_rub_min <= 0:
        return True
    if is_maintenance_grace_active(agent, today=today):
        return True
    paid_until = getattr(agent, "maintenance_paid_until", None)
    if paid_until is None:
        return False
    ref = today or date.today()
    if isinstance(paid_until, datetime):
        paid_until = paid_until.date()
    return paid_until >= ref


def build_agent_billing_state(agent, *, user=None) -> dict[str, Any]:
    template_type = (getattr(agent, "template_type", None) or "qa").strip().lower()
    pricing = get_agent_template_pricing(template_type) or AGENT_TEMPLATE_PRICING["qa"]
    activation_exempt = user_has_free_agent_activation(user)
    activation_paid = is_activation_paid(agent, user=user)
    maintenance_current = is_maintenance_current(agent)
    grace_until = maintenance_grace_until(agent)
    grace_active = is_maintenance_grace_active(agent)
    paid_until = getattr(agent, "maintenance_paid_until", None)
    if isinstance(paid_until, datetime):
        paid_until = paid_until.date()
    requires_subscription = pricing.monthly_maintenance_rub_min > 0
    can_activate = maintenance_current if requires_subscription else activation_paid
    today = date.today()
    trial_days_left = None
    if grace_active and grace_until is not None:
        trial_days_left = max(0, (grace_until - today).days)
    return {
        "template_type": template_type,
        "template_title": pricing.title,
        "setup_rub_min": pricing.setup_rub_min,
        "monthly_maintenance_rub_min": pricing.monthly_maintenance_rub_min,
        "monthly_price_rub": pricing.monthly_maintenance_rub_min,
        "is_free": pricing.is_free,
        "requires_subscription": requires_subscription,
        "activation_exempt": activation_exempt,
        "activation_paid": activation_paid,
        "maintenance_current": maintenance_current,
        "maintenance_grace_active": grace_active,
        "maintenance_grace_until": grace_until.isoformat() if grace_until else None,
        "maintenance_paid_until": paid_until.isoformat() if paid_until else None,
        "trial_days_left": trial_days_left,
        "can_activate": can_activate,
        "activation_required_rub": 0,
        "renewal_payment_kind": PAYMENT_KIND_AGENT_MAINTENANCE if requires_subscription else None,
        "duration_discounts": AGENT_DURATION_DISCOUNT_BY_MONTHS,
        "llm_tokens_included": True,
        "autopay_enabled": bool(getattr(agent, "autopay_enabled", False)),
        "autopay_available": requires_subscription,
        "autopay_has_payment_method": bool(getattr(agent, "yookassa_payment_method_id", None)),
        "autopay_duration_months": int(getattr(agent, "autopay_duration_months", None) or 1),
        "autopay_last_error": getattr(agent, "autopay_last_error", None),
        "yookassa_autopay_available": _yookassa_autopay_available(),
    }


def _yookassa_autopay_available() -> bool:
    from .services.agent_autopay import is_yookassa_autopay_available

    return is_yookassa_autopay_available()


def agent_payment_plan_name(*, payment_kind: str, template_type: str) -> str:
    return f"{AGENT_PAYMENT_PLAN_PREFIX}{payment_kind}:{template_type}"


def parse_agent_payment_plan_name(plan_name: str) -> tuple[str, str] | None:
    raw = (plan_name or "").strip()
    if not raw.startswith(AGENT_PAYMENT_PLAN_PREFIX):
        return None
    body = raw[len(AGENT_PAYMENT_PLAN_PREFIX) :]
    if ":" not in body:
        return None
    kind, template_type = body.split(":", 1)
    if kind not in (PAYMENT_KIND_AGENT_ACTIVATION, PAYMENT_KIND_AGENT_MAINTENANCE):
        return None
    return kind, template_type.strip().lower()
