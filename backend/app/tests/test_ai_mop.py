"""Тесты кастомного рантайма ИИ МОП."""

from __future__ import annotations

import pytest

from app.services.ai_mop.lead_import import (
    _dedup_key,
    account_email_candidates,
    allocate_unique_account_email,
    generate_account_email_from_org,
)
from app.services.ai_mop.llm_helpers import AI_MOP_CONTACT_PHONE, build_lead_context_from_lead
from app.services.ai_mop.outreach import resolve_lead_contact_email
from app.services.ai_mop.provisioning import generate_temp_password
from app.services.sales.outreach_scheduling import EXCEL_STAGGER_MAX_MINUTES, EXCEL_STAGGER_MIN_MINUTES


def test_generate_temp_password_length_and_charset():
    pwd = generate_temp_password()
    assert len(pwd) == 5
    allowed = set("abcdefghjkmnpqrstuvwxyz23456789")
    assert set(pwd) <= allowed


def test_dedup_key_normalizes_email():
    a = _dedup_key(email="Test@Example.COM")
    b = _dedup_key(email="test@example.com")
    assert a == b
    assert len(a) == 64


def test_generate_account_email_from_org(monkeypatch):
    monkeypatch.setattr("app.services.ai_mop.lead_import.settings.AI_MOP_ACCOUNT_EMAIL_DOMAIN", "rsd-ai.ru")
    email = generate_account_email_from_org("Веб студия Webba")
    assert email.endswith("@rsd-ai.ru")
    assert "@" in email
    local = email.split("@")[0]
    assert local.isascii()


def test_account_email_candidates_adds_numeric_suffixes():
    candidates = account_email_candidates("dentrium@rsd-ai.ru", max_candidates=4)
    assert candidates == [
        "dentrium@rsd-ai.ru",
        "dentrium1@rsd-ai.ru",
        "dentrium2@rsd-ai.ru",
        "dentrium3@rsd-ai.ru",
    ]


def test_account_email_candidates_continue_from_existing_suffix():
    candidates = account_email_candidates("dentrium2@rsd-ai.ru", max_candidates=3)
    assert candidates == [
        "dentrium2@rsd-ai.ru",
        "dentrium3@rsd-ai.ru",
        "dentrium4@rsd-ai.ru",
    ]


@pytest.mark.asyncio
async def test_allocate_unique_account_email_skips_taken_addresses():
    class _User:
        def __init__(self, email: str) -> None:
            self.email = email

    class _UserDAO:
        def __init__(self, taken: set[str]) -> None:
            self.taken = taken

        async def find_one_by_filter(self, *, email: str):
            return _User(email) if email in self.taken else None

    dao = _UserDAO({"dentrium@rsd-ai.ru"})
    allocated = await allocate_unique_account_email(dao, "dentrium@rsd-ai.ru")
    assert allocated == "dentrium1@rsd-ai.ru"


def test_ai_mop_contact_phone_constant():
    assert AI_MOP_CONTACT_PHONE == "+79179156670"


def test_build_lead_context_from_lead_for_outreach():
    class _Lead:
        org_name = "Салон"
        email = "test@example.com"
        lpr_name = None
        phone = "+7999"
        address = "Москва"
        category = "красота"
        yandex_url = None
        extra_json = None

    text = build_lead_context_from_lead(_Lead())
    assert "Салон" in text
    assert "красота" in text
    assert "нет сайта" in text.lower() or "Сайта" in text


def test_resolve_lead_contact_email_prefers_extra_contact_email():
    class _Lead:
        email = "login@rsd-ai.ru"
        extra_json = '{"contact_email":"biz@mail.ru","account_email_generated":false}'

    assert resolve_lead_contact_email(_Lead()) == "biz@mail.ru"


def test_resolve_lead_contact_email_skips_generated_login_only():
    class _Lead:
        email = "dentrium@rsd-ai.ru"
        extra_json = '{"account_email_generated":true}'

    assert resolve_lead_contact_email(_Lead()) is None


def test_resolve_lead_contact_email_uses_lead_email_when_not_generated():
    class _Lead:
        email = "biz@yandex.ru"
        extra_json = '{"account_email_generated":false}'

    assert resolve_lead_contact_email(_Lead()) == "biz@yandex.ru"


def test_resolve_lead_contact_email_prefers_personal_over_custom():
    class _Lead:
        email = "login@company-site.ru"
        extra_json = (
            '{"contact_email":"info@company-site.ru, boss@mail.ru", "account_email_generated":false}'
        )

    assert resolve_lead_contact_email(_Lead()) == "boss@mail.ru"


def test_resolve_lead_contact_email_skips_custom_domains_only():
    class _Lead:
        email = "info@company-site.ru"
        extra_json = '{"account_email_generated":false}'

    assert resolve_lead_contact_email(_Lead()) is None


def test_build_website_generation_brief_within_limit():
    from app.services.ai_mop.llm_helpers import build_website_generation_brief

    class _Lead:
        org_name = "Очень длинное название компании " * 20
        category = "Услуги " * 30
        address = "Адрес " * 50
        telegram = "https://t.me/test"
        whatsapp = "https://wa.me/79001234567"
        extra_json = (
            '{"region":"Регион","city":"Город","working_hours":"09-18",'
            '"vk":"https://vk.com/test","youtube":"https://youtube.com/@test"}'
        )

    brief = build_website_generation_brief(lead=_Lead(), business_description="x" * 5000)
    assert len(brief) <= 5000
    assert "ВКонтакте" in brief or "vk.com" in brief


def test_build_lead_context_from_lead_includes_rubric():
    from app.services.ai_mop.llm_helpers import build_lead_context_from_lead

    class _Lead:
        org_name = "Коттеджи у озера"
        email = "test@example.com"
        lpr_name = None
        phone = "+7999"
        address = "Ростовская обл., пос. Овощной"
        category = "Аренда коттеджей — загородный отдых"
        yandex_url = None
        extra_json = '{"region":"Ростовская область","city":"Овощной","working_hours":"08:00-20:00"}'

    text = build_lead_context_from_lead(_Lead())
    assert "Коттеджи" in text
    assert "Аренда коттеджей" in text
    assert "Ростовская область" in text


def test_contact_match_keys_whatsapp():
    from app.services.ai_mop.lead_lookup import contact_match_keys

    keys = contact_match_keys("79991234567@s.whatsapp.net")
    assert "79991234567" in keys


def test_ai_mop_stagger_uses_sales_scheduling_constants():
    assert EXCEL_STAGGER_MIN_MINUTES == 3.0
    assert EXCEL_STAGGER_MAX_MINUTES == 7.0


def test_is_llm_balance_error_detects_402():
    from app.services.ai_mop.lead_recovery import is_llm_balance_error

    assert is_llm_balance_error("Error code: 402 - Insufficient Balance")
    assert is_llm_balance_error("insufficient balance on api")
    assert not is_llm_balance_error("timeout while generating website")


def test_ai_mop_max_provisioned_backlog_default():
    from app.config import settings

    assert settings.AI_MOP_MAX_PROVISIONED_BACKLOG == 10


@pytest.mark.asyncio
async def test_ai_mop_worker_blocks_send_when_outreach_queue_full(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.services.ai_mop.worker import AiMopWorker

    worker = AiMopWorker()
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[10])  # outreach_queued count

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.services.ai_mop.worker.async_session_maker",
        lambda: _Ctx(),
    )
    monkeypatch.setattr(
        "app.services.ai_mop.worker.is_ai_mop_pipeline_paused",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.ai_mop.worker.ai_mop_first_message_allowed_now",
        lambda: True,
    )

    assert await worker._try_send_ready_lead() is False
    session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_ai_mop_worker_blocks_provision_when_ready_backlog_full(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.services.ai_mop.worker import AiMopWorker

    worker = AiMopWorker()
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[10])  # provisioned + outreach_queued

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        "app.services.ai_mop.worker.async_session_maker",
        lambda: _Ctx(),
    )

    assert await worker._try_provision_next_lead() is False


@pytest.mark.asyncio
async def test_ai_mop_worker_provisions_outside_send_window(monkeypatch):
    from unittest.mock import AsyncMock

    from app.services.ai_mop.worker import AiMopWorker

    worker = AiMopWorker()
    send_mock = AsyncMock(return_value=False)
    provision_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(worker, "_try_send_ready_lead", send_mock)
    monkeypatch.setattr(worker, "_try_provision_next_lead", provision_mock)
    monkeypatch.setattr(
        "app.services.ai_mop.worker.is_ai_mop_pipeline_paused",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.ai_mop.worker.ai_mop_first_message_allowed_now",
        lambda: False,
    )

    assert await worker.process_once() is True
    send_mock.assert_not_called()
    provision_mock.assert_called_once()



def test_ai_mop_send_cooldown_only_after_outreach():
    """Антиспам привязан к cooldown_until агента, не к времени провижининга."""
    from datetime import timedelta

    from app.services.ai_mop.worker import _next_send_cooldown_until, _utc_now

    until = _next_send_cooldown_until()
    now = _utc_now()
    assert until > now
    assert until <= now + timedelta(minutes=7, seconds=5)


@pytest.mark.asyncio
async def test_ai_mop_worker_tries_send_before_provision(monkeypatch):
    from unittest.mock import AsyncMock

    from app.services.ai_mop.worker import AiMopWorker

    worker = AiMopWorker()
    send_mock = AsyncMock(return_value=True)
    provision_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(worker, "_try_send_ready_lead", send_mock)
    monkeypatch.setattr(worker, "_try_provision_next_lead", provision_mock)
    monkeypatch.setattr(
        "app.services.ai_mop.worker.is_ai_mop_pipeline_paused",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.ai_mop.worker.ai_mop_first_message_allowed_now",
        lambda: True,
    )

    assert await worker.process_once() is True
    send_mock.assert_called_once()
    provision_mock.assert_not_called()


@pytest.mark.asyncio
async def test_ai_mop_worker_idle_outside_send_window_when_nothing_to_provision(monkeypatch):
    from unittest.mock import AsyncMock

    from app.services.ai_mop.worker import AiMopWorker

    worker = AiMopWorker()
    monkeypatch.setattr(worker, "_try_provision_next_lead", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "app.services.ai_mop.worker.is_ai_mop_pipeline_paused",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.ai_mop.worker.ai_mop_first_message_allowed_now",
        lambda: False,
    )

    assert await worker.process_once() is False


def test_ai_mop_send_window_moscow_hours():
    from datetime import datetime, timezone

    from app.services.ai_mop.send_window import (
        ai_mop_first_message_allowed_now,
        next_ai_mop_first_message_at,
    )

    # 10:00 MSK = 07:00 UTC
    inside = datetime(2026, 5, 11, 7, 0, tzinfo=timezone.utc)
    assert ai_mop_first_message_allowed_now(now=inside) is True
    assert next_ai_mop_first_message_at(now=inside) == inside.replace(tzinfo=None)

    # 21:00 MSK = 18:00 UTC
    outside = datetime(2026, 5, 11, 18, 0, tzinfo=timezone.utc)
    assert ai_mop_first_message_allowed_now(now=outside) is False
    assert next_ai_mop_first_message_at(now=outside) == datetime(2026, 5, 12, 5, 0)

    # 07:00 MSK = 04:00 UTC -> same day 08:00 MSK = 05:00 UTC
    early = datetime(2026, 5, 11, 4, 0, tzinfo=timezone.utc)
    assert ai_mop_first_message_allowed_now(now=early) is False
    assert next_ai_mop_first_message_at(now=early) == datetime(2026, 5, 11, 5, 0)


def test_ai_mop_follow_up_delays_match_sales_manager():
    from datetime import timedelta

    from app.services.sales.outreach_scheduling import FOLLOW_UP_DELAYS

    assert FOLLOW_UP_DELAYS["day"] == timedelta(days=1)
    assert FOLLOW_UP_DELAYS["week"] == timedelta(days=7)
    assert FOLLOW_UP_DELAYS["month"] == timedelta(days=30)


@pytest.mark.asyncio
async def test_template_runtime_ai_mop_discards_unknown_contact(monkeypatch):
    from app.services.ai_mop import runtime as ai_mop_runtime
    from app.services.template_runtime import TemplateRuntimeService

    async def _no_lead(**_kwargs):
        return None

    monkeypatch.setattr(ai_mop_runtime, "find_lead_for_contact", _no_lead)

    runtime = TemplateRuntimeService()
    result = await runtime._execute_sales_manager(
        prompt="sales",
        user_message="привет",
        knowledge_scope_id=1,
        template_config={"custom_runtime": "ai_mop"},
        source_channel="telegram_userbot",
        user_external_id="123",
        agent_id=1,
    )
    assert result.discard_message is True
    assert result.answer in ("", None)


@pytest.mark.asyncio
async def test_template_runtime_ai_mop_pool_only_blocks_unknown_private(monkeypatch):
    from unittest.mock import AsyncMock

    from app.services.ai_mop import runtime as ai_mop_runtime
    from app.services.template_runtime import TemplateRuntimeService

    monkeypatch.setattr(
        "app.services.sales.contact_pool.is_user_in_agent_contact_pool",
        AsyncMock(return_value=False),
    )
    find_mock = AsyncMock(side_effect=AssertionError("find_lead should not run"))
    monkeypatch.setattr(ai_mop_runtime, "find_lead_for_contact", find_mock)

    runtime = TemplateRuntimeService()
    result = await runtime._execute_sales_manager(
        prompt="sales",
        user_message="привет",
        knowledge_scope_id=1,
        template_config={"custom_runtime": "ai_mop", "contacts_pool_only": True},
        source_channel="whatsapp_userbot",
        user_external_id="79991234567",
        agent_id=1,
        runtime_context={"is_private_chat": True, "lead_initiated_private_dialog": True},
    )
    assert result.discard_message is True
    assert result.tool_events[0]["tool_status"] == "contact_not_in_pool"
    assert find_mock.await_count == 0


@pytest.mark.asyncio
async def test_resolve_all_lead_messenger_channels_includes_max(monkeypatch):
    from types import SimpleNamespace

    from app.services.ai_mop import contact_discovery as discovery_mod

    async def _avail(agent_id: int):
        del agent_id
        return discovery_mod.AgentMessengerAvailability(
            whatsapp=False,
            telegram=False,
            max_userbot=True,
        )

    async def _crm(org_name: str, *, limit: int = 5):
        del org_name, limit
        return []

    async def _imp(agent_id: int, org_name: str, *, limit: int = 10):
        del agent_id, org_name, limit
        return []

    monkeypatch.setattr(discovery_mod, "get_agent_messenger_availability", _avail)
    monkeypatch.setattr(discovery_mod, "_fetch_crm_rows_for_org", _crm)
    monkeypatch.setattr(discovery_mod, "_fetch_agent_imported_rows", _imp)

    from app.services.ai_mop.outreach import resolve_all_lead_messenger_channels

    lead = SimpleNamespace(
        id=1,
        org_name="ООО Тест",
        lpr_name=None,
        phone="+79991234567",
        telegram=None,
        whatsapp=None,
        extra_json='{"messenger_max": "+79998887766"}',
    )
    channels = await resolve_all_lead_messenger_channels(agent_id=42, lead=lead)
    pairs = {(c, t) for c, t, _ in channels}
    assert ("max_userbot", "+79998887766") in pairs
    assert all(c == "max_userbot" for c, _, _ in channels)
