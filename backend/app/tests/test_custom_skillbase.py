"""Skillbase brief, file text, and generated skill contracts."""
from app.services.custom.skillbase_prompts import ACTIVITIES, SKILLBASE_AUTHOR, SKILLBASE_EDITOR
from app.services.custom.skillbase_service import (
    author_user_prompt,
    brief_ready,
    missing_anchors,
    normalize_brief,
    parse_skill_bundle,
    parse_skill_edit,
    public_brief,
    read_text_file,
    skill_body,
)


def test_parent_prompts_keep_facts_and_placeholders():
    assert "Не выдумывай цены" in SKILLBASE_AUTHOR
    assert "{имя}" in SKILLBASE_EDITOR
    prompt = author_user_prompt(normalize_brief({"business": "Агентство SEO для интернет-магазинов"}))
    assert "{post_text}" in prompt
    assert "{chat_title}" in prompt
    assert "neuroblog" in prompt


def test_brief_drops_file_text_from_the_public_view():
    stored = normalize_brief(
        {
            "business": "Сервис доставки",
            "files": [{"name": "offer.md", "text": "Доставка за сутки по Москве. " * 5}],
        }
    )
    assert stored["knowledge"].startswith("## offer.md")
    public = public_brief(stored)
    assert public["files"] == [{"name": "offer.md", "chars": len(stored["files"][0]["text"])}]
    assert "text" not in public["files"][0]
    assert "knowledge" not in public
    assert brief_ready({"product": "Коротко"}) is False
    assert brief_ready({"product": "Сервис аналитики позиций для агентств"}) is True


def test_html_file_becomes_plain_text():
    text = read_text_file("base.html", b"<p>Kitchen&nbsp;studio for cafes and dark kitchens.</p>")
    assert "<p>" not in text
    assert "Kitchen" in text


def test_bundle_keeps_contract_and_rejects_a_dropped_placeholder():
    raw = """
    {"skills":[
      {"key":"neurocommenting","content":"Пост {post_text} в {chat_title}. Верни JSON {\\"comment\\": \\"...\\"}"},
      {"key":"shilling","setup":"Кто уже пользовался этим складом?","reply":"Отгружаю через них второй месяц, по срокам нормально."}
    ]}
    """
    bundle = parse_skill_bundle(raw)
    comment = skill_body(
        next(item for item in ACTIVITIES if item["key"] == "neurocommenting"),
        bundle["neurocommenting"],
    )
    assert missing_anchors(comment, ["{post_text}", "{chat_title}", '"comment"']) == []
    pair = skill_body(next(item for item in ACTIVITIES if item["key"] == "shilling"), bundle["shilling"])
    assert "setup" in pair and "reply" in pair
    broken = dict(bundle["neurocommenting"])
    broken["content"] = "Просто напиши комментарий."
    try:
        skill_body(next(item for item in ACTIVITIES if item["key"] == "neurocommenting"), broken)
        raised = False
    except ValueError:
        raised = True
    assert raised is True


def test_edit_payload_reads_content():
    edited = parse_skill_edit('{"content":"Новый текст {post_text}"}')
    assert edited["content"].startswith("Новый текст")
