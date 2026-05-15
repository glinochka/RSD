"""Тесты чека «Мой налог» для отдела продаж."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.sales_moy_nalog_invoice import (
    SalesMoyNalogReceiptResult,
    create_contact_receipt_pdf,
    moy_nalog_configured,
    persist_receipt_metadata,
)


@pytest.fixture
def sales_contact():
    return SimpleNamespace(
        id=42,
        org_name="ООО Тест",
        lpr_name="Иван Иванов",
        lpr_phone="+79001234567",
        org_phone=None,
        org_mobile=None,
        email="test@example.com",
        extra_json=None,
    )


def test_moy_nalog_configured_requires_credentials(monkeypatch):
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_INN", "")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_PASSWORD", "")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_REFRESH_TOKEN", "")
    assert moy_nalog_configured() is False

    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_INN", "123456789012")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_PASSWORD", "secret")
    assert moy_nalog_configured() is True

    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_PASSWORD", "")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_REFRESH_TOKEN", "rt-abc")
    assert moy_nalog_configured() is True


def test_authenticate_by_refresh_token_without_password(sales_contact, monkeypatch):
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_REFRESH_TOKEN", "rt-test")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_INN", "123456789012")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_PASSWORD", "")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_ACCESS_TOKEN", "")

    mock_api = MagicMock()
    mock_api.__enter__.return_value = mock_api
    mock_api.is_authenticated = False
    mock_api.is_token_expired = True
    mock_api.refresh_access_token.return_value = True
    mock_api.create_receipt.return_value = SimpleNamespace(
        uuid="u1", print_url="https://x", total_amount=Decimal("1"),
    )
    mock_api.download_receipt_raw.return_value = b"\x89PNG\r\n\x1a\n" + b"x" * 8

    with patch("app.services.sales_moy_nalog_invoice.MoyNalogClientSync", return_value=mock_api):
        with patch("app.services.sales_moy_nalog_invoice._png_to_pdf", return_value=b"%PDF"):
            create_contact_receipt_pdf(sales_contact, amount_rub=Decimal("100"))

    mock_api.set_tokens.assert_called_once()
    mock_api.refresh_access_token.assert_called_once()
    mock_api.auth_by_password.assert_not_called()


def test_create_contact_receipt_pdf_converts_png_to_pdf(sales_contact, monkeypatch):
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_INN", "123456789012")
    monkeypatch.setattr("app.services.sales_moy_nalog_invoice.settings.MOY_NALOG_PASSWORD", "secret")

    fake_receipt = SimpleNamespace(
        uuid="abc-def-123",
        print_url="https://lknpd.nalog.ru/print/abc",
        total_amount=Decimal("5000.00"),
    )
    mock_api = MagicMock()
    mock_api.__enter__.return_value = mock_api
    mock_api.is_authenticated = True
    mock_api.create_receipt.return_value = fake_receipt
    mock_api.download_receipt_raw.return_value = b"\x89PNG\r\n\x1a\n" + b"x" * 64

    with patch("app.services.sales_moy_nalog_invoice.MoyNalogClientSync", return_value=mock_api):
        with patch("app.services.sales_moy_nalog_invoice._png_to_pdf", return_value=b"%PDF-1.4 fake"):
            result = create_contact_receipt_pdf(
                sales_contact,
                amount_rub=Decimal("5000"),
                service_name="Консультация",
            )

    assert result.pdf_bytes.startswith(b"%PDF")
    assert result.receipt_uuid == "abc-def-123"
    mock_api.create_receipt.assert_called_once()


def test_persist_receipt_metadata_updates_extra_json(sales_contact):
    sales_contact.extra_json = None
    result = SalesMoyNalogReceiptResult(
        pdf_bytes=b"pdf",
        receipt_uuid="uuid-1",
        print_url="https://example.com",
        total_amount=Decimal("100"),
        service_name="Услуга",
    )
    persist_receipt_metadata(sales_contact, result)
    assert "last_moy_nalog_receipt" in sales_contact.extra_json
    assert "uuid-1" in sales_contact.extra_json

