"""Tests for website generation save helpers."""

from app.services.website_generation_service import (
    _build_meta_from_html,
    _normalize_website_meta,
    _prepare_html_for_db_storage,
)


def test_normalize_website_meta_clamps_og_description_to_300_chars():
    long_description = "a" * 500
    normalized = _normalize_website_meta(
        {"title": "Дентриум", "description": long_description}
    )

    assert len(normalized["description"]) == 500
    assert len(normalized["og_description"]) == 300
    assert normalized["og_description"] == "a" * 300


def test_normalize_website_meta_clamps_title_to_100_chars():
    normalized = _normalize_website_meta({"title": "x" * 150, "description": "ok"})

    assert len(normalized["title"]) == 100
    assert len(normalized["og_title"]) == 100


def test_build_meta_from_html_respects_column_limits():
    meta = _build_meta_from_html(
        html="<section>test</section>",
        business_name="Дентриум",
        business_description="b" * 500,
    )

    assert meta["title"] == "Дентриум"
    assert len(meta["description"]) == 500
    assert len(meta["og_description"]) == 300


def test_prepare_html_for_db_storage_strips_null_bytes():
    html = "<div>ok\x00bad</div>"
    assert _prepare_html_for_db_storage(html) == "<div>okbad</div>"
