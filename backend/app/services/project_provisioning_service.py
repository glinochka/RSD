"""Service for provisioning projects from AI-generated plans."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from logging import getLogger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alembic.models import Project, Agent
from app.dao.project_dao import ProjectDAO
from app.router_agents.dao import AgentDAO
from app.router_projects.schemas import (
    ProjectBriefRequest,
    ProjectPlanResponse,
    ApplyProjectPlanResponse,
)
from app.utils.crypto import encrypt_token
from app.utils.api_keys import (
    generate_agent_external_api_key,
    hash_agent_external_api_key,
)

logger = getLogger(__name__)

# In-memory idempotency store (in production, use Redis or DB table)
_idempotency_cache: Dict[str, ApplyProjectPlanResponse] = {}


class ProjectProvisioningError(Exception):
    """Error during project provisioning."""
    pass


class ProjectProvisioningService:
    """Service for provisioning projects and agents from AI plans."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_dao = ProjectDAO(session)
        self.agent_dao = AgentDAO(session)

    async def apply_plan(
        self,
        user_id: int,
        brief: ProjectBriefRequest,
        plan: ProjectPlanResponse,
        idempotency_key: Optional[str] = None,
    ) -> ApplyProjectPlanResponse:
        """Apply AI plan and create project with agents and website.
        
        This operation is idempotent - calling with same idempotency_key
        returns the same result without creating duplicates.
        """
        # Check idempotency
        if idempotency_key:
            cache_key = f"{user_id}:{idempotency_key}"
            if cache_key in _idempotency_cache:
                logger.info(f"Returning cached result for idempotency key: {idempotency_key}")
                return _idempotency_cache[cache_key]

        website_id = None
        website_error = None
        
        try:
            # Create project
            project = await self._create_project(user_id, brief, plan)
            
            # Create agents
            agent_ids = await self._create_agents(user_id, project.id, plan)
            
            # Create website if enabled
            if plan.website and plan.website.enabled:
                try:
                    website_id = await self._create_website(
                        user_id, project.id, agent_ids[0] if agent_ids else None, plan
                    )
                except Exception as e:
                    website_error = str(e)
                    logger.error(f"Failed to create website: {e}")
            
            # Update project with AI plan
            project.ai_plan_json = plan.model_dump()
            project.brief_json = brief.model_dump()
            await self.session.flush()
            
            # Determine status
            status = "created"
            if website_error:
                status = "partial"  # Agents created but website failed
            
            result = ApplyProjectPlanResponse(
                project_id=project.id,
                agent_ids=agent_ids,
                website_id=website_id,
                status=status,
            )
            
            # Cache result for idempotency
            if idempotency_key:
                cache_key = f"{user_id}:{idempotency_key}"
                _idempotency_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.exception("Failed to apply project plan")
            raise ProjectProvisioningError(f"Failed to create project: {str(e)}")

    async def _create_website(
        self,
        user_id: int,
        project_id: int,
        agent_id: Optional[int],
        plan: ProjectPlanResponse,
    ) -> Optional[int]:
        """Create website from plan.
        
        Uses the existing website generation flow.
        """
        from ..router_websites.dao import WebsiteDAO
        
        website_dao = WebsiteDAO(self.session)
        
        # Generate unique slug
        base_slug = plan.website.suggested_slug
        slug = await self._ensure_unique_website_slug(website_dao, base_slug)
        
        # Create website
        website_data = {
            "owner_id": user_id,
            "project_id": project_id,
            "agent_id": agent_id,
            "slug": slug,
            "title": plan.website.title,
            "status": "draft",
            "generation_status": "queued",
        }
        
        website = await website_dao.add(website_data)
        await self.session.flush()
        
        # Start background generation
        from ..router_websites.generation import generate_website_in_background
        from fastapi import BackgroundTasks
        
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            generate_website_in_background,
            website_id=website.id,
            agent_id=agent_id,
            generation_prompt=plan.website.generation_prompt,
            user_id=user_id,
        )
        
        logger.info(f"Created website {website.id} for project {project_id}")
        return website.id

    async def _ensure_unique_website_slug(self, website_dao, base_slug: str) -> str:
        """Ensure website slug is unique."""
        slug = base_slug
        counter = 1
        
        while await website_dao.get_by_slug(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                raise ProjectProvisioningError("Unable to generate unique website slug")
        
        return slug

    async def _create_project(
        self,
        user_id: int,
        brief: ProjectBriefRequest,
        plan: ProjectPlanResponse,
    ) -> Project:
        """Create project from plan."""
        # Generate slug from project name
        base_slug = self._slugify(plan.project.get("name", brief.name))
        slug = await self._ensure_unique_slug(user_id, base_slug)
        
        project = await self.project_dao.create(
            session=self.session,
            user_id=user_id,
            name=plan.project.get("name", brief.name),
            slug=slug,
            industry=plan.project.get("industry", brief.industry),
            description=plan.project.get("description", brief.description[:200]),
        )
        
        logger.info(f"Created project {project.id} for user {user_id}")
        return project

    async def _create_agents(
        self,
        user_id: int,
        project_id: int,
        plan: ProjectPlanResponse,
    ) -> List[int]:
        """Create agents from plan."""
        agent_ids = []
        
        for agent_plan in plan.agents:
            try:
                agent = await self._create_agent(user_id, project_id, agent_plan)
                agent_ids.append(agent.id)
                logger.info(f"Created agent {agent.id} ({agent_plan.suggested_name}) for project {project_id}")
            except Exception as e:
                logger.error(f"Failed to create agent {agent_plan.suggested_name}: {e}")
                # Continue creating other agents
                continue
        
        return agent_ids

    async def _create_agent(
        self,
        user_id: int,
        project_id: int,
        agent_plan: Any,
    ) -> Agent:
        """Create a single agent."""
        # Generate external API key
        external_api_key = generate_agent_external_api_key()
        
        # Prepare template config
        template_config = agent_plan.template_config or {}
        if isinstance(template_config, dict):
            template_config_json = json.dumps(template_config, ensure_ascii=False)
        else:
            template_config_json = str(template_config)
        
        # Get billing fields based on template type
        billing_fields = self._get_billing_fields(agent_plan.template_type)
        
        # Create agent using AgentDAO
        agent_data = {
            "user_id": user_id,
            "project_id": project_id,
            "bot_id": None,
            "primary_provider": "none",
            "template_type": agent_plan.template_type,
            "template_config": template_config_json,
            "encrypted_token": encrypt_token(f"agent:{user_id}:{datetime.now(timezone.utc).timestamp()}"),
            "encrypted_external_api_key": encrypt_token(external_api_key),
            "external_api_key_hash": hash_agent_external_api_key(external_api_key),
            "bot_username": None,
            "system_prompt": agent_plan.system_prompt,
            "welcome_message": agent_plan.welcome_message,
            "is_active": True,
            **billing_fields,
        }
        
        agent = await self.agent_dao.add(agent_data)
        await self.session.flush()
        
        return agent

    def _get_billing_fields(self, template_type: str) -> Dict[str, Any]:
        """Get initial billing fields for agent template type."""
        from ..agent_template_pricing import (
            get_agent_template_pricing,
            initial_maintenance_paid_until_for_template,
        )
        
        pricing = get_agent_template_pricing(template_type)
        
        return {
            "activation_paid_at": datetime.now(timezone.utc),
            "maintenance_paid_until": initial_maintenance_paid_until_for_template(
                pricing, template_type
            ),
        }

    async def _ensure_unique_slug(self, user_id: int, base_slug: str) -> str:
        """Ensure slug is unique for user."""
        slug = base_slug
        counter = 1
        
        while await self.project_dao.get_by_slug(self.session, user_id, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                raise ProjectProvisioningError("Unable to generate unique slug")
        
        return slug

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        import re
        
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z', 'и': 'i',
            'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
            'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
            'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch',
            'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
        }
        
        text = text.lower()
        result = []
        for char in text:
            if char in translit_map:
                result.append(translit_map[char])
            elif char.isalnum():
                result.append(char)
            else:
                result.append('-')
        
        slug = ''.join(result)
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug[:80]


async def apply_project_plan(
    session: AsyncSession,
    user_id: int,
    brief: ProjectBriefRequest,
    plan: ProjectPlanResponse,
    idempotency_key: Optional[str] = None,
) -> ApplyProjectPlanResponse:
    """Convenience function to apply project plan."""
    service = ProjectProvisioningService(session)
    return await service.apply_plan(user_id, brief, plan, idempotency_key)
