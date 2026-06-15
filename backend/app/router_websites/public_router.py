"""Public website endpoints for custom domain and subdomain access (Stage 7)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from typing import Annotated

from ..alembic.database import async_session_maker
from ..alembic.models import Website, WebsiteDomain
from ..utils.rate_limit import rate_limit

from .dao import WebsiteDAO, WebsiteBlockDAO, WebsiteDomainDAO
from .schemas import WebsiteSchemaResponse
from .utils import (
    extract_website_slug_from_host,
    is_system_domain,
    is_valid_slug,
)
from ..services.agent_public_data import get_agent_public_data

from ..config.website_domains import BASE_DOMAIN

router = APIRouter()

# Rate limit for public website access
_PUBLIC_RATE = Depends(rate_limit(max_requests=100, window_seconds=60, scope="websites_public"))

# System domains that should not be treated as website domains
SYSTEM_DOMAINS = {
    "rsd-ai.ru",
    "www.rsd-ai.ru",
    "api.rsd-ai.ru",
    "admin.rsd-ai.ru",
    "staging.rsd-ai.ru",
    "dev.rsd-ai.ru",
}

async def _build_schema_agent_payload(website: Website, *, include_widget_key: bool) -> dict | None:
    """Build agent payload for website schema."""
    if not website.agent_id:
        return None
    data = await get_agent_public_data(website.agent_id, include_widget_key=include_widget_key)
    return data


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


def detect_website_slug_from_request(request: Request) -> str | None:
    """Detect website slug from request (Host header or path).

    This function implements the logic for Stage 7 subdomain support:
    1. Check Host header for subdomain pattern (e.g., mysite.rsd-ai.ru)
    2. Fall back to path-based detection if needed

    Args:
        request: FastAPI request object

    Returns:
        Website slug if detected, None otherwise
    """
    host = request.headers.get("host", "")

    # Skip if it's a system domain
    if is_system_domain(host, SYSTEM_DOMAINS):
        return None

    # Try to extract slug from subdomain (e.g., mysite.rsd-ai.ru -> mysite)
    slug = extract_website_slug_from_host(host, BASE_DOMAIN)
    if slug:
        return slug

    # Check if host is exactly the base domain with a valid slug path
    # e.g., rsd-ai.ru/mysite -> mysite
    if host.lower().split(":")[0] == BASE_DOMAIN:
        # Could extract from path if needed
        pass

    return None


async def resolve_website_by_host(
    host: str,
    website_dao: WebsiteDAO,
    domain_dao: WebsiteDomainDAO,
) -> Website | None:
    """Resolve website by Host header.

    This function handles both:
    1. Subdomain routing (e.g., mysite.rsd-ai.ru)
    2. Custom domain routing (e.g., example.com)

    Args:
        host: Host header value
        website_dao: Website DAO instance
        domain_dao: WebsiteDomain DAO instance

    Returns:
        Website instance if found and published, None otherwise
    """
    # Remove port if present
    if ":" in host:
        host = host.split(":")[0]

    host = host.lower().strip()

    # Skip system domains
    if is_system_domain(host, SYSTEM_DOMAINS):
        return None

    # 1. Try subdomain routing (e.g., mysite.rsd-ai.ru)
    slug = extract_website_slug_from_host(host, BASE_DOMAIN)
    if slug:
        website = await website_dao.get_by_slug_with_relations(slug)
        if website and website.status == "published":
            return website

    # 2. Try custom domain routing (e.g., example.com)
    # Look for verified domain record
    domain_record = await domain_dao.get_verified_by_domain(host)
    if domain_record:
        website = await website_dao.get_by_id_with_relations(domain_record.website_id)
        if website and website.status == "published":
            return website

    return None


@router.get("/schema", response_model=WebsiteSchemaResponse)
async def get_website_schema_by_host(
    request: Request,
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    domain_dao: Annotated[WebsiteDomainDAO, Depends(get_domain_dao)],
    block_dao: Annotated[WebsiteBlockDAO, Depends(get_block_dao)],
    _: None = _PUBLIC_RATE,
):
    """Get website schema by Host header (for custom domain/subdomain access).

    This endpoint is the main entry point for Stage 7 custom domain support.
    It detects the website based on the Host header and returns the schema.

    Usage:
    - Custom domain: Host: example.com -> returns website linked to example.com
    - Subdomain: Host: mysite.rsd-ai.ru -> returns website with slug "mysite"
    """
    host = request.headers.get("host", "")

    if not host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host header is required",
        )

    # Resolve website by host
    website = await resolve_website_by_host(host, website_dao, domain_dao)

    if not website:
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


@router.get("/health")
async def health_check():
    """Health check endpoint for domain routing."""
    return {"status": "ok", "service": "website-public"}


def _format_sitemap_lastmod(value: datetime | None) -> str:
    if not value:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


@router.get("/sitemap-websites.xml", response_class=Response)
async def get_websites_sitemap(
    website_dao: Annotated[WebsiteDAO, Depends(get_website_dao)],
    _: None = _PUBLIC_RATE,
):
    """Dynamic sitemap of all published client websites."""
    websites = await website_dao.list_published_for_sitemap()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for website in websites:
        loc = f"https://{BASE_DOMAIN}/w/{website.slug}"
        lastmod = _format_sitemap_lastmod(website.updated_at or website.published_at)
        lines.extend(
            [
                "  <url>",
                f"    <loc>{loc}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ]
        )

    lines.append("</urlset>")
    return Response(
        content="\n".join(lines),
        media_type="application/xml; charset=utf-8",
    )
