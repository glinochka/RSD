import pytest
from sqlalchemy import select

from app.alembic.models import UserErrorReport
from app.utils.JWT import create_access_token


@pytest.mark.asyncio
async def test_create_error_report_requires_auth(client):
    response = await client.post(
        "/api/users/error-reports",
        json={"description": "1234567890 enough chars"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_error_report_success(client, auth_headers, test_user, test_session):
    client.headers.update(auth_headers)
    body = {"description": "  Описание бага из теста достаточно длинное  "}
    response = await client.post("/api/users/error-reports", json=body)
    assert response.status_code == 201

    async with test_session.begin():
        row = await test_session.scalar(select(UserErrorReport).where(UserErrorReport.user_id == test_user.id))
    assert row is not None
    assert row.description == body["description"].strip()


@pytest.mark.asyncio
async def test_admin_error_reports_requires_admin(client):
    response = await client.get("/api/admin/error-reports")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_error_reports_lists_items(client, test_session, test_user):
    marker = "ERR_REP_UNIQUE_MARKER_XYZ"
    async with test_session.begin():
        test_session.add(
            UserErrorReport(
                user_id=test_user.id,
                description=f"Проблема на странице агентов при сохранении — {marker}",
            )
        )

    admin_token = create_access_token({"admin_web": True}, token_kind="admin")
    client.headers["Authorization"] = f"Bearer {admin_token}"

    response = await client.get(f"/api/admin/error-reports?page=1&page_size=10&search={marker}")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 1
    first = data["items"][0]
    assert marker in first["description"]
    assert first["user"]["id"] == test_user.id
    assert first["user"]["name"] == test_user.name
