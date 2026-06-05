"""Pydantic schemas for Website Builder API."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums as Literals
# ---------------------------------------------------------------------------

WebsiteStatusLiteral = Literal["draft", "published", "archived"]
WebsiteBlockTypeLiteral = Literal[
    "hero",
    "services",
    "about",
    "contacts",
    "cta",
    "footer",
    "agent-widget",
    "booking",
    "custom",
    "fullpage",
]
WebsiteDomainVerificationStatusLiteral = Literal["pending", "verified", "failed"]
WebsiteGenerationStatusLiteral = Literal["idle", "queued", "generating", "completed", "failed"]


# ---------------------------------------------------------------------------
# Website Template Schemas
# ---------------------------------------------------------------------------

class WebsiteTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=512)
    thumbnail_url: str | None = Field(default=None, max_length=1024)
    default_blocks: dict = Field(default_factory=dict)
    default_styles: dict = Field(default_factory=dict)


class WebsiteTemplateResponse(WebsiteTemplateBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Website Block Schemas
# ---------------------------------------------------------------------------

class WebsiteBlockBase(BaseModel):
    type: WebsiteBlockTypeLiteral
    content: dict = Field(default_factory=dict)
    styles: dict = Field(default_factory=dict)
    is_visible: bool = True


class WebsiteBlockCreate(WebsiteBlockBase):
    order: int = Field(default=0, ge=0)


class WebsiteBlockUpdate(BaseModel):
    type: WebsiteBlockTypeLiteral | None = None
    content: dict | None = None
    styles: dict | None = None
    is_visible: bool | None = None
    order: int | None = Field(default=None, ge=0)


class WebsiteBlockResponse(WebsiteBlockBase):
    id: int
    website_id: int
    order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Website Domain Schemas
# ---------------------------------------------------------------------------

class WebsiteDomainBase(BaseModel):
    domain: str = Field(..., min_length=3, max_length=253)


class WebsiteDomainCreate(WebsiteDomainBase):
    pass


class WebsiteDomainResponse(WebsiteDomainBase):
    id: int
    website_id: int
    ssl_enabled: bool
    verification_status: WebsiteDomainVerificationStatusLiteral
    verification_token: str | None
    verified_at: datetime | None
    last_dns_check_at: datetime | None
    dns_check_error: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Website Schemas
# ---------------------------------------------------------------------------

class WebsiteStyles(BaseModel):
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str | None = Field(default=None, max_length=64)
    dark_mode: bool | None = False


class WebsiteMetaUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    meta_description: str | None = Field(default=None, max_length=500)
    og_title: str | None = Field(default=None, max_length=100)
    og_description: str | None = Field(default=None, max_length=300)
    og_image_url: str | None = Field(default=None, max_length=1024)
    favicon_url: str | None = Field(default=None, max_length=1024)


class WebsiteCreateRequest(BaseModel):
    agent_id: int | None = Field(default=None, gt=0)
    template_id: int | None = Field(default=None, gt=0)
    slug: str | None = Field(default=None, min_length=3, max_length=50, pattern=r"^[a-z0-9-]+$")
    title: str | None = Field(default=None, max_length=100)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Slug cannot start or end with hyphen")
        if "--" in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        return v.lower()


class WebsiteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    meta_description: str | None = Field(default=None, max_length=500)
    og_title: str | None = Field(default=None, max_length=100)
    og_description: str | None = Field(default=None, max_length=300)
    og_image_url: str | None = Field(default=None, max_length=1024)
    favicon_url: str | None = Field(default=None, max_length=1024)
    custom_styles: WebsiteStyles | None = None


class WebsitePublishRequest(BaseModel):
    pass  # Empty body for publish action


class WebsiteGenerateRequest(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=200)
    business_description: str = Field(..., min_length=10, max_length=5000)
    agent_id: int | None = Field(default=None, gt=0, description="Optional agent ID to pull services and contacts")
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    dark_mode: bool = Field(default=False, description="Whether to use dark mode theme")
    generation_brief: str | None = Field(
        default=None,
        max_length=1200,
        description="Optional individual brief for AI website generation",
    )


class WebsiteResponse(BaseModel):
    id: int
    owner_id: int
    agent_id: int | None
    template_id: int | None
    slug: str
    title: str | None
    meta_description: str | None
    og_title: str | None
    og_description: str | None
    og_image_url: str | None
    favicon_url: str | None
    status: WebsiteStatusLiteral
    generation_status: WebsiteGenerationStatusLiteral | None
    custom_styles: dict
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    class Config:
        from_attributes = True


class WebsiteDetailResponse(WebsiteResponse):
    blocks: list[WebsiteBlockResponse]
    domains: list[WebsiteDomainResponse]


class WebsiteListResponse(BaseModel):
    total: int
    items: list[WebsiteResponse]


# ---------------------------------------------------------------------------
# Website Schema (for public/preview render)
# ---------------------------------------------------------------------------

class WebsiteSchemaAgentEmbed(BaseModel):
    id: int
    name: str
    description: str | None = None
    logo_url: str | None = None
    template_type: str
    is_admin_template: bool = False
    has_booking: bool = False
    services: list[dict] = Field(default_factory=list)
    contacts: dict = Field(default_factory=dict)
    widget_api_key: str | None = None


class WebsiteSchemaResponse(BaseModel):
    id: int
    slug: str
    title: str | None
    meta_description: str | None
    og_title: str | None
    og_description: str | None
    og_image_url: str | None
    favicon_url: str | None
    status: WebsiteStatusLiteral
    styles: dict  # merged default + custom styles
    blocks: list[dict]  # blocks with content and styles
    agent_id: int | None = None
    agent: WebsiteSchemaAgentEmbed | None = None


# ---------------------------------------------------------------------------
# SEO / Meta Data
# ---------------------------------------------------------------------------

class SEOMetaDataResponse(BaseModel):
    """Complete SEO metadata for a website."""

    website_id: int
    title: str | None
    meta_description: str | None
    og_title: str | None
    og_description: str | None
    og_image_url: str | None
    favicon_url: str | None


class FaviconUploadResponse(BaseModel):
    """Response after favicon upload."""

    success: bool
    favicon_url: str | None
    sizes_generated: list[str]
    message: str


class OGImageUploadResponse(BaseModel):
    """Response after OG image upload."""

    success: bool
    og_image_url: str | None
    message: str


class OGImageGenerateRequest(BaseModel):
    """Request to auto-generate OG image."""

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class OGImageGenerateResponse(BaseModel):
    """Response after OG image generation."""

    success: bool
    og_image_url: str | None
    message: str


class SEOPreviewResponse(BaseModel):
    """SEO preview data for Google SERP and social cards."""

    google_title: str
    google_description: str
    google_url: str
    google_title_length: int
    google_description_length: int
    google_title_status: Literal["good", "warning", "error"]  # good: 30-60, warning: <30 or 60-70, error: >70
    google_description_status: Literal["good", "warning", "error"]  # good: 120-160

    telegram_title: str
    telegram_description: str
    telegram_image_url: str | None

    warnings: list[str]


# ---------------------------------------------------------------------------
# Domain Verification
# ---------------------------------------------------------------------------

class DomainVerificationResponse(BaseModel):
    domain: str
    verification_token: str
    verification_status: WebsiteDomainVerificationStatusLiteral
    dns_record_name: str
    dns_record_value: str
    instructions: str


class DomainVerificationResult(BaseModel):
    domain: str
    verification_status: WebsiteDomainVerificationStatusLiteral
    message: str


# ---------------------------------------------------------------------------
# Generation Status and Responses
# ---------------------------------------------------------------------------

class WebsiteGenerationStatusResponse(BaseModel):
    website_id: int
    generation_status: WebsiteGenerationStatusLiteral
    status: WebsiteStatusLiteral
    updated_at: datetime | None
    error: str | None = None
    runtime_logs: list[str] = Field(default_factory=list)


class WebsiteGenerationStartResponse(BaseModel):
    website_id: int
    message: str
    generation_status: str = "queued"


class WebsiteGenerationResultResponse(BaseModel):
    success: bool
    website_id: int
    generation_status: WebsiteGenerationStatusLiteral
    message: str
    applied_blocks: int | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Constructor / Block editing
# ---------------------------------------------------------------------------

class BlockReorderItem(BaseModel):
    block_id: int = Field(..., gt=0)
    order: int = Field(..., ge=0)


class WebsiteBlocksReorderRequest(BaseModel):
    blocks: list[BlockReorderItem] = Field(..., min_length=1)


class BlockPromptEditRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)


class BlockPromptEditResponse(BaseModel):
    content: dict
    styles: dict
    message: str | None = None


# ---------------------------------------------------------------------------
# Website Export Schemas
# ---------------------------------------------------------------------------

WebsiteExportStatusLiteral = Literal["pending", "processing", "completed", "failed"]


class WebsiteExportStartRequest(BaseModel):
    """Request to start website export."""

    include_widget: bool = Field(default=True, description="Include agent widget in export")
    download_external_images: bool = Field(default=True, description="Download external images to archive")


class WebsiteExportStartResponse(BaseModel):
    """Response when export is started."""

    website_id: int
    export_id: str
    message: str
    status: WebsiteExportStatusLiteral = "pending"


class WebsiteExportStatusResponse(BaseModel):
    """Current status of an export job."""

    website_id: int
    export_id: str | None = None
    status: WebsiteExportStatusLiteral
    progress_percent: int = Field(default=0, ge=0, le=100)
    created_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    download_url: str | None = None
    expires_at: datetime | None = None
    archive_size_bytes: int | None = None


class WebsiteExportResultResponse(BaseModel):
    """Result of completed export."""

    success: bool
    website_id: int
    export_id: str
    download_url: str | None = None
    download_token: str | None = None
    archive_size_bytes: int = 0
    files_included: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    error_message: str | None = None


class WebsiteExportDownloadRequest(BaseModel):
    """Download request with token."""

    token: str = Field(..., min_length=1, max_length=64)


class WebsiteExportHistoryItem(BaseModel):
    """Single export history entry."""

    export_id: str
    website_id: int
    status: WebsiteExportStatusLiteral
    created_at: datetime
    completed_at: datetime | None = None
    archive_size_bytes: int | None = None
    expires_at: datetime | None = None


class WebsiteExportHistoryResponse(BaseModel):
    """List of past exports for a website."""

    website_id: int
    items: list[WebsiteExportHistoryItem]
