from typing import Literal

from pydantic import BaseModel, Field


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
