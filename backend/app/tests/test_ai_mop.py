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


def test_ai_mop_outreach_user_message_includes_demo_credentials():
    class _Lead:
        org_name = "Салон"
        lpr_name = None
        phone = "+7999"
        address = "Москва"
        category = "красота"

    text = _ai_mop_outreach_user_message(
        lead=_Lead(),
        website_url="https://rsd-ai.ru/w/salon",
        login_email="salon@rsd-ai.ru",
        temp_password="abc12",
    )
    assert "https://rsd-ai.ru/w/salon" in text
    assert "salon@rsd-ai.ru" in text
    assert "abc12" in text


def test_ai_mop_stagger_uses_sales_scheduling_constants():
    assert EXCEL_STAGGER_MIN_MINUTES == 3.0
    assert EXCEL_STAGGER_MAX_MINUTES == 7.0


@pytest.mark.asyncio
async def test_template_runtime_skips_ai_mop_custom_runtime():
    from app.services.template_runtime import TemplateRuntimeService

    runtime = TemplateRuntimeService()
    result = await runtime._execute_sales_manager(
        prompt="sales",
        user_message="привет",
        knowledge_scope_id=1,
        template_config={"custom_runtime": "ai_mop"},
        source_channel="telegram",
        user_external_id="123",
        agent_id=1,
    )
    assert result.discard_message is True
    assert result.answer is None
