import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from arq import create_pool
from arq.worker import Worker
from sqlalchemy import select
from testcontainers.redis import RedisContainer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from fitter.models import Activity, Record  # noqa: E402
from fitter.auth import hash_password  # noqa: E402
from fitter.db import Base  # noqa: E402
from fitter.app import create_app  # noqa: E402

import bcrypt
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def redis_container():
    with RedisContainer("redis:7-alpine") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield host, port


@pytest_asyncio.fixture
async def arq_engine(redis_container, pg_container):
    redis_host, redis_port = redis_container
    os.environ["REDIS_HOST"] = redis_host
    os.environ["REDIS_PORT"] = str(redis_port)

    url = pg_container.get_connection_url()
    os.environ["DATABASE_URL"] = url

    # Also update fitter.config.settings to use the testcontainer URL
    import fitter.config as configmod
    configmod.settings = configmod.Settings.from_env()

    # Update the global engine to use the testcontainer
    import fitter.db as dbmod
    dbmod.engine = create_async_engine(url, poolclass=NullPool)
    dbmod.async_session = async_sessionmaker(dbmod.engine, expire_on_commit=False)
    async with dbmod.engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION postgis"))
        await conn.run_sync(Base.metadata.create_all)

    engine = dbmod.engine
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION postgis"))
    await engine.dispose()
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
    from fitter.models import User
    session_factory = async_sessionmaker(arq_engine, expire_on_commit=False)
    async with session_factory() as session:
        user = User(username="testuser", password_hash=hash_password("testpass"), is_admin=True)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def run_worker_briefly(redis_host, redis_port, timeout=10):
    """Run the arq worker for a short time to process pending jobs."""
    from arq.connections import RedisSettings
    from fitter.worker import WorkerSettings

    worker = Worker(
        WorkerSettings.functions,
        redis_settings=RedisSettings(host=redis_host, port=redis_port),
        burst=True,
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
        import fitter.auth as authmod

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[authmod.get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login
            resp = await client.post("/login", json={"username": "testuser", "password": "testpass"})
            assert resp.status_code == 200

            # Upload — should return 202
            fit_data = make_test_fit(num_records=50)
            resp = await client.post(
                "/upload",
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