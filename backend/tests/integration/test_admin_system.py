"""Integration tests for Admin System Dashboard API endpoints (#385)."""

import pytest
from sqlalchemy import text

from trainingdash import cache_stats
from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.models import CacheStats


class TestEventsEndpoint:
    """Tests for GET /api/admin/system/events."""

    @pytest.mark.asyncio
    async def test_events_requires_admin(self, app_client, db_session):
        """Non-admin cannot access events endpoint."""
        from tests.integration.fixtures import CACHED_HASH_PASS
        from trainingdash.repositories.postgres.models import User

        # Create non-admin user and login
        user = User(email="nonadmin@example.com", password_hash=CACHED_HASH_PASS, is_admin=False)
        db_session.add(user)
        await db_session.commit()

        await app_client.post("/api/login", json={"email": "nonadmin@example.com", "password": "pass"})
        response = await app_client.get("/api/admin/system/events")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_events_returns_list(self, auth_client, db_session):
        """Events endpoint returns event list with total."""
        repo = PostgresEventRepo(db_session)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.ACTIVITY_INGESTED.value, outcome=EventOutcome.SUCCESS.value)

        response = await auth_client.get("/api/admin/system/events")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "total" in data
        assert data["total"] >= 2
        assert len(data["events"]) >= 2

    @pytest.mark.asyncio
    async def test_events_filter_by_type(self, auth_client, db_session):
        """Events can be filtered by event_type."""
        repo = PostgresEventRepo(db_session)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.ACTIVITY_INGESTED.value, outcome=EventOutcome.SUCCESS.value)

        response = await auth_client.get(
            "/api/admin/system/events", params={"event_type": EventType.SYNC_COMPLETED.value}
        )
        assert response.status_code == 200
        data = response.json()
        assert all(e["event_type"] == EventType.SYNC_COMPLETED.value for e in data["events"])

    @pytest.mark.asyncio
    async def test_events_filter_by_outcome(self, auth_client, db_session):
        """Events can be filtered by outcome."""
        repo = PostgresEventRepo(db_session)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.FAILURE.value)

        response = await auth_client.get("/api/admin/system/events", params={"outcome": "failure"})
        assert response.status_code == 200
        data = response.json()
        assert all(e["outcome"] == "failure" for e in data["events"])

    @pytest.mark.asyncio
    async def test_events_pagination(self, auth_client, db_session):
        """Events support pagination."""
        repo = PostgresEventRepo(db_session)
        for i in range(5):
            await repo.log(event_type=f"test.event.{i}", outcome=EventOutcome.SUCCESS.value)

        response = await auth_client.get("/api/admin/system/events", params={"limit": 2, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 2
        assert data["total"] >= 5


class TestJobsEndpoint:
    """Tests for GET /api/admin/system/jobs."""

    @pytest.mark.asyncio
    async def test_jobs_requires_admin(self, app_client, db_session):
        """Non-admin cannot access jobs endpoint."""
        from tests.integration.fixtures import CACHED_HASH_PASS
        from trainingdash.repositories.postgres.models import User

        user = User(email="nonadmin2@example.com", password_hash=CACHED_HASH_PASS, is_admin=False)
        db_session.add(user)
        await db_session.commit()

        await app_client.post("/api/login", json={"email": "nonadmin2@example.com", "password": "pass"})
        response = await app_client.get("/api/admin/system/jobs")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_jobs_returns_empty_list(self, auth_client, db_session):
        """Jobs endpoint returns empty list when no active jobs."""
        # Create the saq_jobs table if it doesn't exist (SAQ creates it on first connect)
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS saq_jobs (
                key VARCHAR PRIMARY KEY,
                queue VARCHAR NOT NULL DEFAULT 'default',
                status VARCHAR NOT NULL,
                job JSONB NOT NULL,
                scheduled TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        )
        await db_session.commit()

        response = await auth_client.get("/api/admin/system/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    @pytest.mark.asyncio
    async def test_jobs_returns_active_jobs(self, auth_client, db_session):
        """Jobs endpoint returns active and queued jobs."""
        # Create table and insert test job
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS saq_jobs (
                key VARCHAR PRIMARY KEY,
                queue VARCHAR NOT NULL DEFAULT 'default',
                status VARCHAR NOT NULL,
                job JSONB NOT NULL,
                scheduled TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        )
        await db_session.execute(
            text("""
            INSERT INTO saq_jobs (key, queue, status, job, scheduled)
            VALUES ('test-job-1', 'default', 'active', '{"function": "import_xert_job", "kwargs": {"user_id": 1}}', NOW())
            ON CONFLICT (key) DO UPDATE SET status = 'active'
        """)
        )
        await db_session.commit()

        response = await auth_client.get("/api/admin/system/jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) >= 1

        job = next((j for j in data["jobs"] if j["key"] == "test-job-1"), None)
        assert job is not None
        assert job["function"] == "import_xert_job"
        assert job["status"] == "active"


class TestCacheStatsEndpoint:
    """Tests for GET /api/admin/system/cache-stats."""

    @pytest.fixture(autouse=True)
    def reset_cache_stats(self):
        """Reset cache stats before each test."""
        cache_stats.reset()
        yield
        cache_stats.reset()

    @pytest.mark.asyncio
    async def test_cache_stats_requires_admin(self, app_client, db_session):
        """Non-admin cannot access cache-stats endpoint."""
        from tests.integration.fixtures import CACHED_HASH_PASS
        from trainingdash.repositories.postgres.models import User

        user = User(email="nonadmin3@example.com", password_hash=CACHED_HASH_PASS, is_admin=False)
        db_session.add(user)
        await db_session.commit()

        await app_client.post("/api/login", json={"email": "nonadmin3@example.com", "password": "pass"})
        response = await app_client.get("/api/admin/system/cache-stats")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cache_stats_returns_structure(self, auth_client, db_session):
        """Cache stats endpoint returns expected structure."""
        # Create geocoding_cache table if needed
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(255) UNIQUE NOT NULL,
                result_json JSONB NOT NULL
            )
        """)
        )
        await db_session.commit()

        response = await auth_client.get("/api/admin/system/cache-stats")
        assert response.status_code == 200
        data = response.json()

        assert "current" in data
        assert "history" in data
        assert "sizes" in data
        assert isinstance(data["current"], dict)
        assert isinstance(data["history"], list)
        assert "tiles_mb" in data["sizes"]
        assert "geocoding_count" in data["sizes"]

    @pytest.mark.asyncio
    async def test_cache_stats_includes_current_counters(self, auth_client, db_session):
        """Cache stats includes current in-memory counters."""
        # Create geocoding_cache table
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(255) UNIQUE NOT NULL,
                result_json JSONB NOT NULL
            )
        """)
        )
        await db_session.commit()

        # Record some hits/misses
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_miss("tiles_osm")
        cache_stats.record_hit("geocoding")

        response = await auth_client.get("/api/admin/system/cache-stats")
        assert response.status_code == 200
        data = response.json()

        # Tiles should combine tiles_osm + tiles_carto
        assert "tiles" in data["current"]
        assert data["current"]["tiles"]["hits"] == 2
        assert data["current"]["tiles"]["misses"] == 1

        assert "geocoding" in data["current"]
        assert data["current"]["geocoding"]["hits"] == 1

    @pytest.mark.asyncio
    async def test_cache_stats_includes_history(self, auth_client, db_session):
        """Cache stats includes historical buckets from database."""
        from datetime import UTC, datetime, timedelta

        # Create geocoding_cache table
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(255) UNIQUE NOT NULL,
                result_json JSONB NOT NULL
            )
        """)
        )

        # Insert historical cache stats
        bucket = datetime.now(UTC).replace(minute=0, second=0, microsecond=0, tzinfo=None) - timedelta(hours=1)
        stats = CacheStats(bucket_start=bucket, cache_type="tiles_osm", hits=100, misses=20)
        db_session.add(stats)
        await db_session.commit()

        response = await auth_client.get("/api/admin/system/cache-stats")
        assert response.status_code == 200
        data = response.json()

        assert len(data["history"]) >= 1
        history_entry = data["history"][0]
        assert "bucket_start" in history_entry
        assert "cache_type" in history_entry
        assert "hits" in history_entry
        assert "misses" in history_entry

    @pytest.mark.asyncio
    async def test_cache_stats_days_param(self, auth_client, db_session):
        """Cache stats respects days parameter."""
        # Create geocoding_cache table
        await db_session.execute(
            text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id SERIAL PRIMARY KEY,
                cache_key VARCHAR(255) UNIQUE NOT NULL,
                result_json JSONB NOT NULL
            )
        """)
        )
        await db_session.commit()

        response = await auth_client.get("/api/admin/system/cache-stats", params={"days": 30})
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
