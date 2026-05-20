"""Тесты обновления контактов CRM при повторном импорте Excel."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.internal_sales import (
    _apply_import_fields,
    build_contact_dedup_key,
    upsert_contact_from_import,
)


def test_apply_import_fields_skips_comment_and_status():
    row = MagicMock(
        org_name="Клиника",
        lpr_name="Иванов",
        lpr_phone="+79991234567",
        org_phone=None,
        org_mobile=None,
        import_status=None,
        email=None,
        website=None,
        whatsapp=None,
        telegram=None,
        messenger_max=None,
        extra_json=None,
        comment="Важный комментарий",
        workflow_status="closed",
        dedup_key="tel:9991234567",
    )
    now = MagicMock()
    changed = _apply_import_fields(
        row,
        data={
            "org_name": "Клиника новая",
            "lpr_name": "Петров",
            "workflow_status": "new",
            "comment": "Другой комментарий",
        },
        now=now,
    )
    assert changed is True
    assert row.org_name == "Клиника новая"
    assert row.lpr_name == "Петров"
    assert row.workflow_status == "closed"
    assert row.comment == "Важный комментарий"


@pytest.mark.asyncio
async def test_upsert_updates_existing_contact():
    session = AsyncMock()
    existing = MagicMock(
        org_name="Старое",
        lpr_name=None,
        lpr_phone="+79991112233",
        org_phone=None,
        org_mobile=None,
        import_status=None,
        email=None,
        website=None,
        whatsapp=None,
        telegram="https://t.me/old",
        messenger_max=None,
        extra_json=None,
        comment=None,
        workflow_status="in_progress",
        assignee_id=5,
        archived_at=None,
        dedup_key="tel:9991112233",
    )
    scalars_result = MagicMock()
    scalars_result.all.return_value = [existing]
    session.scalars = AsyncMock(return_value=scalars_result)

    action = await upsert_contact_from_import(
        session,
        data={
            "org_name": "Новое название",
            "lpr_phone": "+79991112233",
            "telegram": "https://t.me/new",
        },
    )
    assert action == "updated"
    assert existing.org_name == "Новое название"
    assert existing.telegram == "https://t.me/new"
    assert existing.workflow_status == "in_progress"


def test_build_contact_dedup_key_unchanged():
    assert build_contact_dedup_key(lpr_phone="+7 999 111-22-33") == "tel:9991112233"
