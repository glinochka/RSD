from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


class AgentTemplatePricingUpdate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=256)
    card_title: str | None = Field(default=None, max_length=256)
    setup_rub_min: int = Field(..., ge=0, le=10_000_000)
    monthly_maintenance_rub_min: int = Field(..., ge=0, le=10_000_000)
    is_free: bool = False
    selectable: bool = False
    status: Literal["available", "in_development"] = "available"
    description: str = Field(default="", max_length=4000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()


class AdminAgentTemplatePricingUpdateRequest(BaseModel):
    templates: list[AgentTemplatePricingUpdate] = Field(..., min_length=1)


class AdminCreateUserRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=30)
    telegram_id: int | None = Field(default=None, description="Необязательный Telegram ID")


class AdminGiftSubscriptionRequest(BaseModel):
    plan_code: Literal["Free", "Advanced", "Pro"] = Field(
        ..., description="Subscription plan to gift"
    )


class AdminFreeAgentActivationRequest(BaseModel):
    enabled: bool = Field(..., description="Бесплатная активация агентов для аккаунта")


class AdminPartnerPayoutUpdateRequest(BaseModel):
    action: Literal["approve", "reject", "mark_paid"]
    admin_note: str | None = Field(default=None, max_length=2000)

    @field_validator("admin_note", mode="before")
    @classmethod
    def strip_admin_note(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


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
    interval_seconds: int | None = Field(
        default=None,
        ge=30,
        le=86_400,
        description="Фиксированная пауза между письмами (сек.); None = случайно 5–10 мин",
    )


class AdminEmailGroupInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    emails_raw: str = Field(default="", max_length=500_000)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        s = value.strip()
        if not s:
            raise ValueError("Название группы не может быть пустым")
        return s


class AdminEmailTargetedPreviewRequest(BaseModel):
    groups: list[AdminEmailGroupInput] = Field(..., min_length=1, max_length=50)
    selected_titles: list[str] = Field(..., min_length=1, max_length=50)

    @field_validator("selected_titles")
    @classmethod
    def strip_titles(cls, titles: list[str]) -> list[str]:
        out = [t.strip() for t in titles if t and str(t).strip()]
        if not out:
            raise ValueError("Нужно выбрать хотя бы одну группу")
        return out

    @model_validator(mode="after")
    def unique_group_titles_and_selection(self):
        titles = [g.title.strip() for g in self.groups]
        if len(titles) != len(set(titles)):
            raise ValueError("Названия групп должны быть уникальны")
        avail = set(titles)
        for st in self.selected_titles:
            if st not in avail:
                raise ValueError(f'Группа «{st}» не найдена среди переданных')
        return self


class AdminTargetedBroadcastRequest(AdminEmailTargetedPreviewRequest):
    subject: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=10, max_length=15000)
    interval_seconds: int | None = Field(
        default=None,
        ge=30,
        le=86_400,
        description="Фиксированная пауза между письмами (сек.); None = случайно 5–10 мин",
    )


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
