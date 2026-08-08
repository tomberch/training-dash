import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from arq import create_pool
from arq.worker import Worker
from sqlalchemy import select, text
from testcontainers.redis import RedisContainer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from trainingdash.models import Activity, Record, User  # noqa: E402
from trainingdash.db import Base  # noqa: E402
from trainingdash.app import create_app  # noqa: E402

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="module")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield host, port


@pytest_asyncio.fixture
async def arq_engine(redis_container, db_engine_session, pg_container):
    """
    ARQ-specific engine setup that reuses the session-scoped postgres from conftest.
    Sets up Redis and global config but uses TRUNCATE instead of DROP/CREATE.
    """
    redis_host, redis_port = redis_container
    os.environ["REDIS_HOST"] = redis_host
    os.environ["REDIS_PORT"] = str(redis_port)

    url = pg_container.get_connection_url()
    os.environ["DATABASE_URL"] = url

    # Update trainingdash.config.settings to use the testcontainer URL
    import trainingdash.config as configmod
    configmod.settings = configmod.Settings.from_env()

    # Update the global engine to use the same testcontainer engine
    import trainingdash.db as dbmod
    dbmod.engine = db_engine_session
    dbmod.async_session = async_sessionmaker(db_engine_session, expire_on_commit=False)

    # TRUNCATE tables instead of DROP/CREATE for faster cleanup
    async with db_engine_session.begin() as conn:
        tables = list(Base.metadata.tables.keys())
        if tables:
            table_list = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))

    yield db_engine_session

    # Cleanup: TRUNCATE again, don't DROP schema
    async with db_engine_session.begin() as conn:
        tables = list(Base.metadata.tables.keys())
        if tables:
            table_list = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))

    os.environ.pop("REDIS_HOST", None)
    os.environ.pop("REDIS_PORT", None)


@pytest_asyncio.fixture
async def arq_session(arq_engine):
    session_factory = async_sessionmaker(arq_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def arq_user(arq_engine):
    from tests.integration.fixtures import CACHED_HASH_TESTPASS
    session_factory = async_sessionmaker(arq_engine, expire_on_commit=False)
    async with session_factory() as session:
        user = User(email="testuser@example.com", password_hash=CACHED_HASH_TESTPASS, is_admin=True)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def run_worker_briefly(redis_host, redis_port, timeout=10):
    """Run the arq worker for a short time to process pending jobs."""
    from arq.connections import RedisSettings
    from trainingdash.worker import WorkerSettings

    worker = Worker(
        WorkerSettings.functions,
        redis_settings=RedisSettings(host=redis_host, port=redis_port),
        burst=True,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
    )
    try:
        await asyncio.wait_for(worker.async_run(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        await worker.close()


class TestArqIngest:
    @pytest.mark.asyncio
    async def test_upload_enqueues_job_and_worker_processes(self, arq_engine, arq_user, redis_container):
        redis_host, redis_port = redis_container

        session_factory = async_sessionmaker(arq_engine, expire_on_commit=False)
        import trainingdash.auth as authmod

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[authmod.get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            resp = await client.post("/api/login", json={"email": "testuser@example.com", "password": "testpass"})
            assert resp.status_code == 200

            # Upload — should return 202
            fit_data = make_test_fit(num_records=50)
            resp = await client.post(
                "/api/upload",
                files={"file": ("test.fit", fit_data, "application/octet-stream")},
            )
            assert resp.status_code == 202
            data = resp.json()
            assert "job_id" in data

            # Run the worker to process the job
            await run_worker_briefly(redis_host, redis_port, timeout=15)

            # Verify the activity was created
            async with session_factory() as session:
                result = await session.execute(select(Activity).order_by(Activity.id.desc()).limit(1))
                activity = result.scalar_one_or_none()
                assert activity is not None
                assert activity.source == "upload"

                records_result = await session.execute(
                    select(Record).where(Record.activity_id == activity.id)
                )
                records = records_result.scalars().all()
                assert len(records) == 50

    @pytest.mark.asyncio
    async def test_job_survives_worker_restart(self, arq_engine, arq_user, redis_container):
        """Test that jobs persist in Redis and survive a worker restart."""
        redis_host, redis_port = redis_container

        session_factory = async_sessionmaker(arq_engine, expire_on_commit=False)
        import trainingdash.auth as authmod

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[authmod.get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            resp = await client.post("/api/login", json={"email": "testuser@example.com", "password": "testpass"})
            assert resp.status_code == 200

            # Upload — job is enqueued but we don't run the worker yet
            fit_data = make_test_fit(num_records=30)
            resp = await client.post(
                "/api/upload",
                files={"file": ("restart_test.fit", fit_data, "application/octet-stream")},
            )
            assert resp.status_code == 202
            data = resp.json()
            job_id = data["job_id"]

            # Verify job is queued in Redis
            from arq.connections import RedisSettings
            from arq.jobs import Job
            pool = await create_pool(RedisSettings(host=redis_host, port=redis_port))
            job = Job(job_id, pool)
            status_before = await job.status()
            await pool.aclose()
            # Job should be queued or deferred
            assert str(status_before) in ["JobStatus.queued", "JobStatus.deferred"]

            # Verify no activity exists yet
            async with session_factory() as session:
                result = await session.execute(
                    select(Activity).where(Activity.source_ref == "restart_test.fit")
                )
                activity = result.scalar_one_or_none()
                assert activity is None

            # Now "restart" the worker by starting a fresh one that processes the queued job
            await run_worker_briefly(redis_host, redis_port, timeout=15)

            # Verify the activity was created after the "restart"
            async with session_factory() as session:
                result = await session.execute(
                    select(Activity).where(Activity.source_ref == "restart_test.fit")
                )
                activity = result.scalar_one_or_none()
                assert activity is not None
                assert activity.source == "upload"

                records_result = await session.execute(
                    select(Record).where(Record.activity_id == activity.id)
                )
                records = records_result.scalars().all()
                assert len(records) == 30



    @pytest.mark.asyncio
    async def test_concurrent_uploads_no_interface_error(self, arq_engine, arq_user, redis_container):
        """
        Test that multiple concurrent job submissions don't cause asyncpg InterfaceError.
        
        This is a regression test for issue #237 where creating a new engine per job
        led to connection conflicts under concurrent load.
        """
        redis_host, redis_port = redis_container
        num_concurrent_uploads = 5

        session_factory = async_sessionmaker(arq_engine, expire_on_commit=False)
        import trainingdash.auth as authmod

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[authmod.get_db] = override_get_db
        transport = ASGITransport(app=app)
        
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            resp = await client.post("/api/login", json={"email": "testuser@example.com", "password": "testpass"})
            assert resp.status_code == 200

            # Submit multiple uploads concurrently
            job_ids = []
            for i in range(num_concurrent_uploads):
                fit_data = make_test_fit(num_records=20 + i * 5)  # Vary sizes slightly
                resp = await client.post(
                    "/api/upload",
                    files={"file": (f"concurrent_{i}.fit", fit_data, "application/octet-stream")},
                )
                assert resp.status_code == 202
                data = resp.json()
                job_ids.append(data["job_id"])

            assert len(job_ids) == num_concurrent_uploads

        # Run worker to process all jobs concurrently
        # The worker processes jobs concurrently by default - this is where the bug would manifest
        await run_worker_briefly(redis_host, redis_port, timeout=30)

        # Verify all activities were created successfully (no InterfaceError)
        async with session_factory() as session:
            result = await session.execute(
                select(Activity).where(Activity.source_ref.like("concurrent_%"))
            )
            activities = result.scalars().all()
            
            # All uploads should have succeeded
            assert len(activities) == num_concurrent_uploads, (
                f"Expected {num_concurrent_uploads} activities, got {len(activities)}. "
                "Some jobs may have failed due to connection conflicts."
            )
            
            # Verify each has records
            for activity in activities:
                records_result = await session.execute(
                    select(Record).where(Record.activity_id == activity.id)
                )
                records = records_result.scalars().all()
                assert len(records) > 0, f"Activity {activity.id} has no records"
