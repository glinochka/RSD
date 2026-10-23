"""Author prompts must demand a news peg and a human voice."""
from types import SimpleNamespace

from app.services.custom.content_factory_pipeline import _authoring_prompt, _creative_system
from app.services.custom.creative_voice import tone_line
from app.services.custom.neuroblog_service import draft_instructions


def test_neuroblog_prompt_hangs_on_news_and_allows_a_human_voice():
    text = draft_instructions({"themes": ["reflection"], "product_name": "разбор авто", "posts": []})
    assert "новост" in text.lower() or "повод" in text.lower()
    assert "Мат можно" in text
    assert "сатир" in text.lower()
    assert "image_prompt" in text


def test_factory_prompt_asks_for_a_satirical_swap():
    video = SimpleNamespace(
        content_format="storytelling",
        visual_style="realism",
        aspect_ratio="9:16",
        duration_seconds=30,
        extra={"media_kind": "carousel"},
    )
    settings = SimpleNamespace(
        product_name="обзоры машин",
        product_description="канал про бюджетные авто",
        audience="водители",
        niche="авто",
        language="ru",
        tone="satire",
        brand_voice="",
        forbidden_topics="",
    )
    system = _creative_system(True)
    prompt = _authoring_prompt(settings, video, [])
    assert "новост" in system.lower()
    assert "летает" in system or "подмени" in system.lower() or "нелеп" in system.lower()
    assert "нелепый объект" in prompt
    assert tone_line("satire").startswith("Одна злая")
    assert "ровно 5" in prompt
