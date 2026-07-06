"""Project routes: /api/projects"""
import ipaddress
import os
import re
import hashlib
import socket
import tempfile
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path
from logging import getLogger
from urllib.parse import urlparse

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

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
    ProjectChecklistVisibilityUpdate,
    ProjectIntegrationCreate,
    ProjectIntegrationUpdate,
    ProjectIntegrationResponse,
    ProjectIntegrationListResponse,
)
from ..dao.project_dao import ProjectDAO
from ..dao.project_document_dao import ProjectDocumentDAO
from ..dao.project_integration_dao import ProjectIntegrationDAO
from ..services.project_integration_service import (
    validate_integration_type,
    encrypt_credentials,
    credentials_from_request,
    generate_webhook_token,
    serialize_integration,
)
from ..alembic.database import async_session_maker
from ..alembic.models import (
    User,
    Project,
    Agent,
    Website,
    ProjectDocument,
    AgentContentJob,
    AgentSalesContact,
    AdminAppointment,
    AgentAnalyticsMessage,
)
from ..qdrant.embeddings import get_active_embedding_profile
from ..qdrant.indexer import (
    extract_text,
    fetch_public_url_text,
    get_chunk_limit_by_plan,
    get_current_chunks_count,
    process_project_document,
    process_project_text_source,
    text_splitter,
)
from ..qdrant.search_service import delete_document_vectors
from ..utils.JWT import get_user_from_access_token
from ..utils.rate_limit import rate_limit
from ..config import settings

logger = getLogger(__name__)
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

    token = authorization.credentials
    # Debug logging
    logger.warning(f"[PROJECTS AUTH] token type={type(token)}, len={len(token)}, preview={token[:20]}...")

    async with async_session_maker() as session:
        from ..router_users.dao import UserDAO
        user_dao = UserDAO(session)
        try:
            async with session.begin():
                user = await get_user_from_access_token(token, user_dao)
                return user
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[PROJECTS AUTH] Error validating token: {e}")
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


async def _get_project_analytics(session, project_id: int) -> dict:
    """Aggregate project-level analytics for the dashboard."""
    from datetime import timedelta

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since_7d = now - timedelta(days=7)

    agent_ids_result = await session.execute(
        select(Agent.id).where(Agent.project_id == project_id)
    )
    agent_ids = [row[0] for row in agent_ids_result.all()]

    if not agent_ids:
        return {
            "dialogs_7d": 0,
            "new_leads_7d": 0,
            "total_leads": 0,
            "total_messages": 0,
            "total_bookings": 0,
            "daily_labels": [],
            "daily_messages": [],
            "daily_leads": [],
        }

    # Count messages in last 7 days
    dialogs_7d_result = await session.execute(
        select(func.count(AgentAnalyticsMessage.id)).where(
            and_(
                AgentAnalyticsMessage.agent_id.in_(agent_ids),
                AgentAnalyticsMessage.created_at >= since_7d,
            )
        )
    )
    dialogs_7d = dialogs_7d_result.scalar() or 0

    total_messages_result = await session.execute(
        select(func.count(AgentAnalyticsMessage.id)).where(
            AgentAnalyticsMessage.agent_id.in_(agent_ids)
        )
    )
    total_messages = total_messages_result.scalar() or 0

    # Count leads
    leads_7d_result = await session.execute(
        select(func.count(AgentSalesContact.id)).where(
            and_(
                AgentSalesContact.agent_id.in_(agent_ids),
                AgentSalesContact.created_at >= since_7d,
            )
        )
    )
    new_leads_7d = leads_7d_result.scalar() or 0

    total_leads_result = await session.execute(
        select(func.count(AgentSalesContact.id)).where(
            AgentSalesContact.agent_id.in_(agent_ids)
        )
    )
    total_leads = total_leads_result.scalar() or 0

    # Count bookings
    total_bookings_result = await session.execute(
        select(func.count(AdminAppointment.id)).where(
            AdminAppointment.agent_id.in_(agent_ids)
        )
    )
    total_bookings = total_bookings_result.scalar() or 0

    # Daily buckets for the last 7 days
    labels = []
    daily_messages = []
    daily_leads = []
    for day_offset in range(6, -1, -1):
        day_start = now - timedelta(days=day_offset + 1)
        day_end = now - timedelta(days=day_offset)
        labels.append(day_end.strftime("%d.%m"))

        msg_count_result = await session.execute(
            select(func.count(AgentAnalyticsMessage.id)).where(
                and_(
                    AgentAnalyticsMessage.agent_id.in_(agent_ids),
                    AgentAnalyticsMessage.created_at >= day_start,
                    AgentAnalyticsMessage.created_at < day_end,
                )
            )
        )
        daily_messages.append(msg_count_result.scalar() or 0)

        lead_count_result = await session.execute(
            select(func.count(AgentSalesContact.id)).where(
                and_(
                    AgentSalesContact.agent_id.in_(agent_ids),
                    AgentSalesContact.created_at >= day_start,
                    AgentSalesContact.created_at < day_end,
                )
            )
        )
        daily_leads.append(lead_count_result.scalar() or 0)

    return {
        "dialogs_7d": dialogs_7d,
        "new_leads_7d": new_leads_7d,
        "total_leads": total_leads,
        "total_messages": total_messages,
        "total_bookings": total_bookings,
        "daily_labels": labels,
        "daily_messages": daily_messages,
        "daily_leads": daily_leads,
    }


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
            
            # Count active agents with eager-loaded channel connections
            agents_result = await session.execute(
                select(Agent)
                .options(selectinload(Agent.channel_connections))
                .where(
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
            
            # Real-time analytics for the last 7 days
            analytics = await _get_project_analytics(session, project_id)

            # Build summary widget
            summary = ProjectSummaryWidget(
                agents_total=len(agents),
                agents_active=len([a for a in agents if a.is_active]),
                dialogs_7d=analytics["dialogs_7d"],
                new_leads_7d=analytics["new_leads_7d"],
                website_status=website.status if website else None,
                website_url=f"/w/{website.slug}" if website and website.status == "published" else None,
            )

            # Build onboarding checklist
            checklist = _build_onboarding_checklist(project, agents, website)

            # Quick actions (deduplicated, focused)
            quick_actions = [
                {
                    "id": "add_agent",
                    "label": "Добавить агента",
                    "icon": "bot",
                    "url": f"/projects/{project_id}/agents",
                },
                {
                    "id": "upload_docs",
                    "label": "Обновить базу знаний",
                    "icon": "file",
                    "url": f"/projects/{project_id}/knowledge",
                },
            ]
            if not website:
                quick_actions.append({
                    "id": "create_website",
                    "label": "Создать сайт",
                    "icon": "globe",
                    "url": f"/projects/{project_id}/website",
                })

            # Chart data
            charts = {
                "growth": {
                    "labels": analytics["daily_labels"],
                    "messages": analytics["daily_messages"],
                    "leads": analytics["daily_leads"],
                },
                "efficiency": {
                    "labels": ["Лиды", "Диалоги", "Бронирования", "Публикации"],
                    "values": [
                        analytics["total_leads"],
                        analytics["total_messages"],
                        analytics["total_bookings"],
                        1 if website and website.status == "published" else 0,
                    ],
                },
            }

            # Integration summary
            integration_dao = ProjectIntegrationDAO(session)
            integrations = await integration_dao.list_by_project(session, project_id)
            integration_summary = [serialize_integration(i) for i in integrations]

            # AI manager summary
            ai_manager_agents = [a for a in agents if a.template_type == "ai_manager"]
            ai_manager_summary = {
                "enabled": len(ai_manager_agents) > 0,
                "agents_count": len(ai_manager_agents),
                "url": f"/projects/{project_id}/manager",
            }

            return ProjectDashboardResponse(
                project=project_summary,
                summary=summary,
                onboarding_checklist=checklist,
                checklist_hidden=project.checklist_hidden,
                quick_actions=quick_actions,
                charts=charts,
                integrations=integration_summary,
                ai_manager=ai_manager_summary,
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
    website_published = bool(website and website.status == "published")
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


def _save_project_upload_to_temp_with_hash(file: UploadFile, suffix: str) -> tuple[str, str]:
    hasher = hashlib.sha256()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            temp_file.write(chunk)
        return temp_file.name, hasher.hexdigest()


def _validate_public_url(url: str) -> str:
    normalized_url = url.strip()
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Некорректная ссылка")

    hostname = parsed.hostname or ""
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ссылка должна быть публичной")

    try:
        host_ip = ipaddress.ip_address(hostname)
        if (
            host_ip.is_private
            or host_ip.is_loopback
            or host_ip.is_reserved
            or host_ip.is_multicast
            or host_ip.is_link_local
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ссылка должна быть публичной",
            )
    except ValueError:
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
                if family not in (socket.AF_INET, socket.AF_INET6):
                    continue
                ip_value = sockaddr[0]
                resolved = ipaddress.ip_address(ip_value)
                if (
                    resolved.is_private
                    or resolved.is_loopback
                    or resolved.is_reserved
                    or resolved.is_multicast
                    or resolved.is_link_local
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Ссылка должна быть публичной",
                    )
        except socket.gaierror:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Не удалось проверить домен")

    return normalized_url


async def _get_project_or_404(session, project_id: int, user_id: int) -> Project:
    project_dao = ProjectDAO(session)
    project = await project_dao.get_by_id(session, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("/{project_id}/documents")
async def upload_project_document(
    background_tasks: BackgroundTasks,
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_from_token),
):
    """Upload a document to project knowledge base."""
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.md'}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not allowed. Allowed: {allowed_extensions}",
        )

    async with async_session_maker() as session:
        async with session.begin():
            await _get_project_or_404(session, project_id, current_user.id)

    embedding_profile = get_active_embedding_profile()

    temp_path, content_hash = _save_project_upload_to_temp_with_hash(
        file=file,
        suffix=file_ext,
    )

    async with async_session_maker() as session:
        doc_dao = ProjectDocumentDAO(session)
        async with session.begin():
            existing_doc = await doc_dao.find_by_project_and_content_hash(
                project_id,
                content_hash,
                embedding_profile_key=embedding_profile["profile_key"],
            )

    if existing_doc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        data = {
            "status": "duplicate",
            "document_id": existing_doc.id,
            "document_status": existing_doc.status,
            "new_chunks_count": 0,
        }
        return JSONResponse(content=data, status_code=status.HTTP_200_OK)

    text = await extract_text(temp_path)
    chunks = text_splitter.split_text(text)
    new_chunks_count = len(chunks)

    current_plan = current_user.subscription_type
    limit = get_chunk_limit_by_plan(current_plan)
    current_count = await get_current_chunks_count(
        project_id=project_id,
        embedding_profile_key=embedding_profile["profile_key"],
    )

    if current_count + new_chunks_count > limit:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        data = {
            "status": "limit_error",
            "current_plan": current_plan,
            "limit": limit,
            "current_count": current_count,
            "new_chunks_count": new_chunks_count,
        }
        return JSONResponse(content=data, status_code=status.HTTP_200_OK)

    doc = None
    try:
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                doc_data = {
                    "project_id": project_id,
                    "file_name": file.filename,
                    "content_hash": content_hash,
                    "embedding_profile_key": embedding_profile["profile_key"],
                    "embedding_schema_version": embedding_profile["schema_version"],
                    "embedding_model_name": embedding_profile["model_name"],
                    "chunk_size": settings.EMBEDDING_CHUNK_SIZE,
                    "chunk_overlap": settings.EMBEDDING_CHUNK_OVERLAP,
                    "status": "processing",
                }
                doc = await doc_dao.add(doc_data)
                await session.flush()
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    background_tasks.add_task(
        process_project_document,
        file_path=temp_path,
        project_id=project_id,
        document_id=doc.id,
        content_hash=content_hash,
        source_name=file.filename,
    )
    data = {
        "status": "limit_ok",
        "new_chunks_count": new_chunks_count,
        "current_plan": current_plan,
        "limit": limit,
        "current_count": current_count,
    }
    return JSONResponse(content=data, status_code=status.HTTP_200_OK)


class _ProjectLinkPayload(BaseModel):
    url: str


@router.post("/{project_id}/documents/link")
async def upload_project_link(
    background_tasks: BackgroundTasks,
    project_id: int,
    payload: _ProjectLinkPayload,
    current_user: User = Depends(get_current_user_from_token),
):
    """Add a public link to project knowledge base."""
    normalized_url = _validate_public_url(payload.url)

    async with async_session_maker() as session:
        async with session.begin():
            await _get_project_or_404(session, project_id, current_user.id)

    embedding_profile = get_active_embedding_profile()

    content_hash = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    async with async_session_maker() as session:
        doc_dao = ProjectDocumentDAO(session)
        async with session.begin():
            existing_doc = await doc_dao.find_by_project_and_content_hash(
                project_id,
                content_hash,
                embedding_profile_key=embedding_profile["profile_key"],
            )

    if existing_doc:
        data = {
            "status": "duplicate",
            "document_id": existing_doc.id,
            "document_status": existing_doc.status,
            "new_chunks_count": 0,
        }
        return JSONResponse(content=data, status_code=status.HTTP_200_OK)

    try:
        text = await fetch_public_url_text(normalized_url)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось получить содержимое ссылки: {exc}",
        )

    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="По ссылке не удалось извлечь текст",
        )

    chunks = text_splitter.split_text(text)
    new_chunks_count = len(chunks)
    if new_chunks_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="По ссылке не удалось подготовить данные для индексации",
        )

    current_plan = current_user.subscription_type
    limit = get_chunk_limit_by_plan(current_plan)
    current_count = await get_current_chunks_count(
        project_id=project_id,
        embedding_profile_key=embedding_profile["profile_key"],
    )

    if current_count + new_chunks_count > limit:
        data = {
            "status": "limit_error",
            "current_plan": current_plan,
            "limit": limit,
            "current_count": current_count,
            "new_chunks_count": new_chunks_count,
        }
        return JSONResponse(content=data, status_code=status.HTTP_200_OK)

    doc = None
    try:
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                doc_data = {
                    "project_id": project_id,
                    "file_name": normalized_url,
                    "content_hash": content_hash,
                    "embedding_profile_key": embedding_profile["profile_key"],
                    "embedding_schema_version": embedding_profile["schema_version"],
                    "embedding_model_name": embedding_profile["model_name"],
                    "chunk_size": settings.EMBEDDING_CHUNK_SIZE,
                    "chunk_overlap": settings.EMBEDDING_CHUNK_OVERLAP,
                    "status": "processing",
                }
                doc = await doc_dao.add(doc_data)
                await session.flush()
    except Exception:
        raise

    background_tasks.add_task(
        process_project_text_source,
        text=text,
        source_name=normalized_url,
        project_id=project_id,
        document_id=doc.id,
        content_hash=content_hash,
    )
    data = {
        "status": "limit_ok",
        "new_chunks_count": new_chunks_count,
        "current_plan": current_plan,
        "limit": limit,
        "current_count": current_count,
    }
    return JSONResponse(content=data, status_code=status.HTTP_200_OK)


@router.delete("/{project_id}/documents/{document_id}")
async def delete_project_document(
    project_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Delete a document from project knowledge base."""
    async with async_session_maker() as session:
        async with session.begin():
            await _get_project_or_404(session, project_id, current_user.id)

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
            await session.flush()

    is_deleted = await delete_document_vectors(document_id)
    if not is_deleted:
        logger.warning(f"Failed to delete Qdrant vectors for project document {document_id}")

    return {"message": "Document deleted"}


@router.post("/{project_id}/documents/{document_id}/reindex")
async def reindex_project_document(
    project_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Trigger reindexing of a project document from existing Qdrant chunks."""
    async with async_session_maker() as session:
        async with session.begin():
            await _get_project_or_404(session, project_id, current_user.id)

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

    try:
        from ..qdrant.indexer import reindex_project_document_from_existing_chunks

        chunks_count, source_name, content_hash = await reindex_project_document_from_existing_chunks(
            project_id=project_id,
            document_id=document_id,
            source_profile_key=doc.embedding_profile_key,
        )

        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                refreshed = await doc_dao.find_one_by_filter(id=document_id)
                if refreshed:
                    await doc_dao.update(refreshed, {"status": "ready"})

        return {
            "id": document_id,
            "status": "ready",
            "chunks_count": chunks_count,
            "message": "Reindexing completed",
        }
    except Exception as exc:
        logger.exception(f"Failed to reindex project document {document_id}")
        async with async_session_maker() as session:
            doc_dao = ProjectDocumentDAO(session)
            async with session.begin():
                refreshed = await doc_dao.find_one_by_filter(id=document_id)
                if refreshed:
                    await doc_dao.update(refreshed, {"status": "error"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось переиндексировать документ: {exc}",
        )


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


MAX_WEBSITES_PER_PROJECT = 3


@router.get("/{project_id}/websites")
async def get_project_websites(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """List all websites for a project (max 3 enforced at creation)."""
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
            )
            websites = result.scalars().all()

            return {
                "items": [
                    {
                        "id": w.id,
                        "slug": w.slug,
                        "title": w.title,
                        "status": w.status,
                        "generation_status": w.generation_status,
                        "agent_id": w.agent_id,
                        "created_at": w.created_at.isoformat() if w.created_at else None,
                        "published_at": w.published_at.isoformat() if w.published_at else None,
                        "url": f"/w/{w.slug}" if w.status == "published" else None,
                    }
                    for w in websites
                ],
                "total": len(websites),
                "can_create": len(websites) < MAX_WEBSITES_PER_PROJECT,
                "max": MAX_WEBSITES_PER_PROJECT,
            }


@router.post("/{project_id}/websites")
async def create_project_website(
    project_id: int,
    request: dict,
    current_user: User = Depends(get_current_user_from_token),
):
    """Create a new website for a project. Enforces the 3-site limit."""
    from ..router_websites.router import create_website
    from ..router_websites.schemas import WebsiteCreateRequest
    from ..router_websites.dao import WebsiteDAO, WebsiteTemplateDAO

    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )

            count_result = await session.execute(
                select(func.count(Website.id)).where(Website.project_id == project_id)
            )
            existing_count = count_result.scalar() or 0
            if existing_count >= MAX_WEBSITES_PER_PROJECT:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Maximum {MAX_WEBSITES_PER_PROJECT} websites per project",
                )

            # Use the website router service with the same user and project.
            website_request = WebsiteCreateRequest(
                agent_id=request.get("agent_id"),
                template_id=request.get("template_id"),
                slug=request.get("slug"),
                title=request.get("title"),
            )
            website_dao = WebsiteDAO(session)
            template_dao = WebsiteTemplateDAO(session)
            website = await create_website(
                request=website_request,
                user=current_user,
                website_dao=website_dao,
                template_dao=template_dao,
            )
            # Ensure project_id is set (Website create does not set it currently).
            website.project_id = project_id
            await session.flush()
            return {
                "id": website.id,
                "slug": website.slug,
                "title": website.title,
                "status": website.status,
                "generation_status": website.generation_status,
                "agent_id": website.agent_id,
                "created_at": website.created_at.isoformat() if website.created_at else None,
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


@router.patch("/{project_id}/checklist-visibility")
async def update_project_checklist_visibility(
    project_id: int,
    data: ProjectChecklistVisibilityUpdate,
    current_user: User = Depends(get_current_user_from_token),
):
    """Hide or show the onboarding checklist permanently."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            project.checklist_hidden = data.checklist_hidden
            await session.flush()
            return {"checklist_hidden": project.checklist_hidden}


# ---------------------------------------------------------------------------
# Project Integrations
# ---------------------------------------------------------------------------

@router.get("/{project_id}/integrations", response_model=ProjectIntegrationListResponse)
async def list_project_integrations(
    project_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """List all integrations for a project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            integration_dao = ProjectIntegrationDAO(session)
            integrations = await integration_dao.list_by_project(session, project_id)
            return ProjectIntegrationListResponse(
                items=[serialize_integration(i) for i in integrations],
                total=len(integrations),
            )


@router.post("/{project_id}/integrations", response_model=ProjectIntegrationResponse)
async def create_project_integration(
    project_id: int,
    data: ProjectIntegrationCreate,
    current_user: User = Depends(get_current_user_from_token),
):
    """Create a new integration for a project."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        integration_dao = ProjectIntegrationDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            try:
                integration_type = validate_integration_type(data.type)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(e),
                )
            encrypted = encrypt_credentials(credentials_from_request(data.model_dump()))
            token = generate_webhook_token()
            integration = await integration_dao.create(
                session=session,
                project_id=project_id,
                name=data.name.strip(),
                type=integration_type,
                config=data.config or {},
                encrypted_credentials=encrypted,
                webhook_token=token,
            )
            return ProjectIntegrationResponse.model_validate(serialize_integration(integration))


@router.patch("/{project_id}/integrations/{integration_id}", response_model=ProjectIntegrationResponse)
async def update_project_integration(
    project_id: int,
    integration_id: int,
    data: ProjectIntegrationUpdate,
    current_user: User = Depends(get_current_user_from_token),
):
    """Update an integration."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        integration_dao = ProjectIntegrationDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            integration = await integration_dao.get_by_id(session, integration_id)
            if not integration or integration.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found",
                )
            if data.type is not None:
                try:
                    data.type = validate_integration_type(data.type)
                except ValueError as e:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=str(e),
                    )
            encrypted = None
            if data.credentials is not None:
                encrypted = encrypt_credentials(data.credentials)
            integration = await integration_dao.update(
                session=session,
                integration=integration,
                name=data.name,
                type=data.type,
                config=data.config,
                encrypted_credentials=encrypted,
                is_active=data.is_active,
            )
            return ProjectIntegrationResponse.model_validate(serialize_integration(integration))


@router.delete("/{project_id}/integrations/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_integration(
    project_id: int,
    integration_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Delete an integration."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        integration_dao = ProjectIntegrationDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            integration = await integration_dao.get_by_id(session, integration_id)
            if not integration or integration.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found",
                )
            await integration_dao.delete(session, integration)
            return None


@router.post("/{project_id}/integrations/{integration_id}/rotate-token", response_model=ProjectIntegrationResponse)
async def rotate_project_integration_token(
    project_id: int,
    integration_id: int,
    current_user: User = Depends(get_current_user_from_token),
):
    """Rotate the webhook token of an integration."""
    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        integration_dao = ProjectIntegrationDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )
            integration = await integration_dao.get_by_id(session, integration_id)
            if not integration or integration.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Integration not found",
                )
            integration.webhook_token = generate_webhook_token()
            await session.flush()
            return ProjectIntegrationResponse.model_validate(serialize_integration(integration))


@router.post("/{project_id}/integrations/webhook/{token}")
async def receive_project_webhook(
    project_id: int,
    token: str,
    payload: dict = Body(default_factory=dict),
):
    """Public webhook endpoint for a project integration.

    The URL token is the secret; no JWT required. The project_id is part of the
    URL but is validated against the integration record.
    """
    async with async_session_maker() as session:
        integration_dao = ProjectIntegrationDAO(session)
        async with session.begin():
            integration = await integration_dao.get_by_token(session, token)
            if not integration or integration.project_id != project_id or not integration.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Webhook not found",
                )
            event_type = payload.get("event_type") or "unknown"
            source = payload.get("source") or "webhook"
            event = await integration_dao.add_event(
                session=session,
                project_id=project_id,
                integration_id=integration.id,
                event_type=str(event_type)[:32],
                source=str(source)[:64],
                payload=payload,
            )
            return {
                "received": True,
                "event_id": event.id,
                "event_type": event.event_type,
            }


# ---------------------------------------------------------------------------
# AI Manager
# ---------------------------------------------------------------------------

class ProjectAiManagerChatRequest(BaseModel):
    """Request to chat with the project AI manager."""
    message: str = Field(..., min_length=1, max_length=2000)
    history: Optional[List[dict]] = Field(default_factory=list)


@router.post("/{project_id}/ai-manager/chat")
async def chat_with_project_ai_manager(
    project_id: int,
    request: ProjectAiManagerChatRequest,
    current_user: User = Depends(get_current_user_from_token),
):
    """Chat with the project AI manager. It has access to project data."""
    from ..services.project_ai_manager_service import ProjectAiManagerService

    async with async_session_maker() as session:
        project_dao = ProjectDAO(session)
        async with session.begin():
            project = await project_dao.get_by_id(session, project_id)
            if not project or project.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Project not found",
                )

    service = ProjectAiManagerService()
    answer = await service.answer(
        project_id=project_id,
        user_id=current_user.id,
        message=request.message,
        history=request.history or [],
    )
    return {"reply": answer}


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
