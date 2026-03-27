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

