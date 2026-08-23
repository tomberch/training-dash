import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.integration.fixtures import CACHED_HASH_PASS
from trainingdash.repositories.postgres.models import User


class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_admin_creates_user_and_new_user_can_login(self, auth_client, app_client):
        # Admin creates a new user
        response = await auth_client.post(
            "/api/admin/users",
            json={"email": "newuser@example.com", "password": "newpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["is_admin"] is False
        assert "id" in data

        # New user can log in
        login_response = await app_client.post(
            "/api/login", json={"email": "newuser@example.com", "password": "newpass123"}
        )
        assert login_response.status_code == 200
        assert login_response.json()["email"] == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_admin_resets_password_and_user_can_login_with_new_password(
        self, auth_client, app_client, db_session
    ):
        # Create a user directly
        user = User(email="resetme@example.com", password_hash=CACHED_HASH_PASS)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Admin resets password
        response = await auth_client.post(
            f"/api/admin/users/{user.id}/reset-password",
            json={"password": "newpass456"},
        )
        assert response.status_code == 200

        # Old password no longer works
        old_login = await app_client.post("/api/login", json={"email": "resetme@example.com", "password": "pass"})
        assert old_login.status_code == 401

        # New password works
        new_login = await app_client.post("/api/login", json={"email": "resetme@example.com", "password": "newpass456"})
        assert new_login.status_code == 200

    @pytest.mark.asyncio
    async def test_non_admin_cannot_access_admin_routes(self, app_client, db_session):
        # Create a non-admin user
        user = User(email="regularuser@example.com", password_hash=CACHED_HASH_PASS, is_admin=False)
        db_session.add(user)
        await db_session.commit()

        # Login as non-admin
        login_response = await app_client.post(
            "/api/login", json={"email": "regularuser@example.com", "password": "pass"}
        )
        assert login_response.status_code == 200

        # Try to access admin endpoints
        list_response = await app_client.get("/api/admin/users")
        assert list_response.status_code == 403

        create_response = await app_client.post(
            "/api/admin/users", json={"email": "hacker@example.com", "password": "hack"}
        )
        assert create_response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_list_users_returns_all_users(self, auth_client, db_session):
        # Create additional users
        user2 = User(email="user2@example.com", password_hash=CACHED_HASH_PASS)
        user3 = User(email="user3@example.com", password_hash=CACHED_HASH_PASS)
        db_session.add_all([user2, user3])
        await db_session.commit()
        await db_session.commit()

        response = await auth_client.get("/api/admin/users")
        assert response.status_code == 200
        users = response.json()
        emails = [u["email"] for u in users]
        assert "testuser@example.com" in emails  # seed admin
        assert "user2@example.com" in emails
        assert "user3@example.com" in emails

    @pytest.mark.asyncio
    async def test_admin_cannot_create_duplicate_email(self, auth_client):
        # Create first user
        response1 = await auth_client.post(
            "/api/admin/users", json={"email": "dupuser@example.com", "password": "pass1"}
        )
        assert response1.status_code == 200

        # Try to create duplicate
        response2 = await auth_client.post(
            "/api/admin/users", json={"email": "dupuser@example.com", "password": "pass2"}
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_reset_password_user_not_found(self, auth_client):
        response = await auth_client.post(
            "/api/admin/users/99999/reset-password",
            json={"password": "newpass"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_trigger_sync_returns_success(self, auth_client, seed_user):
        # Trigger sync (stub job)
        response = await auth_client.post(f"/api/admin/users/{seed_user.id}/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # job_ids is None when no integrations configured or Redis not available
        assert "job_ids" in data

    @pytest.mark.asyncio
    async def test_admin_trigger_sync_user_not_found(self, auth_client):
        response = await auth_client.post("/api/admin/users/99999/sync")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_admin(self, db_engine):
        """Test that unauthenticated requests cannot access admin routes."""
        import trainingdash.auth as authmod
        from trainingdash.app import create_app

        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[authmod.get_db] = override_get_db

        # Use a fresh client with no cookies
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as fresh_client:
            response = await fresh_client.get("/api/admin/users")
            assert response.status_code == 401


class TestWeatherBackfillEndpoints:
    """Tests for admin weather backfill endpoints."""

    def _make_activity(self, user_id: int, title: str, started_at, weather_status: str | None):
        """Create a test activity with required fields."""
        from uuid import uuid4

        from trainingdash.repositories.postgres.models import Activity

        return Activity(
            id=uuid4(),
            user_id=user_id,
            title=title,
            started_at=started_at,
            source="test",
            source_ref=f"test-{uuid4()}",
            weather_status=weather_status,
        )

    @pytest.mark.asyncio
    async def test_weather_backfill_status_returns_counts(self, auth_client, seed_user, db_session):
        """Test that weather backfill status returns correct counts."""
        from datetime import datetime

        # Create activities with different weather statuses
        activities = [
            self._make_activity(seed_user.id, "Fetched", datetime(2024, 1, 1), "fetched"),
            self._make_activity(seed_user.id, "Pending", datetime(2024, 1, 2), "pending"),
            self._make_activity(seed_user.id, "Failed", datetime(2024, 1, 3), "failed"),
            self._make_activity(seed_user.id, "No Status", datetime(2024, 1, 4), None),
            self._make_activity(seed_user.id, "Not Applicable", datetime(2024, 1, 5), "not_applicable"),
        ]
        db_session.add_all(activities)
        await db_session.commit()

        response = await auth_client.get(f"/api/admin/users/{seed_user.id}/weather-backfill/status")
        assert response.status_code == 200

        data = response.json()
        assert data["user_id"] == seed_user.id
        assert data["total_activities"] == 5
        assert data["weather_status_counts"]["fetched"] == 1
        assert data["weather_status_counts"]["pending"] == 1
        assert data["weather_status_counts"]["failed"] == 1
        assert data["weather_status_counts"]["null"] == 1
        assert data["weather_status_counts"]["not_applicable"] == 1
        assert data["needing_backfill"] == 2  # null + pending

    @pytest.mark.asyncio
    async def test_weather_backfill_status_user_not_found(self, auth_client):
        """Test that weather backfill status returns 404 for unknown user."""
        response = await auth_client.get("/api/admin/users/99999/weather-backfill/status")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_weather_backfill_trigger_sets_pending_and_queues_job(self, auth_client, seed_user, db_session):
        """Test that triggering backfill sets statuses to pending."""
        from datetime import datetime

        # Create activities with NULL and pending status
        activities = [
            self._make_activity(seed_user.id, "No Status 1", datetime(2024, 1, 1), None),
            self._make_activity(seed_user.id, "No Status 2", datetime(2024, 1, 2), None),
            self._make_activity(seed_user.id, "Already Pending", datetime(2024, 1, 3), "pending"),
        ]
        db_session.add_all(activities)
        await db_session.commit()

        response = await auth_client.post(f"/api/admin/users/{seed_user.id}/weather-backfill")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["activities_needing_backfill"] == 3
        assert data["activities_queued"] == 3

        # Verify all are now pending
        db_session.expire_all()
        for activity in activities:
            await db_session.refresh(activity)
            assert activity.weather_status == "pending"

    @pytest.mark.asyncio
    async def test_weather_backfill_trigger_include_failed(self, auth_client, seed_user, db_session):
        """Test that include_failed=true also processes failed activities."""
        from datetime import datetime

        # Create activities including a failed one
        activities = [
            self._make_activity(seed_user.id, "No Status", datetime(2024, 1, 1), None),
            self._make_activity(seed_user.id, "Failed", datetime(2024, 1, 2), "failed"),
        ]
        db_session.add_all(activities)
        await db_session.commit()

        # Without include_failed, only NULL is processed
        response = await auth_client.post(f"/api/admin/users/{seed_user.id}/weather-backfill")
        assert response.status_code == 200
        assert response.json()["activities_queued"] == 1

        # Reset for next test
        activities[0].weather_status = None
        activities[1].weather_status = "failed"
        await db_session.commit()

        # With include_failed=true, both are processed
        response = await auth_client.post(f"/api/admin/users/{seed_user.id}/weather-backfill?include_failed=true")
        assert response.status_code == 200
        data = response.json()
        assert data["activities_queued"] == 2

        # Verify both are now pending
        db_session.expire_all()
        for activity in activities:
            await db_session.refresh(activity)
            assert activity.weather_status == "pending"

    @pytest.mark.asyncio
    async def test_weather_backfill_trigger_no_activities_needing_backfill(self, auth_client, seed_user, db_session):
        """Test that backfill returns success with 0 when nothing to process."""
        from datetime import datetime

        # Create only fetched activities
        activity = self._make_activity(seed_user.id, "Already Fetched", datetime(2024, 1, 1), "fetched")
        db_session.add(activity)
        await db_session.commit()

        response = await auth_client.post(f"/api/admin/users/{seed_user.id}/weather-backfill")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["activities_needing_backfill"] == 0
        assert data["activities_queued"] == 0
        assert "No activities need" in data["message"]

    @pytest.mark.asyncio
    async def test_weather_backfill_trigger_user_not_found(self, auth_client):
        """Test that triggering backfill returns 404 for unknown user."""
        response = await auth_client.post("/api/admin/users/99999/weather-backfill")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_cannot_access_weather_backfill(self, app_client, db_session):
        """Test that non-admin users cannot access weather backfill endpoints."""
        # Create a non-admin user
        user = User(email="nonadmin@example.com", password_hash=CACHED_HASH_PASS, is_admin=False)
        db_session.add(user)
        await db_session.commit()

        # Login as non-admin
        login_response = await app_client.post("/api/login", json={"email": "nonadmin@example.com", "password": "pass"})
        assert login_response.status_code == 200

        # Try to access weather backfill endpoints
        status_response = await app_client.get(f"/api/admin/users/{user.id}/weather-backfill/status")
        assert status_response.status_code == 403

        trigger_response = await app_client.post(f"/api/admin/users/{user.id}/weather-backfill")
        assert trigger_response.status_code == 403
