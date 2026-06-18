"""Тесты пула контактов sales_manager."""

import json
from unittest.mock import AsyncMock

import pytest

from app.alembic.models import AgentSalesContact, AgentSalesImportedContact
from app.services.sales.contact_pool import (
    apply_contact_pool_guard,
    contact_row_in_pool,
    external_id_lookup_variants,
)


def test_external_id_lookup_variants_phone():
    variants = external_id_lookup_variants("+79001234567")
    assert "79001234567" in variants
    assert "+79001234567" in variants


def test_external_id_lookup_variants_whatsapp_jid_matches_excel_digits():
    variants = external_id_lookup_variants("79001234567@s.whatsapp.net")
    assert "79001234567" in variants
    assert "79001234567@s.whatsapp.net" in variants


def test_contact_row_in_pool_by_metadata():
    row = AgentSalesContact(
        agent_id=1,
        user_external_id="1",
        source_chat_id="global",
        state="DISCOVERED",
        metadata_json=json.dumps({"in_contact_pool": True}),
    )
    assert contact_row_in_pool(row) is True


def test_contact_row_in_pool_discovered_global_without_flag():
    row = AgentSalesContact(
        agent_id=1,
        user_external_id="1",
        source_chat_id="global",
        state="DISCOVERED",
        metadata_json=None,
    )
    assert contact_row_in_pool(row) is False


def test_contact_row_in_pool_group_source():
    row = AgentSalesContact(
        agent_id=1,
        user_external_id="1",
        source_chat_id="-100123",
        state="DISCOVERED",
        metadata_json=None,
    )
    assert contact_row_in_pool(row) is True


def test_user_in_pool_via_excel_import_unit():
    row = AgentSalesImportedContact(
        agent_id=5,
        import_batch_id="b1",
        org_name="ООО Тест",
        channel="telegram_userbot",
        target_external_id="12345",
        dedup_key="tg:12345:ooo test",
        outreach_status="pending",
    )
    assert row.target_external_id == "12345"
    assert "12345" in external_id_lookup_variants("12345")


@pytest.mark.asyncio
async def test_apply_contact_pool_guard_blocks_group_chat():
    result = await apply_contact_pool_guard(
        agent_id=1,
        user_external_id="123",
        template_config={"contacts_pool_only": True},
        runtime_context={"is_group_chat": True, "is_private_chat": False},
        source_channel="telegram_userbot",
    )
    assert result is not None
    assert result["tool_status"] == "public_chat_blocked"


@pytest.mark.asyncio
async def test_apply_contact_pool_guard_blocks_unknown_private(monkeypatch):
    monkeypatch.setattr(
        "app.services.sales.contact_pool.is_user_in_agent_contact_pool",
        AsyncMock(return_value=False),
    )
    result = await apply_contact_pool_guard(
        agent_id=1,
        user_external_id="999",
        template_config={"contacts_pool_only": True},
        runtime_context={"is_private_chat": True},
        source_channel="whatsapp_userbot",
    )
    assert result is not None
    assert result["tool_status"] == "contact_not_in_pool"


@pytest.mark.asyncio
async def test_apply_contact_pool_guard_disabled():
    result = await apply_contact_pool_guard(
        agent_id=1,
        user_external_id="999",
        template_config={"contacts_pool_only": False},
        runtime_context={"is_group_chat": True},
        source_channel="telegram_userbot",
    )
    assert result is None

