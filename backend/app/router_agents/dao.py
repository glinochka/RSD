
from typing import Any

from ..alembic.database import async_session_maker
from ..alembic.models import Agent, AgentChannelConnection, AgentCrmConnection, AgentHttpIntegration, User
from ..BaseDAO import BaseDAO
from ..utils.agent_template_config import parse_agent_template_config
from sqlalchemy import String, cast, desc, func, or_, select


class AgentDAO(BaseDAO):
    model = Agent

    async def find_all_by_user_id(self, user_id: int) -> list[Agent]:
        query = select(self.model).where(self.model.user_id == user_id)
        return await self.list_scalars(query)

    async def find_all_by_user_id_and_project(
        self, user_id: int, project_id: int | None = None
    ) -> list[Agent]:
        """Get agents for user, optionally filtered by project_id."""
        query = select(self.model).where(self.model.user_id == user_id)
        if project_id is not None:
            query = query.where(self.model.project_id == project_id)
        return await self.list_scalars(query)

    async def count_all(self) -> int:
        query = select(func.count(self.model.id))
        return await self.scalar_or_default(query, 0)

    async def count_active(self) -> int:
        query = select(func.count(self.model.id)).where(self.model.is_active.is_(True))
        return await self.scalar_or_default(query, 0)

    async def count_for_admin(self, search_value: str | None = None) -> int:
        query = select(func.count(self.model.id)).join(User, User.id == self.model.user_id)
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.bot_username.ilike(pattern),
                    User.name.ilike(pattern),
                    cast(self.model.bot_id, String).ilike(pattern),
                )
            )
        return await self.scalar_or_default(query, 0)

    async def list_for_admin(
        self,
        *,
        page: int,
        page_size: int,
        search_value: str | None = None,
    ):
        query = (
            select(
                self.model.id,
                self.model.bot_id,
                self.model.bot_username,
                self.model.is_active,
                self.model.registered,
                User.name.label("owner_name"),
                User.subscription_type.label("owner_subscription_type"),
            )
            .join(User, User.id == self.model.user_id)
            .order_by(desc(self.model.registered), desc(self.model.id))
        )
        if search_value:
            pattern = f"%{search_value}%"
            query = query.where(
                or_(
                    self.model.bot_username.ilike(pattern),
                    User.name.ilike(pattern),
                    cast(self.model.bot_id, String).ilike(pattern),
                )
            )
        return await self.list_rows(query, page=page, page_size=page_size)


class AgentChannelConnectionDAO(BaseDAO):
    model = AgentChannelConnection

    @staticmethod
    def _map_channel_config_row(row: Any, provider: str) -> dict[str, Any]:
        template_config = parse_agent_template_config(row.get("template_config"))
        mapped: dict[str, Any] = {
            "agent_id": int(row["agent_id"]),
            "bot_id": int(row["bot_id"] if row["bot_id"] is not None else row["agent_id"]),
            "connection_id": int(row["connection_id"]),
            "system_prompt": row["system_prompt"] or "",
            "welcome_message": row["welcome_message"],
        }
        if provider in {"telegram_userbot", "max_userbot", "whatsapp_userbot"}:
            mapped["template_type"] = str(row.get("template_type") or "qa").strip().lower()
            mapped["template_config"] = template_config
        if provider == "telegram_userbot":
            mapped["encrypted_userbot_bundle"] = row["encrypted_credentials"]
        elif provider in {"max_userbot", "whatsapp_userbot", "max_bot"}:
            mapped["encrypted_credentials"] = row["encrypted_credentials"]
        if provider == "whatsapp_userbot":
            mapped["phone_number"] = row.get("external_id") or ""
        elif provider == "max_bot":
            mapped["max_bot_id"] = str(row.get("external_id") or "").strip()
        return mapped

    @staticmethod
    async def fetch_active_channel_configs(
        provider: str,
        *,
        connection_type: str = "userbot",
        template_types: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Agent.id.label("agent_id"),
                Agent.bot_id,
                Agent.system_prompt,
                Agent.welcome_message,
                Agent.template_type,
                Agent.template_config,
                AgentChannelConnection.id.label("connection_id"),
                AgentChannelConnection.external_id,
                AgentChannelConnection.encrypted_credentials,
            )
            .join(AgentChannelConnection, AgentChannelConnection.agent_id == Agent.id)
            .where(
                Agent.is_active.is_(True),
                AgentChannelConnection.provider == provider,
                AgentChannelConnection.connection_type == connection_type,
                AgentChannelConnection.is_active.is_(True),
                AgentChannelConnection.encrypted_credentials.is_not(None),
            )
        )
        if template_types:
            stmt = stmt.where(Agent.template_type.in_(template_types))

        async with async_session_maker() as session:
            async with session.begin():
                rows = (await session.execute(stmt)).mappings().all()

        return [
            AgentChannelConnectionDAO._map_channel_config_row(row, provider)
            for row in rows
        ]


class AgentCrmConnectionDAO(BaseDAO):
    model = AgentCrmConnection


class AgentHttpIntegrationDAO(BaseDAO):
    model = AgentHttpIntegration
