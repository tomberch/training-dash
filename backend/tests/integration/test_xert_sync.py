"""Integration tests for Xert sync functionality.

Based on Xert Online API v1.4: https://www.xertonline.com/API.html
"""

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from trainingdash.models import Activity, User, XertCredentials
from trainingdash.xert import XertActivity, XertActivityDetail, XertSessionDataPoint, XertAPIError
from tests.integration.fixtures import CACHED_HASH_TESTPASS, CACHED_HASH_PASS

# Load .env.test if it exists (for local Xert API testing)
_env_test_path = Path(__file__).parent.parent.parent / ".env.test"
if _env_test_path.exists():
    load_dotenv(_env_test_path)


# Generate a test encryption key
TEST_ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode("ascii")


def make_mock_session_data(count: int = 10, start_time_ms: int = 1722344060000) -> list[XertSessionDataPoint]:
    """Generate mock session_data points."""
    data = []
    for i in range(count):
        data.append(XertSessionDataPoint(
            unix_time=start_time_ms + (i * 1000),  # 1 second intervals
            power=150.0 + (i * 5),
            hr=120 + i,
            cad=80.0 + (i * 0.5),
            alt=100.0,
            spd=8000.0,  # 8 m/s * 1000
            dist=float(i * 8),  # meters
            lat=43.622447 + (i * 0.0001),
            lng=-79.792798 + (i * 0.0001),
        ))
    return data


class MockXertClient:
    """Mock Xert client for testing based on actual Xert API v1.4."""
    
    def __init__(self):
        self.activities: list[XertActivity] = []
        self.activity_details: dict[str, XertActivityDetail] = {}
        self.login_called = False
        self.login_username: str | None = None
        self.should_fail_login = False
        self.should_fail_detail: set[str] = set()
    
    async def login(self, username: str, password: str) -> None:
        self.login_called = True
        self.login_username = username
        if self.should_fail_login:
            raise XertAPIError("Invalid credentials")
    
    async def list_activities(
        self, 
        from_timestamp: int | None = None, 
        to_timestamp: int | None = None
    ) -> list[XertActivity]:
        return self.activities
    
    async def get_activity_detail(
        self, 
        activity: XertActivity,
        include_session_data: bool = True
    ) -> XertActivityDetail:
        """Get activity detail with session_data."""
        if activity.id in self.should_fail_detail:
            raise XertAPIError(f"Failed to get detail for {activity.id}")
        
        if activity.id in self.activity_details:
            return self.activity_details[activity.id]
        
        # Return a default detail with mock session data
        return XertActivityDetail(
            id=activity.id,
            name=activity.name,
            description=activity.description,
            started_at=activity.started_at,
            activity_type=activity.activity_type,
            duration=3600.0,  # 1 hour
            distance=30.0,  # 30 km
            session_data=make_mock_session_data(10) if include_session_data else [],
            xss=85.5,  # Mock XSS (training load)
            focus="Rouleur",
        )
    
    async def close(self) -> None:
        pass


@pytest.fixture
def mock_xert_client():
    """Provide a mock Xert client."""
    return MockXertClient()


@pytest.fixture
def encryption_key_env():
    """Set up encryption key in environment."""
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


class TestXertCredentialsEndpoints:
    """Tests for admin Xert credentials endpoints."""

    @pytest.mark.asyncio
    async def test_set_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        """Admin can set Xert credentials for a user."""
        response = await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["xert_email"] == "test@xert.com"
        # Password should NOT be in response
        assert "xert_password" not in data
        assert "encrypted_password" not in data

    @pytest.mark.asyncio
    async def test_get_xert_credentials_shows_email_not_password(
        self, auth_client, seed_user, encryption_key_env
    ):
        """Getting credentials shows email but never password."""
        # First set credentials
        await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        
        # Then get them
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["xert_email"] == "test@xert.com"
        assert "password" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_get_xert_credentials_not_configured(self, auth_client, seed_user):
        """Getting credentials for user without them returns configured=False."""
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["xert_email"] is None

    @pytest.mark.asyncio
    async def test_delete_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        """Admin can delete Xert credentials."""
        # First set credentials
        await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        
        # Delete them
        response = await auth_client.delete(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify they're gone
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.json()["configured"] is False

    @pytest.mark.asyncio
    async def test_update_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        """Setting credentials again updates them."""
        # Set initial credentials
        await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "old@xert.com", "xert_password": "oldpass"},
        )
        
        # Update credentials
        response = await auth_client.put(
            f"/api/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "new@xert.com", "xert_password": "newpass"},
        )
        assert response.status_code == 200
        
        # Verify update
        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/xert-credentials")
        assert response.json()["xert_email"] == "new@xert.com"


class TestSyncXertJob:
    """Tests for the sync_xert_job worker function."""

    @pytest.mark.asyncio
    async def test_sync_xert_imports_new_activities(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should fetch session_data and create Activity/Records for new activities."""
        # Set up mock client with activities
        mock_xert_client.activities = [
            XertActivity(
                id="s8pehgletoecmk5x",  # path from Xert API
                name="Morning Ride",
                started_at=datetime(2024, 1, 15, 8, 0, 0),
                activity_type="Cycling",
            ),
        ]
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        # Patch the client factory and run the job
        with mock.patch("trainingdash.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                from trainingdash.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)
        
        assert result["success"] is True
        assert result["synced_activities"] == 1
        assert mock_xert_client.login_called
        assert mock_xert_client.login_username == "user@xert.com"
        
        # Verify Activity was created in database
        async with session_factory() as session:
            from trainingdash.models import Activity, Record
            activity_result = await session.execute(
                select(Activity).where(Activity.source_ref == "xert:s8pehgletoecmk5x")
            )
            activity = activity_result.scalar_one()
            assert activity is not None
            assert activity.source == "xert"
            assert activity.source_ref == "xert:s8pehgletoecmk5x"
            assert activity.training_load == 85.5  # XSS from mock
            
            # Verify Records were created (from mock session_data with 10 points)
            record_result = await session.execute(
                select(Record).where(Record.activity_id == activity.id)
            )
            records = record_result.scalars().all()
            assert len(records) == 10  # make_mock_session_data returns 10 points

    @pytest.mark.asyncio
    async def test_sync_xert_skips_already_imported(
        self, db_engine, db_session, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should skip activities already imported."""
        # Create an existing activity with the same source_ref (use naive datetime for DB)
        existing = Activity(
            user_id=user_with_xert_creds.id,
            source="xert",
            source_ref="xert:xert-activity-1",
            started_at=datetime(2024, 1, 15, 8, 0, 0),  # naive datetime for DB
            total_distance_m=10000,
            moving_time_s=1800,
            elapsed_time_s=2000,
        )
        db_session.add(existing)
        await db_session.commit()
        
        # Set up mock client with the same activity
        mock_xert_client.activities = [
            XertActivity(
                id="xert-activity-1",
                name="Morning Ride",
                started_at=datetime(2024, 1, 15, 8, 0, 0),
                activity_type="Cycling",
            ),
        ]
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("trainingdash.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                from trainingdash.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)
        
        assert result["success"] is True
        assert result["synced_activities"] == 0

    @pytest.mark.asyncio
    async def test_sync_xert_no_credentials_returns_error(self, db_engine, db_session):
        """sync_xert_job should return error if user has no credentials."""
        user = User(
            email="nocreds@example.com",
            password_hash=CACHED_HASH_TESTPASS,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
            from trainingdash.worker import sync_xert_job
            result = await sync_xert_job({}, user.id)
        
        assert result["success"] is False
        assert "No Xert credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_xert_login_failure_returns_error(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should return error if Xert login fails."""
        mock_xert_client.should_fail_login = True
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("trainingdash.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                from trainingdash.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)
        
        assert result["success"] is False
        assert "Invalid credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_xert_continues_on_detail_failure(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should continue if getting one activity's detail fails."""
        mock_xert_client.activities = [
            XertActivity(
                id="fail-activity",
                name="Failed Detail",
                started_at=datetime(2024, 1, 15, 8, 0, 0),
                activity_type="Cycling",
            ),
            XertActivity(
                id="success-activity",
                name="Success",
                started_at=datetime(2024, 1, 16, 8, 0, 0),
                activity_type="Cycling",
            ),
        ]
        mock_xert_client.should_fail_detail.add("fail-activity")
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("trainingdash.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
                from trainingdash.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)
        
        # Should succeed with 1 activity (the one that didn't fail)
        assert result["success"] is True
        assert result["synced_activities"] == 1
        
        # Verify only successful activity was created
        async with session_factory() as session:
            activity_result = await session.execute(
                select(Activity).where(Activity.source == "xert")
            )
            activities = activity_result.scalars().all()
            assert len(activities) == 1
            assert activities[0].source_ref == "xert:success-activity"


class TestHourlySyncScheduler:
    """Tests for the hourly sync scheduler cron job."""

    @pytest.mark.asyncio
    async def test_hourly_sync_enqueues_for_users_with_matching_sync_hour(
        self, db_engine, db_session, encryption_key_env
    ):
        """hourly_sync_scheduler should enqueue sync for users whose sync_hour matches."""
        from datetime import datetime, timezone
        from trainingdash.crypto import encrypt
        
        current_hour = datetime.now(timezone.utc).hour
        
        # Create users with different sync_hours
        user1 = User(email="user1@example.com", password_hash=CACHED_HASH_PASS, sync_hour=current_hour)
        user2 = User(email="user2@example.com", password_hash=CACHED_HASH_PASS, sync_hour=current_hour)
        user3 = User(email="user3@example.com", password_hash=CACHED_HASH_PASS, sync_hour=(current_hour + 1) % 24)  # different hour
        db_session.add_all([user1, user2, user3])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)
        await db_session.refresh(user3)
        
        # Only user1 and user2 have Xert credentials
        creds1 = XertCredentials(
            user_id=user1.id,
            xert_email="user1@xert.com",
            encrypted_password=encrypt("pass1"),
        )
        creds2 = XertCredentials(
            user_id=user2.id,
            xert_email="user2@xert.com",
            encrypted_password=encrypt("pass2"),
        )
        # user3 also has creds but wrong sync_hour
        creds3 = XertCredentials(
            user_id=user3.id,
            xert_email="user3@xert.com",
            encrypted_password=encrypt("pass3"),
        )
        db_session.add_all([creds1, creds2, creds3])
        await db_session.commit()
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
            with mock.patch("trainingdash.worker.create_redis_pool") as mock_pool:
                mock_arq = mock.AsyncMock()
                mock_pool.return_value = mock_arq
                
                from trainingdash.worker import hourly_sync_scheduler
                result = await hourly_sync_scheduler({})
        
        assert result["success"] is True
        # Only users 1 and 2 match the current hour
        assert result["xert_queued"] == 2
        
        # Verify sync jobs were enqueued for users 1 and 2 only
        enqueued_user_ids = set()
        for call in mock_arq.enqueue_job.call_args_list:
            if call.args[0] == "sync_xert_job":
                enqueued_user_ids.add(call.kwargs["user_id"])
        assert user1.id in enqueued_user_ids
        assert user2.id in enqueued_user_ids
        assert user3.id not in enqueued_user_ids

    @pytest.mark.asyncio
    async def test_hourly_sync_no_users_for_current_hour(self, db_engine, db_session):
        """hourly_sync_scheduler should handle no users matching current hour."""
        from datetime import datetime, timezone
        
        current_hour = datetime.now(timezone.utc).hour
        different_hour = (current_hour + 1) % 24
        
        # Create user with different sync_hour
        user = User(email="nocreds@example.com", password_hash=CACHED_HASH_PASS, sync_hour=different_hour)
        db_session.add(user)
        await db_session.commit()
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("trainingdash.worker.worker_db_session", mock_worker_db_session):
            with mock.patch("trainingdash.worker.create_redis_pool") as mock_pool:
                mock_arq = mock.AsyncMock()
                mock_pool.return_value = mock_arq
                
                from trainingdash.worker import hourly_sync_scheduler
                result = await hourly_sync_scheduler({})
        
        assert result["success"] is True
        assert result["xert_queued"] == 0
        assert result["garmin_queued"] == 0


@pytest.mark.skipif(
    not os.environ.get("XERT_TEST_USERNAME"),
    reason="Set XERT_TEST_USERNAME and XERT_TEST_PASSWORD to run real API tests"
)
class TestXertClientRealAPI:
    """Integration tests against real Xert API. Skipped unless credentials are provided."""

    @pytest.mark.asyncio
    async def test_real_xert_login_and_list_activities(self):
        """Test real Xert API login, activity listing, and session_data retrieval."""
        from trainingdash.xert import XertClient
        
        username = os.environ["XERT_TEST_USERNAME"]
        password = os.environ["XERT_TEST_PASSWORD"]
        
        client = XertClient()
        try:
            # Test login
            await client.login(username, password)
            assert client._access_token is not None
            
            # Test list activities (last 7 days)
            import time
            to_ts = int(time.time())
            from_ts = to_ts - (7 * 24 * 60 * 60)
            
            activities = await client.list_activities(from_timestamp=from_ts, to_timestamp=to_ts)
            
            # Just verify the shape - we may or may not have activities
            assert isinstance(activities, list)
            
            if activities:
                activity = activities[0]
                assert hasattr(activity, 'id')
                assert hasattr(activity, 'name')
                assert hasattr(activity, 'started_at')
                assert hasattr(activity, 'activity_type')
                assert activity.id  # path should not be empty
                
                print(f"DEBUG: Activity id/path: {activity.id}")
                print(f"DEBUG: Activity name: {activity.name}")
                print(f"DEBUG: Activity type: {activity.activity_type}")
                print(f"DEBUG: Activity started_at: {activity.started_at}")
                
                # Test get_activity_detail with session_data
                # This is how Golden Cheetah retrieves Xert data - no FIT download API exists
                detail = await client.get_activity_detail(activity, include_session_data=True)
                
                assert detail.id == activity.id
                assert detail.name == activity.name
                assert detail.duration >= 0
                assert detail.distance >= 0
                
                print(f"DEBUG: Detail duration: {detail.duration}s")
                print(f"DEBUG: Detail distance: {detail.distance}km")
                print(f"DEBUG: XSS (training load): {detail.xss}")
                print(f"DEBUG: Focus: {detail.focus}")
                print(f"DEBUG: Difficulty: {detail.difficulty_rating}")
                print(f"DEBUG: Session data points: {len(detail.session_data)}")
                
                # If activity has session_data, verify structure
                if detail.session_data:
                    point = detail.session_data[0]
                    # Some fields may be None - just verify we got data
                    print(f"DEBUG: First point - time: {point.unix_time}, power: {point.power}, hr: {point.hr}")
                    # At least one field should have data
                    has_data = any([
                        point.power is not None,
                        point.hr is not None, 
                        point.lat is not None,
                        point.spd is not None,
                    ])
                    assert has_data, "Session data point should have at least one field populated"
                
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_real_xert_invalid_credentials(self):
        """Test that invalid credentials raise XertAPIError."""
        from trainingdash.xert import XertClient, XertAPIError
        
        client = XertClient()
        try:
            with pytest.raises(XertAPIError, match="Invalid"):
                await client.login("invalid@example.com", "wrongpassword")
        finally:
            await client.close()
