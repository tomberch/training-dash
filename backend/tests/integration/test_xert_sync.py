"""Integration tests for Xert sync functionality.

Based on Xert Online API v1.4: https://www.xertonline.com/API.html
"""

import base64
import os
from datetime import datetime, timezone
from unittest import mock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from fitter.auth import hash_password
from fitter.models import Activity, User, XertCredentials
from fitter.xert import XertActivity, XertAPIError


# Generate a test encryption key
TEST_ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode("ascii")


class MockXertClient:
    """Mock Xert client for testing based on actual Xert API v1.4."""
    
    def __init__(self):
        self.activities: list[XertActivity] = []
        self.fit_data: dict[str, bytes] = {}  # activity_id -> FIT bytes
        self.login_called = False
        self.login_username: str | None = None
        self.should_fail_login = False
        self.should_fail_download: set[str] = set()
    
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
    
    async def download_fit(self, activity: XertActivity) -> bytes:
        """Download FIT file from /activities/download/<path>."""
        if activity.id in self.should_fail_download:
            raise XertAPIError(f"Failed to download FIT for {activity.id}")
        return self.fit_data.get(activity.id, b"mock-fit-data")
    
    async def close(self) -> None:
        pass


@pytest.fixture
def mock_xert_client():
    """Provide a mock Xert client."""
    return MockXertClient()


@pytest.fixture
def encryption_key_env():
    """Set up encryption key in environment."""
    with mock.patch("fitter.crypto.settings") as mock_settings:
        mock_settings.encryption_key = TEST_ENCRYPTION_KEY
        yield


@pytest_asyncio.fixture
async def user_with_xert_creds(db_session, encryption_key_env):
    """Create a user with Xert credentials."""
    from fitter.crypto import encrypt
    
    user = User(
        username="xertuser",
        password_hash=hash_password("testpass"),
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
            f"/admin/users/{seed_user.id}/xert-credentials",
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
            f"/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        
        # Then get them
        response = await auth_client.get(f"/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["xert_email"] == "test@xert.com"
        assert "password" not in str(data).lower()

    @pytest.mark.asyncio
    async def test_get_xert_credentials_not_configured(self, auth_client, seed_user):
        """Getting credentials for user without them returns configured=False."""
        response = await auth_client.get(f"/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["xert_email"] is None

    @pytest.mark.asyncio
    async def test_delete_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        """Admin can delete Xert credentials."""
        # First set credentials
        await auth_client.put(
            f"/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "test@xert.com", "xert_password": "secret123"},
        )
        
        # Delete them
        response = await auth_client.delete(f"/admin/users/{seed_user.id}/xert-credentials")
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify they're gone
        response = await auth_client.get(f"/admin/users/{seed_user.id}/xert-credentials")
        assert response.json()["configured"] is False

    @pytest.mark.asyncio
    async def test_update_xert_credentials(self, auth_client, seed_user, encryption_key_env):
        """Setting credentials again updates them."""
        # Set initial credentials
        await auth_client.put(
            f"/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "old@xert.com", "xert_password": "oldpass"},
        )
        
        # Update credentials
        response = await auth_client.put(
            f"/admin/users/{seed_user.id}/xert-credentials",
            json={"xert_email": "new@xert.com", "xert_password": "newpass"},
        )
        assert response.status_code == 200
        
        # Verify update
        response = await auth_client.get(f"/admin/users/{seed_user.id}/xert-credentials")
        assert response.json()["xert_email"] == "new@xert.com"


class TestSyncXertJob:
    """Tests for the sync_xert_job worker function."""

    @pytest.mark.asyncio
    async def test_sync_xert_imports_new_activities(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should download FIT and enqueue ingest_job for new activities."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
        from generate_fit import make_test_fit
        
        # Set up mock client with activities and FIT data
        fit_bytes = make_test_fit()
        mock_xert_client.activities = [
            XertActivity(
                id="s8pehgletoecmk5x",  # path used for download URL
                name="Morning Ride",
                started_at=datetime(2024, 1, 15, 8, 0, 0),
                activity_type="Cycling",
            ),
        ]
        mock_xert_client.fit_data["s8pehgletoecmk5x"] = fit_bytes
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        # Patch the client factory and run the job
        with mock.patch("fitter.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
                with mock.patch("fitter.worker.create_redis_pool") as mock_pool:
                    mock_arq = mock.AsyncMock()
                    mock_pool.return_value = mock_arq
                    
                    from fitter.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)
        
        assert result["success"] is True
        assert result["synced_activities"] == 1
        assert mock_xert_client.login_called
        assert mock_xert_client.login_username == "user@xert.com"
        
        # Verify ingest_job was enqueued with FIT data
        mock_arq.enqueue_job.assert_called_once()
        call_args = mock_arq.enqueue_job.call_args
        assert call_args[0][0] == "ingest_job"
        assert call_args.kwargs["source"] == "xert"
        assert call_args.kwargs["source_ref"] == "xert:s8pehgletoecmk5x"
        assert call_args.kwargs["fit_bytes"] == fit_bytes

    @pytest.mark.asyncio
    async def test_sync_xert_skips_already_imported(
        self, db_engine, db_session, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should skip activities already imported."""
        # Create an existing activity with the same source_ref
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
        
        with mock.patch("fitter.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
                with mock.patch("fitter.worker.create_redis_pool") as mock_pool:
                    mock_arq = mock.AsyncMock()
                    mock_pool.return_value = mock_arq
                    
                    from fitter.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)
        
        assert result["success"] is True
        assert result["synced_activities"] == 0
        # No jobs should be enqueued
        mock_arq.enqueue_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_xert_no_credentials_returns_error(self, db_engine, db_session):
        """sync_xert_job should return error if user has no credentials."""
        user = User(
            username="nocreds",
            password_hash=hash_password("testpass"),
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
        
        with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
            from fitter.worker import sync_xert_job
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
        
        with mock.patch("fitter.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
                from fitter.worker import sync_xert_job
                result = await sync_xert_job({}, user_with_xert_creds.id)
        
        assert result["success"] is False
        assert "Invalid credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_sync_xert_continues_on_download_failure(
        self, db_engine, user_with_xert_creds, mock_xert_client, encryption_key_env
    ):
        """sync_xert_job should continue if downloading one activity's FIT fails."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
        from generate_fit import make_test_fit
        
        fit_bytes = make_test_fit()
        mock_xert_client.activities = [
            XertActivity(
                id="fail-activity",
                name="Failed Download",
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
        mock_xert_client.should_fail_download.add("fail-activity")
        mock_xert_client.fit_data["success-activity"] = fit_bytes
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("fitter.xert.get_xert_client", return_value=mock_xert_client):
            with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
                with mock.patch("fitter.worker.create_redis_pool") as mock_pool:
                    mock_arq = mock.AsyncMock()
                    mock_pool.return_value = mock_arq
                    
                    from fitter.worker import sync_xert_job
                    result = await sync_xert_job({}, user_with_xert_creds.id)
        
        # Should succeed with 1 activity (the one that didn't fail)
        assert result["success"] is True
        assert result["synced_activities"] == 1


class TestNightlySyncAllXert:
    """Tests for the nightly cron job."""

    @pytest.mark.asyncio
    async def test_nightly_sync_enqueues_for_all_users_with_creds(
        self, db_engine, db_session, encryption_key_env
    ):
        """nightly_sync_all_xert should enqueue sync for all users with credentials."""
        from fitter.crypto import encrypt
        
        # Create multiple users, some with credentials
        user1 = User(username="user1", password_hash=hash_password("pass"))
        user2 = User(username="user2", password_hash=hash_password("pass"))
        user3 = User(username="user3", password_hash=hash_password("pass"))  # no creds
        db_session.add_all([user1, user2, user3])
        await db_session.commit()
        await db_session.refresh(user1)
        await db_session.refresh(user2)
        
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
        db_session.add_all([creds1, creds2])
        await db_session.commit()
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
            with mock.patch("fitter.worker.create_redis_pool") as mock_pool:
                mock_arq = mock.AsyncMock()
                mock_pool.return_value = mock_arq
                
                from fitter.worker import nightly_sync_all_xert
                result = await nightly_sync_all_xert({})
        
        assert result["success"] is True
        assert result["users_queued"] == 2
        
        # Verify sync jobs were enqueued for both users
        assert mock_arq.enqueue_job.call_count == 2
        enqueued_user_ids = {
            call.kwargs["user_id"]
            for call in mock_arq.enqueue_job.call_args_list
        }
        assert user1.id in enqueued_user_ids
        assert user2.id in enqueued_user_ids

    @pytest.mark.asyncio
    async def test_nightly_sync_no_users_with_creds(self, db_engine, db_session):
        """nightly_sync_all_xert should handle no users with credentials."""
        # Create user without credentials
        user = User(username="nocreds", password_hash=hash_password("pass"))
        db_session.add(user)
        await db_session.commit()
        
        # Mock worker_db_session to use test database
        from contextlib import asynccontextmanager
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        
        @asynccontextmanager
        async def mock_worker_db_session():
            async with session_factory() as session:
                yield session
        
        with mock.patch("fitter.worker.worker_db_session", mock_worker_db_session):
            with mock.patch("fitter.worker.create_redis_pool") as mock_pool:
                mock_arq = mock.AsyncMock()
                mock_pool.return_value = mock_arq
                
                from fitter.worker import nightly_sync_all_xert
                result = await nightly_sync_all_xert({})
        
        assert result["success"] is True
        assert result["users_queued"] == 0
        mock_arq.enqueue_job.assert_not_called()


@pytest.mark.skipif(
    not os.environ.get("XERT_TEST_USERNAME"),
    reason="Set XERT_TEST_USERNAME and XERT_TEST_PASSWORD to run real API tests"
)
class TestXertClientRealAPI:
    """Integration tests against real Xert API. Skipped unless credentials are provided."""

    @pytest.mark.asyncio
    async def test_real_xert_login_and_list_activities(self):
        """Test real Xert API login and activity listing."""
        from fitter.xert import XertClient
        
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
                
                # Test FIT download
                fit_bytes = await client.download_fit(activity)
                assert isinstance(fit_bytes, bytes)
                assert len(fit_bytes) > 0
                # FIT files start with header size byte (usually 14)
                assert fit_bytes[0] in (12, 14)
                
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_real_xert_invalid_credentials(self):
        """Test that invalid credentials raise XertAPIError."""
        from fitter.xert import XertClient, XertAPIError
        
        client = XertClient()
        try:
            with pytest.raises(XertAPIError, match="Invalid"):
                await client.login("invalid@example.com", "wrongpassword")
        finally:
            await client.close()
