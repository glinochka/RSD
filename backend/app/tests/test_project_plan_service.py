"""Tests for Project Plan Service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.project_plan_service import (
    ProjectPlanService,
    ProjectPlanGenerationError,
    ALLOWED_TEMPLATE_TYPES,
    MAX_AGENTS,
)
from app.router_projects.schemas import ProjectBriefRequest, ProjectPlanResponse


@pytest.fixture
def brief_request():
    return ProjectBriefRequest(
        name="Тестовый бизнес",
        industry="beauty_salon",
        automation_goals=["support", "booking"],
        channels=["telegram"],
        description="Салон красоты в центре города. Услуги: стрижки, окрашивание.",
        communication_tone="friendly",
        city="Москва",
    )


@pytest.fixture
def mock_llm_response():
    return {
        "project": {
            "name": "Тестовый бизнес",
            "description": "Салон красоты",
            "industry": "beauty_salon",
        },
        "agents": [
            {
                "suggested_name": "Администратор",
                "template_type": "crm_admin",
                "system_prompt": "Вы администратор салона. " * 20,
                "welcome_message": "Здравствуйте!",
                "template_config": {},
            },
            {
                "suggested_name": "Консультант",
                "template_type": "qa",
                "system_prompt": "Вы консультант. " * 20,
                "welcome_message": "Приветствую!",
                "template_config": {},
            },
        ],
        "website": {
            "enabled": True,
            "title": "Тестовый бизнес",
            "suggested_slug": "testovyj-biznes",
            "generation_prompt": "Создайте сайт для салона",
        },
        "knowledge_recommendations": ["Прайс-лист", "FAQ"],
        "crm_hints": {
            "booking_backend": "crm",
            "suggested_services": ["Стрижка"],
        },
    }


@pytest.mark.asyncio
async def test_generate_plan_success(brief_request, mock_llm_response):
    """Test successful plan generation."""
    service = ProjectPlanService()
    
    # Mock the LLM client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = str(mock_llm_response).replace("'", '"')
    
    with patch.object(service.client.chat.completions, "create", AsyncMock(return_value=mock_response)):
        # For this test, we need to properly mock JSON parsing
        with patch.object(service, "_parse_json_response", return_value=mock_llm_response):
            plan = await service.generate_plan(brief_request)
    
    assert isinstance(plan, ProjectPlanResponse)
    assert len(plan.agents) <= MAX_AGENTS


@pytest.mark.asyncio
async def test_sanitize_plan_limits_agents(brief_request):
    """Test that plan sanitization limits agents to max."""
    service = ProjectPlanService()
    
    # Create plan data with too many agents
    plan_data = {
        "project": {"name": "Test", "industry": "retail"},
        "agents": [
            {"template_type": "qa", "suggested_name": f"Agent {i}", "system_prompt": "Test prompt " * 30}
            for i in range(10)  # More than MAX_AGENTS
        ],
        "website": {"enabled": False, "title": "", "suggested_slug": "", "generation_prompt": ""},
        "knowledge_recommendations": [],
        "crm_hints": {},
    }
    
    sanitized = service._sanitize_plan(plan_data, brief_request)
    
    assert len(sanitized["agents"]) <= MAX_AGENTS


def test_sanitize_plan_filters_template_types(brief_request):
    """Test that only allowed template types are kept."""
    service = ProjectPlanService()
    
    plan_data = {
        "project": {"name": "Test", "industry": "retail"},
        "agents": [
            {
                "template_type": "invalid_type",
                "suggested_name": "Test",
                "system_prompt": "Test prompt " * 30,
            }
        ],
        "website": {"enabled": False, "title": "", "suggested_slug": "", "generation_prompt": ""},
        "knowledge_recommendations": [],
        "crm_hints": {},
    }
    
    sanitized = service._sanitize_plan(plan_data, brief_request)
    
    # Invalid type should be changed to qa
    assert sanitized["agents"][0]["template_type"] in ALLOWED_TEMPLATE_TYPES


def test_sanitize_plan_short_prompt_fallback(brief_request):
    """Test that short system prompts get fallback."""
    service = ProjectPlanService()
    
    plan_data = {
        "project": {"name": "Test", "industry": "retail"},
        "agents": [
            {
                "template_type": "qa",
                "suggested_name": "Test",
                "system_prompt": "Short",  # Too short
            }
        ],
        "website": {"enabled": False, "title": "", "suggested_slug": "", "generation_prompt": ""},
        "knowledge_recommendations": [],
        "crm_hints": {},
    }
    
    sanitized = service._sanitize_plan(plan_data, brief_request)
    
    # Should generate fallback prompt
    assert len(sanitized["agents"][0]["system_prompt"]) > 100


def test_sanitize_plan_removes_placeholders(brief_request):
    """Test that {{placeholders}} are removed from prompts."""
    service = ProjectPlanService()
    
    plan_data = {
        "project": {"name": "Test", "industry": "retail"},
        "agents": [
            {
                "template_type": "qa",
                "suggested_name": "Test",
                "system_prompt": "Prompt with {{placeholder}} and {{another}}",
            }
        ],
        "website": {"enabled": False, "title": "", "suggested_slug": "", "generation_prompt": ""},
        "knowledge_recommendations": [],
        "crm_hints": {},
    }
    
    sanitized = service._sanitize_plan(plan_data, brief_request)
    
    # Placeholders should be removed
    assert "{{" not in sanitized["agents"][0]["system_prompt"]
    assert "}}" not in sanitized["agents"][0]["system_prompt"]


def test_parse_json_response_strips_markdown():
    """Test that markdown code blocks are stripped."""
    service = ProjectPlanService()
    
    # Test with markdown code block
    content = '```json\n{"key": "value"}\n```'
    result = service._parse_json_response(content)
    
    assert result == {"key": "value"}


def test_parse_json_response_extracts_json():
    """Test that JSON is extracted from surrounding text."""
    service = ProjectPlanService()
    
    content = 'Here is the plan: {"key": "value"} Hope it helps!'
    result = service._parse_json_response(content)
    
    assert result == {"key": "value"}


def test_slugify():
    """Test slug generation."""
    service = ProjectPlanService()
    
    assert service._slugify("Тестовый Бизнес") == "testovyj-biznes"
    assert service._slugify("Hello World") == "hello-world"
    assert service._slugify("Test---Multiple---Dashes") == "test-multiple-dashes"


def test_generate_default_knowledge_recs(brief_request):
    """Test default knowledge recommendations generation."""
    service = ProjectPlanService()
    
    recs = service._generate_default_knowledge_recs(brief_request)
    
    assert len(recs) > 0
    assert "Описание услуг" in recs[0]


@pytest.mark.asyncio
async def test_generate_plan_retry_on_error(brief_request):
    """Test that generation retries on failure."""
    service = ProjectPlanService()
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"invalid json'
    
    with patch.object(service.client.chat.completions, "create", AsyncMock(return_value=mock_response)):
        with pytest.raises(ProjectPlanGenerationError):
            await service.generate_plan(brief_request, max_retries=1)
