import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from fitter.auth import hash_password
from fitter.models import User


class TestAdminEndpoints:
    @pytest.mark.asyncio
    async def test_admin_creates_user_and_new_user_can_login(self, auth_client, app_client):
        # Admin creates a new user
        response = await auth_client.post(
            "/admin/users",
            json={"username": "newuser", "password": "newpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["is_admin"] is False
        assert "id" in data

        # New user can log in
        login_response = await app_client.post(
            "/login", json={"username": "newuser", "password": "newpass123"}
        )
        assert login_response.status_code == 200
        assert login_response.json()["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_admin_resets_password_and_user_can_login_with_new_password(
        self, auth_client, app_client, db_session
    ):
        # Create a user directly
        user = User(username="resetme", password_hash=hash_password("oldpass"))
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Admin resets password
        response = await auth_client.post(
            f"/admin/users/{user.id}/reset-password",
            json={"password": "newpass456"},
        )
        assert response.status_code == 200

        # Old password no longer works
        old_login = await app_client.post(
            "/login", json={"username": "resetme", "password": "oldpass"}
        )
        assert old_login.status_code == 401

        # New password works
        new_login = await app_client.post(
            "/login", json={"username": "resetme", "password": "newpass456"}
        )
        assert new_login.status_code == 200

    @pytest.mark.asyncio
    async def test_non_admin_cannot_access_admin_routes(self, app_client, db_session):
        # Create a non-admin user
        user = User(username="regularuser", password_hash=hash_password("pass"), is_admin=False)
        db_session.add(user)
        await db_session.commit()

        # Login as non-admin
        login_response = await app_client.post(
            "/login", json={"username": "regularuser", "password": "pass"}
        )
        assert login_response.status_code == 200

        # Try to access admin endpoints
        list_response = await app_client.get("/admin/users")
        assert list_response.status_code == 403

        create_response = await app_client.post(
            "/admin/users", json={"username": "hacker", "password": "hack"}
        )
        assert create_response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_list_users_returns_all_users(self, auth_client, db_session):
        # Create additional users
        user2 = User(username="user2", password_hash=hash_password("pass2"))
        user3 = User(username="user3", password_hash=hash_password("pass3"))
        db_session.add_all([user2, user3])
        await db_session.commit()

        response = await auth_client.get("/admin/users")
        assert response.status_code == 200
        users = response.json()
        usernames = [u["username"] for u in users]
        assert "testuser" in usernames  # seed admin
        assert "user2" in usernames
        assert "user3" in usernames

    @pytest.mark.asyncio
    async def test_admin_cannot_create_duplicate_username(self, auth_client):
        # Create first user
        response1 = await auth_client.post(
            "/admin/users", json={"username": "dupuser", "password": "pass1"}
        )
        assert response1.status_code == 200

        # Try to create duplicate
        response2 = await auth_client.post(
            "/admin/users", json={"username": "dupuser", "password": "pass2"}
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_reset_password_user_not_found(self, auth_client):
        response = await auth_client.post(
            "/admin/users/99999/reset-password",
            json={"password": "newpass"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_trigger_sync_returns_success(self, auth_client, seed_user):
        # Trigger sync (stub job)
        response = await auth_client.post(f"/admin/users/{seed_user.id}/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # job_id is None when Redis is not available
        assert "job_id" in data

    @pytest.mark.asyncio
    async def test_admin_trigger_sync_user_not_found(self, auth_client):
        response = await auth_client.post("/admin/users/99999/sync")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_admin(self, db_engine):
        """Test that unauthenticated requests cannot access admin routes."""
        import fitter.auth as authmod
        from fitter.app import create_app

        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

        async def override_get_db():
            async with session_factory() as session:
                yield session

        app = create_app()
        app.dependency_overrides[authmod.get_db] = override_get_db

        # Use a fresh client with no cookies
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as fresh_client:
            response = await fresh_client.get("/admin/users")
            assert response.status_code == 401
