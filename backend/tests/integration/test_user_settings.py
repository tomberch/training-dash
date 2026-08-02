import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
import base64
import os


# Generate a test encryption key
TEST_ENCRYPTION_KEY = base64.b64encode(os.urandom(32)).decode("ascii")


@pytest.fixture
def encryption_key_env():
    """Set up encryption key in environment."""
    from unittest import mock
    with mock.patch("fitter.crypto.settings") as mock_settings:
        mock_settings.encryption_key = TEST_ENCRYPTION_KEY
        yield


class TestUserXertCredentials:
    @pytest.mark.asyncio
    async def test_get_xert_credentials_when_not_configured(self, auth_client):
        response = await auth_client.get("/me/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is False
        assert data["xert_email"] is None
        assert data["sync_since"] is None

    @pytest.mark.asyncio
    async def test_get_xert_credentials_when_configured_shows_email_and_sync_since(
        self, auth_client, db_session, seed_user, encryption_key_env
    ):
        from fitter.models import XertCredentials
        from fitter.crypto import encrypt
        from datetime import datetime

        # Create credentials directly in DB
        creds = XertCredentials(
            user_id=seed_user.id,
            xert_email="test@xert.com",
            encrypted_password=encrypt("secret"),
            sync_since=datetime(2024, 1, 15),
        )
        db_session.add(creds)
        await db_session.commit()

        response = await auth_client.get("/me/xert-credentials")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["xert_email"] == "test@xert.com"
        assert data["sync_since"] == "2024-01-15"
        # Password should never be returned
        assert "password" not in data
        assert "encrypted_password" not in data

    @pytest.mark.asyncio
    async def test_put_xert_credentials_validates_and_saves(self, auth_client, seed_user, db_session, encryption_key_env):
        from fitter.models import XertCredentials
        from sqlalchemy import select

        # Mock the Xert client to simulate successful login
        with patch("fitter.app.get_xert_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock()  # No exception = success
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await auth_client.put(
                "/me/xert-credentials",
                json={"xert_email": "user@xert.com", "xert_password": "validpass"},
            )
            assert response.status_code == 200

            # Verify credentials were saved
            result = await db_session.execute(
                select(XertCredentials).where(XertCredentials.user_id == seed_user.id)
            )
            creds = result.scalar_one_or_none()
            assert creds is not None
            assert creds.xert_email == "user@xert.com"
            # sync_since should default to 90 days ago
            assert creds.sync_since is not None

    @pytest.mark.asyncio
    async def test_put_xert_credentials_rejects_invalid_credentials(self, auth_client, encryption_key_env):
        from fitter.xert import XertAPIError

        # Mock the Xert client to simulate failed login
        with patch("fitter.app.get_xert_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=XertAPIError("Invalid credentials"))
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await auth_client.put(
                "/me/xert-credentials",
                json={"xert_email": "user@xert.com", "xert_password": "wrongpass"},
            )
            assert response.status_code == 400
            assert "Invalid Xert credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_put_xert_credentials_with_custom_sync_since(self, auth_client, seed_user, db_session, encryption_key_env):
        from fitter.models import XertCredentials
        from sqlalchemy import select

        with patch("fitter.app.get_xert_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await auth_client.put(
                "/me/xert-credentials",
                json={
                    "xert_email": "user@xert.com",
                    "xert_password": "validpass",
                    "sync_since": "2023-06-01",
                },
            )
            assert response.status_code == 200

            result = await db_session.execute(
                select(XertCredentials).where(XertCredentials.user_id == seed_user.id)
            )
            creds = result.scalar_one_or_none()
            assert creds is not None
            assert creds.sync_since.date() == date(2023, 6, 1)

    @pytest.mark.asyncio
    async def test_delete_xert_credentials_removes_credentials(
        self, auth_client, db_session, seed_user, encryption_key_env
    ):
        from fitter.models import XertCredentials
        from fitter.crypto import encrypt
        from sqlalchemy import select

        # First create credentials
        creds = XertCredentials(
            user_id=seed_user.id,
            xert_email="test@xert.com",
            encrypted_password=encrypt("secret"),
        )
        db_session.add(creds)
        await db_session.commit()

        # Delete them
        response = await auth_client.delete("/me/xert-credentials")
        assert response.status_code == 200

        # Verify they're gone
        result = await db_session.execute(
            select(XertCredentials).where(XertCredentials.user_id == seed_user.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_xert_credentials_idempotent(self, auth_client):
        # Delete when nothing exists should still return 200
        response = await auth_client.delete("/me/xert-credentials")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_xert_credentials_endpoints_require_auth(self, app_client):
        response = await app_client.get("/me/xert-credentials")
        assert response.status_code == 401

        response = await app_client.put(
            "/me/xert-credentials",
            json={"xert_email": "a@b.com", "xert_password": "x"},
        )
        assert response.status_code == 401

        response = await app_client.delete("/me/xert-credentials")
        assert response.status_code == 401
