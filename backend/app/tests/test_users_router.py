import pytest
from sqlalchemy import select
from unittest.mock import patch, AsyncMock

from app.alembic.models import User


# --- Дополнительные фикстуры для тестов (вставьте в conftest.py или оставьте здесь) ---
@pytest.fixture
async def authenticated_client(client, auth_headers, test_user):
    """Возвращает клиент с заголовками авторизации и информацию о пользователе."""
    client.headers.update(auth_headers)
    return client, {"user_id": test_user.id, "name": test_user.name}


@pytest.fixture
async def internal_client(client, internal_api_headers):
    """Возвращает клиент с заголовками внутреннего API."""
    client.headers.update(internal_api_headers)
    return client


@pytest.fixture
def mock_httpx_client():
    """Мок для httpx.AsyncClient."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


class TestUserRegistration:
    """Tests for POST /api/users/registration endpoint."""

    @pytest.mark.asyncio
    async def test_registration_success(self, client, sample_user_data, test_session):
        """Test successful user registration."""
        response = await client.post(
            "/api/users/registration",
            json=sample_user_data
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify user was created in database
        async with test_session.begin():
            result = await test_session.execute(
                select(User).where(User.name == sample_user_data["name"])
            )
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.name == sample_user_data["name"]

    @pytest.mark.asyncio
    async def test_registration_duplicate_name(self, client, sample_user_data, test_session):
        """Test registration fails when username already exists."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": sample_user_data["name"],
                "password": get_password_hash("existingpassword"),
            })
            await test_session.commit()

        response = await client.post(
            "/api/users/registration",
            json=sample_user_data
        )

        assert response.status_code == 409
        assert "Пользователь уже существует" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_registration_short_name(self, client):
        """Test registration fails with name too short."""
        response = await client.post(
            "/api/users/registration",
            json={"name": "ab", "password": "password123"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_registration_short_password(self, client, sample_user_data):
        """Test registration fails with password too short."""
        response = await client.post(
            "/api/users/registration",
            json={"name": sample_user_data["name"], "password": "123"}
        )

        assert response.status_code == 422


class TestUserLogin:
    """Tests for POST /api/users/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, test_session):
        """Test successful user login."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "loginuser",
                "password": get_password_hash("correctpassword123"),
            })
            await test_session.commit()

        response = await client.post(
            "/api/users/login",
            json={"name": "loginuser", "password": "correctpassword123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_session):
        """Test login fails with wrong password."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "testuser",
                "password": get_password_hash("correctpassword"),
            })
            await test_session.commit()

        response = await client.post(
            "/api/users/login",
            json={"name": "testuser", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, client):
        """Test login fails when user doesn't exist."""
        response = await client.post(
            "/api/users/login",
            json={"name": "nonexistent", "password": "anypassword"}
        )

        assert response.status_code == 401
        


# --- Тесты для /api/users/me (требуют реализации эндпоинта) ---
# class TestUserMe:
#     @pytest.mark.asyncio
#     async def test_me_authenticated(self, authenticated_client):
#         client, user_info = authenticated_client
#         response = await client.get("/api/users/me")
#         assert response.status_code == 200
#         data = response.json()
#         assert data["id"] == user_info["user_id"]
#         assert "name" in data
#         assert "is_telegram_linked" in data
#
#     @pytest.mark.asyncio
#     async def test_me_unauthenticated(self, client):
#         response = await client.get("/api/users/me")
#         assert response.status_code == 401


class TestGetUserByAgentID:
    """Tests for GET /api/users/by_agentID endpoint."""

    @pytest.mark.asyncio
    async def test_get_by_agent_id_success(self, internal_client, test_session):
        """Test getting user by agent ID (internal request)."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.add({
                "name": "agentowner",
                "password": get_password_hash("password123"),
            })
            await test_session.flush()  # <-- обязательно, чтобы получить user.id

            agent = await agent_dao.add({
                "user_id": user.id,
                "bot_id": 12345,
                "encrypted_token": "encrypted_test_token",
                "bot_username": "testbot",
            })
            await test_session.commit()

        response = await internal_client.get("/api/users/by_agentID?id=12345")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "agentowner"
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_get_by_agent_id_not_found(self, internal_client):
        """Test getting user by non-existent agent ID."""
        response = await internal_client.get("/api/users/by_agentID?id=99999")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_by_agent_id_unauthorized(self, client):
        """Test getting user by agent ID without internal API key."""
        response = await client.get("/api/users/by_agentID?id=12345")

        assert response.status_code == 401


class TestGetUserByTgID:
    """Tests for GET /api/users/by_tgID endpoint."""

    @pytest.mark.asyncio
    async def test_get_by_tg_id_success(self, internal_client, test_session):
        """Test getting user by Telegram ID (internal request)."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "tguser",
                "password": get_password_hash("password123"),
                "telegram_id": 987654321,
            })
            await test_session.commit()

        response = await internal_client.get("/api/users/by_tgID?id=987654321")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "tguser"
        assert data["telegram_id"] == 987654321

    @pytest.mark.asyncio
    async def test_get_by_tg_id_not_found(self, internal_client):
        """Test getting user by non-existent Telegram ID."""
        response = await internal_client.get("/api/users/by_tgID?id=111111111")

        assert response.status_code == 404


class TestUpdateUserByTgID:
    """Tests for PATCH /api/users/by_tgID endpoint."""

    @pytest.mark.asyncio
    async def test_update_subscription_success(self, internal_client, test_session):
        """Test updating user subscription (internal request)."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "subuser",
                "password": get_password_hash("password123"),
                "telegram_id": 555666777,
                "subscription_type": "Free",
            })
            await test_session.commit()

        response = await internal_client.patch(
            "/api/users/by_tgID",
            json={
                "telegram_id": 555666777,
                "subscription_type": "Pro"
            }
        )

        assert response.status_code == 204

        # Verify update in database
        async with test_session.begin():
            result = await test_session.execute(
                select(User).where(User.telegram_id == 555666777)
            )
            user = result.scalar_one_or_none()
            assert user.subscription_type == "Pro"


class TestCreateUserInternal:
    """Tests for POST /api/users/ endpoint (internal creation)."""

    @pytest.mark.asyncio
    async def test_create_user_internal_success(self, internal_client):
        """Test creating user via internal API."""
        user_data = {
            "name": "internaluser",
            "telegram_id": 111222333
        }

        response = await internal_client.post(
            "/api/users",
            json=user_data
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_user_internal_duplicate(self, internal_client, test_session):
        """Test creating duplicate user via internal API fails."""
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "duplicateuser",
                "telegram_id": 444555666,
            })
            await test_session.commit()

        response = await internal_client.post(
            "/api/users",
            json={"name": "duplicateuser", "telegram_id": 777888999}
        )

        assert response.status_code == 409


# --- Тесты для Telegram link (требуют реализации эндпоинтов и моделей) ---
# class TestTelegramLinkStart:
#     @pytest.mark.asyncio
#     async def test_start_link_success(self, authenticated_client, test_session, mock_httpx_client):
#         ...
#
#     @pytest.mark.asyncio
#     async def test_start_link_already_linked(self, authenticated_client, test_session):
#         ...

# class TestTelegramLinkConfirm:
#     @pytest.mark.asyncio
#     async def test_confirm_link_success(self, internal_client, test_session):
#         ...
#
#     @pytest.mark.asyncio
#     async def test_confirm_link_invalid_code(self, internal_client):
#         ...