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
        "trainingdash.domain.title_generator.generate_activity_title", _fake_title
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


@pytest.fixture(scope="session")
def worker_schema():
    """Per-worker Postgres schema name for xdist isolation.

    Under pytest-xdist each worker (``gw0``, ``gw1``, ...) gets its own schema
    in the shared DB; under serial runs this is ``public`` so behavior is
    unchanged. Tables are created in the worker's schema via ``search_path``;
    the ``postgis`` extension (and its ``geography`` type / ``ST_*`` functions)
    lives in ``public`` and is shared read-only across workers.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    if worker_id == "main":
        return "public"
    return f"test_{worker_id}"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine_session(pg_container, worker_schema):
    """
    Session-scoped database engine. Creates schema once per worker session.

    Under xdist each worker gets its own schema (``test_gw0``, ``test_gw1``,
    ...); under serial runs this is ``public``. The ``postgis`` extension is
    installed once in ``public`` (idempotent ``CREATE EXTENSION IF NOT EXISTS``
    is safe under concurrency — concurrent workers just see "already exists,
    skipping"). Every connection from this engine sets
    ``search_path = <worker_schema>,public`` so tables land in the worker's
    schema and ``geography``/``ST_*`` resolve from ``public``.

    Uses the default pool (not NullPool) so each test can check out its own
    connection for per-test transaction rollback. ``loop_scope="session"``
    keeps one event loop for the whole session so asyncpg connections don't
    cross loops.

    See ADR 0003 for the isolation model and the PostGIS constraint that
    motivated it (the prior "geography only in public" claim was false for
    PostGIS 3.4 — see docs/research/xdist-postgis-patterns.md).
    """
    url = pg_container.get_connection_url()
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": f"{worker_schema},public"}},
    )

    async with engine.begin() as conn:
        if worker_schema != "public":
            # Per-worker schema: drop any leftover from a prior run, then create.
            # No FileLock needed — each worker owns a distinct schema name.
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{worker_schema}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA "{worker_schema}"'))
        # postgis lives in `public` and is shared across all workers. Install it
        # under a transaction-level advisory lock so only one worker does the
        # CREATE EXTENSION; others block until it's done, then see it present.
        # (CREATE EXTENSION IF NOT EXISTS raises UniqueViolation under asyncpg
        # when raced; CREATE EXTENSION ... SCHEMA public puts objects in public
        # regardless of the worker's search_path.)
        await conn.execute(text("SELECT pg_advisory_xact_lock(42)"))
        existing = await conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'")
        )
        if existing.scalar() is None:
            await conn.execute(text("CREATE EXTENSION postgis SCHEMA public"))
        # Tables go in the worker's schema (search_path leads with it).
        await conn.run_sync(Base.metadata.create_all)

    # Seed metric_types once per worker (lives in the worker's schema).
    async with engine.begin() as conn:
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
# Per-test isolation uses SAVEPOINT rollback, not TRUNCATE.
#
# Each test checks out one connection from the pool, begins an outer
# transaction, and yields that connection. ``db_session`` and the ``get_db``
# override (used by HTTP requests) both bind sessions to that connection with
# ``join_transaction_mode="create_savepoint"`` — so HTTP writes and direct
# writes (e.g. ``ingest_fit(db, ...)``) share one rollback-able transaction.
# On teardown the outer transaction is rolled back, undoing every write the
# test made, regardless of which code path produced it.
#
# This is the SQLAlchemy 2.0 test-suite recipe (see ADR 0003). The previous
# TRUNCATE-per-test approach is gone; its ~700-800ms per-test setup cost was
# 96% of every test's wall time.


@pytest_asyncio.fixture(loop_scope="session")
async def _test_conn(db_engine_session):
    """Per-test: one connection with an outer transaction that is rolled back.

    Both ``db_session`` and the ``get_db`` override bind sessions to this
    connection. Explicit ``trans.rollback()`` on teardown — the ``async with
    conn.begin()`` context manager did not roll back reliably with asyncpg
    (verified during the #280 prototype).
    """
    async with db_engine_session.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def db_engine(_test_conn):
    """Per-test connection (kept under the ``db_engine`` name for tests that
    reference it directly; most tests want ``db_session``/``app_client``).
    """
    return _test_conn


def _session_factory_for(conn):
    """Session factory bound to a single connection, joining its transaction
    via SAVEPOINT so app code can ``commit()``/``rollback()`` freely without
    ending the outer test transaction.
    """
    return async_sessionmaker(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(_test_conn):
    """Database session for direct DB access in tests."""
    session_factory = _session_factory_for(_test_conn)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(loop_scope="session")
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


@pytest_asyncio.fixture(loop_scope="session")
async def app_client(_test_conn, seed_user):
    """App client for HTTP requests in tests.

    The ``get_db`` override yields sessions bound to the test's shared
    connection with ``join_transaction_mode="create_savepoint"`` so HTTP
    writes join the same outer transaction as direct writes, and the whole
    transaction is rolled back at teardown.
    """
    import trainingdash.auth as authmod

    session_factory = _session_factory_for(_test_conn)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[authmod.get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(loop_scope="session")
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
    Avoids the per-test connection and seed_user login overhead.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# Backward-compat aliases: older tests referenced the TRUNCATE-named fixtures.
# They now delegate to the rollback fixtures (semantically equivalent — both
# deliver a clean DB per test).
truncate_db_engine = db_engine
truncate_db_session = db_session
truncate_seed_user = seed_user
truncate_app_client = app_client
truncate_auth_client = auth_client
