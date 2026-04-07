from pydantic import BaseModel, Field
from pydantic import field_validator

from ..subscription_plans import get_subscription_plan_codes


class ProcessTelegramPayment(BaseModel):
    telegram_id: int = Field(..., description="Telegram user id")
    plan_name: str = Field(..., description="Paid subscription plan name")
    currency: str = Field(..., min_length=1, max_length=10, description="Telegram payment currency code")
    total_amount: int = Field(..., gt=0, description="Payment amount in minimal currency units")
    telegram_payment_charge_id: str = Field(..., min_length=1, max_length=255)
    provider_payment_charge_id: str | None = Field(default=None, max_length=255)
    invoice_payload: str | None = Field(default=None, max_length=512)

    @field_validator("plan_name")
    @classmethod
    def validate_plan_name(cls, value: str) -> str:
        if value not in get_subscription_plan_codes(paid_only=True):
            raise ValueError("Invalid paid subscription plan name")
        return value


class CreateYooKassaPayment(BaseModel):
    plan_name: str = Field(..., description="Paid subscription plan name")
    return_url: str | None = Field(default=None, description="URL where YooKassa returns user after payment")
    promo_code: str | None = Field(default=None, max_length=64, description="Optional promo code")
    duration_months: int = Field(default=1, description="Subscription duration in months")

    @field_validator("plan_name")
    @classmethod
    def validate_paid_plan_name(cls, value: str) -> str:
        if value not in get_subscription_plan_codes(paid_only=True):
            raise ValueError("Invalid paid subscription plan name")
        return value

    @field_validator("duration_months")
    @classmethod
    def validate_duration_months(cls, value: int) -> int:
        if value not in (1, 3, 6):
            raise ValueError("duration_months must be one of 1, 3, 6")
        return value


class YooKassaPaymentStatusResponse(BaseModel):
    payment_id: str
    status: str
    plan_name: str
    subscription_type: str | None = None
    subscription_end_date: str | None = None


class CreateTurnkeyAgentRequest(BaseModel):
    phone_number: str = Field(..., min_length=5, max_length=32)
    email: str = Field(..., min_length=5, max_length=255)
    requested_agent: str = Field(..., min_length=2, max_length=255)
    purpose: str = Field(..., min_length=5, max_length=2000)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Phone number is required")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("Invalid email")
        return cleaned

    @field_validator("requested_agent", "purpose")
    @classmethod
    def trim_text_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

