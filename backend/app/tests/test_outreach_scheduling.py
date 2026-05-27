from datetime import timedelta

from app.services.sales.outreach_scheduling import (
    EXCEL_STAGGER_MAX_MINUTES,
    EXCEL_STAGGER_MIN_MINUTES,
    FOLLOW_UP_DELAYS,
    next_stagger_delay_minutes,
    schedule_after_stagger,
    utc_now_naive,
)


def test_stagger_delay_in_range() -> None:
    for _ in range(20):
        delay = next_stagger_delay_minutes()
        assert EXCEL_STAGGER_MIN_MINUTES <= delay <= EXCEL_STAGGER_MAX_MINUTES


def test_schedule_after_stagger_in_future() -> None:
    now = utc_now_naive()
    scheduled = schedule_after_stagger(cumulative_minutes=17.5)
    assert scheduled >= now + timedelta(minutes=17)


def test_follow_up_delays() -> None:
    assert FOLLOW_UP_DELAYS["day"].days == 1
    assert FOLLOW_UP_DELAYS["week"].days == 7
    assert FOLLOW_UP_DELAYS["month"].days == 30
