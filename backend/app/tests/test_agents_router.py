import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient

from app.services.crm.providers.base import CRMConnectionHealth


class TestAgentsAuth:
    """Тесты аутентификации агентов"""
    
    @pytest.mark.asyncio
    async def test_get_agent_unauthorized(self, client: AsyncClient, test_agent):
        """Получение агента без авторизации"""
        response = await client.get(
            "/api/agents",
            params={"bot_id": test_agent.bot_id}
        )
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_agent_with_auth(self, client: AsyncClient, auth_headers, test_agent):
        """Получение агента с авторизацией"""
        response = await client.get(
            "/api/agents",
            headers=auth_headers,
            params={"bot_id": test_agent.bot_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["bot_id"] == test_agent.bot_id
        assert data["bot_username"] == test_agent.bot_username


class TestAgentsCRUD:
    """Тесты CRUD операций с агентами"""
    
    @pytest.mark.asyncio
    async def test_create_agent_by_token_success(
        self, client: AsyncClient, auth_headers, test_user, monkeypatch
    ):
        """Успешное создание агента по токену"""
        monkeypatch.setenv("BASE_URL", "https://example.com")
        
        # Мокаем оба вызова urlopen в роутере: getMe и setWebhook
        with patch("app.router_agents.router.urlopen") as mock_urlopen:
            # Первый вызов: getMe
            mock_response_getme = MagicMock()
            mock_response_getme.read.return_value = json.dumps({
                "ok": True,
                "result": {"id": 888888888, "username": "new_test_bot"}
            }).encode()
            
            # Второй вызов: setWebhook
            mock_response_webhook = MagicMock()
            mock_response_webhook.read.return_value = json.dumps({"ok": True}).encode()
            
            # Настраиваем контекстные менеджеры для каждого вызова
            mock_context_getme = MagicMock()
            mock_context_getme.__enter__.return_value = mock_response_getme
            mock_context_getme.__exit__.return_value = None
            
            mock_context_webhook = MagicMock()
            mock_context_webhook.__enter__.return_value = mock_response_webhook
            mock_context_webhook.__exit__.return_value = None
            
            # side_effect возвращает разные контекстные менеджеры по порядку
            mock_urlopen.side_effect = [mock_context_getme, mock_context_webhook]
            
            response = await client.post(
                "/api/agents/by_token",
                headers=auth_headers,
                json={
                    "bot_token": "test_token_123",
                    "system_prompt": "Test system prompt"
                }
            )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["bot_id"] == 888888888
    
    @pytest.mark.asyncio
    async def test_create_agent_duplicate(
        self, client: AsyncClient, auth_headers, test_agent
    ):
        """Создание дубликата агента"""
        # Мокаем только getMe, возвращаем bot_id уже существующего агента
        with patch("app.router_agents.router.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "ok": True,
                "result": {"id": test_agent.bot_id, "username": "existing_bot"}
            }).encode()
            
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_response
            mock_context.__exit__.return_value = None
            mock_urlopen.return_value = mock_context
            
            response = await client.post(
                "/api/agents/by_token",
                headers=auth_headers,
                json={
                    "bot_token": "test_bot_token",
                    "system_prompt": "Test prompt"
                }
            )
        
        # Ожидаем 409 Conflict, так как агент с таким bot_id уже есть
        assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
        assert "уже зарегистрирован" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_update_agent(self, client: AsyncClient, auth_headers, test_agent):
        """Обновление агента"""
        response = await client.patch(
            "/api/agents/by_botID",
            headers=auth_headers,
            json={
                "bot_id": test_agent.bot_id,
                "name": "Updated Bot Name",
                "system_prompt": "Updated system prompt"
            }
        )
        
        assert response.status_code == 204, f"Expected 204, got {response.status_code}: {response.text}"
    
    @pytest.mark.asyncio
    async def test_toggle_agent_status(
        self, client: AsyncClient, auth_headers, test_agent, monkeypatch
    ):
        """Переключение статуса агента"""
        monkeypatch.setenv("BASE_URL", "https://example.com")
        
        # При переключении с True на False будет вызван deleteWebhook
        with patch("app.router_agents.router.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({"ok": True}).encode()
            
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_response
            mock_context.__exit__.return_value = None
            mock_urlopen.return_value = mock_context
            
            response = await client.patch(
                "/api/agents/toggle_status",
                headers=auth_headers,
                json={"bot_id": test_agent.bot_id}
            )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Изначально агент активен (is_active=True), после переключения должен стать False
        assert data["is_active"] is False
    
    @pytest.mark.asyncio
    async def test_delete_agent(self, client: AsyncClient, auth_headers, test_agent):
        """Удаление агента"""
        with patch('app.router_agents.router.delete_agent_vectors', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            
            response = await client.delete(
                "/api/agents",
                headers=auth_headers,
                params={"bot_id": test_agent.bot_id}
            )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        mock_delete.assert_called_once_with(test_agent.bot_id)
    
    @pytest.mark.asyncio
    async def test_get_all_agents_by_tg_id(
        self, client: AsyncClient, auth_headers, test_user, test_agent
    ):
        """Получение всех агентов пользователя по tg_id"""
        response = await client.get(
            "/api/agents/allBy_tgID",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_create_empty_agent_sales_manager_default_config(self, client: AsyncClient, auth_headers):
        """Создание sales_manager с дефолтным безопасным template_config."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Sales system prompt",
                "template_type": "sales_manager",
            },
        )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["template_type"] == "sales_manager"
        cfg = data["template_config"] or {}
        assert cfg["mode"] == "draft_only"
        assert cfg["qualification_model"] == "deepseek-chat"
        assert cfg["generation_model"] == "deepseek-chat"
        assert cfg["min_confidence"] == 0.75
        assert cfg["dm_limits"]["per_minute"] == 3
        assert cfg["dm_limits"]["per_hour"] == 25
        assert cfg["dm_limits"]["per_day"] == 120
        assert cfg["cooldown_days"] == 14
        assert cfg["dedup_window_days"] == 30
        assert cfg["allowed_languages"] == ["ru", "en"]

    @pytest.mark.asyncio
    async def test_create_empty_agent_sales_manager_invalid_mode(self, client: AsyncClient, auth_headers):
        """sales_manager отклоняет невалидный режим."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Sales system prompt",
                "template_type": "sales_manager",
                "template_config": {
                    "mode": "unsafe_auto",
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        assert "template_config.mode" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_empty_agent_sales_manager_invalid_limit(self, client: AsyncClient, auth_headers):
        """sales_manager отклоняет невалидные лимиты."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Sales system prompt",
                "template_type": "sales_manager",
                "template_config": {
                    "dm_limits": {
                        "per_minute": 0,
                    },
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        assert "template_config.dm_limits.per_minute" in response.json()["detail"]


class TestAgentsInternal:
    """Тесты внутренних API агентов"""
    
    @pytest.mark.asyncio
    async def test_create_agent_by_tg_id_internal(
        self, client: AsyncClient, internal_api_headers, test_user
    ):
        """Создание агента через внутренний API по tg_id"""
        response = await client.post(
            "/api/agents/ByUserWith_tgID",
            headers=internal_api_headers,
            json={
                "tg_id": test_user.telegram_id,
                "bot_id": 999999999,
                "bot_username": "internal_bot",
                "encrypted_token": "encrypted_token_value",
                "system_prompt": "Internal bot prompt"
            }
        )
        
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"


class TestAgentsCrm:
    """Smoke-тесты CRM endpoints."""

    @pytest.mark.asyncio
    async def test_connect_crm_bitrix24_smoke(self, client: AsyncClient, auth_headers, test_agent):
        mock_provider = AsyncMock()
        mock_provider.validate_connection.return_value = CRMConnectionHealth(
            ok=True,
            provider="bitrix24",
            external_id="bitrix-user-42",
            details={"name": "Bitrix User"},
        )

        with patch("app.router_agents.router.build_provider", return_value=mock_provider):
            response = await client.post(
                "/api/agents/crm/connect",
                headers=auth_headers,
                json={
                    "bot_id": test_agent.bot_id,
                    "provider": "bitrix24",
                    "account_base_url": "https://portal.bitrix24.ru/rest/1/abc123",
                    "access_token": "x" * 24,
                },
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["health"]["ok"] is True
        assert data["health"]["provider"] == "bitrix24"
        assert data["health"]["external_id"] == "bitrix-user-42"
        assert data["crm_connection"]["provider"] == "bitrix24"