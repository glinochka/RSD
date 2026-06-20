import pytest

from app.services.tool_confirmation import user_has_confirmed_action


def test_explicit_confirmation_always_accepted() -> None:
    assert user_has_confirmed_action("подтверждаю") is True
    assert user_has_confirmed_action("Confirm please") is True


def test_short_affirmative_without_context_is_not_enough() -> None:
    assert user_has_confirmed_action("да") is False
    assert user_has_confirmed_action("верно") is False


def test_short_affirmative_after_bot_question_counts() -> None:
    history = [
        {"role": "user", "content": "Запишите на завтра в 15:00"},
        {"role": "assistant", "content": "Записать вас на завтра в 15:00 к Анне — верно?"},
    ]
    assert user_has_confirmed_action("да", recent_history=history) is True
    assert user_has_confirmed_action("верно", recent_history=history) is True
    assert user_has_confirmed_action("подходит", recent_history=history) is True
