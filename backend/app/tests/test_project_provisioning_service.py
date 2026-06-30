"""Tests for Project Provisioning Service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.project_provisioning_service import (
    ProjectProvisioningService,
    ProjectProvisioningError,
    _idempotency_cache,
)
from app.router_projects.schemas import (
    ProjectBriefRequest,
    ProjectPlanResponse,
    AgentPlanItem,
    WebsitePlanItem,
)


@pytest.fixture
def brief_request():
    return ProjectBriefRequest(
        name="Тестовый бизнес",
        industry="beauty_salon",
        automation_goals=["support", "booking"],
        channels=["telegram"],
        description="Салон красоты в центре города.",
        communication_tone="friendly",
        city="Москва",
    )


@pytest.fixture
def plan_response():
    return ProjectPlanResponse(
        project={
            "name": "Тестовый бизнес",
            "description": "Салон красоты",
            "industry": "beauty_salon",
        },
        agents=[
            AgentPlanItem(
                suggested_name="Администратор",
                template_type="crm_admin",
                system_prompt="Вы администратор салона. " * 20,
                welcome_message="Здравствуйте!",
                template_config={},
            ),
            AgentPlanItem(
                suggested_name="Консультант",
                template_type="qa",
                system_prompt="Вы консультант. " * 20,
                welcome_message="Приветствую!",
                template_config={},
            ),
        ],
        website=WebsitePlanItem(
            enabled=True,
            title="Тестовый бизнес",
            suggested_slug="testovyj-biznes",
            generation_prompt="Создайте сайт для салона",
        ),
        knowledge_recommendations=["Прайс-лист", "FAQ"],
        crm_hints={"booking_backend": "crm", "suggested_services": ["Стрижка"]},
    )


@pytest.mark.asyncio
async def test_apply_plan_creates_project(brief_request, plan_response):
    """Test that apply_plan creates project and agents."""
    mock_session = MagicMock()
    service = ProjectProvisioningService(mock_session)
    
    # Mock DAO methods
    with patch.object(service.project_dao, "create", AsyncMock()) as mock_create_project:
        with patch.object(service.project_dao, "get_by_slug", AsyncMock(return_value=None)):
            with patch.object(service.agent_dao, "add", AsyncMock()) as mock_create_agent:
                mock_project = MagicMock()
                mock_project.id = 1
                mock_create_project.return_value = mock_project
                
                mock_agent = MagicMock()
                mock_agent.id = 1
                mock_create_agent.return_value = mock_agent
                
                with patch.object(service, "_get_billing_fields", return_value={"maintenance_paid_until": None}):
                    result = await service.apply_plan(
                        user_id=1,
                        brief=brief_request,
                        plan=plan_response,
                    )
    
    assert result.project_id == 1
    assert len(result.agent_ids) == 2
    assert result.status == "created"


@pytest.mark.asyncio
async def test_apply_plan_idempotency(brief_request, plan_response):
    """Test that apply_plan respects idempotency key."""
    mock_session = MagicMock()
    service = ProjectProvisioningService(mock_session)
    
    # First call
    with patch.object(service.project_dao, "create", AsyncMock()) as mock_create:
        with patch.object(service.project_dao, "get_by_slug", AsyncMock(return_value=None)):
            with patch.object(service.agent_dao, "add", AsyncMock()) as mock_create_agent:
                mock_project = MagicMock()
                mock_project.id = 1
                mock_create.return_value = mock_project
                
                mock_agent = MagicMock()
                mock_agent.id = 1
                mock_create_agent.return_value = mock_agent
                
                with patch.object(service, "_get_billing_fields", return_value={"maintenance_paid_until": None}):
                    result1 = await service.apply_plan(
                        user_id=1,
                        brief=brief_request,
                        plan=plan_response,
                        idempotency_key="test-key-123",
                    )
    
    # Second call with same key should not create new project
    result2 = await service.apply_plan(
        user_id=1,
        brief=brief_request,
        plan=plan_response,
        idempotency_key="test-key-123",
    )
    
    assert result1.project_id == result2.project_id
    assert result1.agent_ids == result2.agent_ids


def test_slugify():
    """Test slug generation."""
    mock_session = MagicMock()
    service = ProjectProvisioningService(mock_session)
    
    assert service._slugify("Тестовый Бизнес") == "testovyj-biznes"
    assert service._slugify("Hello World") == "hello-world"
    assert service._slugify("Test---Multiple") == "test-multiple"


@pytest.mark.asyncio
async def test_ensure_unique_slug_with_conflict():
    """Test slug uniquification when conflict exists."""
    mock_session = MagicMock()
    service = ProjectProvisioningService(mock_session)
    
    # First call returns existing project (conflict)
    # Second call returns None (available)
    side_effects = [
        MagicMock(),  # Conflict for "test-slug"
        None,         # Available for "test-slug-1"
    ]
    
    with patch.object(service.project_dao, "get_by_slug", AsyncMock(side_effect=side_effects)):
        slug = await service._ensure_unique_slug(1, "test-slug")
    
    assert slug == "test-slug-1"


@pytest.mark.asyncio
async def test_apply_plan_handles_agent_creation_errors(brief_request, plan_response):
    """Test that apply_plan continues even if one agent fails."""
    mock_session = MagicMock()
    service = ProjectProvisioningService(mock_session)
    
    with patch.object(service.project_dao, "create", AsyncMock()) as mock_create_project:
        with patch.object(service.project_dao, "get_by_slug", AsyncMock(return_value=None)):
            with patch.object(service.agent_dao, "add", AsyncMock()) as mock_create_agent:
                mock_project = MagicMock()
                mock_project.id = 1
                mock_create_project.return_value = mock_project
                
                # First agent succeeds, second fails
                mock_agent = MagicMock()
                mock_agent.id = 1
                mock_create_agent.side_effect = [mock_agent, Exception("Failed")]
                
                with patch.object(service, "_get_billing_fields", return_value={"maintenance_paid_until": None}):
                    result = await service.apply_plan(
                        user_id=1,
                        brief=brief_request,
                        plan=plan_response,
                    )
    
    # Should have created 1 agent even though second failed
    assert len(result.agent_ids) == 1


def test_get_billing_fields():
    """Test billing fields generation."""
    mock_session = MagicMock()
    service = ProjectProvisioningService(mock_session)
    
    with patch("app.services.project_provisioning_service.get_agent_template_pricing") as mock_pricing:
        with patch("app.services.project_provisioning_service.initial_maintenance_paid_until_for_template") as mock_paid_until:
            mock_pricing.return_value = {"maintenance_monthly_price_minor": 1000}
            mock_paid_until.return_value = None
            
            fields = service._get_billing_fields("qa")
    
    assert "activation_paid_at" in fields
    assert "maintenance_paid_until" in fields
