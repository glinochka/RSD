import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock, patch

from app.alembic.models import User, Agent


class TestAdminLogin:
    """Tests for POST /api/admin/login endpoint."""

    @pytest.mark.asyncio
    async def test_admin_login_success(self, client):
        """Test successful admin login."""
        from app.utils.security import get_password_hash

        with patch('app.router_admin.router.settings') as mock_settings:
            mock_settings.ADMIN_WEB_LOGIN = "admin"
            mock_settings.ADMIN_WEB_PASSWORD_HASH = get_password_hash("secure_password")

            response = await client.post(
                "/api/admin/login",
                json={"login": "admin", "password": "secure_password"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_admin_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        from app.utils.security import get_password_hash

        with patch('app.router_admin.router.settings') as mock_settings:
            mock_settings.ADMIN_WEB_LOGIN = "admin"
            mock_settings.ADMIN_WEB_PASSWORD_HASH = get_password_hash("secure_password")

            response = await client.post(
                "/api/admin/login",
                json={"login": "admin", "password": "wrong_password"}
            )

        assert response.status_code == 401
        assert "Invalid admin credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_login_not_configured(self, client):
        """Test login when admin credentials are not configured."""
        with patch('app.router_admin.router.settings') as mock_settings:
            mock_settings.ADMIN_WEB_LOGIN = ""
            mock_settings.ADMIN_WEB_PASSWORD_HASH = ""

            response = await client.post(
                "/api/admin/login",
                json={"login": "admin", "password": "password"}
            )

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_login_invalid_hash_config(self, client):
        """Test login when admin password hash has invalid format."""
        with patch('app.router_admin.router.settings') as mock_settings:
            mock_settings.ADMIN_WEB_LOGIN = "admin"
            mock_settings.ADMIN_WEB_PASSWORD_HASH = "plain-text-password"

            response = await client.post(
                "/api/admin/login",
                json={"login": "admin", "password": "plain-text-password"}
            )

        assert response.status_code == 503
        assert "misconfigured" in response.json()["detail"]


class TestAdminStats:
    """Tests for GET /api/admin/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_success(self, client, test_session):
        """Test getting admin statistics."""
        from app.utils.JWT import create_access_token

        # Create admin token
        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        # Create some test data
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user1 = await user_dao.add({
                "name": "statsUser1",
                "password": get_password_hash("password123"),
                "subscription_type": "Free",
            })
            user2 = await user_dao.add({
                "name": "statsUser2",
                "password": get_password_hash("password123"),
                "subscription_type": "Pro",
            })
            # Flush to generate IDs
            await test_session.flush()

            await agent_dao.add({
                "user_id": user1.id,
                "bot_id": 111111,
                "encrypted_token": "encrypted_token_1",  # unique
                "bot_username": "statsbot1",
                "is_active": True,
            })
            await agent_dao.add({
                "user_id": user2.id,
                "bot_id": 222222,
                "encrypted_token": "encrypted_token_2",  # unique
                "bot_username": "statsbot2",
                "is_active": False,
            })
            # commit will happen automatically on context exit

        response = await client.get("/api/admin/stats")

        assert response.status_code == 200
        data = response.json()
        assert "users_total" in data
        assert "agents_total" in data
        assert data["users_total"] >= 2
        assert data["agents_total"] >= 2

    @pytest.mark.asyncio
    async def test_get_stats_unauthorized(self, client):
        """Test getting stats without admin authentication."""
        response = await client.get("/api/admin/stats")

        assert response.status_code == 401


class TestAdminUsers:
    """Tests for GET /api/admin/users endpoint."""

    @pytest.mark.asyncio
    async def test_get_users_list_success(self, client, test_session):
        """Test getting paginated users list."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "listUser1",
                "password": get_password_hash("password123"),
                "telegram_id": 111111,
            })
            await user_dao.add({
                "name": "listUser2",
                "password": get_password_hash("password123"),
                "telegram_id": 222222,
            })
            await test_session.commit()

        response = await client.get("/api/admin/users?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_users_search(self, client, test_session):
        """Test searching users by name."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "SearchableUser",
                "password": get_password_hash("password123"),
            })
            await user_dao.add({
                "name": "AnotherUser",
                "password": get_password_hash("password123"),
            })
            await test_session.commit()

        response = await client.get("/api/admin/users?search=Searchable")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "SearchableUser"

    @pytest.mark.asyncio
    async def test_get_users_unauthorized(self, client):
        """Test getting users list without admin auth."""
        response = await client.get("/api/admin/users")

        assert response.status_code == 401


class TestAdminCreateUser:
    """Tests for POST /api/admin/users endpoint."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, client, test_session):
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        response = await client.post(
            "/api/admin/users",
            json={
                "email": "admin-created@example.com",
                "password": "secret12",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] is True
        assert data["item"]["email"] == "admin-created@example.com"
        assert data["item"]["email_verified"] is True

    @pytest.mark.asyncio
    async def test_create_user_can_login_without_verification(self, client, test_session):
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        email = "login-ready@example.com"
        password = "secret12"
        create_response = await client.post(
            "/api/admin/users",
            json={"email": email, "password": password},
        )
        assert create_response.status_code == 201

        client.headers.pop("Authorization", None)
        login_response = await client.post(
            "/api/users/login",
            json={"name": email, "password": password},
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_verified_email(self, client, test_session):
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "verifiedDup",
                "email": "verified-dup@example.com",
                "email_verified": True,
                "password": get_password_hash("password123"),
            })
            await test_session.commit()

        response = await client.post(
            "/api/admin/users",
            json={"email": "verified-dup@example.com", "password": "secret12"},
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_user_activates_unverified_email(self, client, test_session, verify_session):
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            await user_dao.add({
                "name": "pendingUser",
                "email": "pending@example.com",
                "email_verified": False,
                "password": get_password_hash("oldpass1"),
            })

        response = await client.post(
            "/api/admin/users",
            json={"email": "pending@example.com", "password": "newpass1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["created"] is False
        assert data["item"]["email_verified"] is True

        async with verify_session.begin():
            refreshed = await verify_session.scalar(
                select(User).where(User.email == "pending@example.com")
            )
        assert refreshed is not None
        assert refreshed.email_verified is True

    @pytest.mark.asyncio
    async def test_create_user_unauthorized(self, client):
        response = await client.post(
            "/api/admin/users",
            json={"email": "noauth@example.com", "password": "secret12"},
        )

        assert response.status_code == 401


class TestAdminAgents:
    """Tests for GET /api/admin/agents endpoint."""

    @pytest.mark.asyncio
    async def test_get_agents_list_success(self, client, test_session):
        """Test getting paginated agents list."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from app.router_agents.dao import AgentDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        agent_dao = AgentDAO(test_session)

        async with test_session.begin():
            user = await user_dao.add({
                "name": "agentListUser",
                "password": get_password_hash("password123"),
            })
            await test_session.flush()  # generate user id

            await agent_dao.add({
                "user_id": user.id,
                "bot_id": 333444,
                "encrypted_token": "encrypted_token_agent_list",  # unique
                "bot_username": "agentlistbot",
                "is_active": True,
            })
            # commit will happen on context exit

        response = await client.get("/api/admin/agents?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data


class TestAdminPlans:
    """Tests for GET/PUT /api/admin/plans endpoints."""

    @pytest.mark.asyncio
    async def test_get_plans_success(self, client):
        """Test getting subscription plans."""
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        response = await client.get("/api/admin/plans")

        assert response.status_code == 200
        data = response.json()
        assert "plans" in data

    @pytest.mark.asyncio
    async def test_update_plans_success(self, client):
        """Test updating subscription plans."""
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        # Fixed: request body matches SubscriptionPlanUpdate schema
        response = await client.put(
            "/api/admin/plans",
            json={
                "plans": [
                    {
                        "code": "Free",
                        "price_rub_month": 0,
                        "max_active_agents": 1,
                        "knowledge_base_chunk_limit": 50,
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "plans" in data


class TestAdminAgentTemplatePricing:
    """Tests for GET/PUT /api/admin/agent-template-pricing endpoints."""

    @pytest.mark.asyncio
    async def test_get_agent_template_pricing_success(self, client):
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        response = await client.get("/api/admin/agent-template-pricing")

        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        codes = {row["code"] for row in data["templates"]}
        assert "crm_admin" in codes
        assert "lead_generation" not in codes

    @pytest.mark.asyncio
    async def test_update_agent_template_pricing_success(self, client):
        from app.agent_template_pricing import _OVERRIDE_FILE_PATH, _reload_agent_template_pricing
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        try:
            response = await client.put(
                "/api/admin/agent-template-pricing",
                json={
                    "templates": [
                        {
                            "code": "crm_admin",
                            "title": "ИИ Администратор",
                            "card_title": "ИИ Администратор",
                            "setup_rub_min": 0,
                            "monthly_maintenance_rub_min": 1090,
                            "is_free": False,
                            "selectable": True,
                            "status": "available",
                            "description": "Тестовое описание",
                        }
                    ]
                },
            )

            assert response.status_code == 200
            data = response.json()
            crm = next(row for row in data["templates"] if row["code"] == "crm_admin")
            assert crm["monthly_maintenance_rub_min"] == 1090
        finally:
            if _OVERRIDE_FILE_PATH.exists():
                _OVERRIDE_FILE_PATH.unlink()
            _reload_agent_template_pricing()


class TestAdminBanUser:
    """Tests for POST /api/admin/users/{user_id}/ban endpoint."""

    @pytest.mark.asyncio
    async def test_ban_user_success(self, client, test_session, verify_session):
        """Test banning a user."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "banUser",
                "password": get_password_hash("password123"),
                "is_banned": False,
            })
            await test_session.commit()

        with patch('app.router_admin.router.delete_agent_vectors', return_value=True):
            response = await client.post(f"/api/admin/users/{user.id}/ban")

        assert response.status_code == 200

        # Verify user was banned (fresh session avoids stale identity-map reads)
        async with verify_session.begin():
            banned_user = await verify_session.scalar(
                select(User).where(User.id == user.id)
            )
            assert banned_user is not None
            assert banned_user.is_banned is True

    @pytest.mark.asyncio
    async def test_ban_user_not_found(self, client):
        """Test banning non-existent user."""
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        response = await client.post("/api/admin/users/999999/ban")

        assert response.status_code == 404


class TestAdminUnbanUser:
    """Tests for POST /api/admin/users/{user_id}/unban endpoint."""

    @pytest.mark.asyncio
    async def test_unban_user_success(self, client, test_session, verify_session):
        """Test unbanning a user."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "unbanUser",
                "password": get_password_hash("password123"),
                "is_banned": True,
            })
            await test_session.commit()

        response = await client.post(f"/api/admin/users/{user.id}/unban")

        assert response.status_code == 200

        # Verify user was unbanned
        async with verify_session.begin():
            unbanned_user = await verify_session.scalar(
                select(User).where(User.id == user.id)
            )
            assert unbanned_user is not None
            assert unbanned_user.is_banned is False

    @pytest.mark.asyncio
    async def test_unban_user_not_banned(self, client, test_session):
        """Test unbanning user who is not banned."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "notBannedUser",
                "password": get_password_hash("password123"),
                "is_banned": False,
            })
            await test_session.commit()

        response = await client.post(f"/api/admin/users/{user.id}/unban")

        assert response.status_code == 200
        data = response.json()
        assert "not banned" in data["detail"].lower()


class TestAdminGiftSubscription:
    """Tests for POST /api/admin/users/{user_id}/gift-subscription endpoint."""

    @pytest.mark.asyncio
    async def test_gift_subscription_success(self, client, test_session):
        """Test gifting subscription to a user."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "giftUser",
                "password": get_password_hash("password123"),
                "subscription_type": "Free",
            })
            await test_session.commit()

        response = await client.post(
            f"/api/admin/users/{user.id}/gift-subscription",
            json={"plan_code": "Advanced"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["subscription_type"] == "Advanced"
        assert "subscription_end_date" in data

    @pytest.mark.asyncio
    async def test_gift_subscription_invalid_plan(self, client, test_session):
        """Test gifting with invalid plan code."""
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "invalidGiftUser",
                "password": get_password_hash("password123"),
            })
            await test_session.commit()

        response = await client.post(
            f"/api/admin/users/{user.id}/gift-subscription",
            json={"plan_code": "InvalidPlan"}
        )

        # Pydantic validation returns 422 for literal mismatch
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_gift_subscription_user_not_found(self, client):
        """Test gifting to non-existent user."""
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        response = await client.post(
            "/api/admin/users/999999/gift-subscription",
            json={"plan_code": "Advanced"}
        )

        assert response.status_code == 404


class TestAdminFreeAgentActivation:
    """Tests for POST /api/admin/users/{user_id}/free-agent-activation endpoint."""

    @pytest.mark.asyncio
    async def test_enable_free_agent_activation(self, client, test_session, verify_session):
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from sqlalchemy import select
        from app.alembic.models import User

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "freeActivationUser",
                "password": get_password_hash("password123"),
                "free_agent_activation": False,
            })
            await test_session.commit()

        response = await client.post(
            f"/api/admin/users/{user.id}/free-agent-activation",
            json={"enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["free_agent_activation"] is True

        async with verify_session.begin():
            updated = await verify_session.scalar(select(User).where(User.id == user.id))
            assert updated is not None
            assert updated.free_agent_activation is True

    @pytest.mark.asyncio
    async def test_disable_free_agent_activation(self, client, test_session, verify_session):
        from app.utils.JWT import create_access_token
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO
        from sqlalchemy import select
        from app.alembic.models import User

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "paidActivationUser",
                "password": get_password_hash("password123"),
                "free_agent_activation": True,
            })
            await test_session.commit()

        response = await client.post(
            f"/api/admin/users/{user.id}/free-agent-activation",
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["free_agent_activation"] is False

        async with verify_session.begin():
            updated = await verify_session.scalar(select(User).where(User.id == user.id))
            assert updated is not None
            assert updated.free_agent_activation is False

    @pytest.mark.asyncio
    async def test_free_agent_activation_user_not_found(self, client):
        from app.utils.JWT import create_access_token

        admin_token = create_access_token({"admin_web": True})
        client.headers["Authorization"] = f"Bearer {admin_token}"

        response = await client.post(
            "/api/admin/users/999999/free-agent-activation",
            json={"enabled": True},
        )

        assert response.status_code == 404