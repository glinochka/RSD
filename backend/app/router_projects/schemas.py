"""Pydantic schemas for Project API."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=80)
    industry: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None)


class ProjectCreate(BaseModel):
    """Create project request."""
    name: str = Field(..., min_length=1, max_length=200)
    industry: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None)


class ProjectUpdate(BaseModel):
    """Update project request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    industry: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None)


class ProjectResponse(BaseModel):
    """Project response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    name: str
    slug: str
    industry: Optional[str] = None
    description: Optional[str] = None
    status: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ProjectSummaryResponse(ProjectResponse):
    """Project with summary counts."""
    agents_count: int = 0
    website_id: Optional[int] = None
    website_status: Optional[str] = None


class ProjectListResponse(BaseModel):
    """List of projects response."""
    items: List[ProjectSummaryResponse]
    total: int


class ProjectBriefRequest(BaseModel):
    """AI-first project creation brief."""
    name: str = Field(..., min_length=1, max_length=200, description="Название бизнеса / отдела")
    industry: str = Field(..., description="Отрасль бизнеса")
    automation_goals: List[str] = Field(..., description="Что автоматизируем: поддержка, запись, продажи, контент, сайт")
    channels: List[str] = Field(default=[], description="Каналы связи: telegram, whatsapp, сайт, телефон")
    description: str = Field(..., min_length=50, max_length=800, description="Краткое описание бизнеса")
    communication_tone: Optional[str] = Field(None, description="Тон общения: friendly, business, premium")
    city: Optional[str] = Field(None, max_length=100, description="Город / регион")


class AgentPlanItem(BaseModel):
    """Agent in AI-generated plan."""
    suggested_name: str
    template_type: str
    system_prompt: str
    welcome_message: str
    template_config: Dict[str, Any] = {}


class WebsitePlanItem(BaseModel):
    """Website in AI-generated plan."""
    enabled: bool
    title: str
    suggested_slug: str
    generation_prompt: str


class ProjectPlanResponse(BaseModel):
    """AI-generated project plan."""
    project: Dict[str, Any]
    agents: List[AgentPlanItem]
    website: WebsitePlanItem
    knowledge_recommendations: List[str]
    crm_hints: Dict[str, Any]


class ApplyProjectPlanRequest(BaseModel):
    """Request to apply AI plan and create entities."""
    brief: ProjectBriefRequest
    plan: ProjectPlanResponse
    idempotency_key: Optional[str] = None


class ApplyProjectPlanResponse(BaseModel):
    """Response after applying project plan."""
    project_id: int
    agent_ids: List[int]
    website_id: Optional[int] = None
    status: str


class ProjectSummaryWidget(BaseModel):
    """Project summary for dashboard."""
    agents_total: int
    agents_active: int
    dialogs_7d: int = 0
    new_leads_7d: int = 0
    website_status: Optional[str] = None
    website_url: Optional[str] = None


class OnboardingChecklistItem(BaseModel):
    """Onboarding checklist item."""
    id: str
    label: str
    completed: bool
    action_url: Optional[str] = None


class ProjectDashboardResponse(BaseModel):
    """Dashboard data for project."""
    project: ProjectSummaryResponse
    summary: ProjectSummaryWidget
    onboarding_checklist: List[OnboardingChecklistItem]
    quick_actions: List[Dict[str, Any]]
