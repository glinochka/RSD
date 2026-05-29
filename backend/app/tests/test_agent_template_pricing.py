import pytest

from datetime import date, timedelta

from app.agent_template_pricing import (
    MAINTENANCE_GRACE_DAYS,
    assert_template_selectable,
    build_agent_billing_state,
    get_agent_template_pricing,
    initial_maintenance_paid_until_for_template,
    is_activation_paid,
    is_maintenance_grace_active,
    list_public_agent_template_pricing,
    parse_agent_payment_plan_name,
    agent_payment_plan_name,
    PAYMENT_KIND_AGENT_ACTIVATION,
    user_has_free_agent_activation,
)


class _FakeUser:
    def __init__(self, *, free_agent_activation: bool = False):
        self.free_agent_activation = free_agent_activation


class _FakeAgent:
    def __init__(
        self,
        *,
        template_type: str,
        activation_paid_at=None,
        maintenance_paid_until=None,
        registered=None,
    ):
        self.template_type = template_type
        self.activation_paid_at = activation_paid_at
        self.maintenance_paid_until = maintenance_paid_until
        self.registered = registered or date.today()


def test_qa_is_free():
    pricing = get_agent_template_pricing("qa")
    assert pricing is not None
    assert pricing.is_free is True
    assert pricing.setup_rub_min == 0
    assert pricing.monthly_maintenance_rub_min == 0


def test_crm_admin_minimum_prices():
    pricing = get_agent_template_pricing("crm_admin")
    assert pricing.setup_rub_min == 0
    assert pricing.monthly_maintenance_rub_min == 990


def test_sales_manager_minimum_prices():
    pricing = get_agent_template_pricing("sales_manager")
    assert pricing.setup_rub_min == 0
    assert pricing.monthly_maintenance_rub_min == 1_990


def test_content_factory_not_selectable():
    with pytest.raises(ValueError):
        assert_template_selectable("content_factory")


def test_ai_manager_not_selectable():
    with pytest.raises(ValueError):
        assert_template_selectable("ai_manager")


def test_ai_logist_not_selectable():
    with pytest.raises(ValueError):
        assert_template_selectable("ai_logist")


def test_activation_billing_state_paid_template_in_trial():
    created = date.today()
    agent = _FakeAgent(
        template_type="crm_admin",
        registered=created,
        maintenance_paid_until=initial_maintenance_paid_until_for_template("crm_admin", from_date=created),
    )
    billing = build_agent_billing_state(agent)
    assert billing["can_activate"] is True
    assert billing["maintenance_current"] is True
    assert billing["requires_subscription"] is True
    assert billing["monthly_price_rub"] == 990


def test_free_agent_activation_exempt_user():
    user = _FakeUser(free_agent_activation=True)
    agent = _FakeAgent(template_type="crm_admin")
    assert user_has_free_agent_activation(user) is True
    assert is_activation_paid(agent, user=user) is True
    billing = build_agent_billing_state(agent, user=user)
    assert billing["activation_exempt"] is True
    assert billing["can_activate"] is True
    assert billing["activation_required_rub"] == 0


def test_agent_payment_plan_roundtrip():
    plan = agent_payment_plan_name(
        payment_kind=PAYMENT_KIND_AGENT_ACTIVATION,
        template_type="sales_manager",
    )
    parsed = parse_agent_payment_plan_name(plan)
    assert parsed == (PAYMENT_KIND_AGENT_ACTIVATION, "sales_manager")


def test_public_catalog_only_pricing_page_templates():
    codes = [row["code"] for row in list_public_agent_template_pricing()]
    assert codes == ["qa", "crm_admin", "sales_manager"]
    assert "content_factory" not in codes
    admin = next(row for row in list_public_agent_template_pricing() if row["code"] == "crm_admin")
    assert admin["card_title"] == "ИИ Администратор"
    mop = next(row for row in list_public_agent_template_pricing() if row["code"] == "sales_manager")
    assert mop["card_title"] == "ИИ МОП"
    qa = next(row for row in list_public_agent_template_pricing() if row["code"] == "qa")
    assert qa["card_title"] == "ИИ консультант"


def test_maintenance_grace_three_day_trial():
    created = date.today() - timedelta(days=1)
    agent = _FakeAgent(
        template_type="crm_admin",
        registered=created,
        maintenance_paid_until=initial_maintenance_paid_until_for_template("crm_admin", from_date=created),
    )
    assert is_maintenance_grace_active(agent) is True
    billing = build_agent_billing_state(agent)
    assert billing["maintenance_current"] is True
    assert billing["maintenance_grace_active"] is True

    old_agent = _FakeAgent(
        template_type="crm_admin",
        registered=date.today() - timedelta(days=MAINTENANCE_GRACE_DAYS + 1),
        maintenance_paid_until=date.today() - timedelta(days=1),
    )
    assert is_maintenance_grace_active(old_agent) is False
    assert build_agent_billing_state(old_agent)["maintenance_current"] is False
