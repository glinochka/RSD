from pydantic import BaseModel, Field

class Agent_by_botID(BaseModel):
    bot_id: int = Field(..., description="id бота")


class PublicLinkSource(BaseModel):
    bot_id: int = Field(..., description="id бота")
    url: str = Field(..., description="Публичная ссылка (http/https)")


class ReindexJobCreateRequest(BaseModel):
    bot_id: int = Field(..., description="Telegram bot id агента")
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

