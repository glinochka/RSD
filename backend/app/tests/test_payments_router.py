import pytest
from sqlalchemy import select
from unittest.mock import MagicMock, patch

from app.alembic.models import User, WebsitePaymentTransaction


class TestGetSubscriptionPlans:
    """Tests for GET /api/payments/plans endpoint."""

    @pytest.mark.asyncio
    async def test_get_plans_success(self, client):
        response = await client.get("/api/payments/plans")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)


class TestProcessSuccessfulPayment:
    """Tests for POST /api/payments/process_successful endpoint."""

    @pytest.mark.asyncio
    async def test_process_payment_success(self, internal_client, test_session):
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "paymentUser",
                "telegram_id": 123456789,
                "password": get_password_hash("password123"),
                "subscription_type": "Free",
            })
            await test_session.commit()

        payment_data = {
            "telegram_id": 123456789,
            "plan_name": "Advanced",
            "currency": "RUB",
            "total_amount": 29900,
            "telegram_payment_charge_id": "test_charge_123",
            "provider_payment_charge_id": "provider_123",
            "invoice_payload": "test_payload",
        }

        response = await internal_client.post(
            "/api/payments/process_successful",
            json=payment_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["subscription_type"] == "Advanced"

        async with test_session.begin():
            result = await test_session.execute(
                select(User).where(User.telegram_id == 123456789)
            )
            updated_user = result.scalar_one_or_none()
            assert updated_user.subscription_type == "Advanced"

    @pytest.mark.asyncio
    async def test_process_payment_duplicate(self, internal_client, test_session):
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "dupPaymentUser",
                "telegram_id": 987654321,
                "password": get_password_hash("password123"),
            })
            await test_session.commit()

        payment_data = {
            "telegram_id": 987654321,
            "plan_name": "Pro",
            "currency": "RUB",
            "total_amount": 49900,
            "telegram_payment_charge_id": "duplicate_charge",
            "provider_payment_charge_id": "provider_456",
            "invoice_payload": "test_payload",
        }

        response1 = await internal_client.post(
            "/api/payments/process_successful",
            json=payment_data
        )
        assert response1.status_code == 200

        response2 = await internal_client.post(
            "/api/payments/process_successful",
            json=payment_data
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "duplicate"

    @pytest.mark.asyncio
    async def test_process_payment_user_not_found(self, internal_client):
        payment_data = {
            "telegram_id": 999999999,
            "plan_name": "Advanced",
            "currency": "RUB",
            "total_amount": 29900,
            "telegram_payment_charge_id": "new_charge",
            "provider_payment_charge_id": "provider_789",
            "invoice_payload": "test_payload",
        }
        response = await internal_client.post(
            "/api/payments/process_successful",
            json=payment_data
        )
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_process_payment_unauthorized(self, client):
        response = await client.post(
            "/api/payments/process_successful",
            json={"telegram_id": 123, "plan_name": "Advanced"}
        )
        assert response.status_code == 401


class TestCreateYooKassaPayment:
    """Tests for POST /api/payments/yookassa/create endpoint."""

    @pytest.mark.asyncio
    async def test_create_yookassa_payment_success(self, authenticated_client):
        client, _ = authenticated_client

        # Мокаем настройки, чтобы _configure_yookassa не падал
        with patch("app.router_payments.router.settings") as mock_settings:
            mock_settings.YOOKASSA_SHOP_ID = "test_shop"
            mock_settings.YOOKASSA_SECRET_KEY = "test_secret"

            # Мокаем сам Payment в роутере
            with patch("app.router_payments.router.Payment") as mock_payment_class:
                mock_payment = MagicMock()
                mock_payment.id = "test_payment_id_123"
                mock_payment.status = "pending"
                mock_confirmation = MagicMock()
                mock_confirmation.confirmation_url = "https://yookassa.ru/confirm/test"
                mock_payment.confirmation = mock_confirmation
                mock_payment_class.create = MagicMock(return_value=mock_payment)

                response = await client.post(
                    "/api/payments/yookassa/create",
                    json={
                        "plan_name": "Advanced",
                        "return_url": "http://localhost:3000/success"
                    }
                )

        assert response.status_code == 201
        data = response.json()
        assert data["payment_id"] == "test_payment_id_123"
        assert data["confirmation_url"] == "https://yookassa.ru/confirm/test"

    @pytest.mark.asyncio
    async def test_create_yookassa_payment_invalid_plan(self, authenticated_client):
        client, _ = authenticated_client
        response = await client.post(
            "/api/payments/yookassa/create",
            json={
                "plan_name": "InvalidPlan",
                "return_url": "http://localhost:3000/success"
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_yookassa_payment_missing_return_url(self, authenticated_client):
        client, _ = authenticated_client
        with patch("app.router_payments.router.settings") as mock_settings:
            mock_settings.YOOKASSA_RETURN_URL = None
            response = await client.post(
                "/api/payments/yookassa/create",
                json={"plan_name": "Advanced"}
            )
        assert response.status_code == 400
        assert "return_url is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_yookassa_payment_unauthenticated(self, client):
        response = await client.post(
            "/api/payments/yookassa/create",
            json={
                "plan_name": "Advanced",
                "return_url": "http://localhost:3000/success"
            }
        )
        assert response.status_code == 401


class TestGetYooKassaPaymentStatus:
    """Tests for GET /api/payments/yookassa/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_payment_status_success(self, authenticated_client, test_session):
        client, user_info = authenticated_client

        async with test_session.begin():
            tx = WebsitePaymentTransaction(
                user_id=user_info["user_id"],
                plan_name="Pro",
                currency="RUB",
                total_amount=49900,
                original_total_amount=49900,
                yookassa_payment_id="test_payment_status_123",
                status="pending",
            )
            test_session.add(tx)
            await test_session.commit()

        with patch("app.router_payments.router.settings") as mock_settings:
            mock_settings.YOOKASSA_SHOP_ID = "test_shop"
            mock_settings.YOOKASSA_SECRET_KEY = "test_secret"

            with patch("app.router_payments.router.Payment") as mock_payment_class:
                mock_payment = MagicMock()
                mock_payment.status = "succeeded"
                mock_payment_class.find_one = MagicMock(return_value=mock_payment)

                response = await client.get(
                    "/api/payments/yookassa/status?payment_id=test_payment_status_123"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["payment_id"] == "test_payment_status_123"
        assert data["status"] == "succeeded"

    @pytest.mark.asyncio
    async def test_get_payment_status_not_found(self, authenticated_client, test_session):
        client, user_info = authenticated_client

        async with test_session.begin():
            tx = WebsitePaymentTransaction(
                user_id=user_info["user_id"],
                plan_name="Pro",
                currency="RUB",
                total_amount=49900,
                original_total_amount=49900,
                yookassa_payment_id="nonexistent_payment",
                status="pending",
            )
            test_session.add(tx)
            await test_session.commit()

        from yookassa.domain.exceptions import NotFoundError

        with patch("app.router_payments.router.settings") as mock_settings:
            mock_settings.YOOKASSA_SHOP_ID = "test_shop"
            mock_settings.YOOKASSA_SECRET_KEY = "test_secret"

            with patch("app.router_payments.router.Payment") as mock_payment_class:
                # Создаём объект ошибки, который принимает конструктор NotFoundError
                error_response = {"type": "error", "code": "not_found", "description": "Not found"}
                mock_payment_class.find_one = MagicMock(side_effect=NotFoundError(error_response))

                response = await client.get(
                    "/api/payments/yookassa/status?payment_id=nonexistent_payment"
                )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_payment_status_unauthenticated(self, client):
        response = await client.get("/api/payments/yookassa/status?payment_id=test")
        assert response.status_code == 401


class TestYooKassaWebhook:
    """Tests for POST /api/payments/yookassa/webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_payment_succeeded(self, client, test_session):
        from app.utils.security import get_password_hash
        from app.router_users.dao import UserDAO

        user_dao = UserDAO(test_session)
        async with test_session.begin():
            user = await user_dao.add({
                "name": "webhookUser",
                "password": get_password_hash("password123"),
            })
            await test_session.flush()

            tx = WebsitePaymentTransaction(
                user_id=user.id,
                plan_name="Advanced",
                currency="RUB",
                total_amount=29900,
                original_total_amount=29900,
                yookassa_payment_id="webhook_payment_123",
                status="pending",
            )
            test_session.add(tx)
            await test_session.commit()

        webhook_body = {
            "event": "payment.succeeded",
            "object": {"id": "webhook_payment_123"}
        }

        with patch("app.router_payments.router.settings") as mock_settings:
            mock_settings.YOOKASSA_SHOP_ID = "test_shop"
            mock_settings.YOOKASSA_SECRET_KEY = "test_secret"

            with patch("app.router_payments.router.WebhookNotificationFactory") as mock_factory:
                mock_notification = MagicMock()
                mock_notification.event = "payment.succeeded"
                mock_object = MagicMock()
                mock_object.id = "webhook_payment_123"
                mock_notification.object = mock_object
                mock_factory.return_value.create.return_value = mock_notification

                with patch("app.router_payments.router.Payment") as mock_payment_class:
                    mock_payment = MagicMock()
                    mock_payment.status = "succeeded"
                    mock_payment_class.find_one = MagicMock(return_value=mock_payment)

                    response = await client.post(
                        "/api/payments/yookassa/webhook",
                        json=webhook_body
                    )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_refund_succeeded(self, client):
        webhook_body = {
            "event": "refund.succeeded",
            "object": {"id": "refund_123"}
        }

        with patch("app.router_payments.router.WebhookNotificationFactory") as mock_factory:
            mock_notification = MagicMock()
            mock_notification.event = "refund.succeeded"
            mock_factory.return_value.create.return_value = mock_notification

            response = await client.post(
                "/api/payments/yookassa/webhook",
                json=webhook_body
            )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_invalid_json(self, client):
        response = await client.post(
            "/api/payments/yookassa/webhook",
            content="invalid json content"
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_unknown_event(self, client):
        webhook_body = {
            "event": "unknown.event",
            "object": {"id": "unknown_123"}
        }

        with patch("app.router_payments.router.WebhookNotificationFactory") as mock_factory:
            mock_notification = MagicMock()
            mock_notification.event = "unknown.event"
            mock_factory.return_value.create.return_value = mock_notification

            response = await client.post(
                "/api/payments/yookassa/webhook",
                json=webhook_body
            )
        assert response.status_code == 200