"""Планирование задержек между исходящими сообщениями sales_manager."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# Случайный интервал между контактами при загрузке Excel-базы (минуты).
# Снижено до 3–7 минут для более плотного, но безопасного прогрева.
EXCEL_STAGGER_MIN_MINUTES = 3.0
EXCEL_STAGGER_MAX_MINUTES = 7.0

FOLLOW_UP_DELAYS = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_stagger_delay_minutes() -> float:
    """Случайная пауза 3–7 минут до следующего контакта."""
    return random.uniform(EXCEL_STAGGER_MIN_MINUTES, EXCEL_STAGGER_MAX_MINUTES)


def schedule_after_stagger(*, cumulative_minutes: float) -> datetime:
    return utc_now_naive() + timedelta(minutes=cumulative_minutes)
