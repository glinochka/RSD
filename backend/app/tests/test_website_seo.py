"""Tests for website SEO helpers (letter favicon generation)."""
import os

import pytest

from app.services.website_seo_service import WebsiteSEOService


@pytest.fixture
def seo_service(tmp_path):
    return WebsiteSEOService(storage_path=str(tmp_path))


def test_extract_brand_letter_from_cyrillic_title():
    assert WebsiteSEOService.extract_brand_letter("Стоматология Дента") == "С"
    assert WebsiteSEOService.extract_brand_letter("  123 Cafe  ") == "1"


def test_contrast_text_color_picks_readable_pair():
    assert WebsiteSEOService.contrast_text_color("#111827") == "#FFFFFF"
    assert WebsiteSEOService.contrast_text_color("#F9FAFB") == "#111827"


def test_generate_letter_favicon_creates_ico_and_pngs(seo_service):
    result = seo_service.generate_letter_favicon(
        website_id=42,
        title="Автосервис",
        background_color="#2563EB",
    )

    assert result.success is True
    assert "favicon.ico" in result.files
    assert os.path.exists(result.files["favicon.ico"])

    favicon_url = seo_service.favicon_url_from_result(42, result)
    assert favicon_url == f"/assets/websites/42/{os.path.basename(result.files['favicon.ico'])}"


def test_generate_letter_favicon_respects_existing_upload_path_pattern(seo_service):
    result = seo_service.generate_letter_favicon(
        website_id=7,
        title="RSD",
        background_color="#10B981",
        text_color="#FFFFFF",
    )

    assert result.success is True
    for _size_name, path in result.files.items():
        assert path.startswith(str(seo_service.storage_path))
        assert os.path.getsize(path) > 0
