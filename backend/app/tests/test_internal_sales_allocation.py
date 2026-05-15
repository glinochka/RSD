"""Тесты пула CRM, дневной выдачи и архива отдела продаж."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.internal_sales import (
    apply_workflow_timestamps,
    archive_if_worked,
    effective_daily_quota,
    ensure_daily_allocation,
    request_more_contacts,
    utc_today,
)


def test_effective_daily_quota_role_defaults():
    trainee = MagicMock(daily_contacts_quota=0, role="trainee")
    mop = MagicMock(daily_contacts_quota=0, role="mop")
    assert effective_daily_quota(trainee) == 30
    assert effective_daily_quota(mop) == 50


def test_effective_daily_quota_custom_override():
    member = MagicMock(daily_contacts_quota=17, role="trainee")
    assert effective_daily_quota(member) == 17


def test_archive_if_worked_on_status_change():
    contact = MagicMock(workflow_status="in_progress", archived_at=None)
    archive_if_worked(contact, previous_status="new", now=MagicMock())
    assert contact.archived_at is not None


def test_apply_workflow_timestamps_archives_from_new():
    contact = MagicMock(workflow_status="new", archived_at=None, called_at=None, demo_at=None, closed_at=None)
    now = MagicMock()
    apply_workflow_timestamps(contact, "rejected", now)
    assert contact.workflow_status == "rejected"
    assert contact.archived_at == now


@pytest.mark.asyncio
async def test_ensure_daily_allocation_skips_if_already_today():
    session = AsyncMock()
    member = MagicMock(
        id=1,
        role="trainee",
        daily_contacts_quota=0,
        last_daily_allocation_date=utc_today(),
    )
    result = await ensure_daily_allocation(session, member)
    assert result == 0
    session.scalars.assert_not_called()


@pytest.mark.asyncio
async def test_request_more_requires_no_pending_new():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=2)
    member = MagicMock(id=1, role="mop", daily_contacts_quota=0)
    with pytest.raises(ValueError, match="проставьте статусы"):
        await request_more_contacts(session, member)
