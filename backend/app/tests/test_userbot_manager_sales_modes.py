from app.channels.userbot_manager import (
    _is_message_matching_triggers,
    _should_process_sales_manager_public_event,
)


def test_sales_modes_group_listening_for_lead_generation() -> None:
    should_group, should_channel = _should_process_sales_manager_public_event(
        is_group_message=True,
        is_channel_message=False,
        lead_generation_enabled=True,
        neuro_commenting_enabled=False,
        live_chat_simulation_enabled=False,
    )
    assert should_group is True
    assert should_channel is False


def test_sales_modes_channel_listening_for_neuro_commenting() -> None:
    should_group, should_channel = _should_process_sales_manager_public_event(
        is_group_message=False,
        is_channel_message=True,
        lead_generation_enabled=False,
        neuro_commenting_enabled=True,
        live_chat_simulation_enabled=False,
    )
    assert should_group is False
    assert should_channel is True


def test_sales_modes_group_listening_for_live_chat_simulation() -> None:
    should_group, should_channel = _should_process_sales_manager_public_event(
        is_group_message=True,
        is_channel_message=False,
        lead_generation_enabled=False,
        neuro_commenting_enabled=False,
        live_chat_simulation_enabled=True,
    )
    assert should_group is True
    assert should_channel is False


def test_sales_modes_neuro_only_ignores_groups() -> None:
    should_group, should_channel = _should_process_sales_manager_public_event(
        is_group_message=True,
        is_channel_message=False,
        lead_generation_enabled=False,
        neuro_commenting_enabled=True,
        live_chat_simulation_enabled=False,
    )
    assert should_group is False
    assert should_channel is False


def test_sales_modes_non_neuro_ignores_channels() -> None:
    should_group, should_channel = _should_process_sales_manager_public_event(
        is_group_message=False,
        is_channel_message=True,
        lead_generation_enabled=True,
        neuro_commenting_enabled=False,
        live_chat_simulation_enabled=False,
    )
    assert should_group is False
    assert should_channel is False


def test_trigger_matching_non_strict_stem_like_behavior() -> None:
    assert _is_message_matching_triggers("Думаю купить курс", ["купи"]) is True
    assert _is_message_matching_triggers("Можно купить сегодня?", ["купить"]) is True
    assert _is_message_matching_triggers("Интерес к покупке есть", ["куп"]) is True


def test_trigger_matching_fallback_for_existing_agents() -> None:
    assert _is_message_matching_triggers("Хочу купить товар", []) is True
    assert _is_message_matching_triggers("Просто болтаем", []) is False


def test_trigger_matching_ignores_short_stopword_tokens() -> None:
    triggers = ["купить", "ии автоматизация бизнес"]
    assert _is_message_matching_triggers("Перенсти парты и стулья в подсобку 5500р", triggers) is False
    assert (
        _is_message_matching_triggers(
            "Если хочешь расти, нужна честная критика, а не поглаживание))",
            triggers,
        )
        is False
    )
    assert (
        _is_message_matching_triggers(
            "Всем привет , ищу компании в Европе , Дубае , Турции , Индонезии "
            "с подключенной системой платежей western union",
            triggers,
        )
        is False
    )
    assert (
        _is_message_matching_triggers(
            "Оскар, с днём рождения! Процветания во всём! Вы - мой Герой!",
            triggers,
        )
        is False
    )


def test_trigger_matching_multi_word_phrase_split() -> None:
    assert _is_message_matching_triggers("Нужна автоматизация бизнес-процессов", ["ии автоматизация бизнес"]) is True
    assert _is_message_matching_triggers("Интересуюсь ИИ для склада", ["ии автоматизация бизнес"]) is True


SALES_DEFAULT_TRIGGER_WORDS = [
    "цена",
    "стоимость",
    "сколько",
    "купить",
    "заказать",
    "демо",
    "попробовать",
    "условия",
    "рассчитать",
    "предложение",
    "скидка",
    "оплата",
    "внедрить",
    "подключить",
    "тест",
    "доступ",
    "тариф",
    "пробный",
    "консультация",
    "заявка",
]


def test_trigger_matching_russian_word_forms() -> None:
    triggers = SALES_DEFAULT_TRIGGER_WORDS
    assert _is_message_matching_triggers("Хочу узнать цену", triggers) is True
    assert _is_message_matching_triggers("Сколько стоит?", triggers) is True
    assert _is_message_matching_triggers("Оставить заявку на демо", triggers) is True
    assert _is_message_matching_triggers("несколько человек в офисе", triggers) is False
    assert _is_message_matching_triggers("Просто болтаем о погоде", triggers) is False
