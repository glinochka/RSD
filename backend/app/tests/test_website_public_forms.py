"""Tests for public website lead form intake."""
from __future__ import annotations

import pytest

from app.services.website_public_forms import (
    WEBSITE_UNIFIED_LEAD_FIELDS,
    map_website_form_payload,
    resolve_website_lead_fields,
)


def test_resolve_website_lead_fields_is_unified():
    fields = resolve_website_lead_fields()
    keys = [f["key"] for f in fields]
    assert keys == ["fio", "phone", "message"]
    assert fields == WEBSITE_UNIFIED_LEAD_FIELDS


def test_map_website_form_payload_aliases():
    mapped = map_website_form_payload(
        {
            "full_name": "Иван Иванов",
            "tel": "+79991234567",
            "comment": "Нужна консультация",
        }
    )
    assert mapped["fio"] == "Иван Иванов"
    assert mapped["phone"] == "+79991234567"
    assert mapped["message"] == "Нужна консультация"


def test_map_website_form_payload_legacy_name():
    mapped = map_website_form_payload({"name": "Пётр", "phone": "123"})
    assert mapped["fio"] == "Пётр"
    assert mapped["phone"] == "123"
