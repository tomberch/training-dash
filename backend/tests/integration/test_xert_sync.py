"""Integration tests for Xert sync functionality.

Xert sync downloads raw FIT files via a web session cookie and ingests them
through the standard ingest_fit() pipeline. XSS is fetched separately via
the OAuth JSON summary endpoint and stored as Activity.training_load.

Based on Xert Online API v1.5: https://www.xertonline.com/API.html
"""

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from trainingdash.repositories.postgres.models import Activity, Record, User, XertCredentials
from trainingdash.integrations.xert import XertActivity, XertAPIError
from tests.integration.fixtures import CACHED_HASH_TESTPASS, CACHED_HASH_PASS

# Load .env.test if it exists (for local Xert API testing)
_env_test_path = Path(__file__).parent.parent.parent / ".env.test"
if _env_test_path.exists():
    load_dotenv(_env_test_path)

# Fixture FIT file — 10 records, cycling activity with GPS/power/HR/cadence/temp/grade
FIXTURE_FIT_PATH = Path(__file__).parent.parent / "fixtures" / "xert_activity.fit"
FIXTURE_FIT_BYTES = FIXTURE_FIT_PATH.read_bytes()

# Generate a test encryption key
TEST_ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode("ascii")

# XSS value the mock will return (Xert Strain Score stored as training_load)
MOCK_XSS = 85.5


class MockXertClient:
    """
    Mock Xert client for testing.

    Returns the fixture FIT bytes from download_fit() and MOCK_XSS from get_xss().
    Tracks call counts and flags for controlling failure modes.
    """

    def __init__(self):
        self.activities: list[XertActivity] = []
        self.login_called = False
        self.login_username: str | None = None
        self.should_fail_login = False
        self.should_fail_download: set[str] = set()
        # Map activity_id -> XSS override; defaults to MOCK_XSS
        self.xss_values: dict[str, float | None] = {}

    async def login(self, username: str, password: str) -> None:
        self.login_called = True
        self.login_username = username
        if self.should_fail_login:
            raise XertAPIError("Invalid credentials")

    async def list_activities(
        self,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> list[XertActivity]:
        return self.activities

    async def download_fit(self, activity_id: str) -> bytes:
        if activity_id in self.should_fail_download:
            raise XertAPIError(f"FIT download failed for {activity_id}")
        return FIXTURE_FIT_BYTES

    async def get_xss(self, activity_id: str) -> float | None:
        return self.xss_values.get(activity_id, MOCK_XSS)

    def get_last_synced_at(self, creds: Any) -> datetime | None:
        # Mock always returns None; last_synced_at is written by run_sync directly
        return None

    async def close(self) -> None:
        pass


@pytest.fixture
def mock_xert_client():
    return MockXertClient()


@pytest.fixture
def encryption_key_env():
    with mock.patch("trainingdash.crypto.settings") as mock_settings:
        mock_settings.encryption_key = TEST_ENCRYPTION_KEY
        yield


@pytest_asyncio.fixture
async def user_with_xert_creds(db_session, encryption_key_env):
    """Create a user with Xert credentials."""
    from trainingdash.crypto import encrypt

    user = User(
        email="xertuser@example.com",
        password_hash=CACHED_HASH_TESTPASS,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    creds = XertCredentials(
        user_id=user.id,
        xert_email="user@xert.com",
        encrypted_password=encrypt("xert-password"),
    )
    db_session.add(creds)
    await db_session.commit()

    return user


def _make_worker_db_session_ctx(db_engine):
    """Return an async context manager that yields a session on the test DB."""
    from contextlib import asynccontextmanager

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    @asynccontextmanager
    async def mock_worker_db_session(ctx):
        """Mock worker_db_session that ignores ctx and uses test engine directly."""
        async with session_factory() as session:
            yield session

    return mock_worker_db_session, session_factory


def _patch_pipeline():
    """
    Patch ActivityPipeline.run() so sync tests don't execute the full pipeline.

    The pipeline uses asyncio.gather() internally, which fires two concurrent DB
    operations on the same asyncpg connection. This works in production (real
    connection pool) but fails in the testcontainer (NullPool, single connection
    per session). The pipeline has its own test suite; here we only test sync
    orchestration.
    """
    from trainingdash.activity_pipeline import PipelineResult

    async def _noop_run(self):
        return PipelineResult()

    return mock.patch("trainingdash.activity_pipeline.ActivityPipeline.run", _noop_run)


# ---------------------------------------------------------------------------
# Admin credential endpoint tests
# ---------------------------------------------------------------------------

class TestXertCredentialsEndpoints:
    """Tests for admin Xert credentials endpoints."""

    @pytest.mark.asyncio
    async def test_set_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        response = await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["xert_email"] == "test@xert.com"
        assert "xert_password" not in data
        assert "encrypted_password" not in data

    @pytest.mark.asyncio
    async def test_get_xert_credentials_shows_email_not_password(
        self, auth_client, seed_user, encryption_key_env
    ):
        await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["xert_email"] == "test@xert.com"
        assert "password" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_get_xert_credentials_not_configured(self, auth_client, seed_user):
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["xert_email"] is None

    @pytest.mark.asyncio
    async def test_delete_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        response = await auth_client.delete(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        assert response.json()["success"] is True

        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.json()["configured"] is False

    @pytest.mark.asyncio
    async def test_update_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "old@xert.com", "xert_password": "oldpass"},
        )
        response = await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "new@xert.com", "xert_password": "newpass"},
        )
        assert response.status_code == 200
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.json()["xert_email"] == "new@xert.com"


# ---------------------------------------------------------------------------
# sync_xert_job tests
# ---------------------------------------------------------------------------

class TestSyncXertJob:
    """Tests for the sync_xert_job worker function."""

    @pytest.mark.asyncio
    async def test_sync_xert_imports_new_activities(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job downloads FIT and creates Activity+Records for new activities."""
        mock_xert_client.activities = [
            XertActivity(
                id="s8pehgletoecmk5x",
                name="Morning Ride",
                started_at=datetime(2026, 8, 5, 7, 23, 56),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is True
        assert result["synced_activities"] == 1
        assert mock_xert_client.login_called
        assert mock_xert_client.login_username == "user@xert.com"

        async with session_factory() as session:
            activity_result = await session.execute(
                select(Activity).where(Activity.source_ref == "xert:s8pehgletoecmk5x")
            )
            activity = activity_result.scalar_one()
            assert activity.source == "xert"
            assert activity.source_ref == "xert:s8pehgletoecmk5x"
            # training_load should be XSS from get_xss()
            assert activity.training_load == MOCK_XSS

            # Verify Records were created from the fixture FIT (10 records)
            record_result = await session.execute(
                select(Record).where(Record.activity_id == activity.id)
            )
            records = record_result.scalars().all()
            assert len(records) == 10

    @pytest.mark.asyncio
    async def test_sync_xert_writes_last_synced_at(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """A successful sync writes last_synced_at to xert_credentials."""
        mock_xert_client.activities = [
            XertActivity(
                id="last-synced-test",
                name="Test Ride",
                started_at=datetime(2026, 8, 5, 7, 0, 0),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is True

        async with session_factory() as session:
            creds_result = await session.execute(
                select(XertCredentials).where(
                    XertCredentials.user_id == user_with_xert_creds.id
                )
            )
            creds = creds_result.scalar_one()
            assert creds.last_synced_at is not None
            # last_synced_at should be very recent (within 60 seconds of now)
            delta = datetime.now(timezone.utc).replace(tzinfo=None) - creds.last_synced_at
            assert abs(delta.total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_sync_xert_no_new_activities_still_writes_last_synced_at(
        self, db_engine, db_session, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """last_synced_at is updated even when there are no new activities to import."""
        # Pre-populate so the list returns nothing new
        existing = Activity(
            user_id=user_with_xert_creds.id,
            source="xert",
            source_ref="xert:already-there",
            started_at=datetime(2026, 8, 1, 7, 0, 0),
            total_distance_m=10000,
            moving_time_s=3600,
            elapsed_time_s=3600,
        )
        db_session.add(existing)
        await db_session.commit()

        mock_xert_client.activities = [
            XertActivity(
                id="already-there",
                name="Already Imported",
                started_at=datetime(2026, 8, 1, 7, 0, 0),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                from trainingdash.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is True
        assert result["synced_activities"] == 0

        async with session_factory() as session:
            creds_result = await session.execute(
                select(XertCredentials).where(
                    XertCredentials.user_id == user_with_xert_creds.id
                )
            )
            creds = creds_result.scalar_one()
            assert creds.last_synced_at is not None

    @pytest.mark.asyncio
    async def test_sync_xert_activity_has_fit_fields(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """Records from the FIT file include temperature, grade, and GPS."""
        mock_xert_client.activities = [
            XertActivity(
                id="fit-fields-test",
                name="Test Ride",
                started_at=datetime(2026, 8, 5, 7, 23, 56),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    await sync_xert_job({}, user_with_xert_creds.id)

        async with session_factory() as session:
            activity_result = await session.execute(
                select(Activity).where(Activity.source_ref == "xert:fit-fields-test")
            )
            activity = activity_result.scalar_one()

            # Activity summary fields computed from FIT
            assert activity.avg_power_w is not None
            assert activity.avg_hr_bpm is not None
            assert activity.total_distance_m > 0

            # Records have GPS coordinates (fixture has lat/lng)
            record_result = await session.execute(
                select(Record).where(
                    Record.activity_id == activity.id,
                    Record.lat.isnot(None),
                )
            )
            gps_records = record_result.scalars().all()
            assert len(gps_records) == 10

    @pytest.mark.asyncio
    async def test_sync_xert_xss_stored_as_training_load(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """XSS from get_xss() is stored as training_load on the activity."""
        activity_id = "xss-test-activity"
        expected_xss = 142.7
        mock_xert_client.xss_values[activity_id] = expected_xss
        mock_xert_client.activities = [
            XertActivity(
                id=activity_id,
                name="Hard Ride",
                started_at=datetime(2026, 8, 5, 7, 23, 56),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    await sync_xert_job({}, user_with_xert_creds.id)

        async with session_factory() as session:
            activity_result = await session.execute(
                select(Activity).where(Activity.source_ref == f"xert:{activity_id}")
            )
            activity = activity_result.scalar_one()
            assert activity.training_load == expected_xss

    @pytest.mark.asyncio
    async def test_sync_xert_xss_none_leaves_training_load_from_pipeline(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """When get_xss() returns None, training_load is whatever the pipeline computed."""
        activity_id = "no-xss-activity"
        mock_xert_client.xss_values[activity_id] = None
        mock_xert_client.activities = [
            XertActivity(
                id=activity_id,
                name="Indoor Ride",
                started_at=datetime(2026, 8, 5, 7, 23, 56),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is True
        assert result["synced_activities"] == 1
        # Activity should exist even without XSS
        async with session_factory() as session:
            activity_result = await session.execute(
                select(Activity).where(Activity.source_ref == f"xert:{activity_id}")
            )
            activity = activity_result.scalar_one()
            assert activity is not None

    @pytest.mark.asyncio
    async def test_sync_xert_skips_already_imported(
        self, db_engine, db_session, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job skips activities already in the database."""
        existing = Activity(
            user_id=user_with_xert_creds.id,
            source="xert",
            source_ref="xert:xert-activity-1",
            started_at=datetime(2026, 1, 15, 8, 0, 0),
            total_distance_m=10000,
            moving_time_s=1800,
            elapsed_time_s=2000,
        )
        db_session.add(existing)
        await db_session.commit()

        mock_xert_client.activities = [
            XertActivity(
                id="xert-activity-1",
                name="Morning Ride",
                started_at=datetime(2026, 1, 15, 8, 0, 0),
                activity_type="Cycling",
            ),
        ]

        mock_worker_db_session, _ = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is True
        assert result["synced_activities"] == 0

    @pytest.mark.asyncio
    async def test_sync_xert_no_credentials_returns_error(self, db_engine, db_session):
        """sync_xert_job returns an error when the user has no Xert credentials."""
        user = User(email="nocreds@example.com", password_hash=CACHED_HASH_TESTPASS)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        mock_worker_db_session, _ = _make_worker_db_session_ctx(db_engine)

        with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
            from trainingdash.worker import sync_xert_job
            result = await sync_xert_job({}, user.id)

        assert result["success"] is False
        assert "No Xert credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_xert_login_failure_returns_error(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job returns an error when Xert login fails."""
        mock_xert_client.should_fail_login = True

        mock_worker_db_session, _ = _make_worker_db_session_ctx(db_engine)

        with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                from trainingdash.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is False
        assert "Invalid credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_xert_continues_on_download_failure(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job continues when one activity's FIT download fails."""
        mock_xert_client.activities = [
            XertActivity(
                id="fail-activity",
                name="Failed Download",
                started_at=datetime(2026, 1, 15, 8, 0, 0),
                activity_type="Cycling",
            ),
            XertActivity(
                id="success-activity",
                name="Success",
                started_at=datetime(2026, 1, 16, 8, 0, 0),
                activity_type="Cycling",
            ),
        ]
        mock_xert_client.should_fail_download.add("fail-activity")

        mock_worker_db_session, session_factory = _make_worker_db_session_ctx(db_engine)

        with _patch_pipeline():
            with mock.patch("trainingdash.integrations.xert.get_xert_client", return_value=mock_xert_client):
                with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                    from trainingdash.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)

        assert result["success"] is True
        assert result["synced_activities"] == 1

        async with session_factory() as session:
            activity_result = await session.execute(
                select(Activity).where(Activity.source == "xert")
            )
            activities = activity_result.scalars().all()
            assert len(activities) == 1
            assert activities[0].source_ref == "xert:success-activity"


# ---------------------------------------------------------------------------
# Hourly scheduler tests
# ---------------------------------------------------------------------------

class TestHourlySyncScheduler:
    """Tests for the hourly sync scheduler cron job."""

    @pytest.mark.asyncio
    async def test_hourly_sync_enqueues_for_users_with_matching_sync_hour(
        self, db_engine, db_session, encryption_key_env
    ):
        """hourly_sync_scheduler enqueues sync only for users whose sync_hour matches."""
        from trainingdash.crypto import encrypt

        current_hour = datetime.now(timezone.utc).hour

        user1 = User(email="user1@example.com", password_hash=CACHED_HASH_PASS, sync_hour=current_hour)
        user2 = User(email="user2@example.com", password_hash=CACHED_HASH_PASS, sync_hour=current_hour)
        user3 = User(email="user3@example.com", password_hash=CACHED_HASH_PASS, sync_hour=(current_hour + 1) % 24)
        db_session.add_all([user1, user2, user3])
        await db_session.commit()
        for u in [user1, user2, user3]:
            await db_session.refresh(u)

        creds1 = XertCredentials(user_id=user1.id, xert_email="u1@xert.com", encrypted_password=encrypt("p1"))
        creds2 = XertCredentials(user_id=user2.id, xert_email="u2@xert.com", encrypted_password=encrypt("p2"))
        creds3 = XertCredentials(user_id=user3.id, xert_email="u3@xert.com", encrypted_password=encrypt("p3"))
        db_session.add_all([creds1, creds2, creds3])
        await db_session.commit()

        mock_worker_db_session, _ = _make_worker_db_session_ctx(db_engine)

        with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
            with mock.patch("trainingdash.worker.create_redis_pool") as mock_pool:
                mock_arq = mock.AsyncMock()
                mock_pool.return_value = mock_arq

                from trainingdash.worker import hourly_sync_scheduler
                result = await hourly_sync_scheduler({})

        assert result["success"] is True
        assert result["xert_queued"] == 2

        enqueued_user_ids = set()
        for call in mock_arq.enqueue_job.call_args_list:
            if call.args[0] == "sync_xert_job":
                enqueued_user_ids.add(call.kwargs["user_id"])
        assert user1.id in enqueued_user_ids
        assert user2.id in enqueued_user_ids
        assert user3.id not in enqueued_user_ids

    @pytest.mark.asyncio
    async def test_hourly_sync_no_users_for_current_hour(self, db_engine, db_session):
        """hourly_sync_scheduler handles no users matching the current sync hour."""
        current_hour = datetime.now(timezone.utc).hour
        different_hour = (current_hour + 1) % 24

        user = User(email="nocreds@example.com", password_hash=CACHED_HASH_PASS, sync_hour=different_hour)
        db_session.add(user)
        await db_session.commit()

        mock_worker_db_session, _ = _make_worker_db_session_ctx(db_engine)

        with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
            with mock.patch("trainingdash.worker.create_redis_pool") as mock_pool:
                mock_arq = mock.AsyncMock()
                mock_pool.return_value = mock_arq

                from trainingdash.worker import hourly_sync_scheduler
                result = await hourly_sync_scheduler({})

        assert result["success"] is True
        assert result["xert_queued"] == 0
        assert result["garmin_queued"] == 0


# ---------------------------------------------------------------------------
# Real API tests (skipped unless credentials are set)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("XERT_TEST_USERNAME"),
    reason="Set XERT_TEST_USERNAME and XERT_TEST_PASSWORD to run real API tests",
)
class TestXertClientRealAPI:
    """Integration tests against the real Xert API."""

    @pytest_asyncio.fixture
    async def live_client(self):
        """Authenticated XertClient connected to the real API."""
        from trainingdash.integrations.xert import XertClient

        client = XertClient()
        await client.login(
            os.environ["XERT_TEST_USERNAME"],
            os.environ["XERT_TEST_PASSWORD"],
        )
        yield client
        await client.close()

    @pytest_asyncio.fixture
    async def live_activities(self, live_client):
        """Recent activities from the real API (last 7 days)."""
        import time

        to_ts = int(time.time())
        from_ts = to_ts - (7 * 24 * 60 * 60)
        return await live_client.list_activities(
            from_timestamp=from_ts, to_timestamp=to_ts
        )

    @pytest.mark.asyncio
    async def test_real_xert_login_and_list_activities(self, live_client, live_activities):
        """OAuth login and activity listing work against the real API."""
        assert live_client._oauth._access_token is not None
        assert isinstance(live_activities, list)
        if live_activities:
            a = live_activities[0]
            assert a.id
            assert a.name
            assert a.started_at
            assert a.activity_type

    @pytest.mark.asyncio
    async def test_real_xert_download_fit(self, live_client, live_activities):
        """FIT download via web session returns valid FIT bytes."""
        if not live_activities:
            pytest.skip("No activities in the last 7 days")

        fit_bytes = await live_client.download_fit(live_activities[0].id)

        assert len(fit_bytes) > 100
        # Valid FIT file has ".FIT" magic at bytes 8-12
        assert fit_bytes[8:12] == b".FIT", (
            f"Expected FIT magic at bytes 8-12, got {fit_bytes[8:12]!r}"
        )

    @pytest.mark.asyncio
    async def test_real_xert_get_xss(self, live_client, live_activities):
        """XSS is fetched from response['summary']['xss'] and is a positive float."""
        if not live_activities:
            pytest.skip("No activities in the last 7 days")

        xss = await live_client.get_xss(live_activities[0].id)
        # XSS may be None for activities without power data; otherwise a positive float
        assert xss is None or (isinstance(xss, float) and xss > 0)

    @pytest.mark.asyncio
    async def test_real_xert_invalid_credentials(self):
        """Invalid credentials raise XertAPIError."""
        from trainingdash.integrations.xert import XertClient, XertAPIError

        client = XertClient()
        try:
            with pytest.raises(XertAPIError, match="Invalid"):
                await client.login("invalid@example.com", "wrongpassword")
        finally:
            await client.close()
