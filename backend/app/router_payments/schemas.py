from pydantic import BaseModel, Field
from typing import Literal


class ProcessTelegramPayment(BaseModel):
    telegram_id: int = Field(..., description="Telegram user id")
    plan_name: Literal["Advanced", "Pro"] = Field(..., description="Paid subscription plan name")
    currency: str = Field(..., min_length=1, max_length=10, description="Telegram payment currency code")
    total_amount: int = Field(..., gt=0, description="Payment amount in minimal currency units")
    telegram_payment_charge_id: str = Field(..., min_length=1, max_length=255)
    provider_payment_charge_id: str | None = Field(default=None, max_length=255)
    invoice_payload: str | None = Field(default=None, max_length=512)

