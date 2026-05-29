from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
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


AGENT_TEMPLATE_PRICING: dict[str, AgentTemplatePricing] = {
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
AGENT_TEMPLATE_PRICING["lead_generation"] = AgentTemplatePricing(
    code="lead_generation",
    title="Генерация лидов (legacy)",
    setup_rub_min=0,
    monthly_maintenance_rub_min=1_990,
    is_free=False,
    selectable=False,
    status="in_development",
    description="Устаревший шаблон, используйте «ИИ МОП».",
)

TEMPLATE_TYPES_IN_DEVELOPMENT = {
    code for code, row in AGENT_TEMPLATE_PRICING.items() if row.status == "in_development"
}

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
