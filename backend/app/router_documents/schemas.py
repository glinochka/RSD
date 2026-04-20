from pydantic import BaseModel, Field, model_validator

class AgentLookup(BaseModel):
    agent_id: int | None = Field(default=None, gt=0, description="Внутренний id агента")
    bot_id: int | None = Field(default=None, description="Legacy Telegram id канала")

    @model_validator(mode="after")
    def validate_lookup(self):
        if self.agent_id is None and self.bot_id is None:
            raise ValueError("Either agent_id or bot_id is required")
        return self


class Agent_by_botID(AgentLookup):
    pass


class PublicLinkSource(AgentLookup):
    url: str = Field(..., description="Публичная ссылка (http/https)")


class ReindexJobCreateRequest(AgentLookup):
    # Manual trigger only: if omitted, uses active profile from backend config.
    target_embedding_profile_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Целевой embedding profile key (опционально)",
    )
    batch_size: int = Field(default=10, ge=1, le=200, description="Размер батча документов")


class ReindexJobItem(BaseModel):
    id: int
    agent_id: int
    status: str
    target_embedding_profile_key: str
    target_embedding_schema_version: int
    target_embedding_model_name: str
    batch_size: int
    total_documents: int
    processed_documents: int
    success_documents: int
    failed_documents: int
    document_cursor: int
    last_error: str | None
    created_at: str | None
    started_at: str | None
    finished_at: str | None

