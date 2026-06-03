import pytest
from sqlalchemy import select

from app.alembic.models import ApplicationErrorLog
from app.services.error_log_service import record_error_log
from app.utils.JWT import create_access_token


@pytest.mark.asyncio
async def test_admin_logs_requires_admin(client):
    response = await client.get("/api/admin/logs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_logs_lists_items(client, test_session, test_user):
    marker = "APP_ERR_LOG_UNIQUE_MARKER_XYZ"
    async with test_session.begin():
        test_session.add(
            ApplicationErrorLog(
                level="error",
                source="api",
                scenario=f"POST /api/test-endpoint — {marker}",
                error_type="RuntimeError",
                message=f"Something failed — {marker}",
                traceback="Traceback (most recent call last):\n  RuntimeError: test",
                context_json={"method": "POST", "path": "/api/test-endpoint"},
                user_id=test_user.id,
                status_code=500,
            )
        )

    admin_token = create_access_token({"admin_web": True}, token_kind="admin")
    client.headers["Authorization"] = f"Bearer {admin_token}"

    response = await client.get(f"/api/admin/logs?page=1&page_size=10&search={marker}")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 1
    first = data["items"][0]
    assert marker in first["message"]
    assert first["scenario"].startswith("POST")
    assert first["user"]["id"] == test_user.id
    assert first["is_resolved"] is False


@pytest.mark.asyncio
async def test_admin_logs_resolve(client, test_session):
    async with test_session.begin():
        row = ApplicationErrorLog(
            level="error",
            source="cron",
            scenario="subscription maintenance cron",
            message="cron failed",
        )
        test_session.add(row)
        await test_session.flush()
        log_id = row.id

    admin_token = create_access_token({"admin_web": True}, token_kind="admin")
    client.headers["Authorization"] = f"Bearer {admin_token}"

    response = await client.patch(f"/api/admin/logs/{log_id}/resolve")
    assert response.status_code == 200

    async with test_session.begin():
        updated = await test_session.scalar(select(ApplicationErrorLog).where(ApplicationErrorLog.id == log_id))
    assert updated is not None
    assert updated.is_resolved is True
    assert updated.resolved_at is not None


@pytest.mark.asyncio
async def test_record_error_log_persists(test_session):
    exc = RuntimeError("unit test failure")
    await record_error_log(
        exc=exc,
        source="service",
        scenario="test scenario",
        level="error",
        status_code=500,
        context={"step": "unit-test"},
    )

    async with test_session.begin():
        row = await test_session.scalar(
            select(ApplicationErrorLog).where(ApplicationErrorLog.scenario == "test scenario")
        )
    assert row is not None
    assert row.message == "unit test failure"
    assert row.error_type == "RuntimeError"
    assert row.context_json == {"step": "unit-test"}
