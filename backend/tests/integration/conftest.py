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
from trainingdash.repositories.postgres.db import Base
from trainingdash.repositories.postgres.models import User
from tests.integration.fixtures import CACHED_HASH_TESTPASS


@pytest.fixture(autouse=True)
def _mock_geocoding(monkeypatch):
    """Skip reverse geocoding in integration tests.

    generate_activity_title normally calls out to photon.komoot.io with a
    1-second rate-limit sleep per request (3-12 per upload). Patching it out
    eliminates the sleep tax without losing coverage — the real title logic is
    untested today (see #259) and is independent of the integration suite.
    """
    async def _fake_title(records, activity_date=None):
        return "Test Ride"

    monkeypatch.setattr(
        "trainingdash.title_generator.generate_activity_title", _fake_title
    )


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
    
    NOTE: pytest-xdist parallel execution is NOT supported due to PostGIS constraints.
    The geography type is only available in the public schema where postgis extension
    is installed. Schema-per-worker isolation doesn't work. Use sequential execution
    or run test files in parallel with external orchestration.
    """
    url = pg_container.get_connection_url()
    engine = create_async_engine(url, poolclass=NullPool)
    
    # Create schema once at session start
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed metric_types once at session start (reference data, never changes)
    async with engine.begin() as conn:
        # Use raw SQL for speed - avoid ORM overhead
        await conn.execute(text("""
            INSERT INTO metric_types (key, display_name, unit, category, data_type, min_value, max_value, allowed_sources, recalc_targets, sort_order)
            VALUES 
                ('ftp', 'Functional Threshold Power', 'W', 'threshold', 'integer', 50, 500, ARRAY['manual', 'calculated', 'device'], ARRAY['power_zones', 'tss', 'if'], 1),
                ('lthr', 'Lactate Threshold HR', 'bpm', 'threshold', 'integer', 80, 220, ARRAY['manual', 'calculated', 'device'], ARRAY['hr_zones'], 2),
                ('hrmax', 'Maximum Heart Rate', 'bpm', 'threshold', 'integer', 100, 250, ARRAY['manual', 'calculated', 'device'], ARRAY['hr_zones'], 3),
                ('weight_kg', 'Weight', 'kg', 'body', 'decimal', 30, 200, ARRAY['manual', 'device'], ARRAY['vo2max', 'w_per_kg'], 4),
                ('vo2max', 'VO2 Max', 'ml/kg/min', 'fitness', 'decimal', 20, 90, ARRAY['manual', 'calculated', 'device'], NULL, 5),
                ('resting_hr', 'Resting Heart Rate', 'bpm', 'recovery', 'integer', 30, 100, ARRAY['manual', 'device'], NULL, 6),
                ('hrv', 'Heart Rate Variability', 'ms', 'recovery', 'integer', 10, 200, ARRAY['manual', 'device'], NULL, 7)
            ON CONFLICT (key) DO NOTHING
        """))
    
    yield engine
    await engine.dispose()


# =============================================================================
# DATABASE FIXTURES
# =============================================================================
# Default fixtures use TRUNCATE for test isolation. This is reliable and works
# with all test patterns (HTTP clients, direct DB access, mixed usage).
#
# Transaction rollback is faster but only works when all DB access goes through
# the same connection, which doesn't work with tests that mix HTTP clients
# with direct ingest_fit() calls.


@pytest_asyncio.fixture
async def db_engine(db_engine_session):
    """
    Function-scoped fixture that cleans data between tests via TRUNCATE.
    Excludes metric_types which is seeded once at session start.
    """
    # Truncate all tables EXCEPT metric_types (reference data seeded at session start)
    async with db_engine_session.begin() as conn:
        tables = [t for t in Base.metadata.tables.keys() if t != "metric_types"]
        if tables:
            table_list = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))
    
    yield db_engine_session


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Database session for direct DB access in tests."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


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
    """App client for HTTP requests in tests."""
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


@pytest_asyncio.fixture
async def http_client():
    """Lightweight app client with no database dependency.

    For tests that only hit unauthenticated HTTP endpoints (e.g. tile proxy).
    Avoids the db_engine TRUNCATE and seed_user bcrypt login overhead.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# Aliases for tests that explicitly want TRUNCATE (same as default now)
truncate_db_engine = db_engine
truncate_db_session = db_session
truncate_seed_user = seed_user
truncate_app_client = app_client
truncate_auth_client = auth_client
