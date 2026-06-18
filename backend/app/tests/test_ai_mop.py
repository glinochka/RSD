"""Тесты кастомного рантайма ИИ МОП."""

from __future__ import annotations

import pytest

from app.services.ai_mop.lead_import import (
    _dedup_key,
    account_email_candidates,
    allocate_unique_account_email,
    generate_account_email_from_org,
)
from app.services.ai_mop.outreach import _ai_mop_outreach_user_message
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


def test_ai_mop_outreach_user_message_excludes_credentials():
    class _Lead:
        org_name = "Салон"
        lpr_name = None
        phone = "+7999"
        address = "Москва"
        category = "красота"

    text = _ai_mop_outreach_user_message(
        lead=_Lead(),
        website_url="https://rsd-ai.ru/w/salon",
    )
    assert "https://rsd-ai.ru/w/salon" in text
    assert "НЕ указывай логин" in text
    assert "salon@rsd-ai.ru" not in text
    assert "abc12" not in text


def test_contact_match_keys_whatsapp():
    from app.services.ai_mop.lead_lookup import contact_match_keys

    keys = contact_match_keys("79991234567@s.whatsapp.net")
    assert "79991234567" in keys


def test_ai_mop_stagger_uses_sales_scheduling_constants():
    assert EXCEL_STAGGER_MIN_MINUTES == 3.0
    assert EXCEL_STAGGER_MAX_MINUTES == 7.0


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
