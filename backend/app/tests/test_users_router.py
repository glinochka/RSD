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
        with patch("app.router_users.router._send_registration_email_code", new=AsyncMock()):
            response = await client.post(
                "/api/users/registration",
                json=sample_user_data
            )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "verification_required"
        assert data["email"] == sample_user_data["email"]

        # Verify user was created in database
        async with test_session.begin():
            result = await test_session.execute(
                select(User).where(User.email == sample_user_data["email"])
            )
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.email == sample_user_data["email"]
            assert isinstance(user.name, str)
            assert len(user.name) >= 3
            assert user.email_verified is False
            assert user.email_verification_last_sent_at is not None

    @pytest.mark.asyncio
    async def test_registration_resend_cooldown(self, client, sample_user_data):
        """Repeated resend code is blocked for 120s after a successful send."""
        with patch("app.router_users.router._send_registration_email_code", new=AsyncMock()):
            first = await client.post("/api/users/registration", json=sample_user_data)
        assert first.status_code == 201

        with patch("app.router_users.router._send_registration_email_code", new=AsyncMock()):
            second = await client.post(
                "/api/users/registration/resend-code",
                json={"email": sample_user_data["email"]},
            )
        assert second.status_code == 429
        assert "Повторная отправка" in second.json()["detail"]
        assert second.headers.get("retry-after") is not None

    @pytest.mark.asyncio
    async def test_registration_repeat_for_existing_user_conflict(self, client, sample_user_data):
        """Existing account cannot re-register and no additional code should be sent."""
        send_mock = AsyncMock()
        with patch("app.router_users.router._send_registration_email_code", new=send_mock):
            first = await client.post("/api/users/registration", json=sample_user_data)
            second = await client.post("/api/users/registration", json=sample_user_data)
        assert first.status_code == 201
        assert second.status_code == 409
        assert send_mock.await_count == 1

    @pytest.mark.asyncio
    async def test_registration_duplicate_email(self, client, sample_user_data, test_session):
        """Test registration fails when email already exists and verified."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "existing_user",
                "email": sample_user_data["email"],
                "password": get_password_hash("existingpassword"),
                "email_verified": True,
            })
            await test_session.commit()

        with patch("app.router_users.router._send_registration_email_code", new=AsyncMock()):
            response = await client.post(
                "/api/users/registration",
                json=sample_user_data
            )

        assert response.status_code == 409
        assert "Email уже используется" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_registration_invalid_email(self, client):
        """Test registration fails with invalid email."""
        response = await client.post(
            "/api/users/registration",
            json={"email": "invalid-email", "password": "password123"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_registration_short_password(self, client, sample_user_data):
        """Test registration fails with password too short."""
        response = await client.post(
            "/api/users/registration",
            json={"email": sample_user_data["email"], "password": "123"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_registration_verify_success(self, client, sample_user_data):
        """Test successful email verification after registration."""
        with patch("app.router_users.router._generate_email_code", return_value="123456"), \
             patch("app.router_users.router._send_registration_email_code", new=AsyncMock()):
            response = await client.post("/api/users/registration", json=sample_user_data)
        assert response.status_code == 201

        verify_response = await client.post(
            "/api/users/registration/verify",
            json={
                "email": sample_user_data["email"],
                "code": "123456",
            },
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert "access_token" in verify_data
        assert verify_data["token_type"] == "bearer"


class TestPasswordReset:
    """Tests for password reset flow endpoints."""

    @pytest.mark.asyncio
    async def test_password_reset_request_success(self, client, test_session):
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        email = "restore@example.com"
        async with test_session.begin():
            await user_dao.add({
                "name": "restore_user",
                "email": email,
                "email_verified": True,
                "password": get_password_hash("oldpassword123"),
            })

        with patch("app.router_users.router._send_password_reset_email_code", new=AsyncMock()):
            response = await client.post(
                "/api/users/password-reset/request",
                json={"email": email},
            )
        assert response.status_code == 200

        async with test_session.begin():
            result = await test_session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.password_reset_code_hash is not None
            assert user.password_reset_attempts_left > 0
            assert user.password_reset_last_sent_at is not None

    @pytest.mark.asyncio
    async def test_password_reset_request_user_not_found(self, client):
        response = await client.post(
            "/api/users/password-reset/request",
            json={"email": "not-found@example.com"},
        )
        assert response.status_code == 404
        assert "Пользователь не найден" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_password_reset_full_flow_success(self, client, test_session):
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        email = "restore2@example.com"
        old_password = "oldpassword123"
        new_password = "newpassword123"
        async with test_session.begin():
            await user_dao.add({
                "name": "restore_user2",
                "email": email,
                "email_verified": True,
                "password": get_password_hash(old_password),
            })

        with patch("app.router_users.router._generate_password_reset_code", return_value="123456"), \
             patch("app.router_users.router._send_password_reset_email_code", new=AsyncMock()):
            request_resp = await client.post(
                "/api/users/password-reset/request",
                json={"email": email},
            )
        assert request_resp.status_code == 200

        verify_resp = await client.post(
            "/api/users/password-reset/verify",
            json={"email": email, "code": "123456"},
        )
        assert verify_resp.status_code == 200
        reset_token = verify_resp.json().get("reset_token")
        assert reset_token

        confirm_resp = await client.post(
            "/api/users/password-reset/confirm",
            json={"email": email, "reset_token": reset_token, "new_password": new_password},
        )
        assert confirm_resp.status_code == 200

        login_resp = await client.post(
            "/api/users/login",
            json={"name": email, "password": new_password},
        )
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.json()


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
    async def test_login_success_by_email(self, client, test_session):
        """Test successful login using email as login field."""
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        long_email = "very.long.login.identifier.for.user@example.com"
        async with test_session.begin():
            await user_dao.add({
                "name": "emailuser",
                "email": long_email,
                "email_verified": True,
                "password": get_password_hash("correctpassword123"),
            })
            await test_session.commit()

        response = await client.post(
            "/api/users/login",
            json={"name": long_email, "password": "correctpassword123"}
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
        assert "Неверные учетные данные" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, client):
        """Test login fails when user doesn't exist."""
        response = await client.post(
            "/api/users/login",
            json={"name": "nonexistent", "password": "anypassword"}
        )

        assert response.status_code == 401
        assert "Неверные учетные данные" in response.json()["detail"]


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