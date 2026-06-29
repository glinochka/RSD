"""Tests for public website lead form intake."""
from __future__ import annotations

import json
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.alembic.models import AdminApplication, Agent, User
from app.router_websites.schemas import WebsiteSchemaResponse
from app.services.website_public_forms import (
    WEBSITE_UNIFIED_LEAD_FIELDS,
    map_website_form_payload,
    resolve_website_lead_fields,
    submit_website_lead,
)


def test_resolve_website_lead_fields_is_unified():
    fields = resolve_website_lead_fields()
    keys = [f["key"] for f in fields]
    assert keys == ["fio", "phone", "message"]
    assert fields == WEBSITE_UNIFIED_LEAD_FIELDS


def test_map_website_form_payload_aliases():
    mapped = map_website_form_payload(
        {
            "full_name": "Иван Иванов",
            "tel": "+79991234567",
            "comment": "Нужна консультация",
        }
    )
    assert mapped["fio"] == "Иван Иванов"
    assert mapped["phone"] == "+79991234567"
    assert mapped["message"] == "Нужна консультация"


def test_map_website_form_payload_legacy_name():
    mapped = map_website_form_payload({"name": "Пётр", "phone": "123"})
    assert mapped["fio"] == "Пётр"
    assert mapped["phone"] == "123"


def test_website_schema_agent_embed_preserves_has_applications():
    schema = WebsiteSchemaResponse(
        id=1,
        slug="dentalpro",
        title="Клиника",
        meta_description=None,
        og_title=None,
        og_description=None,
        og_image_url=None,
        favicon_url=None,
        status="published",
        styles={},
        blocks=[],
        agent_id=50,
        agent={
            "id": 50,
            "name": "@dental_agent",
            "template_type": "crm_admin",
            "is_admin_template": True,
            "workflow_mode": "applications",
            "has_booking": False,
            "has_applications": True,
            "services": [],
            "contacts": {},
            "widget_api_key": None,
        },
    )
    assert schema.agent is not None
    assert schema.agent.has_applications is True
    assert schema.agent.workflow_mode == "applications"


@pytest_asyncio.fixture()
async def forms_session_factory(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _create_active_agent(session_factory, *, is_active: bool = True) -> Agent:
    async with session_factory() as session:
        async with session.begin():
            user = User(
                name="forms_user",
                password="pwd",
                telegram_id=int(datetime.utcnow().timestamp() * 1000) % 10_000_000_000,
                subscription_type="Free",
            )
            session.add(user)
            await session.flush()

            agent = Agent(
                user_id=user.id,
                bot_username="forms_agent",
                encrypted_token=f"enc_{datetime.utcnow().timestamp()}",
                bot_id=int(datetime.utcnow().timestamp() * 100),
                template_type="crm_admin",
                template_config=json.dumps({"workflow_mode": "applications"}, ensure_ascii=False),
                system_prompt="test",
                is_active=is_active,
            )
            session.add(agent)
            await session.flush()
            await session.refresh(agent)
            return agent


@pytest.mark.asyncio
async def test_submit_website_lead_persists_application(forms_session_factory, monkeypatch):
    monkeypatch.setattr(
        "app.services.website_public_forms.async_session_maker",
        forms_session_factory,
    )
    agent = await _create_active_agent(forms_session_factory)

    row = await submit_website_lead(
        agent_id=agent.id,
        client_name="Салих",
        fields={"fio": "Салих", "phone": "+79179156670", "message": "консультация"},
    )

    assert row["id"] > 0
    assert row["agent_id"] == agent.id
    assert row["client_name"] == "Салих"
    assert row["status"] == "new"
    assert row["source_channel"] == "website"
    assert row["fields"]["fio"] == "Салих"
    assert row["fields"]["phone"] == "+79179156670"
    assert row["fields"]["message"] == "консультация"

    async with forms_session_factory() as session:
        db_row = (
            await session.execute(
                select(AdminApplication).where(AdminApplication.id == row["id"])
            )
        ).scalar_one()
        assert db_row.client_external_id.startswith("web_")


@pytest.mark.asyncio
async def test_submit_website_lead_rejects_missing_phone(forms_session_factory, monkeypatch):
    monkeypatch.setattr(
        "app.services.website_public_forms.async_session_maker",
        forms_session_factory,
    )
    agent = await _create_active_agent(forms_session_factory)

    with pytest.raises(ValueError, match="обязательно"):
        await submit_website_lead(
            agent_id=agent.id,
            client_name="Салих",
            fields={"fio": "Салих"},
        )


@pytest.mark.asyncio
async def test_submit_website_lead_rejects_inactive_agent(forms_session_factory, monkeypatch):
    monkeypatch.setattr(
        "app.services.website_public_forms.async_session_maker",
        forms_session_factory,
    )
    agent = await _create_active_agent(forms_session_factory, is_active=False)

    with pytest.raises(ValueError, match="Agent not found"):
        await submit_website_lead(
            agent_id=agent.id,
            client_name="Салих",
            fields={"fio": "Салих", "phone": "+79179156670"},
        )
