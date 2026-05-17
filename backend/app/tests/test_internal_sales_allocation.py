"""Тесты пула CRM, дневной выдачи и архива отдела продаж."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.internal_sales import (
    apply_workflow_timestamps,
    build_contact_dedup_key,
    can_request_more_contacts,
    effective_daily_quota,
    ensure_daily_allocation,
    funnel_period_range,
    normalize_funnel_period,
    request_more_contacts,
    sales_today,
)


def test_effective_daily_quota_role_defaults():
    trainee = MagicMock(daily_contacts_quota=0, role="trainee")
    mop = MagicMock(daily_contacts_quota=0, role="mop")
    assert effective_daily_quota(trainee) == 30
    assert effective_daily_quota(mop) == 50


def test_effective_daily_quota_custom_override():
    member = MagicMock(daily_contacts_quota=17, role="trainee")
    assert effective_daily_quota(member) == 17


def test_build_contact_dedup_key_phone():
    assert build_contact_dedup_key(lpr_phone="+7 (999) 123-45-67") == "tel:9991234567"


def test_build_contact_dedup_key_org_fallback():
    assert build_contact_dedup_key(org_name="  ООО Ромашка  ") == "org:ооо ромашка"


def test_normalize_funnel_period():
    assert normalize_funnel_period("DAY") == "day"
    assert normalize_funnel_period(None, default="month") == "month"


def test_funnel_period_range_all_is_open():
    assert funnel_period_range("all") == (None, None)


def test_funnel_period_range_day_has_bounds():
    start, end = funnel_period_range("day")
    assert start is not None and end is not None
    assert start <= end


def test_apply_workflow_timestamps_does_not_archive():
    contact = MagicMock(workflow_status="new", archived_at=None, called_at=None, demo_at=None, closed_at=None)
    now = MagicMock()
    apply_workflow_timestamps(contact, "rejected", now)
    assert contact.workflow_status == "rejected"
    assert contact.archived_at is None
    assert contact.called_at is None


def test_apply_workflow_timestamps_sets_called_on_in_progress():
    contact = MagicMock(workflow_status="new", archived_at=None, called_at=None, demo_at=None, closed_at=None)
    now = MagicMock()
    apply_workflow_timestamps(contact, "in_progress", now)
    assert contact.called_at is now


def test_can_request_more_only_after_first_batch():
    member = MagicMock(role="trainee", daily_allocation_events=1)
    assert can_request_more_contacts(member, pending_new=0, pool_size=10) is True
    assert can_request_more_contacts(member, pending_new=1, pool_size=10) is False
    member.daily_allocation_events = 2
    assert can_request_more_contacts(member, pending_new=0, pool_size=10) is False


@pytest.mark.asyncio
async def test_ensure_daily_allocation_skips_if_first_event_done():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=10)
    member = MagicMock(
        id=1,
        role="trainee",
        daily_contacts_quota=0,
        last_daily_allocation_date=sales_today(),
        daily_pool_alloc_total=5,
        daily_allocation_events=1,
    )
    result = await ensure_daily_allocation(session, member)
    assert result == 0
    session.scalars.assert_not_called()


@pytest.mark.asyncio
async def test_request_more_requires_no_pending_new():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=2)
    member = MagicMock(
        id=1,
        role="mop",
        daily_contacts_quota=0,
        daily_pool_alloc_total=30,
        daily_allocation_events=1,
        last_daily_allocation_date=sales_today(),
    )
    with pytest.raises(ValueError, match="проставьте статусы"):
        await request_more_contacts(session, member)


@pytest.mark.asyncio
async def test_request_more_blocks_third_batch():
    session = AsyncMock()
    session.scalar = AsyncMock(side_effect=[0, 100])
    session.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    member = MagicMock(
        id=1,
        role="mop",
        daily_contacts_quota=0,
        daily_pool_alloc_total=60,
        daily_allocation_events=2,
        last_daily_allocation_date=sales_today(),
    )
    with pytest.raises(ValueError, match="2 выдач"):
        await request_more_contacts(session, member)
