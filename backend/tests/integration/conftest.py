import os
import socket
import sys
import tempfile
import time
from pathlib import Path

# Set up test environment before importing app
os.environ.setdefault("TRAININGDASH_UPLOADS_DIR", tempfile.mkdtemp(prefix="traindash-test-uploads-"))

import docker
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

# Dedicated test container settings
TEST_CONTAINER_NAME = "traindash-test-db"
TEST_CONTAINER_IMAGE = "postgis/postgis:16-3.4"
TEST_CONTAINER_PORT = 5433
TEST_DB_USER = "test"
TEST_DB_PASSWORD = "test"
TEST_DB_NAME = "test"


def _is_port_available(host: str = "localhost", port: int = TEST_CONTAINER_PORT) -> bool:
    """Check if a service is listening on the given port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((host, port))
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _is_postgres_ready(host: str = "localhost", port: int = TEST_CONTAINER_PORT) -> bool:
    """Check if postgres is actually ready to accept queries (not just TCP connections)."""
    import subprocess
    result = subprocess.run(
        [
            "docker", "exec", TEST_CONTAINER_NAME,
            "pg_isready", "-h", "localhost", "-U", TEST_DB_USER
        ],
        capture_output=True,
        timeout=5,
    )
    return result.returncode == 0


def _wait_for_postgres(host: str = "localhost", port: int = TEST_CONTAINER_PORT, timeout: int = 30) -> bool:
    """Wait for postgres to accept connections."""
    start = time.time()
    while time.time() - start < timeout:
        # First check port is open
        if _is_port_available(host, port):
            # Then verify postgres is actually ready
            try:
                if _is_postgres_ready(host, port):
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    return False


def _ensure_test_container_running() -> bool:
    """
    Ensure the dedicated test postgres container is running.
    
    Returns True if container is ready, False if we should fall back to testcontainers.
    """
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        # Docker not available
        return False
    
    try:
        container = client.containers.get(TEST_CONTAINER_NAME)
        if container.status == "running":
            # Already running, just verify it's accepting connections
            if _is_port_available(port=TEST_CONTAINER_PORT):
                print(f"\n[pytest] Using existing container '{TEST_CONTAINER_NAME}' (instant startup)")
                return True
            # Container running but not accepting connections yet, wait
            if _wait_for_postgres(port=TEST_CONTAINER_PORT, timeout=10):
                print(f"\n[pytest] Using existing container '{TEST_CONTAINER_NAME}' (waited for ready)")
                return True
            return False
        elif container.status in ("exited", "created"):
            # Container exists but stopped, start it
            print(f"\n[pytest] Starting stopped container '{TEST_CONTAINER_NAME}'...")
            container.start()
            if _wait_for_postgres(port=TEST_CONTAINER_PORT, timeout=15):
                print(f"[pytest] Container '{TEST_CONTAINER_NAME}' ready")
                return True
            return False
        else:
            # Unknown state, let it fall through
            return False
    except docker.errors.NotFound:
        # Container doesn't exist, create it
        print(f"\n[pytest] Creating test container '{TEST_CONTAINER_NAME}'...")
        try:
            container = client.containers.run(
                TEST_CONTAINER_IMAGE,
                name=TEST_CONTAINER_NAME,
                environment={
                    "POSTGRES_USER": TEST_DB_USER,
                    "POSTGRES_PASSWORD": TEST_DB_PASSWORD,
                    "POSTGRES_DB": TEST_DB_NAME,
                },
                ports={"5432/tcp": TEST_CONTAINER_PORT},
                detach=True,
                # Keep container after tests for fast re-runs
                remove=False,
            )
            if _wait_for_postgres(port=TEST_CONTAINER_PORT, timeout=30):
                print(f"[pytest] Container '{TEST_CONTAINER_NAME}' ready")
                return True
            return False
        except docker.errors.APIError as e:
            print(f"[pytest] Failed to create container: {e}")
            return False


@pytest.fixture(scope="session")
def pg_container():
    """
    Session-scoped postgres connection.
    
    Priority order:
    1. TEST_DATABASE_URL environment variable (explicit override)
    2. Dedicated test container 'traindash-test-db' on port 5433 (auto-managed)
    3. Testcontainers fallback (~6s startup per session)
    
    The dedicated container persists between test runs for instant startup.
    To reset it: docker rm -f traindash-test-db
    """
    # Check for TEST_DATABASE_URL override
    if os.environ.get("TEST_DATABASE_URL"):
        class LocalPg:
            def get_connection_url(self):
                return os.environ["TEST_DATABASE_URL"]
        yield LocalPg()
        return
    
    # Try to use/start the dedicated test container
    if _ensure_test_container_running():
        class LocalPg:
            def get_connection_url(self):
                return f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@localhost:{TEST_CONTAINER_PORT}/{TEST_DB_NAME}"
        yield LocalPg()
        return
    
    # Fall back to testcontainers (ephemeral, slower)
    print("\n[pytest] Falling back to testcontainers (no dedicated container available)")
    with PostgresContainer(TEST_CONTAINER_IMAGE, driver="asyncpg") as pg:
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


METRIC_TYPES_SEED = [
    {"key": "ftp", "display_name": "Functional Threshold Power", "unit": "W", "category": "threshold", "data_type": "integer", "min_value": 50, "max_value": 500, "allowed_sources": ["manual", "calculated", "device"], "recalc_targets": ["power_zones", "tss", "if"], "sort_order": 1},
    {"key": "lthr", "display_name": "Lactate Threshold HR", "unit": "bpm", "category": "threshold", "data_type": "integer", "min_value": 80, "max_value": 220, "allowed_sources": ["manual", "calculated", "device"], "recalc_targets": ["hr_zones"], "sort_order": 2},
    {"key": "hrmax", "display_name": "Maximum Heart Rate", "unit": "bpm", "category": "threshold", "data_type": "integer", "min_value": 100, "max_value": 250, "allowed_sources": ["manual", "calculated", "device"], "recalc_targets": ["hr_zones"], "sort_order": 3},
    {"key": "weight_kg", "display_name": "Weight", "unit": "kg", "category": "body", "data_type": "decimal", "min_value": 30, "max_value": 200, "allowed_sources": ["manual", "device"], "recalc_targets": ["vo2max", "w_per_kg"], "sort_order": 4},
    {"key": "vo2max", "display_name": "VO2 Max", "unit": "ml/kg/min", "category": "fitness", "data_type": "decimal", "min_value": 20, "max_value": 90, "allowed_sources": ["manual", "calculated", "device"], "recalc_targets": None, "sort_order": 5},
    {"key": "resting_hr", "display_name": "Resting Heart Rate", "unit": "bpm", "category": "recovery", "data_type": "integer", "min_value": 30, "max_value": 100, "allowed_sources": ["manual", "device"], "recalc_targets": None, "sort_order": 6},
    {"key": "hrv", "display_name": "Heart Rate Variability", "unit": "ms", "category": "recovery", "data_type": "integer", "min_value": 10, "max_value": 200, "allowed_sources": ["manual", "device"], "recalc_targets": None, "sort_order": 7},
]


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
    
    # Seed metric_types (required for metrics API tests)
    # Use merge to handle existing data from previous runs
    session_factory = async_sessionmaker(db_engine_session, expire_on_commit=False)
    async with session_factory() as session:
        from trainingdash.models import MetricType
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        
        # Use upsert to handle existing metric_types
        for mt_data in METRIC_TYPES_SEED:
            stmt = pg_insert(MetricType).values(**mt_data)
            stmt = stmt.on_conflict_do_nothing(index_elements=["key"])
            await session.execute(stmt)
        await session.commit()
    
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
