import pytest


class TestAuth:
    @pytest.mark.asyncio
    async def test_login_with_admin_provisioned_credentials_returns_session(self, app_client, seed_user):
        response = await app_client.post(
            "/login", json={"username": "testuser", "password": "testpass"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == "testuser"
        assert "session" in response.cookies

    @pytest.mark.asyncio
    async def test_login_with_wrong_password_rejected(self, app_client, seed_user):
        response = await app_client.post(
            "/login", json={"username": "testuser", "password": "wrongpass"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_with_missing_field_returns_422(self, app_client, seed_user):
        response = await app_client.post("/login", json={"username": "testuser"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_activities_requires_authentication(self, app_client):
        response = await app_client.get("/activities")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_activities(self, app_client, auth_client, db_session):
        from fitter.models import User, Activity
        from fitter.auth import hash_password
        from datetime import datetime

        user_b = User(username="userb", password_hash=hash_password("passb"))
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

        response = await auth_client.get("/activities")
        assert response.status_code == 200
        activities = response.json()
        assert all(a["id"] != activity_b.id for a in activities)