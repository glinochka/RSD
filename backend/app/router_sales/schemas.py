from pydantic import BaseModel, Field


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
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6, max_length=128)
    plan_calls_monthly: int | None = Field(None, ge=0, le=1_000_000)
    plan_demos_monthly: int | None = Field(None, ge=0, le=1_000_000)
    plan_closes_monthly: int | None = Field(None, ge=0, le=1_000_000)
    daily_contacts_quota: int | None = Field(None, ge=0, le=1_000_000)


class SalesContactUpdate(BaseModel):
    lpr_name: str | None = Field(None, max_length=256)
    lpr_phone: str | None = Field(None, max_length=64)
    comment: str | None = Field(None, max_length=20000)
    workflow_status: str | None = Field(
        None,
        pattern="^(new|in_progress|demo|closed|rejected|hesitating)$",
    )
