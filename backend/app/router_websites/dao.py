"""DAO layer for Website Builder."""
from datetime import datetime, timezone

from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import joinedload, selectinload

from ..alembic.models import Website, WebsiteBlock, WebsiteTemplate, WebsiteDomain
from ..BaseDAO import BaseDAO


class WebsiteTemplateDAO(BaseDAO):
    model = WebsiteTemplate

    async def list_active(self) -> list[WebsiteTemplate]:
        query = select(self.model).where(self.model.is_active == True)
        return await self.list_scalars(query)

    async def get_by_name(self, name: str) -> WebsiteTemplate | None:
        query = select(self.model).where(
            self.model.name == name,
            self.model.is_active == True
        )
        return await self._session.scalar(query)


class WebsiteDAO(BaseDAO):
    model = Website
    _GENERATION_LOGS_KEY = "_generation_runtime_logs"

    async def get_by_id_with_relations(self, website_id: int) -> Website | None:
        query = (
            select(self.model)
            .where(self.model.id == website_id)
            .options(
                selectinload(self.model.blocks),
                selectinload(self.model.domains),
                joinedload(self.model.template),
            )
        )
        return await self._session.scalar(query)

    async def get_by_slug(self, slug: str) -> Website | None:
        query = select(self.model).where(self.model.slug == slug)
        return await self._session.scalar(query)

    async def get_by_slug_with_relations(self, slug: str) -> Website | None:
        query = (
            select(self.model)
            .where(self.model.slug == slug)
            .options(
                selectinload(self.model.blocks),
                selectinload(self.model.domains),
                joinedload(self.model.template),
            )
        )
        return await self._session.scalar(query)

    async def list_by_owner(
        self,
        owner_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Website]:
        query = (
            select(self.model)
            .where(self.model.owner_id == owner_id)
            .order_by(desc(self.model.created_at))
        )
        return await self.list_scalars(query, page=page, page_size=page_size)

    async def count_by_owner(self, owner_id: int) -> int:
        query = select(func.count(self.model.id)).where(self.model.owner_id == owner_id)
        return await self.scalar_or_default(query, 0)

    async def slug_exists(self, slug: str) -> bool:
        query = select(func.count(self.model.id)).where(self.model.slug == slug)
        count = await self.scalar_or_default(query, 0)
        return count > 0

    async def get_max_order_for_website(self, website_id: int) -> int:
        query = (
            select(func.coalesce(func.max(WebsiteBlock.order), -1))
            .where(WebsiteBlock.website_id == website_id)
        )
        return await self.scalar_or_default(query, -1)

    async def publish(self, website: Website) -> None:
        website.status = "published"
        website.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
        website.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    async def unpublish(self, website: Website) -> None:
        website.status = "draft"
        website.published_at = None
        website.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    async def set_generation_status(
        self,
        website: Website,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Set the generation status of a website.

        Args:
            website: Website to update
            status: One of 'idle', 'queued', 'generating', 'completed', 'failed'
            error_message: Optional error message for failed status
        """
        website.generation_status = status
        website.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # Store error message in custom_styles temporarily (for failed state)
        if error_message and status == "failed":
            custom_styles = website.custom_styles or {}
            custom_styles["_generation_error"] = error_message[:500]
            website.custom_styles = custom_styles

    async def get_generation_status(self, website_id: int) -> dict | None:
        """Get current generation status for a website.

        Returns:
            Dict with status and optional error message, or None if website not found
        """
        website = await self.find_one_by_filter(id=website_id)
        if not website:
            return None

        result = {
            "website_id": website.id,
            "generation_status": website.generation_status,
            "status": website.status,
            "updated_at": website.updated_at.isoformat() if website.updated_at else None,
            "runtime_logs": [],
        }

        if website.custom_styles:
            logs = website.custom_styles.get(self._GENERATION_LOGS_KEY)
            if isinstance(logs, list):
                result["runtime_logs"] = [str(line) for line in logs if isinstance(line, str)]

            # Include error if present
            if website.generation_status == "failed":
                error = website.custom_styles.get("_generation_error")
                if error:
                    result["error"] = error

        return result


class WebsiteBlockDAO(BaseDAO):
    model = WebsiteBlock

    async def list_by_website(
        self,
        website_id: int,
        only_visible: bool = True,
    ) -> list[WebsiteBlock]:
        query = (
            select(self.model)
            .where(self.model.website_id == website_id)
            .order_by(self.model.order)
        )
        if only_visible:
            query = query.where(self.model.is_visible == True)
        return await self.list_scalars(query)

    async def reorder_blocks(self, website_id: int, block_orders: list[tuple[int, int]]) -> None:
        """Reorder blocks: list of (block_id, new_order) tuples."""
        for block_id, new_order in block_orders:
            block = await self.find_one_by_filter(id=block_id, website_id=website_id)
            if block:
                block.order = new_order
                block.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    async def duplicate_block(self, block: WebsiteBlock) -> WebsiteBlock:
        new_block = WebsiteBlock(
            website_id=block.website_id,
            type=block.type,
            content=block.content.copy(),
            styles=block.styles.copy(),
            is_visible=block.is_visible,
            order=block.order + 1,
        )
        self._session.add(new_block)
        return new_block


class WebsiteDomainDAO(BaseDAO):
    model = WebsiteDomain

    async def list_by_website(self, website_id: int) -> list[WebsiteDomain]:
        query = (
            select(self.model)
            .where(self.model.website_id == website_id)
            .order_by(self.model.created_at)
        )
        return await self.list_scalars(query)

    async def get_by_domain(self, domain: str) -> WebsiteDomain | None:
        query = select(self.model).where(self.model.domain == domain.lower())
        return await self._session.scalar(query)

    async def domain_exists(self, domain: str) -> bool:
        query = select(func.count(self.model.id)).where(
            self.model.domain == domain.lower()
        )
        count = await self.scalar_or_default(query, 0)
        return count > 0

    async def get_verified_by_domain(self, domain: str) -> WebsiteDomain | None:
        query = select(self.model).where(
            and_(
                self.model.domain == domain.lower(),
                self.model.verification_status == "verified"
            )
        )
        return await self._session.scalar(query)

    async def mark_verified(self, domain: WebsiteDomain) -> None:
        from datetime import datetime, timezone
        domain.verification_status = "verified"
        domain.verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
        domain.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    async def mark_failed(self, domain: WebsiteDomain, error: str | None = None) -> None:
        domain.verification_status = "failed"
        domain.dns_check_error = error[:512] if error else None
        domain.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
