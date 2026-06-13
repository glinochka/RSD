from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SalesLoginRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class SalesTeamMemberCreate(BaseModel):
    login: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(..., pattern="^(trainee|mop|rop)$")
    supervisor_id: int | None = None


class SalesTeamMemberUpdate(BaseModel):
    supervisor_id: int | None = None
    role: str | None = Field(None, pattern="^(trainee|mop|rop)$")
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6, max_length=128)
    plan_calls_monthly: int | None = Field(None, ge=0, le=1_000_000)
    plan_demos_monthly: int | None = Field(None, ge=0, le=1_000_000)
    plan_closes_monthly: int | None = Field(None, ge=0, le=1_000_000)
    daily_contacts_quota: int | None = Field(None, ge=0, le=1_000_000)


class SalesInvoiceCreate(BaseModel):
    amount_rub: Decimal = Field(..., gt=0, le=Decimal("10000000"))
    service_name: str | None = Field(None, max_length=512)
    client_inn: str | None = Field(None, max_length=12)

    @field_validator("client_inn")
    @classmethod
    def validate_client_inn(cls, v: str | None) -> str | None:
        if v is None:
            return None
        digits = v.strip()
        if not digits:
            return None
        if not digits.isdigit() or len(digits) not in (10, 12):
            raise ValueError("ИНН должен содержать 10 или 12 цифр")
        return digits


class SalesContactUpdate(BaseModel):
    lpr_name: str | None = Field(None, max_length=256)
    lpr_phone: str | None = Field(None, max_length=256)
    comment: str | None = Field(None, max_length=20000)
    workflow_status: str | None = Field(
        None,
        pattern="^(new|in_progress|demo|closed|rejected|hesitating)$",
    )
