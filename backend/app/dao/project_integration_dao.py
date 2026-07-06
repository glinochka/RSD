"""Data Access Object for Project Integration entities."""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import ProjectIntegration, ProjectExternalEvent


class ProjectIntegrationDAO:
    """DAO for project integrations and external events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    async def list_by_project(session: AsyncSession, project_id: int) -> list[ProjectIntegration]:
        result = await session.execute(
            select(ProjectIntegration)
            .where(ProjectIntegration.project_id == project_id)
            .order_by(ProjectIntegration.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_by_id(session: AsyncSession, integration_id: int) -> Optional[ProjectIntegration]:
        result = await session.execute(
            select(ProjectIntegration).where(ProjectIntegration.id == integration_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_token(session: AsyncSession, token: str) -> Optional[ProjectIntegration]:
        result = await session.execute(
            select(ProjectIntegration).where(ProjectIntegration.webhook_token == token)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        project_id: int,
        name: str,
        type: str,
        config: dict,
        encrypted_credentials: str,
        webhook_token: str,
    ) -> ProjectIntegration:
        integration = ProjectIntegration(
            project_id=project_id,
            name=name,
            type=type,
            config=config,
            encrypted_credentials=encrypted_credentials,
            webhook_token=webhook_token,
            is_active=True,
        )
        session.add(integration)
        await session.flush()
        return integration

    @staticmethod
    async def update(
        session: AsyncSession,
        integration: ProjectIntegration,
        name: Optional[str] = None,
        type: Optional[str] = None,
        config: Optional[dict] = None,
        encrypted_credentials: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> ProjectIntegration:
        if name is not None:
            integration.name = name
        if type is not None:
            integration.type = type
        if config is not None:
            integration.config = config
        if encrypted_credentials is not None:
            integration.encrypted_credentials = encrypted_credentials
        if is_active is not None:
            integration.is_active = is_active
        await session.flush()
        return integration

    @staticmethod
    async def delete(session: AsyncSession, integration: ProjectIntegration) -> None:
        await session.delete(integration)

    @staticmethod
    async def count_events_by_project(
        session: AsyncSession,
        project_id: int,
        limit: int = 50,
    ) -> list[ProjectExternalEvent]:
        result = await session.execute(
            select(ProjectExternalEvent)
            .where(ProjectExternalEvent.project_id == project_id)
            .order_by(ProjectExternalEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def add_event(
        session: AsyncSession,
        project_id: int,
        integration_id: Optional[int],
        event_type: str,
        source: str,
        payload: dict,
    ) -> ProjectExternalEvent:
        event = ProjectExternalEvent(
            project_id=project_id,
            integration_id=integration_id,
            event_type=event_type,
            source=source,
            payload=payload,
        )
        session.add(event)
        await session.flush()
        return event
