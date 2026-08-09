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
        old_login = await app_client.post(
            "/api/login", json={"email": "resetme@example.com", "password": "pass"}
        )
        assert old_login.status_code == 401

        # New password works
        new_login = await app_client.post(
            "/api/login", json={"email": "resetme@example.com", "password": "newpass456"}
        )
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
