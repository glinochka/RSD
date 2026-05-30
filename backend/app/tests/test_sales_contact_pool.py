"""Тесты пула контактов sales_manager."""

import json

from app.alembic.models import AgentSalesContact, AgentSalesImportedContact
from app.services.sales.contact_pool import (
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

