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
    with mock.patch("trainingdash.crypto.settings") as mock_settings:
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
        from trainingdash.models import XertCredentials
        from trainingdash.crypto import encrypt
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
        from trainingdash.models import XertCredentials
        from sqlalchemy import select

        # Mock the Xert client to simulate successful login
        with patch("trainingdash.app.get_xert_client") as mock_get_client:
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
        from trainingdash.xert import XertAPIError

        # Mock the Xert client to simulate failed login
        with patch("trainingdash.app.get_xert_client") as mock_get_client:
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
        from trainingdash.models import XertCredentials
        from sqlalchemy import select

        with patch("trainingdash.app.get_xert_client") as mock_get_client:
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
        from trainingdash.models import XertCredentials
        from trainingdash.crypto import encrypt
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



class TestUserProfile:
    """Tests for user profile fields: date_of_birth and weight_kg."""

    @pytest.mark.asyncio
    async def test_get_me_returns_profile_fields(self, auth_client):
        """GET /me returns date_of_birth and weight_kg (initially null)."""
        response = await auth_client.get("/me")
        assert response.status_code == 200
        data = response.json()
        assert "date_of_birth" in data
        assert "weight_kg" in data
        # Initially null for seed_user
        assert data["date_of_birth"] is None
        assert data["weight_kg"] is None

    @pytest.mark.asyncio
    async def test_update_date_of_birth(self, auth_client):
        """PATCH /me can update date_of_birth."""
        response = await auth_client.patch("/me", json={"date_of_birth": "1990-05-15"})
        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1990-05-15"

    @pytest.mark.asyncio
    async def test_update_weight_kg(self, auth_client):
        """PATCH /me can update weight_kg."""
        response = await auth_client.patch("/me", json={"weight_kg": 75.5})
        assert response.status_code == 200
        data = response.json()
        assert data["weight_kg"] == 75.5

    @pytest.mark.asyncio
    async def test_update_both_profile_fields(self, auth_client):
        """PATCH /me can update both date_of_birth and weight_kg together."""
        response = await auth_client.patch(
            "/me", json={"date_of_birth": "1985-12-01", "weight_kg": 82.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1985-12-01"
        assert data["weight_kg"] == 82.0

    @pytest.mark.asyncio
    async def test_date_of_birth_rejects_future_date(self, auth_client):
        """PATCH /me rejects date_of_birth in the future."""
        future_date = (date.today() + timedelta(days=1)).isoformat()
        response = await auth_client.patch("/me", json={"date_of_birth": future_date})
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_date_of_birth_rejects_age_under_10(self, auth_client):
        """PATCH /me rejects date_of_birth representing age < 10."""
        young_date = (date.today() - timedelta(days=365 * 5)).isoformat()  # ~5 years old
        response = await auth_client.patch("/me", json={"date_of_birth": young_date})
        assert response.status_code == 400
        assert "10" in response.json()["detail"] and "100" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_date_of_birth_rejects_age_over_100(self, auth_client):
        """PATCH /me rejects date_of_birth representing age > 100."""
        old_date = (date.today() - timedelta(days=365 * 110)).isoformat()  # ~110 years old
        response = await auth_client.patch("/me", json={"date_of_birth": old_date})
        assert response.status_code == 400
        assert "10" in response.json()["detail"] and "100" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_weight_kg_rejects_zero(self, auth_client):
        """PATCH /me rejects weight_kg of 0."""
        response = await auth_client.patch("/me", json={"weight_kg": 0})
        assert response.status_code == 400
        assert "positive" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_weight_kg_rejects_negative(self, auth_client):
        """PATCH /me rejects negative weight_kg."""
        response = await auth_client.patch("/me", json={"weight_kg": -70})
        assert response.status_code == 400
        assert "positive" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_weight_kg_rejects_unrealistic_value(self, auth_client):
        """PATCH /me rejects weight_kg > 500."""
        response = await auth_client.patch("/me", json={"weight_kg": 600})
        assert response.status_code == 400
        assert "500" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_profile_fields_persist(self, auth_client):
        """Profile fields persist across requests."""
        # Set values
        response = await auth_client.patch(
            "/me", json={"date_of_birth": "1992-03-20", "weight_kg": 68.5}
        )
        assert response.status_code == 200

        # Verify they persist
        response = await auth_client.get("/me")
        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1992-03-20"
        assert data["weight_kg"] == 68.5

    @pytest.mark.asyncio
    async def test_profile_update_requires_auth(self, app_client):
        """PATCH /me requires authentication."""
        response = await app_client.patch("/me", json={"weight_kg": 70})
        assert response.status_code == 401
