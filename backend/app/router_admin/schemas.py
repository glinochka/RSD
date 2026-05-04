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


class AdminEmailBroadcastRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=10, max_length=15000)


# ---------------------------------------------------------------------------
# Article Publisher schemas
# ---------------------------------------------------------------------------

class ArticlePublisherSettingsUpdateRequest(BaseModel):
    posting_enabled: bool | None = None
    posting_frequency_hours: int | None = Field(default=None, ge=1, le=720)
    vcru_enabled: bool | None = None
    vcru_email: str | None = Field(default=None, max_length=255)
    vcru_password: str | None = Field(default=None, max_length=512)
    vcru_subsite_id: str | None = Field(default=None, max_length=64)
    zen_enabled: bool | None = None
    zen_login: str | None = Field(default=None, max_length=255)
    zen_password: str | None = Field(default=None, max_length=512)
    zen_channel_id: str | None = Field(default=None, max_length=128)
    auto_topics_enabled: bool | None = None
    topic_categories: list[str] | None = None
    promo_ratio: int | None = Field(default=None, ge=0, le=100)
    company_name: str | None = Field(default=None, max_length=256)
    company_url: str | None = Field(default=None, max_length=512)
    company_description: str | None = Field(default=None, max_length=2000)
    article_min_words: int | None = Field(default=None, ge=100, le=5000)
    article_max_words: int | None = Field(default=None, ge=200, le=10000)


class ArticlePublisherAddTopicsRequest(BaseModel):
    topics: list[str] = Field(..., min_length=1)


class ArticlePublisherGenerateTopicsRequest(BaseModel):
    categories: list[str] | None = None
    count: int = Field(default=10, ge=1, le=50)


class ArticlePublisherRunNowRequest(BaseModel):
    platform: str | None = Field(default=None, description="vcru or yandex_zen; auto if None")
    topic: str | None = Field(default=None, max_length=1000)
