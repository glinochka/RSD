from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient


async def _create_admin_agent(client: AsyncClient, auth_headers: dict, cfg: dict | None = None) -> int:
    template_config = {
        "domain_type": "beauty_salon",
        "crm_mode": "disabled",
        "booking_backend": "local",
    }
    if isinstance(cfg, dict):
        template_config.update(cfg)
    response = await client.post(
        "/api/agents",
        headers=auth_headers,
        json={
            "system_prompt": "Admin template",
            "template_type": "crm_admin",
            "template_config": template_config,
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


@pytest.mark.asyncio
async def test_admin_template_cards_endpoints(client: AsyncClient, auth_headers):
    agent_id = await _create_admin_agent(client, auth_headers)

    staff_resp = await client.post(
        "/api/agents/admin_template/staff",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "role": "master",
            "full_name": "Anna Master",
            "specializations": ["haircut"],
        },
    )
    assert staff_resp.status_code == 201, staff_resp.text
    staff = staff_resp.json()

    staff_list = await client.get(
        "/api/agents/admin_template/staff",
        headers=auth_headers,
        params={"agent_id": agent_id},
    )
    assert staff_list.status_code == 200
    assert len(staff_list.json()["items"]) == 1

    resource_resp = await client.post(
        "/api/agents/admin_template/resources",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "resource_type": "chair",
            "title": "Chair A",
        },
    )
    assert resource_resp.status_code == 201, resource_resp.text

    service_resp = await client.post(
        "/api/agents/admin_template/services",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "target_role": "master",
            "title": "Haircut",
            "duration_minutes": 60,
            "price_minor": 1000,
            "resource_type_filters": ["chair"],
        },
    )
    assert service_resp.status_code == 201, service_resp.text

    update_staff = await client.patch(
        "/api/agents/admin_template/staff",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "staff_id": staff["id"],
            "full_name": "Anna Master Updated",
        },
    )
    assert update_staff.status_code == 200, update_staff.text
    assert update_staff.json()["full_name"] == "Anna Master Updated"


@pytest.mark.asyncio
async def test_admin_template_schedule_appointments_and_occupancy(client: AsyncClient, auth_headers):
    agent_id = await _create_admin_agent(client, auth_headers)

    staff = (
        await client.post(
            "/api/agents/admin_template/staff",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "role": "master",
                "full_name": "Olga Master",
            },
        )
    ).json()
    resource = (
        await client.post(
            "/api/agents/admin_template/resources",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "resource_type": "chair",
                "title": "Chair 1",
            },
        )
    ).json()
    service = (
        await client.post(
            "/api/agents/admin_template/services",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "target_role": "master",
                "title": "Coloring",
                "duration_minutes": 60,
                "resource_type_filters": ["chair"],
            },
        )
    ).json()

    now = datetime.utcnow().replace(microsecond=0)
    starts_at = now.isoformat()
    ends_at = (now + timedelta(hours=1)).isoformat()
    shifted_start = (now + timedelta(hours=1)).isoformat()
    shifted_end = (now + timedelta(hours=2)).isoformat()

    slot_resp = await client.post(
        "/api/agents/admin_template/schedule",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "staff_id": staff["id"],
            "resource_id": resource["id"],
        },
    )
    assert slot_resp.status_code == 201, slot_resp.text

    available_resp = await client.get(
        "/api/agents/admin_template/schedule/available",
        headers=auth_headers,
        params={
            "agent_id": agent_id,
            "starts_at": starts_at,
            "ends_at": (now + timedelta(hours=3)).isoformat(),
            "service_id": service["id"],
        },
    )
    assert available_resp.status_code == 200, available_resp.text
    assert len(available_resp.json()["items"]) >= 1

    appointment_resp = await client.post(
        "/api/agents/admin_template/appointments",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "client_external_id": "client-1",
            "client_name": "Client 1",
            "starts_at": starts_at,
            "ends_at": ends_at,
            "staff_id": staff["id"],
            "resource_id": resource["id"],
            "service_id": service["id"],
        },
    )
    assert appointment_resp.status_code == 201, appointment_resp.text
    appointment = appointment_resp.json()

    reschedule_resp = await client.patch(
        "/api/agents/admin_template/appointments/reschedule",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "appointment_id": appointment["id"],
            "starts_at": shifted_start,
            "ends_at": shifted_end,
        },
    )
    assert reschedule_resp.status_code == 200, reschedule_resp.text

    occupancy_resp = await client.get(
        "/api/agents/admin_template/occupancy",
        headers=auth_headers,
        params={
            "agent_id": agent_id,
            "starts_at": starts_at,
            "ends_at": (now + timedelta(hours=4)).isoformat(),
            "granularity_minutes": 30,
        },
    )
    assert occupancy_resp.status_code == 200, occupancy_resp.text
    data = occupancy_resp.json()
    assert "aggregates" in data
    assert "kpis" in data
    assert "drilldown" in data
    assert "matrix" in data
    assert len(data["matrix"]) >= 1
    assert "by_staff" in data["aggregates"]
    assert "by_resource" in data["aggregates"]
    assert "by_service" in data["aggregates"]
    assert "schedule_gaps" in data["aggregates"]
    assert "utilization_percent" in data["kpis"]
    assert "peak_hours" in data["kpis"]
    assert "no_show" in data["kpis"]
    assert isinstance(data["drilldown"].get("appointments"), list)


@pytest.mark.asyncio
async def test_admin_template_stage8_waitlist_reminders_profiles_quick_replies(client: AsyncClient, auth_headers):
    agent_id = await _create_admin_agent(
        client,
        auth_headers,
        cfg={
            "waitlist_enabled": True,
            "reminder_enabled": True,
            "reminder_offsets_hours": [24, 2],
            "manual_confirmation_enabled": True,
            "manual_confirmation_price_minor": 0,
            "manual_confirmation_duration_minutes": 1,
        },
    )
    staff = (
        await client.post(
            "/api/agents/admin_template/staff",
            headers=auth_headers,
            json={"agent_id": agent_id, "role": "master", "full_name": "Stage8 Master"},
        )
    ).json()
    resource = (
        await client.post(
            "/api/agents/admin_template/resources",
            headers=auth_headers,
            json={"agent_id": agent_id, "resource_type": "chair", "title": "Stage8 Chair"},
        )
    ).json()
    service = (
        await client.post(
            "/api/agents/admin_template/services",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "target_role": "master",
                "title": "Premium Service",
                "duration_minutes": 90,
                "price_minor": 10000,
            },
        )
    ).json()
    now = datetime.utcnow().replace(microsecond=0)
    starts = now + timedelta(hours=3)
    ends = starts + timedelta(hours=1)
    appointment = (
        await client.post(
            "/api/agents/admin_template/appointments",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "client_external_id": "client-main",
                "starts_at": starts.isoformat(),
                "ends_at": ends.isoformat(),
                "staff_id": staff["id"],
                "resource_id": resource["id"],
                "service_id": service["id"],
            },
        )
    ).json()
    assert appointment["status"] == "pending_confirmation"

    waitlist = (
        await client.post(
            "/api/agents/admin_template/waitlist",
            headers=auth_headers,
            json={
                "agent_id": agent_id,
                "client_external_id": "client-waitlist",
                "client_name": "Waitlist Client",
                "service_id": service["id"],
                "desired_staff_id": staff["id"],
                "desired_resource_id": resource["id"],
                "earliest_starts_at": starts.isoformat(),
                "latest_ends_at": ends.isoformat(),
            },
        )
    ).json()
    assert waitlist["status"] == "waiting"

    cancel_resp = await client.patch(
        "/api/agents/admin_template/appointments/cancel",
        headers=auth_headers,
        json={"agent_id": agent_id, "appointment_id": appointment["id"], "reason": "free_slot_for_waitlist"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    waitlist_list = await client.get(
        "/api/agents/admin_template/waitlist",
        headers=auth_headers,
        params={"agent_id": agent_id},
    )
    assert waitlist_list.status_code == 200, waitlist_list.text
    waitlist_items = waitlist_list.json()["items"]
    assert any(item["status"] == "matched" for item in waitlist_items)

    profile_update = await client.patch(
        "/api/agents/admin_template/client_profiles",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "client_external_id": "client-main",
            "tags": ["vip", "prefers-morning"],
            "preferences": {"drink": "coffee"},
            "history_note": "Loves quick service",
        },
    )
    assert profile_update.status_code == 200, profile_update.text
    assert "vip" in profile_update.json()["tags"]

    quick_reply = await client.post(
        "/api/agents/admin_template/quick_replies",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "title": "Confirm visit",
            "body": "Подтвердите, пожалуйста, визит ответом Да.",
            "category": "confirmation",
        },
    )
    assert quick_reply.status_code == 201, quick_reply.text

    quick_reply_list = await client.get(
        "/api/agents/admin_template/quick_replies",
        headers=auth_headers,
        params={"agent_id": agent_id},
    )
    assert quick_reply_list.status_code == 200
    assert len(quick_reply_list.json()["items"]) >= 1

    remind_start = now + timedelta(hours=24, minutes=10)
    remind_end = remind_start + timedelta(hours=1)
    appointment_for_reminder = await client.post(
        "/api/agents/admin_template/appointments",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "client_external_id": "client-reminder",
            "starts_at": remind_start.isoformat(),
            "ends_at": remind_end.isoformat(),
            "staff_id": staff["id"],
            "resource_id": resource["id"],
            "service_id": service["id"],
        },
    )
    assert appointment_for_reminder.status_code == 201

    reminders_run = await client.post(
        "/api/agents/admin_template/reminders/run",
        headers=auth_headers,
        json={
            "agent_id": agent_id,
            "now_iso": (remind_start - timedelta(hours=24)).isoformat(),
            "channel": "test",
        },
    )
    assert reminders_run.status_code == 200, reminders_run.text
    assert reminders_run.json()["sent"] >= 1
