import asyncio
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
# Ищем .env: backend/app/.env, app/tests/.env, корень репозитория (часто один общий .env)
_env_candidates = [
    Path(__file__).parent.parent / ".env",
    Path(__file__).parent / ".env",
    Path(__file__).resolve().parents[3] / ".env",
]
env_path = next((p for p in _env_candidates if p.exists()), _env_candidates[0])
load_dotenv(env_path, override=True)

from cryptography.fernet import Fernet

_TEST_FERNET_KEY = Fernet.generate_key().decode()

_TEST_ENV_DEFAULTS = {
    "SECRET_KEY": "test-jwt-secret-key-for-ci-min-32-chars-long",
    "INTERNAL_API_KEY": "test-internal-api-key",
    "ENCRYPTION_KEY": _TEST_FERNET_KEY,
    "USER_JWT_SECRET_KEY": "798cd1b6cb25d52ce4e49824b01b5b22a117325ad327161c50ad5a8c2898fc89",
    "CUSTOM_ADMIN_JWT_SECRET_KEY": "test-custom-admin-jwt-secret-key-min-32",
    "CUSTOM_AUTOMATION_JWT_SECRET_KEY": "test-custom-automation-jwt-secret-min-32",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ[_key] = _value

required_vars = ["SECRET_KEY", "INTERNAL_API_KEY", "ENCRYPTION_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"{var} not found in .env")

# Импортируем Base ДО создания фикстур
from app.alembic.database import Base


def _sqlite_tables_from_ddl_target(target):
    if hasattr(target, "columns"):
        return [target]
    if hasattr(target, "tables"):
        return list(target.tables.values())
    return []


def _replace_jsonb_columns_for_sqlite(tables) -> None:
    for table in tables:
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
            server_default = column.server_default
            if server_default is not None and "::jsonb" in str(
                getattr(server_default, "arg", server_default)
            ):
                column.server_default = text("'{}'")


@event.listens_for(Base.metadata, "before_create")
def _prepare_sqlite_schema(target, connection, **kw):
    if connection.dialect.name != "sqlite":
        return
    _replace_jsonb_columns_for_sqlite(_sqlite_tables_from_ddl_target(target))


# ВАЖНО: Импортируем модели здесь, чтобы они зарегистрировались в Base.metadata
from app.alembic import models  # noqa: F401

_replace_jsonb_columns_for_sqlite(Base.metadata.tables.values())

_ASYNC_SESSION_MAKER_PATCH_TARGETS = (
    "app.alembic.database.async_session_maker",
    "app.router_admin.router.async_session_maker",
    "app.router_users.router.async_session_maker",
    "app.router_agents.shared.async_session_maker",
    "app.router_payments.router.async_session_maker",
    "app.router_documents.router.async_session_maker",
    "app.services.template_runtime.async_session_maker",
    "app.telephony.routing.async_session_maker",
    "app.services.error_log_service.async_session_maker",
    "app.services.admin_booking.service.async_session_maker",
    "app.services.admin_booking.payment_service.async_session_maker",
    "app.services.admin_booking.client_notify.async_session_maker",
    "app.services.http_integration.tool_registry.async_session_maker",
    "app.services.admin_booking.providers.local.async_session_maker",
    "app.telephony.orchestrator_worker.async_session_maker",
    "app.services.website_public_forms.async_session_maker",
    "app.services.agent_public_data.async_session_maker",
    "app.router_custom.automation_router.async_session_maker",
    "app.router_custom.admin_router.async_session_maker",
    "app.services.custom.account_health_worker.async_session_maker",
    "app.services.custom.chat_join_service.async_session_maker",
    "app.services.custom.chat_discovery_service.async_session_maker",
    "app.services.custom.chat_monitoring_service.async_session_maker",
    "app.services.custom.dmp_one_service.async_session_maker",
    "app.services.custom.amocrm_service.async_session_maker",
)


def _make_sqlite_async_session_maker(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


def _patch_async_session_makers(stack: ExitStack, test_engine):
    factory = _make_sqlite_async_session_maker(test_engine)

    for target in _ASYNC_SESSION_MAKER_PATCH_TARGETS:
        try:
            stack.enter_context(patch(target, factory))
        except (AttributeError, ModuleNotFoundError):
            # Module may be missing or not import a session maker; skip.
            pass
    _wire_test_booking_service(factory)
    return factory


def _wire_test_booking_service(factory):
    from app.services.admin_booking.service import AdminBookingService
    import app.services.admin_booking.service as booking_module

    booking_module._admin_booking_service = AdminBookingService(session_factory=factory)


@pytest.fixture(autouse=True)
def _reset_booking_service_singletons():
    import app.services.admin_booking.payment_service as payment_module
    import app.services.admin_booking.service as booking_module

    booking_module._admin_booking_service = None
    payment_module._payment_service = None
    yield
    booking_module._admin_booking_service = None
    payment_module._payment_service = None


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Создает движок SQLite в памяти и инициализирует схему БД."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Создает сессию БД, привязанную к тестовому движку."""
    async_session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def verify_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Fresh DB session for assertions after HTTP handlers commit in another session."""
    factory = _make_sqlite_async_session_maker(test_engine)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(test_engine, test_session) -> AsyncGenerator[AsyncClient, None]:
    """Создает тестовый HTTP клиент FastAPI."""
    
    # --- 1. ПОДГОТОВКА МОКОВ ДЛЯ ТЯЖЕЛЫХ ЗАВИСИМОСТЕЙ ---
    
    # Создаем мок для модуля indexer вручную, чтобы избежать выполнения кода инициализации модели
    mock_indexer_module = MagicMock()
    
    # Создаем асинхронные заглушки для функций внутри модуля
    async def mock_delete_agent_vectors(*args, **kwargs):
        return True  # Возвращаем успех
    
    async def mock_upsert_agent_documents(*args, **kwargs):
        return True
        
    # Привязываем их к модулю
    mock_indexer_module.delete_agent_vectors = mock_delete_agent_vectors
    mock_indexer_module.upsert_agent_documents = mock_upsert_agent_documents
    # Можно добавить другие функции по мере необходимости
    
    # Моки для других сервисов
    mock_search_service = MagicMock()
    mock_ai_authoring = MagicMock()
    mock_sentence_transformers = MagicMock()
    # Heavy PDF/image dependencies that can abort on some environments.
    mock_pikepdf = MagicMock()
    mock_img2pdf = MagicMock()

    # --- 2. ПАТЧИНГ СИСТЕМНЫХ МОДУЛЕЙ ПЕРЕД ИМПОРТОМ РОУТЕРОВ ---
    # Это критически важно: мы подменяем модуль в sys.modules ДО того, как кто-то сделает 'import app.qdrant.indexer'
    
    with patch.dict('sys.modules', {
        'app.qdrant.indexer': mock_indexer_module,  # Полная замена модуля
        'app.qdrant.search_service': mock_search_service,
        'app.services.ai_authoring': mock_ai_authoring,
        'sentence_transformers': mock_sentence_transformers,
        'pikepdf': mock_pikepdf,
        'img2pdf': mock_img2pdf,
    }):
        
        # --- 3. ПАТЧИНГ ФУНКЦИЙ КРИПТОГРАФИИ ---
        # decrypt_token должен уметь работать с нашими тестовыми строками "mock_encrypted_..."
        def mock_encrypt_token(token: str) -> str:
            return f"mock_encrypted_{token}"

        def mock_decrypt_token(token: str) -> str:
            if token.startswith("mock_encrypted_"):
                return token.replace("mock_encrypted_", "")
            return token

        def mock_encrypt_crm_credentials(payload: str) -> str:
            return f"crmv1:mock_crm_{payload}"

        with patch('app.utils.crypto.encrypt_token', side_effect=mock_encrypt_token):
            with patch('app.utils.crypto.decrypt_token', side_effect=mock_decrypt_token):
                with patch('app.utils.crypto.encrypt_crm_credentials', side_effect=mock_encrypt_crm_credentials):
                    # --- 4. ПАТЧИНГ БАЗЫ ДАННЫХ ---
                    with ExitStack() as stack:
                        _patch_async_session_makers(stack, test_engine)

                        from fastapi import FastAPI
                        from fastapi.middleware.cors import CORSMiddleware
                        
                        try:
                            from app.origins import origins
                        except ImportError:
                            origins = ["*"]

                        # Теперь импортируем роутеры. Они подхватят наши моки из sys.modules
                        from app.router_users.router import router as users_router
                        from app.router_agents.router import router as agents_router
                        from app.router_documents.router import router as documents_router
                        from app.router_payments.router import router as payments_router
                        from app.router_admin.router import router as admin_router
                        from app.router_custom import router as custom_router

                        test_app = FastAPI()
                        test_app.add_middleware(
                            CORSMiddleware,
                            allow_origins=origins,
                            allow_methods=['*'],
                            allow_headers=['*'],
                            allow_credentials=True
                        )

                        test_app.include_router(users_router)
                        test_app.include_router(agents_router)
                        test_app.include_router(documents_router)
                        test_app.include_router(payments_router)
                        test_app.include_router(admin_router)
                        test_app.include_router(custom_router)

                        async with AsyncClient(
                            transport=ASGITransport(app=test_app),
                            base_url="http://test"
                        ) as ac:
                            yield ac

@pytest_asyncio.fixture(scope="function")
async def test_user(test_session) -> Generator:
    """Создает тестового пользователя в БД."""
    from app.router_users.dao import UserDAO
    from app.utils.security import get_password_hash
    
    user_dao = UserDAO(test_session)
    
    user_data = {
        "name": "testuser",
        "password": get_password_hash("testpassword123"),
        "telegram_id": 123456789,
        "subscription_type": "Free",
    }
    
    async with test_session.begin():
        user = await user_dao.add(user_data)
        await test_session.flush()
        await test_session.refresh(user)
        
    yield user


@pytest_asyncio.fixture(scope="function")
async def test_agent(test_session, test_user) -> Generator:
    """Создает тестового агента в БД."""
    from app.router_agents.dao import AgentDAO
    from app.utils import crypto
    
    # Мок шифрования
    original_encrypt = crypto.encrypt_token
    
    def mock_encrypt_token(token: str) -> str:
        return f"mock_encrypted_{token}"
    
    crypto.encrypt_token = mock_encrypt_token

    agent_dao = AgentDAO(test_session)

    agent_data = {
        "bot_id": 987654321,
        "bot_username": "test_bot",
        "encrypted_token": mock_encrypt_token("test_bot_token_123"),
        "system_prompt": "Test prompt",
        "is_active": True,
        "user_id": test_user.id
    }
    
    try:
        async with test_session.begin():
            agent = await agent_dao.add(agent_data)
            await test_session.flush()
            await test_session.refresh(agent)
            
        yield agent
    finally:
        crypto.encrypt_token = original_encrypt


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user, test_session):
    """
    Генерирует заголовки с JWT токеном.
    Использует вашу функцию create_access_token без изменений.
    """
    from datetime import datetime, timedelta, timezone
    import secrets
    import hashlib
    from app.alembic.models import UserAuthSession
    from app.utils.JWT import create_access_token

    sid = secrets.token_hex(16)
    refresh_raw = secrets.token_urlsafe(48)
    material = f"{os.getenv('USER_JWT_SECRET_KEY', '')}:{refresh_raw}"
    refresh_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()

    async with test_session.begin():
        test_session.add(
            UserAuthSession(
                id=sid,
                user_id=test_user.id,
                refresh_token_hash=refresh_hash,
                expires_at=(datetime.now(timezone.utc) + timedelta(days=30)).replace(tzinfo=None),
            )
        )

    access_token = create_access_token(data={"user_id": str(test_user.id), "sid": sid})

    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def internal_api_headers():
    """Генерирует заголовки для внутреннего API."""
    internal_key = os.getenv("INTERNAL_API_KEY")
    return {"X-Internal-API-Key": internal_key}


# --- Вспомогательные фикстуры ---

@pytest.fixture
def mock_telegram_get_me():
    """Mock Telegram getMe API response."""
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"ok": true, "result": {"id": 12345, "username": "testbot"}}'
        
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__.return_value = None
        mock_urlopen.return_value = mock_context
        
        yield mock_urlopen


@pytest.fixture
def sample_user_data():
    return {"email": "testuser@example.com", "password": "testpassword123"}

@pytest.fixture
def sample_agent_data():
    return {"bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz", "system_prompt": "Test"}
@pytest_asyncio.fixture(scope="function")
async def authenticated_client(client, test_session, test_user, auth_headers):
    """
    Возвращает кортеж (client, user_info), где client уже имеет заголовки авторизации,
    а user_info содержит id и name тестового пользователя.
    """
    # Используем существующего test_user
    user_info = {
        "user_id": test_user.id,
        "name": test_user.name,
        "telegram_id": test_user.telegram_id,
    }
    # Применяем заголовки авторизации к клиенту
    client.headers.update(auth_headers)
    return client, user_info


@pytest_asyncio.fixture(scope="function")
async def internal_client(client, internal_api_headers):
    """
    Возвращает клиент с заголовками для внутреннего API (X-Internal-API-Key).
    """
    client.headers.update(internal_api_headers)
    return client


@pytest.fixture
def mock_httpx_client():
    """
    Мок для httpx.AsyncClient, используемый в тестах Telegram link.
    """
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest_asyncio.fixture(scope="function")
async def mock_db_session(test_engine):
    """
    Fixtures that provides mocked async_session_maker for database services.
    This allows tests to use DmQueueService, SalesFSMService, etc. without connecting to PostgreSQL.
    """
    with ExitStack() as stack:
        factory = _patch_async_session_makers(stack, test_engine)
        async with factory() as session:
            yield session