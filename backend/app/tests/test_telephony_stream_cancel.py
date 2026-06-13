from app.telephony.stream_cancel import (
    cancel_turn,
    cancel_turn_by_call_id,
    clear_cancel,
    clear_cancel_call_id,
    is_cancelled,
    is_cancelled_call_id,
    register_cancel,
    register_cancel_call_id,
)


def test_cancel_turn():
    register_cancel(42)
    assert cancel_turn(42) is True
    assert is_cancelled(42) is True
    clear_cancel(42)
    assert is_cancelled(42) is False


def test_cancel_turn_missing():
    assert cancel_turn(99999) is False


def test_cancel_by_call_id():
    register_cancel_call_id("call-abc")
    assert cancel_turn_by_call_id("call-abc") is True
    assert is_cancelled_call_id("call-abc") is True
    clear_cancel_call_id("call-abc")
    assert is_cancelled_call_id("call-abc") is False
