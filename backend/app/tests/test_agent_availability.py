"""Tests for agent availability schedule (timezone-aware)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.services.agent_availability import (
    agent_availability_allows_now,
    default_weekdays_for_ui,
    normalize_agent_availability_for_storage,
)


def test_default_normalize_is_always_on():
    out = normalize_agent_availability_for_storage(None)
    assert out["always_on"] is True
    assert out["timezone"] == "Europe/Moscow"


def test_scheduled_weekday_respects_timezone():
    weekdays = default_weekdays_for_ui()
    # Monday enabled 09:00–18:00 Europe/Moscow
    cfg = {
        "agent_availability": normalize_agent_availability_for_storage(
            {
                "always_on": False,
                "timezone": "Europe/Moscow",
                "weekdays": weekdays,
            }
        )
    }
    # 2026-05-11 is Monday
    monday_noon = datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc)
    assert agent_availability_allows_now(cfg, now=monday_noon) is True

    monday_morning_msk = datetime(2026, 5, 11, 5, 0, tzinfo=timezone.utc)
    assert agent_availability_allows_now(cfg, now=monday_morning_msk) is False


def test_overnight_window():
    days = [{"enabled": i == 0, "start": "22:00", "end": "06:00"} for i in range(7)]
    cfg = {
        "agent_availability": normalize_agent_availability_for_storage(
            {
                "always_on": False,
                "timezone": "Europe/Moscow",
                "weekdays": days,
            }
        )
    }
    # Monday 23:00 UTC+3 = 20:00 UTC
    dt = datetime(2026, 5, 11, 20, 0, tzinfo=timezone.utc)
    assert agent_availability_allows_now(cfg, now=dt) is True


def test_normalize_rejects_all_days_disabled():
    days = [{"enabled": False, "start": "09:00", "end": "18:00"} for _ in range(7)]
    with pytest.raises(HTTPException):
        normalize_agent_availability_for_storage(
            {"always_on": False, "timezone": "Europe/Moscow", "weekdays": days}
        )
