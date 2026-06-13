from pydantic import BaseModel, Field, field_validator

from ..services.referral import MAX_PARTNER_PROMO_DISCOUNT_PERCENT, normalize_promo_code


class PartnerPromoCodeCreateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=32)
    discount_percent: int = Field(..., ge=0, le=MAX_PARTNER_PROMO_DISCOUNT_PERCENT)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = normalize_promo_code(value)
        if not normalized:
            raise ValueError("Promo code is required")
        return normalized


class PartnerPromoCodePatchRequest(BaseModel):
    is_active: bool | None = None
    discount_percent: int | None = Field(default=None, ge=0, le=MAX_PARTNER_PROMO_DISCOUNT_PERCENT)


class PartnerPayoutCreateRequest(BaseModel):
    amount_rub: int = Field(..., ge=1, le=10_000_000, description="Сумма вывода в рублях")
    payment_details: str = Field(..., min_length=10, max_length=2000)

    @field_validator("payment_details", mode="before")
    @classmethod
    def strip_payment_details(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value
