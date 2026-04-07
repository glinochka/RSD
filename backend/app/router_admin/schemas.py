from typing import Literal

from pydantic import BaseModel, Field
from pydantic import field_validator


class AdminLoginRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class SubscriptionPlanUpdate(BaseModel):
    code: Literal["Free", "Advanced", "Pro"]
    price_rub_month: int = Field(..., ge=0, le=1_000_000)
    max_active_agents: int = Field(..., ge=0, le=1_000_000)
    knowledge_base_chunk_limit: int | None = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="null means unlimited",
    )


class AdminSubscriptionPlansUpdateRequest(BaseModel):
    plans: list[SubscriptionPlanUpdate] = Field(..., min_length=1)


class AdminGiftSubscriptionRequest(BaseModel):
    plan_code: Literal["Free", "Advanced", "Pro"] = Field(
        ..., description="Subscription plan to gift"
    )


class AdminPromoCodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    discount_percent: int = Field(..., ge=0, le=100)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("Promo code is required")
        return cleaned
