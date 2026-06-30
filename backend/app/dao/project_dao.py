"""Data Access Object for Project entity."""
from typing import Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import Project, Agent, Website


class ProjectDAO:
    """DAO for Project CRUD operations."""

    def __init__(self, session: AsyncSession | None = None):
        # Backward compatibility: many call sites instantiate DAO with session,
        # while methods still accept explicit session arguments.
        self.session = session

    @staticmethod
    async def list_by_user(session: AsyncSession, user_id: int) -> list[Project]:
        """List all non-archived projects for a user."""
        result = await session.execute(
            select(Project)
            .where(
                and_(
                    Project.user_id == user_id,
                    Project.status != "archived",
                )
            )
            .order_by(Project.is_default.desc(), Project.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, project_id: int) -> Optional[Project]:
        """Get project by ID."""
        result = await session.execute(
            select(Project).where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(session: AsyncSession, user_id: int, slug: str) -> Optional[Project]:
        """Get project by slug for a specific user."""
        result = await session.execute(
            select(Project).where(
                and_(
                    Project.user_id == user_id,
                    Project.slug == slug,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: int,
        name: str,
        slug: str,
        industry: Optional[str] = None,
        description: Optional[str] = None,
        is_default: bool = False,
    ) -> Project:
        """Create a new project."""
        project = Project(
            user_id=user_id,
            name=name,
            slug=slug,
            industry=industry,
            description=description,
            is_default=is_default,
            status="active",
        )
        session.add(project)
        await session.flush()
        return project

    @staticmethod
    async def update(
        session: AsyncSession,
        project: Project,
        name: Optional[str] = None,
        description: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Project:
        """Update project fields."""
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if industry is not None:
            project.industry = industry
        await session.flush()
        return project

    @staticmethod
    async def archive(session: AsyncSession, project: Project) -> Project:
        """Archive a project (soft delete)."""
        project.status = "archived"
        await session.flush()
        return project

    @staticmethod
    async def get_default_for_user(session: AsyncSession, user_id: int) -> Optional[Project]:
        """Get default project for user."""
        result = await session.execute(
            select(Project).where(
                and_(
                    Project.user_id == user_id,
                    Project.is_default == True,
                    Project.status == "active",
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_agents_count(session: AsyncSession, project_id: int) -> int:
        """Get count of agents in project."""
        result = await session.execute(
            select(func.count(Agent.id)).where(Agent.project_id == project_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_websites_count(session: AsyncSession, project_id: int) -> int:
        """Get count of websites in project."""
        result = await session.execute(
            select(func.count(Website.id)).where(Website.project_id == project_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_primary_website(session: AsyncSession, project_id: int) -> Optional[Website]:
        """Get primary website for project (most recent)."""
        result = await session.execute(
            select(Website)
            .where(Website.project_id == project_id)
            .order_by(Website.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
