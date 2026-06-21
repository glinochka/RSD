"""Tests for website generation save helpers."""

from app.services.website_generation_service import (
    _build_meta_from_html,
    _build_polish_user_prompt,
    _edit_prompt_needs_clarification,
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


def test_build_polish_user_prompt_includes_html_and_context():
    prompt = _build_polish_user_prompt(
        html_content="<section>hero</section>",
        business_name="Дентриум",
        dark_mode=True,
        primary_color="#112233",
    )
    assert "Дентриум" in prompt
    assert "dark" in prompt
    assert "#112233" in prompt
    assert "<section>hero</section>" in prompt


def test_edit_prompt_needs_clarification_for_vague_short_requests():
    assert _edit_prompt_needs_clarification("сделай красивее") is True
    assert _edit_prompt_needs_clarification("поправь") is True


def test_edit_prompt_skips_clarification_for_specific_requests():
    assert (
        _edit_prompt_needs_clarification(
            "Поменяй фон hero-секции на тёмно-синий (#1e3a8a) и увеличь заголовок"
        )
        is False
    )
