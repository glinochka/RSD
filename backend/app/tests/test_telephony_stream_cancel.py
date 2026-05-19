import asyncio

from app.telephony.stream_cancel import cancel_turn, clear_cancel, is_cancelled, register_cancel


def test_cancel_turn():
    register_cancel(42)
    assert cancel_turn(42) is True
    assert is_cancelled(42) is True
    clear_cancel(42)
    assert is_cancelled(42) is False


def test_cancel_turn_missing():
    assert cancel_turn(99999) is False
