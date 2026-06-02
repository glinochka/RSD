"""Schemas for public agent / booking API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentContactInfo(BaseModel):
    telegram: str | None = None
    whatsapp: str | None = None
    phone: str | None = None
    email: str | None = None


class AgentPublicServiceItem(BaseModel):
    id: int
    name: str
    title: str
    description: str | None = None
    duration_minutes: int
    price_minor: int = 0
    price: str
    staff_id: int | None = None


class AgentPublicDataResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    logo_url: str | None = None
    template_type: str
    is_admin_template: bool = False
    has_booking: bool = False
    services: list[AgentPublicServiceItem] = Field(default_factory=list)
    contacts: AgentContactInfo | dict[str, str] = Field(default_factory=dict)
    widget_api_key: str | None = None


class PublicBookingSlotsResponse(BaseModel):
    items: list[dict[str, Any]]


class PublicBookingCreateRequest(BaseModel):
    service_id: int = Field(..., gt=0)
    starts_at: str = Field(..., min_length=10, max_length=64)
    ends_at: str = Field(..., min_length=10, max_length=64)
    client_name: str = Field(..., min_length=1, max_length=128)
    client_phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    staff_id: int | None = Field(default=None, gt=0)


class PublicBookingCreateResponse(BaseModel):
    id: int
    status: str
    starts_at: str | None = None
    ends_at: str | None = None
    message: str = "Запись создана"
