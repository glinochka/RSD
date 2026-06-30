"""Project routes: /api/projects"""
import re
import hashlib
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, func, select

from .schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectListResponse,
    ProjectBriefRequest,
    ProjectPlanResponse,
    ApplyProjectPlanRequest,
    ApplyProjectPlanResponse,
    ProjectDashboardResponse,
    ProjectSummaryWidget,
    OnboardingChecklistItem,
)
from ..dao.project_dao import ProjectDAO
from ..alembic.database import async_session_maker
from ..alembic.models import User, Project, Agent, Website, ProjectDocument, AgentContentJob
from ..utils.JWT import get_user_from_access_token
from ..utils.rate_limit import rate_limit
from ..config import settings

router = APIRouter(prefix="/api/projects")
http_bearer = HTTPBearer(auto_error=False)


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    # Transliterate Cyrillic to Latin (simplified)
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
    # Remove consecutive dashes
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing dashes
    slug = slug.strip('-')
    return slug[:80]


async def get_current_user_from_token(
    authorization: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> Optional[User]:
    """Extract and validate user from JWT token."""
    if not authorization or not authorization.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )

    async with async_session_maker() as session:
        from ..router_users.dao import UserDAO
        user_dao = UserDAO(session)
        try:
            user = await get_user_from_access_token(authorization.credentials, user_dao)
            return user
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )


async def _get_project_summary(
    session, project: Project
) -> ProjectSummaryResponse:
    """Get project with summary counts."""
    # Count agents
    agents_result = await session.execute(
        select(func.count(Agent.id)).where(Agent.project_id == project.id)
    )
    agents_count = agents_result.scalar() or 0
    
    # Get primary website
    website_result = await session.execute(
        select(Website)
        .where(Website.project_id == project.id)
        .order_by(Website.created_at.desc())
        .limit(1)
    )
    website = website_result.scalar_one_or_none()
    
    return ProjectSummaryResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        slug=project.slug,
        industry=project.industry,
        description=project.description,
        status=project.status,
        is_default=project.is_default,
        created_at=project.created_at,
        updated_at=project.updated_at,
        agents_count=agents_count,
        website_id=website.id if website else None,
        website_status=website.status if website else None,
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    current_user: User = Depends(get_current_user_from_token),
):
    """List all projects for current user."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            projects = await project_dao.list_by_user(session, current_user.id)
            
            items = []
            for project in projects:
                summary = await _get_project_summary(session, project)
                items.append(summary)
            
            return ProjectListResponse(
                items=items,
                total=len(items),
            )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user_from_token),
):
    """Create a new project."""
    # Generate slug from name
    base_slug = slugify(data.name)
    slug = base_slug
    
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            # Ensure unique slug
            counter = 1
            while await project_dao.get_by_slug(session, current_user.id, slug):
                slug = f"{base_slug}-{counter}"
                counter += 1
                if counter > 100:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Unable to generate unique slug",
                    )
            
            project = await project_dao.create(
                session=session,
                user_id=current_user.id,
                name=data.name,
                slug=slug,
                industry=data.industry,
                description=data.description,
            )
            
            return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectSummaryResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Get project by ID with summary."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            if project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            if project.status == "archived":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            return await _get_project_summary(session, project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user_from_token),
):
    """Update project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            if project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            if project.status == "archived":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot update archived project",
                )
            
            updated = await project_dao.update(
                session=session,
                project=project,
                name=data.name,
                description=data.description,
                industry=data.industry,
            )
            
            return ProjectResponse.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_project(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Archive project (soft delete)."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            if project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            if project.is_default:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot archive default project",
                )
            
            await project_dao.archive(session, project)
            
            return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ai/generate-plan", response_model=ProjectPlanResponse)
async def generate_project_plan(
    brief: ProjectBriefRequest,
    current_user: User = Depends(get_current_user_from_token),
    _rate_limited=Depends(rate_limit(max_requests=10, window_seconds=60, scope="project_generate_plan")),
):
    """Generate AI plan from brief (no side effects in DB)."""
    from ..services.project_plan_service import get_project_plan_service, ProjectPlanGenerationError
    
    plan_service = get_project_plan_service()
    
    try:
        plan = await plan_service.generate_plan(brief)
        return plan
    except ProjectPlanGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to generate plan: {str(e)}",
        )
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Unexpected error generating project plan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate plan. Please try again.",
        )


@router.post("/ai/apply-plan", response_model=ApplyProjectPlanResponse, status_code=status.HTTP_201_CREATED)
async def apply_project_plan(
    request: ApplyProjectPlanRequest,
    current_user: User = Depends(get_current_user_from_token),
    _rate_limited=Depends(rate_limit(max_requests=5, window_seconds=60, scope="project_apply_plan")),
):
    """Apply AI plan and create project with agents (idempotent)."""
    from ..services.project_provisioning_service import (
        apply_project_plan,
        ProjectProvisioningError,
    )
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                result = await apply_project_plan(
                    session=session,
                    user_id=current_user.id,
                    brief=request.brief,
                    plan=request.plan,
                    idempotency_key=request.idempotency_key,
                )
                return result
                
    except ProjectProvisioningError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Unexpected error applying project plan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project. Please try again.",
        )


@router.get("/{project_id}/dashboard", response_model=ProjectDashboardResponse)
async def get_project_dashboard(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Get dashboard data for project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            # Get project summary
            project_summary = await _get_project_summary(session, project)
            
            # Count active agents
            agents_result = await session.execute(
                select(Agent).where(
                    and_(
                        Agent.project_id == project_id,
                        Agent.is_active == True,
                    )
                )
            )
            agents = agents_result.scalars().all()
            
            # Get website
            website_result = await session.execute(
                select(Website)
                .where(Website.project_id == project_id)
                .order_by(Website.created_at.desc())
                .limit(1)
            )
            website = website_result.scalar_one_or_none()
            
            # Build summary widget (placeholder stats - will be populated from analytics)
            summary = ProjectSummaryWidget(
                agents_total=len(agents),
                agents_active=len([a for a in agents if a.is_active]),
                dialogs_7d=0,  # TODO: Connect to analytics
                new_leads_7d=0,  # TODO: Connect to CRM data
                website_status=website.status if website else None,
                website_url=f"/w/{website.slug}" if website and website.status == "published" else None,
            )
            
            # Build onboarding checklist
            checklist = _build_onboarding_checklist(project, agents, website)
            
            # Quick actions
            quick_actions = [
                {
                    "id": "add_agent",
                    "label": "Добавить агента",
                    "icon": "bot",
                    "url": f"/projects/{project_id}/agents",
                },
                {
                    "id": "upload_docs",
                    "label": "Загрузить документы",
                    "icon": "file",
                    "url": f"/projects/{project_id}/knowledge",
                },
            ]
            
            if website:
                quick_actions.append({
                    "id": "edit_website",
                    "label": "Редактировать сайт",
                    "icon": "globe",
                    "url": f"/websites/{website.id}/edit",
                })
            
            return ProjectDashboardResponse(
                project=project_summary,
                summary=summary,
                onboarding_checklist=checklist,
                quick_actions=quick_actions,
            )


def _build_onboarding_checklist(project, agents, website) -> list:
    """Build onboarding checklist based on project state."""
    checklist = []
    
    # Check 1: Add Telegram bot
    has_telegram = any(
        a.channel_connections and any(
            c.provider == "telegram_bot" and c.is_active
            for c in a.channel_connections
        )
        for a in agents
    )
    checklist.append(OnboardingChecklistItem(
        id="connect_telegram",
        label="Подключить Telegram бота",
        completed=has_telegram,
        action_url=f"/projects/{project.id}/agents",
    ))
    
    # Check 2: Upload knowledge documents
    has_docs = bool(
        project.ai_plan_json and 
        project.ai_plan_json.get("knowledge_recommendations")
    )
    checklist.append(OnboardingChecklistItem(
        id="upload_knowledge",
        label="Загрузить базу знаний",
        completed=has_docs,
        action_url=f"/projects/{project.id}/knowledge",
    ))
    
    # Check 3: Publish website
    website_published = website and website.status == "published"
    checklist.append(OnboardingChecklistItem(
        id="publish_website",
        label="Опубликовать сайт",
        completed=website_published,
        action_url=f"/websites/{website.id}/edit" if website else None,
    ))
    
    # Check 4: Test agent
    has_active_agent = any(a.is_active for a in agents)
    checklist.append(OnboardingChecklistItem(
        id="test_agent",
        label="Протестировать агента",
        completed=has_active_agent and has_telegram,
        action_url=f"/projects/{project.id}/agents",
    ))
    
    return checklist


from fastapi import Response, UploadFile, File, Form
from typing import List, Optional
from app.alembic.models import ProjectDocument, AgentContentJob


@router.get("/{project_id}/documents", response_model=List[dict])
async def list_project_documents(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """List all documents for a project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            result = await session.execute(
                select(ProjectDocument)
                .where(ProjectDocument.project_id == project_id)
                .order_by(ProjectDocument.created_at.desc())
            )
            documents = result.scalars().all()
            
            return [
                {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "status": doc.status,
                    "content_hash": doc.content_hash,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }
                for doc in documents
            ]


@router.post("/{project_id}/documents")
async def upload_project_document(
    project_id: int,
    file: UploadFile = File(None),
    url: str = Form(None),
    current_user: User = Depends(get_current_user_from_token),
):
    """Upload a document or add a link to project knowledge base."""
    if not file and not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either file or url must be provided",
        )
    
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            # Handle file upload
            if file:
                # Validate file type
                allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md'}
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in allowed_extensions:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File type {file_ext} not allowed. Allowed: {allowed_extensions}",
                    )
                
                # Read file content
                content = await file.read()
                
                # Generate content hash
                content_hash = hashlib.sha256(content).hexdigest()
                
                # Create document record
                doc = ProjectDocument(
                    project_id=project_id,
                    file_name=file.filename,
                    content_hash=content_hash,
                    status="processing",
                )
                session.add(doc)
                await session.flush()
                
                # TODO: Trigger async processing (background task)
                # For now, mark as ready immediately
                doc.status = "ready"
                
                return {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "status": doc.status,
                    "message": "Document uploaded and is being processed",
                }
            
            # Handle URL/link
            if url:
                doc = ProjectDocument(
                    project_id=project_id,
                    file_name=url,
                    content_hash=None,
                    status="processing",
                )
                session.add(doc)
                await session.flush()
                
                # TODO: Trigger URL scraping
                doc.status = "ready"
                
                return {
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "status": doc.status,
                    "message": "Link added and is being processed",
                }


@router.delete("/{project_id}/documents/{document_id}")
async def delete_project_document(
    project_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Delete a document from project knowledge base."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            result = await session.execute(
                select(ProjectDocument).where(
                    and_(
                        ProjectDocument.id == document_id,
                        ProjectDocument.project_id == project_id,
                    )
                )
            )
            doc = result.scalar_one_or_none()
            
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )
            
            await session.delete(doc)
            
            return {"message": "Document deleted"}


@router.post("/{project_id}/documents/{document_id}/reindex")
async def reindex_project_document(
    project_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Trigger reindexing of a document."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            result = await session.execute(
                select(ProjectDocument).where(
                    and_(
                        ProjectDocument.id == document_id,
                        ProjectDocument.project_id == project_id,
                    )
                )
            )
            doc = result.scalar_one_or_none()
            
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )
            
            doc.status = "processing"
            await session.flush()
            
            # TODO: Trigger reindexing background task
            # For now, mark as ready
            doc.status = "ready"
            
            return {
                "id": doc.id,
                "status": doc.status,
                "message": "Reindexing started",
            }


@router.get("/{project_id}/crm/summary")
async def get_project_crm_summary(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Get CRM summary for project - bookings, contacts, leads from all agents."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            # Get agents with their types
            agents_result = await session.execute(
                select(Agent).where(Agent.project_id == project_id)
            )
            agents = agents_result.scalars().all()
            
            has_crm_admin = any(a.template_type == "crm_admin" for a in agents)
            has_sales_manager = any(a.template_type == "sales_manager" for a in agents)
            
            # Aggregate data from all agents
            bookings = []
            contacts = []
            
            for agent in agents:
                # Get bookings from crm_admin agents
                if agent.template_type == "crm_admin":
                    from app.alembic.models import AdminAppointment
                    appts_result = await session.execute(
                        select(AdminAppointment)
                        .where(AdminAppointment.agent_id == agent.id)
                        .order_by(AdminAppointment.created_at.desc())
                        .limit(50)
                    )
                    for appt in appts_result.scalars().all():
                        bookings.append({
                            "id": appt.id,
                            "client_name": appt.client_name or "Клиент",
                            "service_title": appt.service_id or "Услуга",
                            "status": appt.status,
                            "created_at": appt.created_at.isoformat() if appt.created_at else None,
                        })
                
                # Get contacts from sales_manager agents
                if agent.template_type == "sales_manager":
                    from app.alembic.models import AgentSalesContact
                    contacts_result = await session.execute(
                        select(AgentSalesContact)
                        .where(AgentSalesContact.agent_id == agent.id)
                        .order_by(AgentSalesContact.created_at.desc())
                        .limit(50)
                    )
                    for contact in contacts_result.scalars().all():
                        contacts.append({
                            "id": contact.id,
                            "name": f"Контакт {contact.user_external_id[:8]}",
                            "state": contact.state,
                            "created_at": contact.created_at.isoformat() if contact.created_at else None,
                        })
            
            return {
                "has_crm_admin": has_crm_admin,
                "has_sales_manager": has_sales_manager,
                "total_bookings": len(bookings),
                "total_contacts": len(contacts),
                "bookings": bookings[:20],  # Return last 20
                "contacts": contacts[:20],  # Return last 20
            }


@router.get("/{project_id}/website")
async def get_project_website(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Get website info for project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            result = await session.execute(
                select(Website)
                .where(Website.project_id == project_id)
                .order_by(Website.created_at.desc())
                .limit(1)
            )
            website = result.scalar_one_or_none()
            
            if not website:
                return {"exists": False}
            
            return {
                "exists": True,
                "id": website.id,
                "slug": website.slug,
                "title": website.title,
                "status": website.status,
                "generation_status": website.generation_status,
                "agent_id": website.agent_id,
                "created_at": website.created_at.isoformat() if website.created_at else None,
                "published_at": website.published_at.isoformat() if website.published_at else None,
            }


@router.get("/{project_id}/content")
async def get_project_content(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Get content factory agents and jobs for project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            # Get content_factory agents
            result = await session.execute(
                select(Agent)
                .where(
                    and_(
                        Agent.project_id == project_id,
                        Agent.template_type == "content_factory",
                    )
                )
            )
            agents = result.scalars().all()
            
            agent_list = []
            all_jobs = []
            
            for agent in agents:
                agent_list.append({
                    "id": agent.id,
                    "bot_username": agent.bot_username,
                    "is_active": agent.is_active,
                })
                
                # Get jobs for this agent
                jobs_result = await session.execute(
                    select(AgentContentJob)
                    .where(AgentContentJob.agent_id == agent.id)
                    .order_by(AgentContentJob.created_at.desc())
                    .limit(10)
                )
                for job in jobs_result.scalars().all():
                    all_jobs.append({
                        "id": job.id,
                        "agent_id": agent.id,
                        "status": job.status,
                        "title": job.script_text[:50] if job.script_text else "Контент",
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                    })
            
            return {
                "agents": agent_list,
                "jobs": all_jobs,
            }


@router.get("/{project_id}/ai-manager")
async def get_project_ai_manager(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Get AI manager agents and analytics for project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            
            # Get ai_manager agents
            result = await session.execute(
                select(Agent)
                .where(
                    and_(
                        Agent.project_id == project_id,
                        Agent.template_type == "ai_manager",
                    )
                )
            )
            agents = result.scalars().all()
            
            return {
                "agents": [
                    {
                        "id": agent.id,
                        "bot_username": agent.bot_username,
                        "is_active": agent.is_active,
                        "user_id": agent.user_id,
                    }
                    for agent in agents
                ],
                "analytics": {
                    "conversions": 0,  # Placeholder - implement actual tracking
                    "messages": 0,
                    "goals": 0,
                },
            }
