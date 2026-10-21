"""Neuroblog: personal channel, no bio link, own LLM keys."""
import json
from datetime import datetime
from pathlib import Path

from app.services.custom.neuroblog_service import (
    bio_mentions_channel,
    default_neuroblog_settings,
    due_slot,
    image_needed,
    infer_image_provider,
    infer_text_provider,
    neuroblog_issues,
    normalize_neuroblog_settings,
    parse_post_draft,
    plan_day_slots,
    public_neuroblog_settings,
    strip_channel_from_bio,
)


def test_diary_post_has_no_picture_case_does():
    assert image_needed("blog", True) is False
    assert image_needed("reflection", True) is False
    assert image_needed("expert", True) is False
    assert image_needed("case", True) is True
    assert image_needed("infographic", False) is False


def test_draft_drops_image_for_a_diary_theme():
    draft = parse_post_draft(
        '{"theme":"blog","text":"Просто мысль про отчёт.","needs_image":true,"image_prompt":"chart"}'
    )
    assert draft["theme"] == "blog"
    assert draft["needs_image"] is False
    assert draft["image_prompt"] == ""
    case = parse_post_draft(
        '{"theme":"case","text":"Было 12, стало 40.","needs_image":true,"image_prompt":"bar chart"}'
    )
    assert case["needs_image"] is True
    assert "bar chart" in case["image_prompt"]


def test_slots_are_sorted_and_due_only_after_their_time():
    slots = plan_day_slots(day_key="2026-10-21", count=3, start_hour=8, end_hour=20, seed=7)
    assert len(slots) == 3
    assert slots == sorted(slots)
    assert due_slot(slots, 0, now=datetime(2026, 10, 21, 3, 0)) is False
    assert due_slot(slots, 0, now=datetime(2026, 10, 21, 20, 0)) is True
    assert due_slot(slots, 3, now=datetime(2026, 10, 21, 20, 0)) is False


def test_legacy_deepseek_model_keeps_provider():
    cfg = normalize_neuroblog_settings({"text_model": "deepseek-chat"}, previous={})
    assert cfg["text_provider"] == "deepseek"
    assert cfg["text_model"] == "deepseek-flash"
    assert infer_text_provider("gpt-4o-mini") == "chatgpt"
    assert infer_text_provider("claude-sonnet-5-5") == "claude"
    assert infer_image_provider("dall-e-3", None) == "chatgpt"
    assert infer_image_provider("", "") == ""


def test_saved_old_models_map_to_current_catalog():
    cfg = normalize_neuroblog_settings(
        {"text_provider": "chatgpt", "text_model": "gpt-4o-mini", "image_provider": "chatgpt", "image_model": "dall-e-3"},
        previous={},
    )
    assert cfg["text_model"] == "gpt-6-luna"
    assert cfg["image_model"] == "gpt-image-2.5-flare"


def test_api_key_is_encrypted_and_hidden():
    cfg = normalize_neuroblog_settings(
        {"text_api_key": "sk-secret-1234", "text_provider": "chatgpt", "text_model": "gpt-4o-mini"},
        previous=default_neuroblog_settings(),
    )
    dumped = json.dumps(cfg)
    assert "sk-secret-1234" not in dumped
    assert cfg["text_api_key_enc"]
    assert "text_api_key" not in cfg
    public = public_neuroblog_settings(cfg)
    assert "text_api_key_enc" not in public
    assert public["text_api_key_set"] is True
    assert "sk-secret" not in json.dumps(public)
    assert public["text_api_key_hint"].endswith("1234")


def test_empty_key_keeps_previous_secret():
    first = normalize_neuroblog_settings(
        {"text_api_key": "sk-keep-me-9999", "text_provider": "chatgpt"},
        previous=default_neuroblog_settings(),
    )
    second = normalize_neuroblog_settings(
        {"text_api_key": "", "text_provider": "chatgpt", "account_ids": [1]},
        previous=first,
    )
    assert second["text_api_key_enc"] == first["text_api_key_enc"]
    assert second["account_ids"] == [1]


def test_bio_never_keeps_our_channel_link():
    stored = {"username": "notes12", "link": "https://t.me/notes12"}
    assert bio_mentions_channel("https://t.me/notes12", stored) is True
    assert bio_mentions_channel("t.me/notes12", stored) is True
    assert bio_mentions_channel("просто про работу", stored) is False
    assert bio_mentions_channel("https://t.me/other", stored) is False
    assert strip_channel_from_bio("https://t.me/notes12", stored) == ""
    assert strip_channel_from_bio("пишу тут https://t.me/notes12 вечером", stored) == "пишу тут вечером"


def test_service_attaches_personal_channel_and_never_sets_bio_link():
    source = Path(__file__).resolve().parents[1] / "services" / "custom" / "neuroblog_service.py"
    text = source.read_text(encoding="utf-8")
    assert "UpdatePersonalChannelRequest" in text
    assert "set_bio(link)" not in text
    assert "client.set_bio(cleaned)" in text


def test_issues_require_accounts_and_own_key_for_claude():
    cfg = default_neuroblog_settings()
    cfg["text_provider"] = "claude"
    cfg["text_model"] = "claude-sonnet-4-5"
    cfg["account_ids"] = []
    problems = neuroblog_issues(cfg)
    assert any("аккаунт" in item.lower() for item in problems)
    assert any("ключ" in item.lower() for item in problems)
    cfg["account_ids"] = [7]
    cfg = normalize_neuroblog_settings({"text_api_key": "sk-ant-test", "text_provider": "claude", "account_ids": [7]}, previous=cfg)
    assert neuroblog_issues(cfg) == []
