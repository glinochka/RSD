import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient
import jwt

from app.services.crm.providers.base import CRMConnectionHealth
from app.config import settings
from app.alembic.models import AgentContentJob

YOUTUBE_OAUTH_STATE_SCOPE = "youtube_oauth_connect"


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
        from app.config import settings

        monkeypatch.setattr(settings, "BASE_URL", "https://example.com")
        
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
        
        with patch(
            "app.router_agents.router._telegram_bot_api_json",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
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
        with patch(
            "app.router_agents.router._schedule_sales_trigger_words_generation",
            new_callable=AsyncMock,
        ):
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
        assert cfg["mode"] == "auto"
        assert cfg["qualification_model"] == "deepseek-chat"
        assert cfg["generation_model"] == "deepseek-chat"
        assert cfg["min_confidence"] == 0.75
        assert cfg["workflow_completion_mode"] == "auto_finish_on_signal"
        assert cfg["lead_score_scale"] == 100
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

    @pytest.mark.asyncio
    async def test_create_empty_agent_sales_manager_invalid_workflow_completion_mode(self, client: AsyncClient, auth_headers):
        """sales_manager отклоняет невалидную настройку завершения диалога."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Sales system prompt",
                "template_type": "sales_manager",
                "template_config": {
                    "workflow_completion_mode": "invalid_mode",
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        assert "template_config.workflow_completion_mode" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_empty_agent_sales_manager_invalid_lead_score_scale(self, client: AsyncClient, auth_headers):
        """sales_manager отклоняет невалидную шкалу score лида."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Sales system prompt",
                "template_type": "sales_manager",
                "template_config": {
                    "lead_score_scale": 42,
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        assert "template_config.lead_score_scale" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_empty_agent_crm_admin_default_v2_config(self, client: AsyncClient, auth_headers):
        """crm_admin создаётся с v2-контрактом template_config по умолчанию."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "CRM admin system prompt",
                "template_type": "crm_admin",
            },
        )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        cfg = data["template_config"] or {}
        assert data["template_type"] == "crm_admin"
        assert cfg["domain_type"] == "beauty_salon"
        assert cfg["crm_mode"] == "optional"
        assert cfg["booking_backend"] == "crm"
        assert cfg["crm_provider"] == "amocrm"
        assert cfg["confirmation_policy"] == "confirm_risky"
        assert cfg["fallback_mode"] == "ask_clarifying_question"
        assert cfg["allowed_booking_tools"] == [
            "check_availability",
            "find_next_available",
            "list_appointments",
            "create_appointment",
            "reschedule_appointment",
            "cancel_appointment",
            "list_staff",
            "list_services",
        ]
        assert cfg["allowed_tools"] == [
            "find_contact",
            "create_contact",
            "find_lead",
            "create_lead",
            "update_lead",
            "add_note",
            "create_task",
            "assign_owner",
        ]

    @pytest.mark.asyncio
    async def test_get_agent_migrates_legacy_crm_admin_template_config(
        self, client: AsyncClient, auth_headers, test_session, test_agent
    ):
        """Legacy crm_admin config автоматически дополняется v2 полями при чтении."""
        async with test_session.begin():
            test_agent.template_type = "crm_admin"
            test_agent.template_config = json.dumps(
                {
                    "crm_provider": "bitrix24",
                    "allowed_tools": ["find_contact", "create_lead"],
                },
                ensure_ascii=False,
            )
            test_session.add(test_agent)

        response = await client.get(
            "/api/agents",
            headers=auth_headers,
            params={"bot_id": test_agent.bot_id},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        cfg = (response.json() or {}).get("template_config") or {}
        assert cfg["domain_type"] == "beauty_salon"
        assert cfg["crm_mode"] == "optional"
        assert cfg["booking_backend"] == "crm"
        assert cfg["crm_provider"] == "bitrix24"
        assert cfg["allowed_tools"] == ["find_contact", "create_lead"]

    @pytest.mark.asyncio
    async def test_youtube_oauth_start_returns_auth_url(self, client: AsyncClient, auth_headers, test_agent):
        fake_client = MagicMock()
        fake_client.build_oauth_authorization_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?state=test"
        with patch("app.router_agents.router.get_youtube_client", return_value=fake_client):
            response = await client.post(
                "/api/agents/channels/by_youtube_oauth_start",
                headers=auth_headers,
                json={
                    "bot_id": test_agent.bot_id,
                    "redirect_uri": "https://app.example.com/oauth/youtube/callback",
                },
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        payload = response.json()
        assert payload["agent_id"] == test_agent.id
        assert payload["auth_url"].startswith("https://accounts.google.com/")
        assert payload["state"]

    @pytest.mark.asyncio
    async def test_youtube_oauth_callback_connects_channel(self, client: AsyncClient, test_agent, test_user):
        now = datetime.utcnow()
        state = jwt.encode(
            {
                "scope": YOUTUBE_OAUTH_STATE_SCOPE,
                "user_id": test_user.id,
                "agent_id": test_agent.id,
                "redirect_uri": "https://app.example.com/oauth/youtube/callback",
                "exp": now + timedelta(minutes=10),
                "iat": now,
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        fake_client = MagicMock()
        fake_client.exchange_code_for_tokens = AsyncMock(
            return_value={
                "access_token": "ya29.token",
                "refresh_token": "refresh.token",
                "expires_at": (now + timedelta(hours=1)).isoformat(),
            }
        )
        fake_client.health_check = AsyncMock(
            return_value={
                "ok": True,
                "external_id": "UC_CHANNEL_123",
                "details": {"title": "My Channel"},
                "token_bundle": {
                    "access_token": "ya29.token",
                    "refresh_token": "refresh.token",
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                },
            }
        )

        with patch("app.router_agents.router.get_youtube_client", return_value=fake_client):
            response = await client.post(
                "/api/agents/channels/by_youtube_oauth_callback",
                json={"code": "oauth-code-12345", "state": state},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        payload = response.json()
        providers = [item["provider"] for item in payload["channels"]]
        assert "youtube" in providers
        assert payload["youtube_health"]["ok"] is True

    @pytest.mark.asyncio
    async def test_youtube_health_endpoint(self, client: AsyncClient, auth_headers, test_agent, test_user):
        now = datetime.utcnow()
        state = jwt.encode(
            {
                "scope": YOUTUBE_OAUTH_STATE_SCOPE,
                "user_id": test_user.id,
                "agent_id": test_agent.id,
                "redirect_uri": "https://app.example.com/oauth/youtube/callback",
                "exp": now + timedelta(minutes=10),
                "iat": now,
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        fake_client = MagicMock()
        fake_client.exchange_code_for_tokens = AsyncMock(
            return_value={
                "access_token": "ya29.token",
                "refresh_token": "refresh.token",
                "expires_at": (now + timedelta(hours=1)).isoformat(),
            }
        )
        fake_client.health_check = AsyncMock(
            side_effect=[
                {
                    "ok": True,
                    "external_id": "UC_CHANNEL_123",
                    "details": {"title": "My Channel"},
                    "token_bundle": {
                        "access_token": "ya29.token",
                        "refresh_token": "refresh.token",
                        "expires_at": (now + timedelta(hours=1)).isoformat(),
                    },
                },
                {
                    "ok": True,
                    "external_id": "UC_CHANNEL_123",
                    "details": {"title": "My Channel"},
                    "token_bundle": {
                        "access_token": "ya29.token.updated",
                        "refresh_token": "refresh.token",
                        "expires_at": (now + timedelta(hours=1)).isoformat(),
                    },
                },
            ]
        )

        with patch("app.router_agents.router.get_youtube_client", return_value=fake_client):
            callback_resp = await client.post(
                "/api/agents/channels/by_youtube_oauth_callback",
                json={"code": "oauth-code-12345", "state": state},
            )
            assert callback_resp.status_code == 200, callback_resp.text

            response = await client.get(
                "/api/agents/channels/youtube/health",
                headers=auth_headers,
                params={"bot_id": test_agent.bot_id},
            )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        payload = response.json()
        assert payload["health"]["ok"] is True
        assert payload["connection"]["provider"] == "youtube"

    @pytest.mark.asyncio
    async def test_content_jobs_list_filter_detail_and_metrics(
        self, client: AsyncClient, auth_headers, test_session, test_agent
    ):
        now = datetime.utcnow().replace(microsecond=0)
        async with test_session.begin():
            test_session.add_all(
                [
                    AgentContentJob(
                        agent_id=test_agent.id,
                        status="published",
                        scheduled_for=now,
                        started_at=now,
                        finished_at=now + timedelta(minutes=2),
                        retry_count=1,
                        max_retries=3,
                        metadata_json=json.dumps(
                            {
                                "render_started_at": now.isoformat(),
                                "render_finished_at": (now + timedelta(seconds=30)).isoformat(),
                            }
                        ),
                        created_at=now,
                        updated_at=now,
                        youtube_video_id="vid_1",
                        youtube_video_url="https://youtube.com/shorts/vid_1",
                    ),
                    AgentContentJob(
                        agent_id=test_agent.id,
                        status="failed",
                        scheduled_for=now + timedelta(hours=1),
                        retry_count=0,
                        max_retries=3,
                        metadata_json=json.dumps(
                            {
                                "render_started_at": (now + timedelta(hours=1)).isoformat(),
                                "render_finished_at": (now + timedelta(hours=1, seconds=10)).isoformat(),
                            }
                        ),
                        created_at=now + timedelta(hours=1),
                        updated_at=now + timedelta(hours=1),
                        last_error="publish_failed",
                    ),
                ]
            )

        list_resp = await client.get(
            "/api/agents/content/jobs",
            headers=auth_headers,
            params={"bot_id": test_agent.bot_id},
        )
        assert list_resp.status_code == 200, list_resp.text
        list_payload = list_resp.json()
        assert list_payload["total"] == 2
        assert len(list_payload["items"]) == 2

        filtered_resp = await client.get(
            "/api/agents/content/jobs",
            headers=auth_headers,
            params={"bot_id": test_agent.bot_id, "status": "published"},
        )
        assert filtered_resp.status_code == 200, filtered_resp.text
        filtered_payload = filtered_resp.json()
        assert filtered_payload["total"] == 1
        assert filtered_payload["items"][0]["status"] == "published"
        job_id = int(filtered_payload["items"][0]["id"])

        detail_resp = await client.get(
            f"/api/agents/content/jobs/{job_id}",
            headers=auth_headers,
            params={"bot_id": test_agent.bot_id},
        )
        assert detail_resp.status_code == 200, detail_resp.text
        detail_payload = detail_resp.json()
        assert detail_payload["id"] == job_id
        assert detail_payload["youtube_video_id"] == "vid_1"

        metrics_resp = await client.get(
            "/api/agents/content/jobs/metrics",
            headers=auth_headers,
            params={"bot_id": test_agent.bot_id},
        )
        assert metrics_resp.status_code == 200, metrics_resp.text
        metrics_payload = metrics_resp.json()
        assert metrics_payload["jobs_total"] == 2
        assert metrics_payload["jobs_published"] == 1
        assert metrics_payload["jobs_failed"] == 1
        assert metrics_payload["avg_render_latency_seconds"] == 20.0
        assert metrics_payload["retry_rate_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_create_empty_agent_content_factory_blocked_in_development(self, client: AsyncClient, auth_headers):
        """content_factory недоступен для создания — шаблон в разработке."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Content factory system prompt",
                "template_type": "content_factory",
                "template_config": {
                    "content_language": "ru",
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        detail = response.json()["detail"]
        assert "разработке" in detail.lower()

    @pytest.mark.asyncio
    async def test_create_empty_agent_content_factory_defaults(self, client: AsyncClient, auth_headers):
        """content_factory с полным конфигом тоже недоступен — шаблон в разработке."""
        response = await client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "system_prompt": "Content factory system prompt",
                "template_type": "content_factory",
                "template_config": {
                    "company_name": "Acme AI",
                    "company_activity": "Автоматизация клиентской поддержки",
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        assert "разработке" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_agent_content_factory_rejects_duration_more_than_8(
        self, client: AsyncClient, auth_headers, test_agent
    ):
        """content_factory в update отклоняет duration > 8."""
        response = await client.patch(
            "/api/agents/by_botID",
            headers=auth_headers,
            json={
                "bot_id": test_agent.bot_id,
                "template_type": "content_factory",
                "template_config": {
                    "company_name": "Acme AI",
                    "company_activity": "Создание AI-видео",
                    "video_duration_seconds": 12,
                },
            },
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        assert "разработке" in response.json()["detail"].lower()


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


class TestTelegramWebhookSync:
    @pytest.mark.asyncio
    async def test_toggle_status_surfaces_telegram_webhook_error(
        self, client: AsyncClient, auth_headers, test_agent, test_session
    ):
        from app.config import settings

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(settings, "BASE_URL", "https://example.com")

        async with test_session.begin():
            test_agent.is_active = False
            await test_session.flush()

        mock_channel = MagicMock()
        mock_channel.encrypted_credentials = "mock_encrypted_test_bot_token_123"
        mock_channel.external_id = "12345"

        try:
            with (
                patch(
                    "app.router_agents.router._get_telegram_bot_channel_for_agent",
                    new_callable=AsyncMock,
                    return_value=mock_channel,
                ),
                patch(
                    "app.router_agents.router._telegram_bot_api_json",
                    new_callable=AsyncMock,
                    side_effect=__import__("fastapi").HTTPException(
                        status_code=502,
                        detail="Telegram API (setWebhook): Bad Request: bad webhook: HTTPS URL must be provided",
                    ),
                ),
            ):
                response = await client.patch(
                    "/api/agents/toggle_status",
                    headers=auth_headers,
                    json={"bot_id": test_agent.bot_id},
                )

            assert response.status_code == 502
            assert "setWebhook" in response.json()["detail"]
        finally:
            monkeypatch.undo()