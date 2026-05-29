from app.services.sales.trigger_words import (
    normalize_sales_trigger_words,
    parse_llm_trigger_words_response,
)


def test_normalize_strips_json_fence_and_quotes() -> None:
    raw = '```json\n["цена", "стоимость", "сколько"]\n```'
    assert normalize_sales_trigger_words(parse_llm_trigger_words_response(raw)) == [
        "цена",
        "стоимость",
        "сколько",
    ]


def test_normalize_dirty_list_items() -> None:
    dirty = ['json [ "цена"', '"стоимость"', "сколько", "купить"]
    assert normalize_sales_trigger_words(dirty) == [
        "цена",
        "стоимость",
        "сколько",
        "купить",
    ]


def test_normalize_json_string_field() -> None:
    assert normalize_sales_trigger_words('["демо", "заявка"]') == ["демо", "заявка"]
