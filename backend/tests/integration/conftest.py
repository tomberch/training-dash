import os
import socket
import sys
import tempfile
from pathlib import Path

# Set up test environment before importing app
os.environ.setdefault("TRAININGDASH_UPLOADS_DIR", tempfile.mkdtemp(prefix="traindash-test-uploads-"))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402

from trainingdash.app import create_app
from trainingdash.db import Base
from trainingdash.models import User
from tests.integration.fixtures import CACHED_HASH_TESTPASS


def _is_local_postgres_available(host: str = "localhost", port: int = 5433) -> bool:
    """Check if a local postgres is listening on the test port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((host, port))
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


@pytest.fixture(scope="session")
def pg_container():
    """
    Session-scoped postgres connection.
    
    Uses local postgres on port 5433 if available (instant startup),
    otherwise falls back to testcontainers (~6s startup).
    
    To use local postgres for tests:
        docker run -d --name traindash-test-db -p 5433:5432 \\
            -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \\
            postgis/postgis:16-3.4
    """
    # Check for TEST_DATABASE_URL override
    if os.environ.get("TEST_DATABASE_URL"):
        # Return a mock object with get_connection_url method
        class LocalPg:
            def get_connection_url(self):
                return os.environ["TEST_DATABASE_URL"]
        yield LocalPg()
        return
    
    # Check if local test postgres is available on port 5433
    if _is_local_postgres_available(port=5433):
        class LocalPg:
            def get_connection_url(self):
                return "postgresql+asyncpg://test:test@localhost:5433/test"
        print("\n[pytest] Using local postgres on port 5433 (fast mode)")
        yield LocalPg()
        return
    
    # Fall back to testcontainers
    print("\n[pytest] Starting testcontainer (no local postgres on port 5433)")
    with PostgresContainer("postgis/postgis:16-3.4", driver="asyncpg") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session")
async def db_engine_session(pg_container):
    """
    Session-scoped database engine. Creates schema once at session start.
    This dramatically reduces test overhead by avoiding schema recreation per test.
    """
    url = pg_container.get_connection_url()
    engine = create_async_engine(url, poolclass=NullPool)
    
    # Create schema once at session start
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_engine(db_engine_session):
    """
    Function-scoped fixture that cleans data between tests via TRUNCATE.
    Much faster than DROP/CREATE schema (~10ms vs ~1000ms).
    """
    # Truncate all tables before each test (CASCADE handles FK constraints)
    async with db_engine_session.begin() as conn:
        # Get all table names - use metadata.tables to avoid sort issues with circular FKs
        tables = list(Base.metadata.tables.keys())
        if tables:
            table_list = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))
    
    yield db_engine_session


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seed_user(db_session):
    user = User(
        email="testuser@example.com",
        password_hash=CACHED_HASH_TESTPASS,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def app_client(db_engine, seed_user):
    import trainingdash.auth as authmod

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[authmod.get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_client(app_client, seed_user):
    response = await app_client.post(
        "/api/login", json={"email": "testuser@example.com", "password": "testpass"}
    )
    assert response.status_code == 200
    return app_client
