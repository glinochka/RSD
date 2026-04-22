import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
 
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

# Проверка критических переменных
required_vars = ["SECRET_KEY", "INTERNAL_API_KEY", "ENCRYPTION_KEY"]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"{var} not found in .env")

# Импортируем Base ДО создания фикстур
from app.alembic.database import Base

# ВАЖНО: Импортируем модели здесь, чтобы они зарегистрировались в Base.metadata
from app.alembic import models  # noqa: F401


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
    mock_fastembed = MagicMock()

    # --- 2. ПАТЧИНГ СИСТЕМНЫХ МОДУЛЕЙ ПЕРЕД ИМПОРТОМ РОУТЕРОВ ---
    # Это критически важно: мы подменяем модуль в sys.modules ДО того, как кто-то сделает 'import app.qdrant.indexer'
    
    with patch.dict('sys.modules', {
        'app.qdrant.indexer': mock_indexer_module,  # Полная замена модуля
        'app.qdrant.search_service': mock_search_service,
        'app.services.ai_authoring': mock_ai_authoring,
        'fastembed': mock_fastembed,
        'fastembed.sparse': mock_fastembed,
        'fastembed.sparse.sparse_text_embedding': mock_fastembed,
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
                    with patch('app.alembic.database.async_session_maker') as mock_factory:
                        mock_factory.return_value.__aenter__.return_value = test_session
                        mock_factory.return_value.__aexit__.return_value = None

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