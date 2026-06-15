"""Default SEO asset helpers for generated/published websites."""
from __future__ import annotations

from ..alembic.models import Website
from ..router_websites.dao import WebsiteDAO
from .website_seo_service import WebsiteSEOService, get_website_seo_service


def resolve_primary_color(website: Website, override: str | None = None) -> str:
    if override:
        return override
    styles = website.custom_styles or {}
    return styles.get("primaryColor") or "#2563EB"


async def ensure_default_favicon(
    website_dao: WebsiteDAO,
    website: Website,
    *,
    primary_color: str | None = None,
    seo_service: WebsiteSEOService | None = None,
) -> str | None:
    """Create a letter favicon when the site has none yet."""
    if website.favicon_url:
        return website.favicon_url

    service = seo_service or get_website_seo_service()
    result = service.generate_letter_favicon(
        website_id=website.id,
        title=website.title or website.slug or "Site",
        background_color=resolve_primary_color(website, primary_color),
    )
    if not result.success:
        return None

    favicon_url = service.favicon_url_from_result(website.id, result)
    if not favicon_url:
        return None

    await website_dao.update(website, {"favicon_url": favicon_url})
    return favicon_url
