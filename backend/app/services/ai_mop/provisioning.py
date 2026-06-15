"""Провижининг аккаунта, агента и сайта для лида ИИ МОП."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import string
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from ...agent_template_pricing import initial_maintenance_paid_until_for_template
from ...alembic.database import async_session_maker
from ...alembic.models import Agent, AiMopLead, User, Website
from ...config.website_domains import BASE_DOMAIN
from ...router_agents.dao import AgentDAO
from ...router_users.dao import UserDAO
from ...router_users.router import _build_unique_username, _validate_email_or_422
from ...router_websites.dao import WebsiteDAO
from ...router_websites.router import _run_website_generation
from ...router_websites.schemas import WebsiteGenerateRequest
from ...router_websites.utils import generate_slug_from_name
from ...utils.api_keys import generate_agent_external_api_key, hash_agent_external_api_key
from ...utils.crypto import encrypt_token
from ...utils.security import get_password_hash
from ..admin_booking import get_admin_booking_service
from ..admin_booking.domains import DOMAIN_REGISTRY
from ..website_generation_service import get_website_generation_service
from .llm_helpers import build_lead_context, generate_provision_profile

logger = logging.getLogger(__name__)

_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_GENERATION_POLL_SECONDS = 5
_GENERATION_MAX_WAIT_SECONDS = 600


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_temp_password(length: int = 5) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(max(5, length)))


def _default_crm_admin_config(domain_type: str) -> dict[str, object]:
    domain = DOMAIN_REGISTRY.get(domain_type) or DOMAIN_REGISTRY["beauty_salon"]
    return {
        "domain_type": domain_type,
        "crm_mode": "disabled",
        "booking_backend": "local",
        "crm_provider": "amocrm",
        "allowed_tools": [
            "list_staff",
            "list_services",
            "get_available_slots",
            "create_appointment",
            "cancel_appointment",
            "reschedule_appointment",
        ],
        "allowed_booking_tools": [
            "list_staff",
            "list_services",
            "get_available_slots",
            "create_appointment",
        ],
        "confirmation_policy": "confirm_risky",
        "fallback_mode": "ask_clarifying_question",
        "waitlist_enabled": False,
        "reminder_enabled": False,
        "paid_booking_enabled": False,
        "appointment_confirmation_enabled": True,
        "resources_enabled": domain.resources_mode != "none",
        "resource_linked_to_staff": domain.resource_linked_to_staff,
        "custom_staff_role": domain.staff_role_default,
        "custom_staff_label": domain.staff_label_ru,
        "http_integrations_enabled": False,
    }


def _initial_billing_fields(template_type: str) -> dict[str, object]:
    fields: dict[str, object] = {
        "activation_paid_at": _utc_now(),
    }
    grace_until = initial_maintenance_paid_until_for_template(template_type)
    if grace_until is not None:
        fields["maintenance_paid_until"] = grace_until
    else:
        fields["maintenance_paid_until"] = date.today() + timedelta(days=30)
    return fields


def _website_public_url(slug: str) -> str:
    return f"https://{BASE_DOMAIN}/w/{slug}"


async def _wait_for_website_generation(website_id: int) -> str:
    deadline = asyncio.get_event_loop().time() + _GENERATION_MAX_WAIT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        async with async_session_maker() as session:
            website = await session.scalar(select(Website).where(Website.id == website_id))
            if website is None:
                raise RuntimeError("Website disappeared during generation")
            status = str(website.generation_status or "")
            if status == "completed":
                return str(website.slug)
            if status == "failed":
                raise RuntimeError("Website generation failed")
        await asyncio.sleep(_GENERATION_POLL_SECONDS)
    raise RuntimeError("Website generation timed out")


async def provision_lead_demo(
    *,
    lead: AiMopLead,
    sales_agent: Agent,
) -> dict[str, Any]:
    """Создать user + crm_admin agent + website для лида. Возвращает credentials и URL."""
    if not lead.email:
        raise ValueError("Lead email is required")

    lead_context = build_lead_context(
        org_name=lead.org_name,
        email=lead.email,
        lpr_name=lead.lpr_name,
        phone=lead.phone,
        address=lead.address,
        category=lead.category,
    )
    profile = await generate_provision_profile(lead_context=lead_context)
    domain_type = str(profile.get("domain_type") or "beauty_salon")
    business_description = str(profile.get("business_description") or lead.org_name)
    agent_prompt = str(profile.get("agent_system_prompt") or f"Ты ИИ-администратор компании {lead.org_name}.")
    agent_prompt = f"Ты ИИ-администратор компании «{lead.org_name}». {agent_prompt}".strip()
    temp_password = generate_temp_password()
    normalized_email = _validate_email_or_422(lead.email)

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        agent_dao = AgentDAO(session)
        async with session.begin():
            existing = await user_dao.find_one_by_filter(email=normalized_email)
            if existing and existing.email_verified:
                raise ValueError(f"Email already registered: {normalized_email}")

            username = await _build_unique_username(user_dao, normalized_email)
            if existing:
                user = existing
                await user_dao.update(
                    user,
                    {
                        "name": username,
                        "password": get_password_hash(temp_password),
                        "email_verified": True,
                    },
                )
            else:
                user = await user_dao.add(
                    {
                        "name": username,
                        "email": normalized_email,
                        "password": get_password_hash(temp_password),
                        "email_verified": True,
                    }
                )
                await session.flush()

            template_config = _default_crm_admin_config(domain_type)
            external_api_key = generate_agent_external_api_key()
            created_agent = await agent_dao.add(
                {
                    "user_id": user.id,
                    "bot_id": None,
                    "primary_provider": "none",
                    "template_type": "crm_admin",
                    "template_config": json.dumps(template_config, ensure_ascii=False),
                    "encrypted_token": encrypt_token(f"ai_mop:{user.id}:{_utc_now().timestamp()}"),
                    "encrypted_external_api_key": encrypt_token(external_api_key),
                    "external_api_key_hash": hash_agent_external_api_key(external_api_key),
                    "bot_username": None,
                    "system_prompt": agent_prompt.strip(),
                    "is_active": True,
                    **_initial_billing_fields("crm_admin"),
                }
            )
            await session.flush()
            provisioned_agent_id = int(created_agent.id)
            provisioned_user_id = int(user.id)

    booking = get_admin_booking_service()
    staff_list = profile.get("staff") if isinstance(profile.get("staff"), list) else []
    if not staff_list:
        domain = DOMAIN_REGISTRY.get(domain_type) or DOMAIN_REGISTRY["beauty_salon"]
        staff_list = [{"full_name": lead.lpr_name or "Администратор", "role": domain.staff_role_default, "specializations": []}]

    staff_id: int | None = None
    first_staff = staff_list[0] if staff_list else {}
    staff_row = await booking.create_staff(
        agent_id=provisioned_agent_id,
        role=str(first_staff.get("role") or "master"),
        full_name=str(first_staff.get("full_name") or lead.org_name)[:128],
        specializations=first_staff.get("specializations") if isinstance(first_staff.get("specializations"), list) else None,
        is_active=True,
    )
    staff_id = int(staff_row.get("id") or 0) or None

    services = profile.get("services") if isinstance(profile.get("services"), list) else []
    domain_cfg = DOMAIN_REGISTRY.get(domain_type) or DOMAIN_REGISTRY["beauty_salon"]
    if not services:
        for hint in domain_cfg.default_services_hints[:3]:
            services.append({"name": hint, "description": hint, "duration_minutes": 60, "price_rub": 0})

    for svc in services[:5]:
        if not isinstance(svc, dict):
            continue
        title = str(svc.get("name") or svc.get("title") or "Услуга").strip()[:128]
        duration = int(svc.get("duration_minutes") or 60)
        price_rub = int(svc.get("price_rub") or 0)
        await booking.create_service(
            agent_id=provisioned_agent_id,
            target_role=str(first_staff.get("role") or domain_cfg.staff_role_default),
            staff_id=staff_id,
            title=title,
            duration_minutes=max(15, duration),
            price_minor=price_rub * 100,
            is_active=True,
        )

    slug_base = generate_slug_from_name(lead.org_name)
    async with async_session_maker() as session:
        website_dao = WebsiteDAO(session)
        async with session.begin():
            slug = slug_base
            counter = 1
            while await website_dao.slug_exists(slug):
                slug = f"{slug_base}-{counter}"
                counter += 1
            website = await website_dao.add(
                {
                    "owner_id": provisioned_user_id,
                    "agent_id": provisioned_agent_id,
                    "template_id": None,
                    "slug": slug,
                    "title": lead.org_name[:255],
                    "status": "draft",
                    "generation_status": "queued",
                    "custom_styles": {},
                }
            )
            await session.flush()
            website_id = int(website.id)

    gen_request = WebsiteGenerateRequest(
        business_name=lead.org_name,
        business_description=business_description,
        agent_id=provisioned_agent_id,
        generation_brief=(
            f"Сайт для {lead.org_name}. {business_description}. "
            f"Категория: {lead.category or 'малый бизнес'}. "
            f"Адрес: {lead.address or 'не указан'}. "
            "Добавь виджет ИИ-чата. Современный дизайн."
        ),
    )
    service = get_website_generation_service()
    await _run_website_generation(website_id, gen_request, service)
    final_slug = await _wait_for_website_generation(website_id)

    async with async_session_maker() as session:
        website_dao = WebsiteDAO(session)
        async with session.begin():
            website = await website_dao.find_one_by_filter(id=website_id)
            if website is None:
                raise RuntimeError("Website not found after generation")
            await website_dao.publish(website)

    website_url = _website_public_url(final_slug)
    return {
        "provisioned_user_id": provisioned_user_id,
        "provisioned_agent_id": provisioned_agent_id,
        "provisioned_website_id": website_id,
        "website_url": website_url,
        "temp_password": temp_password,
        "login_email": normalized_email,
        "lead_context": lead_context,
        "sales_agent_id": int(sales_agent.id),
    }
