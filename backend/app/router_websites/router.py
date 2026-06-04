"""Website Builder API Router."""
import asyncio
import os
from datetime import datetime, timezone, timedelta
from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, status, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..alembic.database import async_session_maker
from ..alembic.models import AdminService, Agent, AgentChannelConnection, User, Website, WebsiteBlock, WebsiteDomain, WebsiteTemplate
from ..utils.JWT import get_user_from_access_token
from ..config import settings
from ..router_users.dao import UserDAO
from ..services.website_generation_service import (
    WebsiteGenerationService,
    get_website_generation_service,
)
from ..services.website_export_service import (
    WebsiteExportService,
    get_website_export_service,
    EXPORT_TTL_HOURS,
)
from ..services.error_log_service import record_error_log
from ..services.website_seo_service import (
    get_website_seo_service,
    FAVICON_SIZES,
)

from .dao import WebsiteDAO, WebsiteBlockDAO, WebsiteDomainDAO, WebsiteTemplateDAO
from .schemas import (
    WebsiteCreateRequest,
    WebsiteUpdateRequest,
    WebsitePublishRequest,
    WebsiteResponse,
    WebsiteDetailResponse,
    WebsiteListResponse,
    WebsiteBlockCreate,
    WebsiteBlockUpdate,
    WebsiteBlockResponse,
    WebsiteDomainCreate,
    WebsiteDomainResponse,
    WebsiteTemplateResponse,
    WebsiteSchemaResponse,
    DomainVerificationResponse,
    DomainVerificationResult,
    WebsiteMetaUpdate,
    WebsiteGenerateRequest,
    WebsiteGenerationStatusResponse,
    WebsiteGenerationStartResponse,
    WebsiteGenerationResultResponse,
    WebsiteBlocksReorderRequest,
    BlockPromptEditRequest,
    BlockPromptEditResponse,
    WebsiteExportStartRequest,
    WebsiteExportStartResponse,
    WebsiteExportStatusResponse,
    SEOMetaDataResponse,
    FaviconUploadResponse,
    OGImageUploadResponse,
    OGImageGenerateRequest,
    OGImageGenerateResponse,
    SEOPreviewResponse,
)
from ..services.agent_public_data import get_agent_public_data

from .utils import (
    generate_slug_from_name,
    validate_slug,
    validate_domain,
    generate_verification_token,
    generate_dns_verification_record,
    is_valid_slug,
    verify_dns_txt_record,
    extract_website_slug_from_host,
    is_system_domain,
)


async def _build_schema_agent_payload(website: Website, *, include_widget_key: bool) -> dict | None:
    if not website.agent_id:
        return None
    data = await get_agent_public_data(website.agent_id, include_widget_key=include_widget_key)
    return data

logger = getLogger(__name__)

router = APIRouter(prefix="/api/v1/websites")
http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(credentials: Annotated[HTTPBearer, Depends(http_bearer)]) -> User:
    """Dependency to get the current authenticated user."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials

    # Skip JWT prefix if present
    if token.lower().startswith("bearer "):
        token = token[7:]

    async with async_session_maker() as session:
        user_dao = UserDAO(session)
        user = await get_user_from_access_token(token, user_dao)
        return user


async def get_website_dao():
    """Dependency to get WebsiteDAO with session."""
    async with async_session_maker() as session:
        async with session.begin():
            yield WebsiteDAO(session)


async def get_block_dao():
    """Dependency to get WebsiteBlockDAO with session."""
    async with async_session_maker() as session:
        async with session.begin():
            yield WebsiteBlockDAO(session)


async def get_domain_dao():
    """Dependency to get WebsiteDomainDAO with session."""
    async with async_session_maker() as session:
        async with session.begin():
            yield WebsiteDomainDAO(session)


async def get_template_dao():
    """Dependency to get WebsiteTemplateDAO with session."""
    async with async_session_maker() as session:
        async with session.begin():
            yield WebsiteTemplateDAO(session)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.get("/templates", response_model=list[WebsiteTemplateResponse])
async def list_templates(dao: Annotated[WebsiteTemplateDAO, Depends(get_template_dao)]):
    """List all active website templates."""
    templates = await dao.list_active()
    return templates


# ---------------------------------------------------------------------------
# Websites CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=WebsiteResponse, status_code=status.HTTP_201_CREATED)
async def create_website(
    request: WebsiteCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    template_dao: Annotated[WebsiteTemplateDAO, Depends(get_template_dao)],
):
    """Create a new website for the current user."""
    # Validate or generate slug
    slug = request.slug
    if not slug:
        # Auto-generate slug from title or agent name
        base_name = request.title or "site"
        slug = generate_slug_from_name(base_name)

    # Validate slug format
    is_valid, error_msg = validate_slug(slug)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": error_msg, "field": "slug"},
        )

    # Check slug uniqueness
    exists = await website_dao.slug_exists(slug)
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": f"Slug '{slug}' is already taken", "field": "slug"},
        )

    # Verify template if provided
    template = None
    if request.template_id:
        template = await template_dao.find_one_by_filter(id=request.template_id, is_active=True)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )

    # Create website
    website_data = {
        "owner_id": user.id,
        "agent_id": request.agent_id,
        "template_id": request.template_id,
        "slug": slug,
        "title": request.title,
        "status": "draft",
        "custom_styles": template.default_styles if template else {},
    }

    try:
        website = await website_dao.add(website_data)

        # Flush to get the website ID before creating blocks
        await website_dao._session.flush()

        # Create default blocks from template if provided
        if template and template.default_blocks:
            from ..alembic.database import async_session_maker
            async with async_session_maker() as session:
                async with session.begin():
                    block_dao = WebsiteBlockDAO(session)
                    for idx, block_data in enumerate(template.default_blocks.get("blocks", [])):
                        block = WebsiteBlock(
                            website_id=website.id,
                            type=block_data.get("type", "custom"),
                            order=idx,
                            content=block_data.get("content", {}),
                            styles=block_data.get("styles", {}),
                            is_visible=True,
                        )
                        session.add(block)

        return website

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Website with this slug already exists",
        )


@router.get("", response_model=WebsiteListResponse)
async def list_websites(
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """List all websites for the current user."""
    total = await website_dao.count_by_owner(user.id)
    items = await website_dao.list_by_owner(user.id, page=page, page_size=page_size)

    return WebsiteListResponse(total=total, items=items)


@router.get("/{website_id}", response_model=WebsiteDetailResponse)
async def get_website(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Get detailed information about a specific website."""
    website = await website_dao.get_by_id_with_relations(website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    # Check ownership
    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return website


@router.put("/{website_id}", response_model=WebsiteResponse)
async def update_website(
    website_id: int,
    request: WebsiteUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Update website metadata and styles."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Build update dict
    updates = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.meta_description is not None:
        updates["meta_description"] = request.meta_description
    if request.og_title is not None:
        updates["og_title"] = request.og_title
    if request.og_description is not None:
        updates["og_description"] = request.og_description
    if request.og_image_url is not None:
        updates["og_image_url"] = request.og_image_url
    if request.favicon_url is not None:
        updates["favicon_url"] = request.favicon_url
    if request.custom_styles is not None:
        updates["custom_styles"] = request.custom_styles.model_dump(exclude_none=True)

    updates["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

    await website_dao.update(website, updates)
    return website


@router.put("/{website_id}/meta", response_model=WebsiteResponse)
async def update_website_meta(
    website_id: int,
    request: WebsiteMetaUpdate,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Update website SEO meta information."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    updates = request.model_dump(exclude_none=True)
    updates["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

    await website_dao.update(website, updates)
    return website


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_website(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Delete a website and all its blocks and domains."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await website_dao.delete(website)
    return None


# ---------------------------------------------------------------------------
# Publish / Unpublish
# ---------------------------------------------------------------------------

@router.post("/{website_id}/publish", response_model=WebsiteResponse)
async def publish_website(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Publish a website (make it publicly accessible)."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Check minimum requirements for publishing
    if not website.title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Website must have a title before publishing",
        )

    await website_dao.publish(website)
    return website


@router.post("/{website_id}/unpublish", response_model=WebsiteResponse)
async def unpublish_website(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Unpublish a website (return to draft status)."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await website_dao.unpublish(website)
    return website


# ---------------------------------------------------------------------------
# Website Blocks CRUD
# ---------------------------------------------------------------------------

@router.get("/{website_id}/blocks", response_model=list[WebsiteBlockResponse])
async def list_blocks(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
    include_hidden: Annotated[bool, Query()] = False,
):
    """List all blocks for a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    blocks = await block_dao.list_by_website(website_id, only_visible=not include_hidden)
    return blocks


@router.post("/{website_id}/blocks", response_model=WebsiteBlockResponse, status_code=status.HTTP_201_CREATED)
async def create_block(
    website_id: int,
    request: WebsiteBlockCreate,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Add a new block to a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # If order not specified, add to the end
    order = request.order
    if order == 0:
        max_order = await website_dao.get_max_order_for_website(website_id)
        order = max_order + 1

    block_data = {
        "website_id": website_id,
        "type": request.type,
        "order": order,
        "content": request.content,
        "styles": request.styles,
        "is_visible": request.is_visible,
    }

    block = await block_dao.add(block_data)
    return block


@router.put("/{website_id}/blocks/{block_id}", response_model=WebsiteBlockResponse)
async def update_block(
    website_id: int,
    block_id: int,
    request: WebsiteBlockUpdate,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Update a block's content, style, or visibility."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    block = await block_dao.find_one_by_filter(id=block_id, website_id=website_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found",
        )

    updates = request.model_dump(exclude_none=True)
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        await block_dao.update(block, updates)

    return block


@router.delete("/{website_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    website_id: int,
    block_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Delete a block from a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    block = await block_dao.find_one_by_filter(id=block_id, website_id=website_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found",
        )

    await block_dao.delete(block)
    return None


@router.post("/{website_id}/blocks/reorder", response_model=list[WebsiteBlockResponse])
async def reorder_blocks(
    website_id: int,
    request: WebsiteBlocksReorderRequest,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Reorder blocks by providing list of block_id + order pairs."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    block_orders = [(item.block_id, item.order) for item in request.blocks]
    await block_dao.reorder_blocks(website_id, block_orders)

    blocks = await block_dao.list_by_website(website_id, only_visible=False)
    return blocks


@router.post(
    "/{website_id}/blocks/{block_id}/edit-prompt",
    response_model=BlockPromptEditResponse,
)
async def edit_block_with_prompt(
    website_id: int,
    block_id: int,
    request: BlockPromptEditRequest,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Apply AI-assisted edits to a block based on a natural-language prompt."""
    website = await website_dao.get_by_id_with_relations(website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    block = await block_dao.find_one_by_filter(id=block_id, website_id=website_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found",
        )

    service = get_website_generation_service()
    try:
        if block.type == "fullpage":
            # AI-coder mode: edit the raw HTML
            current_html = (block.content or {}).get("html", "")
            if not current_html:
                raise ValueError("Fullpage block has no HTML content")

            edited_html = await service.edit_website_with_prompt(
                current_html=current_html,
                prompt=request.prompt,
                business_name=website.title or "",
            )
            edited = {
                "content": {"html": edited_html},
                "styles": block.styles or {},
            }
        else:
            # Legacy JSON-based block editing
            edited = await service.edit_block_with_prompt(
                block_type=block.type,
                content=block.content or {},
                block_styles=block.styles or {},
                global_styles=website.custom_styles or {},
                prompt=request.prompt,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    updates = {
        "content": edited["content"],
        "styles": edited["styles"],
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    await block_dao.update(block, updates)

    return BlockPromptEditResponse(
        content=edited["content"],
        styles=edited["styles"],
        message="Изменения применены",
    )


@router.post("/{website_id}/blocks/{block_id}/duplicate", response_model=WebsiteBlockResponse)
async def duplicate_block(
    website_id: int,
    block_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Duplicate an existing block."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    block = await block_dao.find_one_by_filter(id=block_id, website_id=website_id)
    if not block:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Block not found",
        )

    new_block = await block_dao.duplicate_block(block)
    await block_dao._session.flush()  # Get the ID
    return new_block


# ---------------------------------------------------------------------------
# Custom Domains
# ---------------------------------------------------------------------------

@router.get("/{website_id}/domains", response_model=list[WebsiteDomainResponse])
async def list_domains(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    domain_dao: Annotated[WebsiteDomainDAO, Depends(get_domain_dao)],
):
    """List all custom domains for a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    domains = await domain_dao.list_by_website(website_id)
    return domains


@router.post("/{website_id}/domains", response_model=DomainVerificationResponse, status_code=status.HTTP_201_CREATED)
async def add_domain(
    website_id: int,
    request: WebsiteDomainCreate,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    domain_dao: Annotated[WebsiteDomainDAO, Depends(get_domain_dao)],
):
    """Add a custom domain to a website. Returns DNS verification instructions."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Validate domain format
    is_valid, error_msg = validate_domain(request.domain)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": error_msg, "field": "domain"},
        )

    domain_lower = request.domain.lower().strip()

    # Check if domain already exists
    exists = await domain_dao.domain_exists(domain_lower)
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Domain is already registered",
        )

    # Generate verification token
    verification_token = generate_verification_token()
    record_name, record_value = generate_dns_verification_record(domain_lower, verification_token)

    # Create domain record
    domain_data = {
        "website_id": website_id,
        "domain": domain_lower,
        "ssl_enabled": False,
        "verification_status": "pending",
        "verification_token": verification_token,
    }

    domain = await domain_dao.add(domain_data)

    return DomainVerificationResponse(
        domain=domain.domain,
        verification_token=domain.verification_token,
        verification_status=domain.verification_status,
        dns_record_name=record_name,
        dns_record_value=record_value,
        instructions=(
            f"Add a TXT record to your DNS with name '{record_name}' "
            f"and value '{record_value}'. Then call the verify endpoint."
        ),
    )


@router.post("/{website_id}/domains/{domain_id}/verify", response_model=DomainVerificationResult)
async def verify_domain(
    website_id: int,
    domain_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    domain_dao: Annotated[WebsiteDomainDAO, Depends(get_domain_dao)],
):
    """Trigger verification of a domain (DNS TXT record check).

    This endpoint performs a DNS lookup to verify the TXT record
    containing the verification token is correctly configured.
    """
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    domain = await domain_dao.find_one_by_filter(id=domain_id, website_id=website_id)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found",
        )

    # Skip if already verified
    if domain.verification_status == "verified":
        return DomainVerificationResult(
            domain=domain.domain,
            verification_status="verified",
            message="Domain is already verified",
        )

    # Perform DNS verification
    is_verified, error_message = verify_dns_txt_record(
        domain.domain,
        domain.verification_token or ""
    )

    if is_verified:
        await domain_dao.mark_verified(domain)
        return DomainVerificationResult(
            domain=domain.domain,
            verification_status="verified",
            message="Domain verified successfully",
        )
    else:
        await domain_dao.mark_failed(domain, error_message)
        return DomainVerificationResult(
            domain=domain.domain,
            verification_status="failed",
            message=f"Verification failed: {error_message}",
        )


@router.delete("/{website_id}/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_domain(
    website_id: int,
    domain_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    domain_dao: Annotated[WebsiteDomainDAO, Depends(get_domain_dao)],
):
    """Remove a custom domain from a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    domain = await domain_dao.find_one_by_filter(id=domain_id, website_id=website_id)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found",
        )

    await domain_dao.delete(domain)
    return None


# ---------------------------------------------------------------------------
# AI Generation Endpoints
# ---------------------------------------------------------------------------

async def _get_agent_services(agent_id: int) -> list[dict]:
    """Fetch services from Agent admin template."""
    async with async_session_maker() as session:
        query = select(AdminService).where(
            AdminService.agent_id == agent_id,
            AdminService.is_active == True
        )
        result = await session.execute(query)
        services = result.scalars().all()
        return [
            {
                "name": s.title,
                "description": f"Длительность: {s.duration_minutes} мин",
                "price": f"{s.price_minor / 100:.0f} ₽" if s.price_minor > 0 else "По запросу",
            }
            for s in services
        ]


async def _get_agent_contacts(agent_id: int) -> dict[str, str]:
    """Fetch contact info from Agent channels."""
    contacts = {}
    async with async_session_maker() as session:
        # Get Telegram channel connection
        query = select(AgentChannelConnection).where(
            AgentChannelConnection.agent_id == agent_id,
            AgentChannelConnection.provider == "telegram",
            AgentChannelConnection.is_active == True
        )
        result = await session.execute(query)
        tg_conn = result.scalar_one_or_none()
        if tg_conn and tg_conn.external_id:
            contacts["telegram"] = tg_conn.external_id.replace("@", "")

        # TODO: Add WhatsApp, phone lookup from other sources
        return contacts


async def _log_website_builder_failure(
    *,
    scenario: str,
    message: str,
    website_id: int | None = None,
    export_id: str | None = None,
    exc: BaseException | None = None,
    context: dict | None = None,
) -> None:
    """Persist website builder failures to admin application logs."""
    ctx = dict(context or {})
    if website_id is not None:
        ctx["website_id"] = website_id
    if export_id is not None:
        ctx["export_id"] = export_id
    await record_error_log(
        exc=exc or RuntimeError(message),
        source="worker",
        scenario=scenario,
        level="error",
        context=ctx,
    )


async def _run_website_generation(
    website_id: int,
    request: WebsiteGenerateRequest,
    service: WebsiteGenerationService,
) -> None:
    """Background task for AI website generation.

    This function handles AI website generation with comprehensive logging.
    Each website must be uniquely generated by AI - no template fallbacks.
    If generation fails, the website remains empty with 'failed' status.
    """
    logger.info(f"[WebsiteGen] Starting generation for website_id={website_id}")

    # Step 1: Set generating status
    try:
        async with async_session_maker() as session:
            async with session.begin():
                website_dao = WebsiteDAO(session)
                website = await website_dao.find_one_by_filter(id=website_id)
                if not website:
                    logger.error(f"[WebsiteGen] Website not found: {website_id}")
                    return
                await website_dao.set_generation_status(website, "generating")
                logger.info(f"[WebsiteGen] Status set to 'generating' for website_id={website_id}")
    except Exception as e:
        logger.exception(f"[WebsiteGen] Failed to set generating status: {e}")
        await _log_website_builder_failure(
            scenario=f"Website AI generation: failed to start (website_id={website_id})",
            message=str(e),
            website_id=website_id,
            exc=e,
            context={"business_name": request.business_name, "agent_id": request.agent_id},
        )
        return

    # Step 2: Gather agent data if linked
    services = []
    contacts = {}
    if request.agent_id:
        try:
            services = await _get_agent_services(request.agent_id)
            logger.info(f"[WebsiteGen] Fetched {len(services)} services for agent_id={request.agent_id}")
        except Exception as e:
            logger.warning(f"[WebsiteGen] Failed to fetch agent services: {e}")

        try:
            contacts = await _get_agent_contacts(request.agent_id)
            logger.info(f"[WebsiteGen] Fetched contacts for agent_id={request.agent_id}: {list(contacts.keys())}")
        except Exception as e:
            logger.warning(f"[WebsiteGen] Failed to fetch agent contacts: {e}")

    # Step 3: Run AI generation
    result = None
    generation_exc: Exception | None = None
    try:
        logger.info(f"[WebsiteGen] Calling AI generation for website_id={website_id}")
        result = await service.generate_website(
            business_name=request.business_name,
            business_description=request.business_description,
            services=services if services else None,
            contacts=contacts if contacts else None,
            primary_color=request.primary_color,
            dark_mode=request.dark_mode,
            generation_brief=request.generation_brief,
        )
        logger.info(f"[WebsiteGen] AI generation completed. Success={result.success if result else False}")
    except Exception as e:
        generation_exc = e
        logger.exception(f"[WebsiteGen] AI generation threw exception: {e}")

    # Step 4: Apply results or mark as failed
    try:
        async with async_session_maker() as session:
            async with session.begin():
                website_dao = WebsiteDAO(session)
                website = await website_dao.find_one_by_filter(id=website_id)
                if not website:
                    logger.error(f"[WebsiteGen] Website not found after generation: {website_id}")
                    return

                # Check if generation was successful
                if result and result.success and result.html_content:
                    # Apply generated HTML
                    logger.info(f"[WebsiteGen] Applying generated HTML for website_id={website_id}")
                    success = await service.apply_generated_html(
                        website_id, result.html_content, result.meta or {}
                    )
                    if success:
                        await website_dao.set_generation_status(website, "completed")
                        logger.info(f"[WebsiteGen] Generation completed successfully for website_id={website_id}")
                    else:
                        # apply_generated_html failed - mark as failed
                        error_msg = "AI generated HTML but failed to save to database"
                        logger.error(f"[WebsiteGen] apply_generated_html failed for website_id={website_id}")
                        await _log_website_builder_failure(
                            scenario=f"Website AI generation: save failed (website_id={website_id})",
                            message=error_msg,
                            website_id=website_id,
                            context={
                                "business_name": request.business_name,
                                "agent_id": request.agent_id,
                                "html_length": len(result.html_content or ""),
                            },
                        )
                        await website_dao.set_generation_status(
                            website, "failed",
                            error_message=error_msg
                        )
                else:
                    # AI generation failed - mark as failed (no fallback)
                    if generation_exc is not None:
                        error_msg = str(generation_exc)
                    else:
                        error_msg = result.error_message if result else "No result from AI generation"
                    logger.error(f"[WebsiteGen] AI generation failed for website_id={website_id}: {error_msg}")
                    await _log_website_builder_failure(
                        scenario=f"Website AI generation failed (website_id={website_id})",
                        message=error_msg,
                        website_id=website_id,
                        exc=generation_exc,
                        context={
                            "business_name": request.business_name,
                            "agent_id": request.agent_id,
                            "generation_success": bool(result and result.success),
                        },
                    )
                    await website_dao.set_generation_status(
                        website, "failed",
                        error_message=f"AI generation failed: {error_msg}"
                    )
                    logger.info(f"[WebsiteGen] Website marked as failed for website_id={website_id}")
    except Exception as e:
        logger.exception(f"[WebsiteGen] Failed to apply results: {e}")
        await _log_website_builder_failure(
            scenario=f"Website AI generation: apply results failed (website_id={website_id})",
            message=str(e),
            website_id=website_id,
            exc=e,
            context={"business_name": request.business_name, "agent_id": request.agent_id},
        )
        # Try to mark as failed
        try:
            async with async_session_maker() as session:
                async with session.begin():
                    website_dao = WebsiteDAO(session)
                    website = await website_dao.find_one_by_filter(id=website_id)
                    if website:
                        await website_dao.set_generation_status(
                            website, "failed", error_message=str(e)[:500]
                        )
        except Exception:
            logger.exception(f"[WebsiteGen] Critical: Failed to update status after all retries for {website_id}")




@router.post("/{website_id}/generate", response_model=WebsiteGenerationStartResponse)
async def generate_website(
    website_id: int,
    request: WebsiteGenerateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Start AI generation for an existing website (runs in background).

    This endpoint queues the website for AI generation using DeepSeek.
    Generation runs asynchronously and updates the website's generation_status.
    Use GET /{website_id}/generation-status to check progress.
    """
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Check if already generating
    if website.generation_status == "queued" or website.generation_status == "generating":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Generation already in progress (status: {website.generation_status})",
        )

    # Set queued status
    await website_dao.set_generation_status(website, "queued")

    # Start background generation
    service = get_website_generation_service()
    background_tasks.add_task(_run_website_generation, website_id, request, service)

    return WebsiteGenerationStartResponse(
        website_id=website_id,
        message="Website generation queued. Check generation-status endpoint for progress.",
        generation_status="queued",
    )


@router.post("/generate/create-and-generate", response_model=WebsiteGenerationStartResponse, status_code=status.HTTP_201_CREATED)
async def create_and_generate_website(
    request: WebsiteGenerateRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Create a new website and immediately start AI generation.

    This is a convenience endpoint that:
    1. Creates a new website with auto-generated slug
    2. Queues it for AI generation
    """
    # Auto-generate slug from business name
    slug = generate_slug_from_name(request.business_name)

    # Ensure slug uniqueness
    counter = 1
    base_slug = slug
    while await website_dao.slug_exists(slug):
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 1000:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate unique slug",
            )

    # Build custom styles with user preferences
    custom_styles = {}
    if request.primary_color:
        custom_styles["primaryColor"] = request.primary_color
    if request.dark_mode:
        custom_styles["darkMode"] = True
        custom_styles["mode"] = "dark"

    # Create website
    website_data = {
        "owner_id": user.id,
        "agent_id": request.agent_id,
        "template_id": None,
        "slug": slug,
        "title": request.business_name,
        "status": "draft",
        "generation_status": "queued",
        "custom_styles": custom_styles,
    }

    website = await website_dao.add(website_data)

    # Flush to get the website ID before returning
    await website_dao._session.flush()
    website_id = website.id

    # Ensure the newly created website is committed before background generation starts.
    # Otherwise the background task may run in another session and not see this row yet.
    await website_dao._session.commit()

    # Start background generation
    service = get_website_generation_service()
    background_tasks.add_task(_run_website_generation, website_id, request, service)

    return WebsiteGenerationStartResponse(
        website_id=website_id,
        message=f"Website created and generation queued. Slug: {slug}",
        generation_status="queued",
    )


@router.get("/{website_id}/generation-status", response_model=WebsiteGenerationStatusResponse)
async def get_generation_status(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Get the current generation status for a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    status_data = await website_dao.get_generation_status(website_id)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not retrieve generation status",
        )

    return WebsiteGenerationStatusResponse(
        website_id=status_data["website_id"],
        generation_status=status_data["generation_status"],
        status=status_data["status"],
        updated_at=status_data["updated_at"],
        error=status_data.get("error"),
    )


# ---------------------------------------------------------------------------
# Public / Preview Endpoints
# ---------------------------------------------------------------------------

@router.get("/{website_id}/schema", response_model=WebsiteSchemaResponse)
async def get_website_schema(
    website_id: int,
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Get the complete schema for rendering a website (public endpoint)."""
    website = await website_dao.get_by_id_with_relations(website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    # Only published websites are accessible
    if website.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    # Merge styles from template and custom
    styles = {}
    if website.template:
        styles.update(website.template.default_styles or {})
    styles.update(website.custom_styles or {})

    # Build blocks list
    blocks = await block_dao.list_by_website(website_id, only_visible=True)
    blocks_data = [
        {
            "id": b.id,
            "type": b.type,
            "order": b.order,
            "content": b.content,
            "styles": b.styles,
        }
        for b in blocks
    ]

    agent_payload = await _build_schema_agent_payload(website, include_widget_key=True)

    return WebsiteSchemaResponse(
        id=website.id,
        slug=website.slug,
        title=website.title,
        meta_description=website.meta_description,
        og_title=website.og_title,
        og_description=website.og_description,
        og_image_url=website.og_image_url,
        favicon_url=website.favicon_url,
        status=website.status,
        styles=styles,
        blocks=blocks_data,
        agent_id=website.agent_id,
        agent=agent_payload,
    )


@router.get("/by-slug/{slug}/schema", response_model=WebsiteSchemaResponse)
async def get_website_schema_by_slug(
    slug: str,
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Get website schema by slug (for public access via rsd-ai.ru/{slug})."""
    if not is_valid_slug(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid slug format",
        )

    website = await website_dao.get_by_slug_with_relations(slug)

    if not website or website.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    # Merge styles from template and custom
    styles = {}
    if website.template:
        styles.update(website.template.default_styles or {})
    styles.update(website.custom_styles or {})

    # Build blocks list
    blocks = await block_dao.list_by_website(website.id, only_visible=True)
    blocks_data = [
        {
            "id": b.id,
            "type": b.type,
            "order": b.order,
            "content": b.content,
            "styles": b.styles,
        }
        for b in blocks
    ]

    agent_payload = await _build_schema_agent_payload(website, include_widget_key=True)

    return WebsiteSchemaResponse(
        id=website.id,
        slug=website.slug,
        title=website.title,
        meta_description=website.meta_description,
        og_title=website.og_title,
        og_description=website.og_description,
        og_image_url=website.og_image_url,
        favicon_url=website.favicon_url,
        status=website.status,
        styles=styles,
        blocks=blocks_data,
        agent_id=website.agent_id,
        agent=agent_payload,
    )


@router.get("/by-domain/{domain}/schema", response_model=WebsiteSchemaResponse)
async def get_website_schema_by_domain(
    domain: str,
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    domain_dao: Annotated[WebsiteDomainDAO, Depends(get_domain_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Get website schema by custom domain (for public access via custom domain).

    This endpoint is used when a website is accessed through a custom domain
    that has been verified and linked to the website.
    """
    # Validate domain format
    is_valid, error_msg = validate_domain(domain)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # Get verified domain record
    domain_record = await domain_dao.get_verified_by_domain(domain)

    if not domain_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found or not verified",
        )

    # Get website by ID from domain record
    website = await website_dao.get_by_id_with_relations(domain_record.website_id)

    if not website or website.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found or not published",
        )

    # Merge styles from template and custom
    styles = {}
    if website.template:
        styles.update(website.template.default_styles or {})
    styles.update(website.custom_styles or {})

    # Build blocks list
    blocks = await block_dao.list_by_website(website.id, only_visible=True)
    blocks_data = [
        {
            "id": b.id,
            "type": b.type,
            "order": b.order,
            "content": b.content,
            "styles": b.styles,
        }
        for b in blocks
    ]

    agent_payload = await _build_schema_agent_payload(website, include_widget_key=True)

    return WebsiteSchemaResponse(
        id=website.id,
        slug=website.slug,
        title=website.title,
        meta_description=website.meta_description,
        og_title=website.og_title,
        og_description=website.og_description,
        og_image_url=website.og_image_url,
        favicon_url=website.favicon_url,
        status=website.status,
        styles=styles,
        blocks=blocks_data,
        agent_id=website.agent_id,
        agent=agent_payload,
    )


# ---------------------------------------------------------------------------
# Export (ZIP Archive)
# ---------------------------------------------------------------------------

# In-memory store for export jobs (use Redis in production for distributed setups)
_export_jobs: dict[str, dict] = {}


def _generate_export_id(website_id: int) -> str:
    """Generate unique export job ID."""
    timestamp = int(datetime.now(timezone.utc).timestamp())
    return f"exp_{website_id}_{timestamp}_{os.urandom(4).hex()}"


async def _run_website_export(
    export_id: str,
    website_id: int,
    website_data: dict,
    agent_contacts: dict | None,
    widget_config: dict | None,
) -> None:
    """Background task for website export."""
    try:
        _export_jobs[export_id]["status"] = "processing"
        _export_jobs[export_id]["progress_percent"] = 20

        service = get_website_export_service()

        _export_jobs[export_id]["progress_percent"] = 40

        result = await service.export_website(
            website_id=website_id,
            website_data=website_data,
            agent_contacts=agent_contacts,
            widget_config=widget_config,
        )

        _export_jobs[export_id]["progress_percent"] = 80

        if result.success:
            _export_jobs[export_id]["status"] = "completed"
            _export_jobs[export_id]["archive_path"] = result.archive_path
            _export_jobs[export_id]["archive_size_bytes"] = result.archive_size_bytes
            _export_jobs[export_id]["files_included"] = result.files_included
            _export_jobs[export_id]["download_url"] = result.download_url
            _export_jobs[export_id]["completed_at"] = datetime.now(timezone.utc)
            _export_jobs[export_id]["expires_at"] = datetime.now(timezone.utc) + timedelta(hours=EXPORT_TTL_HOURS)
            _export_jobs[export_id]["progress_percent"] = 100
            logger.info(f"Export completed: {export_id}, archive: {result.archive_path}")
        else:
            _export_jobs[export_id]["status"] = "failed"
            error_msg = result.error_message or "Unknown export error"
            _export_jobs[export_id]["error_message"] = error_msg
            logger.error(f"Export failed: {export_id}, error: {error_msg}")
            await _log_website_builder_failure(
                scenario=f"Website export failed (website_id={website_id})",
                message=error_msg,
                website_id=website_id,
                export_id=export_id,
            )

    except Exception as e:
        logger.exception(f"Export task failed: {export_id}: {e}")
        _export_jobs[export_id]["status"] = "failed"
        _export_jobs[export_id]["error_message"] = str(e)[:500]
        await _log_website_builder_failure(
            scenario=f"Website export exception (website_id={website_id})",
            message=str(e),
            website_id=website_id,
            export_id=export_id,
            exc=e,
        )


@router.post("/{website_id}/export", response_model=WebsiteExportStartResponse)
async def export_website(
    website_id: int,
    request: WebsiteExportStartRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
):
    """Export a website as a ZIP archive.

    This endpoint starts an asynchronous export process that generates a ZIP archive
    containing static HTML/CSS/JS files ready for deployment to any static hosting.
    """
    website = await website_dao.get_by_id_with_relations(website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Generate export ID
    export_id = _generate_export_id(website_id)

    # Initialize export job
    _export_jobs[export_id] = {
        "website_id": website_id,
        "status": "pending",
        "progress_percent": 0,
        "created_at": datetime.now(timezone.utc),
    }

    # Merge styles
    styles = {}
    if website.template:
        styles.update(website.template.default_styles or {})
    styles.update(website.custom_styles or {})

    # Get blocks
    blocks = await block_dao.list_by_website(website.id, only_visible=True)
    blocks_data = [
        {
            "id": b.id,
            "type": b.type,
            "order": b.order,
            "content": b.content,
            "styles": b.styles,
        }
        for b in blocks
    ]

    # Build website data for export
    website_data = {
        "id": website.id,
        "slug": website.slug,
        "title": website.title or website.slug,
        "meta_description": website.meta_description or "",
        "og_title": website.og_title or (website.title or website.slug),
        "og_description": website.og_description or (website.meta_description or ""),
        "og_image_url": website.og_image_url,
        "favicon_url": website.favicon_url,
        "styles": styles,
        "blocks": blocks_data,
    }

    # Get agent contacts if website is linked to an agent
    agent_contacts = None
    widget_config = None
    if website.agent_id and request.include_widget:
        # Get agent public data
        try:
            agent_data = await get_agent_public_data(website.agent_id, include_widget_key=True)
            if agent_data:
                agent_contacts = agent_data.get("contacts", {})
                widget_config = {
                    "agent_id": website.agent_id,
                    "api_key": agent_data.get("widget_api_key", ""),
                }
        except Exception as e:
            logger.warning(f"Failed to get agent data for export: {e}")

    # Start background export
    background_tasks.add_task(
        _run_website_export,
        export_id,
        website_id,
        website_data,
        agent_contacts,
        widget_config if request.include_widget else None,
    )

    return WebsiteExportStartResponse(
        website_id=website_id,
        export_id=export_id,
        message="Export started. Check export-status endpoint for progress.",
        status="pending",
    )


@router.get("/{website_id}/export-status", response_model=WebsiteExportStatusResponse)
async def get_export_status(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    export_id: str = Query(..., description="Export job ID"),
):
    """Get the status of an export job."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    job = _export_jobs.get(export_id)
    if not job or job.get("website_id") != website_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export job not found",
        )

    return WebsiteExportStatusResponse(
        website_id=website_id,
        export_id=export_id,
        status=job.get("status", "unknown"),
        progress_percent=job.get("progress_percent", 0),
        created_at=job.get("created_at"),
        completed_at=job.get("completed_at"),
        error_message=job.get("error_message"),
        download_url=job.get("download_url") if job.get("status") == "completed" else None,
        expires_at=job.get("expires_at"),
        archive_size_bytes=job.get("archive_size_bytes"),
    )


@router.get("/{website_id}/download")
async def download_export(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    token: str = Query(..., description="Download token"),
):
    """Download the exported ZIP archive.

    The token parameter is used to verify the download request.
    The archive is deleted after download to free up space.
    """
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Find the export job by token (export_id)
    job = _export_jobs.get(token)
    if not job or job.get("website_id") != website_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export not found or expired",
        )

    if job.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export not ready",
        )

    archive_path = job.get("archive_path")
    if not archive_path or not os.path.exists(archive_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archive file not found or expired",
        )

    # Return the file
    filename = f"website-{website.slug}.zip"

    return FileResponse(
        path=archive_path,
        filename=filename,
        media_type="application/zip",
    )


# ---------------------------------------------------------------------------
# SEO / Meta Data Management
# ---------------------------------------------------------------------------

@router.get("/{website_id}/seo/preview", response_model=SEOPreviewResponse)
async def get_seo_preview(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Get SEO preview for Google SERP and social sharing."""
    website = await website_dao.get_by_id_with_relations(website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Build SEO preview
    title = website.og_title or website.title or website.slug
    description = website.og_description or website.meta_description or ""

    # Truncate for display
    google_title = title[:70] if len(title) > 70 else title
    google_description = description[:160] if len(description) > 160 else description

    # Calculate lengths and statuses
    title_len = len(title) if title else 0
    desc_len = len(description) if description else 0

    if 30 <= title_len <= 60:
        title_status = "good"
    elif title_len < 30 or 60 < title_len <= 70:
        title_status = "warning"
    else:
        title_status = "error"

    if 120 <= desc_len <= 160:
        desc_status = "good"
    elif desc_len < 120 or 160 < desc_len <= 180:
        desc_status = "warning"
    else:
        desc_status = "error"

    # Build warnings
    warnings = []
    if title_len < 30:
        warnings.append(f"Title is too short ({title_len} chars). Recommended: 30-60 characters.")
    elif title_len > 60:
        warnings.append(f"Title is too long ({title_len} chars). May be truncated in search results.")

    if desc_len < 120:
        warnings.append(f"Description is too short ({desc_len} chars). Recommended: 120-160 characters.")
    elif desc_len > 160:
        warnings.append(f"Description is too long ({desc_len} chars). May be truncated in search results.")

    if not website.og_image_url:
        warnings.append("No OpenGraph image set. Social shares may appear without preview image.")

    if not website.favicon_url:
        warnings.append("No favicon set. Browser tab will show default icon.")

    # Build URL preview
    from ..config.website_domains import BASE_DOMAIN
    url_preview = f"https://{BASE_DOMAIN}/w/{website.slug}"

    return SEOPreviewResponse(
        google_title=google_title,
        google_description=google_description,
        google_url=url_preview,
        google_title_length=title_len,
        google_description_length=desc_len,
        google_title_status=title_status,
        google_description_status=desc_status,
        telegram_title=title[:100],
        telegram_description=description[:200],
        telegram_image_url=website.og_image_url,
        warnings=warnings,
    )


@router.post("/{website_id}/favicon", response_model=FaviconUploadResponse)
async def upload_favicon(
    website_id: int,
    file: Annotated[UploadFile, File(...)],
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Upload and convert favicon to multiple sizes.

    Accepts PNG, JPG, SVG, ICO files and converts them to:
    - favicon.ico (16x16, 32x32, 48x48 combined)
    - Individual PNG files: 16x16, 32x32, 64x64, 128x128, 180x180 (Apple touch), 192x192, 256x256
    """
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"}
    content_type = file.content_type or ""

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPG, SVG, ICO. Got: {content_type}"
        )

    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Read file content
    file_content = await file.read()

    if len(file_content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size: 5MB"
        )

    # Convert favicon
    import io
    seo_service = get_website_seo_service()

    result = seo_service.convert_favicon(
        image_data=io.BytesIO(file_content),
        original_filename=file.filename or "favicon.png",
        website_id=website_id,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "Favicon conversion failed"
        )

    # Update website with favicon URL (pointing to the ICO file)
    ico_path = result.files.get("favicon.ico", "")
    if ico_path:
        favicon_url = f"/assets/websites/{website_id}/{os.path.basename(ico_path)}"
        await website_dao.update(website, {
            "favicon_url": favicon_url,
            "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)
        })

    sizes_generated = list(result.files.keys())

    return FaviconUploadResponse(
        success=True,
        favicon_url=website.favicon_url,
        sizes_generated=sizes_generated,
        message=f"Favicon converted successfully. Generated {len(sizes_generated)} sizes.",
    )


@router.post("/{website_id}/og-image/upload", response_model=OGImageUploadResponse)
async def upload_og_image(
    website_id: int,
    file: Annotated[UploadFile, File(...)],
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Upload custom OpenGraph image (1200x630 recommended).

    This image will be displayed when the website is shared on social media.
    Recommended size: 1200x630 pixels, PNG or JPG format.
    """
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    content_type = file.content_type or ""

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: PNG, JPG, WebP. Got: {content_type}"
        )

    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Read and validate file
    file_content = await file.read()

    if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size: 10MB"
        )

    # Save file
    import uuid
    ext = "png" if "png" in content_type else "jpg"
    filename = f"og-image-custom-{uuid.uuid4().hex[:8]}.{ext}"

    seo_service = get_website_seo_service()
    filepath = os.path.join(seo_service.og_image_path, str(website_id), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(file_content)

    # Update website
    og_url = f"/assets/websites/{website_id}/og_images/{filename}"
    await website_dao.update(website, {
        "og_image_url": og_url,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)
    })

    return OGImageUploadResponse(
        success=True,
        og_image_url=og_url,
        message="OpenGraph image uploaded successfully",
    )


@router.post("/{website_id}/og-image/generate", response_model=OGImageGenerateResponse)
async def generate_og_image(
    website_id: int,
    request: OGImageGenerateRequest,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Auto-generate OpenGraph image from template.

    Creates a 1200x630 image with the website title and description.
    Uses the website's color scheme if available.
    """
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get colors from website styles
    primary_color = request.background_color or "#3B82F6"
    text_color = request.text_color or "#FFFFFF"

    if website.custom_styles:
        primary_color = website.custom_styles.get("primaryColor", primary_color)

    # Generate image
    seo_service = get_website_seo_service()

    result = seo_service.generate_og_image(
        title=request.title,
        description=request.description,
        website_id=website_id,
        background_color=primary_color,
        text_color=text_color,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "OG image generation failed"
        )

    # Save generated image
    import uuid
    filename = f"og-image-generated-{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(seo_service.og_image_path, str(website_id), filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(result.image_bytes or b"")

    # Update website
    og_url = f"/assets/websites/{website_id}/og_images/{filename}"
    await website_dao.update(website, {
        "og_image_url": og_url,
        "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)
    })

    return OGImageGenerateResponse(
        success=True,
        og_image_url=og_url,
        message="OpenGraph image generated successfully",
    )


@router.get("/{website_id}/seo/meta", response_model=SEOMetaDataResponse)
async def get_seo_meta(
    website_id: int,
    user: Annotated[User, Depends(get_current_user)],
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
):
    """Get current SEO metadata for a website."""
    website = await website_dao.find_one_by_filter(id=website_id)

    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )

    if website.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return SEOMetaDataResponse(
        website_id=website.id,
        title=website.title,
        meta_description=website.meta_description,
        og_title=website.og_title,
        og_description=website.og_description,
        og_image_url=website.og_image_url,
        favicon_url=website.favicon_url,
    )
