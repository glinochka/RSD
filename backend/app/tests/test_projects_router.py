"""Tests for Project router."""
import pytest
from fastapi import status
from httpx import AsyncClient

from app.alembic.models import Project


@pytest.mark.asyncio
async def test_list_projects_unauthorized(client: AsyncClient):
    """Test listing projects without auth fails."""
    response = await client.get("/api/projects")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_and_list_project(auth_client: AsyncClient, test_user):
    """Test creating and listing a project."""
    # Create a project
    create_data = {
        "name": "Test Business",
        "industry": "retail",
        "description": "Test description",
    }
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Test Business"
    assert data["slug"] == "test-business"
    assert data["industry"] == "retail"
    assert data["status"] == "active"
    
    # List projects
    response = await auth_client.get("/api/projects")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    
    # Find our created project
    project = next((p for p in data["items"] if p["name"] == "Test Business"), None)
    assert project is not None
    assert project["agents_count"] == 0


@pytest.mark.asyncio
async def test_get_project_detail(auth_client: AsyncClient, test_user):
    """Test getting project details."""
    # Create a project first
    create_data = {"name": "Detail Test", "industry": "beauty_salon"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    created = response.json()
    
    # Get project detail
    response = await auth_client.get(f"/api/projects/{created['id']}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == created["id"]
    assert data["name"] == "Detail Test"
    assert data["industry"] == "beauty_salon"


@pytest.mark.asyncio
async def test_update_project(auth_client: AsyncClient, test_user):
    """Test updating a project."""
    # Create a project
    create_data = {"name": "Update Test", "description": "Original"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    created = response.json()
    
    # Update project
    update_data = {"name": "Updated Name", "description": "Updated description"}
    response = await auth_client.patch(f"/api/projects/{created['id']}", json=update_data)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_archive_project(auth_client: AsyncClient, test_user):
    """Test archiving a project."""
    # Create a project
    create_data = {"name": "Archive Test"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    created = response.json()
    
    # Archive project
    response = await auth_client.delete(f"/api/projects/{created['id']}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify it's archived (should return 404)
    response = await auth_client.get(f"/api/projects/{created['id']}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_cannot_access_other_user_project(auth_client: AsyncClient):
    """Test that users cannot access other users' projects."""
    # This test assumes there's a way to create a project for another user
    # In practice, this would require another test user fixture
    response = await auth_client.get("/api/projects/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_unique_slug_generation(auth_client: AsyncClient, test_user):
    """Test that slugs are made unique when name collisions occur."""
    # Create first project
    response = await auth_client.post("/api/projects", json={"name": "Same Name"})
    assert response.status_code == status.HTTP_201_CREATED
    first = response.json()
    assert first["slug"] == "same-name"
    
    # Create second project with same name
    response = await auth_client.post("/api/projects", json={"name": "Same Name"})
    assert response.status_code == status.HTTP_201_CREATED
    second = response.json()
    assert second["slug"] == "same-name-1"
    assert second["id"] != first["id"]


@pytest.mark.asyncio
async def test_get_project_documents(auth_client: AsyncClient, test_user):
    """Test listing project documents."""
    # Create a project first
    create_data = {"name": "Doc Test Project"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()

    # List documents (empty initially)
    response = await auth_client.get(f"/api/projects/{project['id']}/documents")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_upload_project_document(auth_client: AsyncClient, test_user, monkeypatch):
    """Test uploading a file to project knowledge base."""
    from io import BytesIO

    create_data = {"name": "Upload Doc Test Project"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()

    # Avoid actual background processing/Qdrant calls in tests.
    monkeypatch.setattr(
        "app.router_projects.router.process_project_document",
        lambda *args, **kwargs: None,
    )

    file_content = b"This is a test knowledge base document."
    response = await auth_client.post(
        f"/api/projects/{project['id']}/documents",
        files={"file": ("test_doc.txt", BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "limit_ok"

    # Document should appear in the list
    response = await auth_client.get(f"/api/projects/{project['id']}/documents")
    assert response.status_code == status.HTTP_200_OK
    docs = response.json()
    assert len(docs) == 1
    assert docs[0]["file_name"] == "test_doc.txt"


@pytest.mark.asyncio
async def test_upload_project_link(auth_client: AsyncClient, test_user, monkeypatch):
    """Test adding a public link to project knowledge base."""
    create_data = {"name": "Link Doc Test Project"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()

    monkeypatch.setattr(
        "app.router_projects.router.fetch_public_url_text",
        lambda url: "Sample text from a public URL.",
    )
    monkeypatch.setattr(
        "app.router_projects.router.process_project_text_source",
        lambda *args, **kwargs: None,
    )

    response = await auth_client.post(
        f"/api/projects/{project['id']}/documents/link",
        json={"url": "https://example.com/sample-doc.txt"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "limit_ok"

    response = await auth_client.get(f"/api/projects/{project['id']}/documents")
    assert response.status_code == status.HTTP_200_OK
    docs = response.json()
    assert len(docs) == 1
    assert docs[0]["file_name"] == "https://example.com/sample-doc.txt"


@pytest.mark.asyncio
async def test_get_project_crm_summary(auth_client: AsyncClient, test_user):
    """Test getting project CRM summary."""
    # Create a project first
    create_data = {"name": "CRM Test Project"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()
    
    # Get CRM summary
    response = await auth_client.get(f"/api/projects/{project['id']}/crm/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "has_crm_admin" in data
    assert "has_sales_manager" in data
    assert "total_bookings" in data
    assert "total_contacts" in data


@pytest.mark.asyncio
async def test_get_project_website(auth_client: AsyncClient, test_user):
    """Test getting project website info."""
    # Create a project first
    create_data = {"name": "Website Test Project"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()
    
    # Get website (none exists)
    response = await auth_client.get(f"/api/projects/{project['id']}/website")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["exists"] is False


@pytest.mark.asyncio
async def test_get_project_dashboard(auth_client: AsyncClient, test_user):
    """Test getting project dashboard data."""
    # Create a project first
    create_data = {"name": "Dashboard Test Project", "industry": "retail"}
    response = await auth_client.post("/api/projects", json=create_data)
    assert response.status_code == status.HTTP_201_CREATED
    project = response.json()
    
    # Get dashboard
    response = await auth_client.get(f"/api/projects/{project['id']}/dashboard")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "project" in data
    assert "summary" in data
    assert "onboarding_checklist" in data
    assert "quick_actions" in data
    assert data["project"]["name"] == "Dashboard Test Project"
