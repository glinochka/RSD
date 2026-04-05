import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock, patch

from app.alembic.models import User, Agent, AgentDocument


class TestGetAllDocumentsByBotID:
    """Tests for GET /api/documents/allBy_botID endpoint."""

    @pytest.mark.asyncio
    async def test_get_documents_success(self, authenticated_client, test_session):
        """Test getting all documents for an agent (authenticated user)."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO
        from app.router_documents.dao import DocumentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)
        doc_dao = DocumentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 54321,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "docbot",
            })
            await test_session.flush()
            doc1 = await doc_dao.add({
                "agent_id": agent.id,
                "file_name": "test_doc1.pdf",
                "status": "processed",
            })
            doc2 = await doc_dao.add({
                "agent_id": agent.id,
                "file_name": "test_doc2.txt",
                "status": "processed",
            })
            await test_session.commit()

        response = await client.get("/api/documents/allBy_botID?bot_id=54321")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_documents_agent_not_found(self, authenticated_client):
        """Test getting documents for non-existent agent."""
        client, _ = authenticated_client
        response = await client.get("/api/documents/allBy_botID?bot_id=99999")
        assert response.status_code == 404
        assert "Agent not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_documents_unauthorized(self, client, test_session):
        """Test getting documents without authentication."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.add({
                "name": "otheruser",
                "password": get_password_hash("password123"),
            })
            await test_session.flush()
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 11111,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "otherbot",
            })
            await test_session.commit()

        response = await client.get("/api/documents/allBy_botID?bot_id=11111")
        assert response.status_code == 401


class TestGetDocumentByID:
    """Tests for GET /api/documents/{doc_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_document_success(self, authenticated_client, test_session):
        """Test getting a specific document by ID."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO
        from app.router_documents.dao import DocumentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)
        doc_dao = DocumentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 22222,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "singlebot",
            })
            await test_session.flush()
            doc = await doc_dao.add({
                "agent_id": agent.id,
                "file_name": "single_doc.pdf",
                "status": "processed",
            })
            await test_session.commit()

        response = await client.get(f"/api/documents/{doc.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["file_name"] == "single_doc.pdf"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, authenticated_client):
        """Test getting non-existent document."""
        client, _ = authenticated_client
        response = await client.get("/api/documents/99999")
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_document_forbidden(self, authenticated_client, test_session):
        """Test getting document belonging to another user."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO
        from app.router_documents.dao import DocumentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)
        doc_dao = DocumentDAO(test_session)

        async with test_session.begin():
            other_user = await user_dao.add({
                "name": "otheruser123",
                "password": get_password_hash("password123"),
            })
            await test_session.flush()
            agent = await agent_dao.add({
                "user_id": other_user.id,
                "bot_id": 33333,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "otherbot123",
            })
            await test_session.flush()
            doc = await doc_dao.add({
                "agent_id": agent.id,
                "file_name": "private_doc.pdf",
                "status": "processed",
            })
            await test_session.commit()

        response = await client.get(f"/api/documents/{doc.id}")
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]


class TestDeleteDocument:
    """Tests for DELETE /api/documents/{doc_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_document_success(self, authenticated_client, test_session):
        """Test successful document deletion."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO
        from app.router_documents.dao import DocumentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)
        doc_dao = DocumentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 44444,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "deletebot",
            })
            await test_session.flush()
            doc = await doc_dao.add({
                "agent_id": agent.id,
                "file_name": "to_delete.pdf",
                "status": "processed",
            })
            await test_session.commit()

        # Используем AsyncMock для асинхронной функции delete_document_vectors
        with patch('app.router_documents.router.delete_document_vectors', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            response = await client.delete(f"/api/documents/{doc.id}")

        assert response.status_code == 200
        data = response.json()
        assert "agent_id" in data

        async with test_session.begin():
            result = await test_session.execute(
                select(AgentDocument).where(AgentDocument.id == doc.id)
            )
            deleted_doc = result.scalar_one_or_none()
            assert deleted_doc is None

    @pytest.mark.asyncio
    async def test_delete_document_qdrant_error(self, authenticated_client, test_session):
        """Test deletion fails when Qdrant returns error."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO
        from app.router_documents.dao import DocumentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)
        doc_dao = DocumentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 55555,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "qdrantbot",
            })
            await test_session.flush()
            doc = await doc_dao.add({
                "agent_id": agent.id,
                "file_name": "qdrant_error.pdf",
                "status": "processed",
            })
            await test_session.commit()

        with patch('app.router_documents.router.delete_document_vectors', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = False
            response = await client.delete(f"/api/documents/{doc.id}")

        assert response.status_code == 500
        assert "Qdrant deleting error" in response.json()["detail"]


class TestGetContext:
    """Tests for GET /api/documents/getContextBy_agentID endpoint."""

    @pytest.mark.asyncio
    async def test_get_context_success(self, authenticated_client, test_session):
        """Test getting context for a query."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 66666,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "contextbot",
            })
            await test_session.commit()

        mock_context = [
            {"text": "Relevant context 1", "source": "doc1.pdf"},
            {"text": "Relevant context 2", "source": "doc2.pdf"},
        ]
        with patch('app.router_documents.router.search_knowledge_base', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_context
            response = await client.get(f"/api/documents/getContextBy_agentID?agent_id={agent.bot_id}&query=test+question")

        assert response.status_code == 200
        data = response.json()
        assert data == mock_context

    @pytest.mark.asyncio
    async def test_get_context_agent_not_found(self, authenticated_client):
        """Test getting context for non-existent agent."""
        client, _ = authenticated_client
        response = await client.get("/api/documents/getContextBy_agentID?agent_id=99999&query=test")
        assert response.status_code == 404
        assert "Agent not found" in response.json()["detail"]


class TestUploadDocument:
    """Tests for POST /api/documents/ endpoint (upload)."""

    @pytest.mark.asyncio
    async def test_upload_document_success(self, authenticated_client, test_session):
        """Test successful document upload."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            await user_dao.update(user, {"subscription_type": "Free"})
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 77777,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "uploadbot",
            })
            await test_session.commit()

        with patch('app.router_documents.router.extract_text', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = "Sample document text content"
            with patch('app.router_documents.router.text_splitter') as mock_splitter:
                mock_splitter.split_text = MagicMock(return_value=["chunk1", "chunk2"])
                with patch('app.router_documents.router.get_current_chunks_count', new_callable=AsyncMock) as mock_count:
                    mock_count.return_value = 0
                    with patch('app.router_documents.router.get_chunk_limit_by_plan', return_value=100):
                        with patch('app.router_documents.router.process_document', new_callable=AsyncMock):
                            import io
                            file_content = io.BytesIO(b"fake pdf content")
                            response = await client.post(
                                "/api/documents",
                                data={"agent_data": f'{{"bot_id": {agent.bot_id}}}'},
                                files={"file": ("test.pdf", file_content, "application/pdf")}
                            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "limit_ok"
        assert data["new_chunks_count"] == 2

    @pytest.mark.asyncio
    async def test_upload_document_limit_exceeded(self, authenticated_client, test_session):
        """Test upload fails when chunk limit exceeded."""
        client, user_info = authenticated_client
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            await user_dao.update(user, {"subscription_type": "Free"})
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 88888,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "limitbot",
            })
            await test_session.commit()

        with patch('app.router_documents.router.extract_text', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = "Very long text"
            with patch('app.router_documents.router.text_splitter') as mock_splitter:
                mock_splitter.split_text = MagicMock(return_value=["chunk"] * 1000)
                with patch('app.router_documents.router.get_current_chunks_count', new_callable=AsyncMock) as mock_count:
                    mock_count.return_value = 0
                    with patch('app.router_documents.router.get_chunk_limit_by_plan', return_value=10):
                        import io
                        file_content = io.BytesIO(b"fake pdf content")
                        response = await client.post(
                            "/api/documents",
                            data={"agent_data": f'{{"bot_id": {agent.bot_id}}}'},
                            files={"file": ("test.pdf", file_content, "application/pdf")}
                        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "limit_error"


class TestUploadPublicLink:
    """Tests for POST /api/documents/link endpoint."""

    @pytest.mark.asyncio
    async def test_upload_public_link_success(self, authenticated_client, test_session):
        client, user_info = authenticated_client
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.find_one_by_filter(id=user_info["user_id"])
            await user_dao.update(user, {"subscription_type": "Free"})
            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 99991,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "linkbot",
            })
            await test_session.commit()

        with patch('app.router_documents.router.fetch_public_url_text', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "Some page text for indexing"
            with patch('app.router_documents.router.text_splitter') as mock_splitter:
                mock_splitter.split_text = MagicMock(return_value=["chunk1", "chunk2", "chunk3"])
                with patch('app.router_documents.router.get_current_chunks_count', new_callable=AsyncMock) as mock_count:
                    mock_count.return_value = 0
                    with patch('app.router_documents.router.get_chunk_limit_by_plan', return_value=100):
                        with patch('app.router_documents.router.process_text_source', new_callable=AsyncMock):
                            response = await client.post(
                                "/api/documents/link",
                                json={"bot_id": agent.bot_id, "url": "https://example.com/docs"},
                            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "limit_ok"
        assert data["new_chunks_count"] == 3

    @pytest.mark.asyncio
    async def test_upload_public_link_rejects_private_host(self, authenticated_client):
        client, _ = authenticated_client
        response = await client.post(
            "/api/documents/link",
            json={"bot_id": 1, "url": "http://127.0.0.1/private"},
        )
        assert response.status_code == 422
        assert "публичной" in response.json()["detail"]
