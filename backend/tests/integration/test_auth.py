import pytest


class TestAuth:
    @pytest.mark.asyncio
    async def test_login_with_admin_provisioned_credentials_returns_session(self, app_client, seed_user):
        response = await app_client.post(
            "/api/login", json={"email": "testuser@example.com", "password": "testpass"}
        )
        assert response.status_code == 200
        assert response.json()["email"] == "testuser@example.com"
        assert "session" in response.cookies

    @pytest.mark.asyncio
    async def test_login_with_wrong_password_rejected(self, app_client, seed_user):
        response = await app_client.post(
            "/api/login", json={"email": "testuser@example.com", "password": "wrongpass"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_missing_field_returns_422(self, app_client, seed_user):
        response = await app_client.post("/api/login", json={"email": "testuser@example.com"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_activities_requires_authentication(self, app_client):
        response = await app_client.get("/api/activities")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_clears_session_cookie(self, auth_client):
        # First verify we're authenticated
        response = await auth_client.get("/api/activities")
        assert response.status_code == 200

        # Logout
        response = await auth_client.post("/api/logout")
        assert response.status_code == 200

        # Subsequent requests should be unauthorized
        response = await auth_client.get("/api/activities")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_requires_auth(self, app_client):
        response = await app_client.post("/api/logout")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_returns_user_info_with_unit_system(self, auth_client, seed_user):
        response = await auth_client.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == seed_user.id
        assert data["email"] == seed_user.email
        assert data["is_admin"] == seed_user.is_admin
        assert data["unit_system"] == "metric"  # default

    @pytest.mark.asyncio
    async def test_get_me_requires_auth(self, app_client):
        response = await app_client.get("/api/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_patch_me_updates_unit_system(self, auth_client):
        response = await auth_client.patch("/api/me", json={"unit_system": "imperial"})
        assert response.status_code == 200
        data = response.json()
        assert data["unit_system"] == "imperial"

        # Verify it persisted
        response = await auth_client.get("/api/me")
        assert response.json()["unit_system"] == "imperial"

    @pytest.mark.asyncio
    async def test_patch_me_rejects_invalid_unit_system(self, auth_client):
        response = await auth_client.patch("/api/me", json={"unit_system": "invalid"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_me_requires_auth(self, app_client):
        response = await app_client.patch("/api/me", json={"unit_system": "imperial"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_activities(self, app_client, auth_client, db_session):
        from trainingdash.repositories.postgres.models import User, Activity
        from tests.integration.fixtures import CACHED_HASH_PASS
        from datetime import datetime

        user_b = User(email="userb@example.com", password_hash=CACHED_HASH_PASS)
        db_session.add(user_b)
        await db_session.commit()
        await db_session.refresh(user_b)

        activity_b = Activity(
            user_id=user_b.id,
            source="upload",
            source_ref="b.fit",
            started_at=datetime(2024, 3, 15, 10, 0),
            total_distance_m=1000,
        )
        db_session.add(activity_b)
        await db_session.commit()

        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        data = response.json()
        activities = data["activities"]
        assert all(a["id"] != str(activity_b.id) for a in activities)