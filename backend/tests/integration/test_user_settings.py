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
        response = await auth_client.get("/api/me/xert-credentials")
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

        response = await auth_client.get("/api/me/xert-credentials")
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
        with patch("trainingdash.routers.user.get_xert_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock()  # No exception = success
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await auth_client.put(
                "/api/me/xert-credentials",
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
        with patch("trainingdash.routers.user.get_xert_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=XertAPIError("Invalid credentials"))
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await auth_client.put(
                "/api/me/xert-credentials",
                json={"xert_email": "user@xert.com", "xert_password": "wrongpass"},
            )
            assert response.status_code == 400
            assert "Invalid Xert credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_put_xert_credentials_with_custom_sync_since(self, auth_client, seed_user, db_session, encryption_key_env):
        from trainingdash.models import XertCredentials
        from sqlalchemy import select

        with patch("trainingdash.routers.user.get_xert_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await auth_client.put(
                "/api/me/xert-credentials",
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
        response = await auth_client.delete("/api/me/xert-credentials")
        assert response.status_code == 200

        # Verify they're gone
        result = await db_session.execute(
            select(XertCredentials).where(XertCredentials.user_id == seed_user.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_xert_credentials_idempotent(self, auth_client):
        # Delete when nothing exists should still return 200
        response = await auth_client.delete("/api/me/xert-credentials")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_xert_credentials_endpoints_require_auth(self, app_client):
        response = await app_client.get("/api/me/xert-credentials")
        assert response.status_code == 401

        response = await app_client.put(
            "/api/me/xert-credentials",
            json={"xert_email": "a@b.com", "xert_password": "x"},
        )
        assert response.status_code == 401

        response = await app_client.delete("/api/me/xert-credentials")
        assert response.status_code == 401



class TestUserProfile:
    """Tests for user profile fields: date_of_birth and weight_kg."""

    @pytest.mark.asyncio
    async def test_get_me_returns_profile_fields(self, auth_client):
        """GET /me returns date_of_birth and weight_kg (initially null)."""
        response = await auth_client.get("/api/me")
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
        response = await auth_client.patch("/api/me", json={"date_of_birth": "1990-05-15"})
        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1990-05-15"

    @pytest.mark.asyncio
    async def test_update_weight_kg(self, auth_client):
        """PATCH /me can update weight_kg."""
        response = await auth_client.patch("/api/me", json={"weight_kg": 75.5})
        assert response.status_code == 200
        data = response.json()
        assert data["weight_kg"] == 75.5

    @pytest.mark.asyncio
    async def test_update_both_profile_fields(self, auth_client):
        """PATCH /me can update both date_of_birth and weight_kg together."""
        response = await auth_client.patch(
            "/api/me", json={"date_of_birth": "1985-12-01", "weight_kg": 82.0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1985-12-01"
        assert data["weight_kg"] == 82.0

    @pytest.mark.asyncio
    async def test_date_of_birth_rejects_future_date(self, auth_client):
        """PATCH /me rejects date_of_birth in the future."""
        future_date = (date.today() + timedelta(days=1)).isoformat()
        response = await auth_client.patch("/api/me", json={"date_of_birth": future_date})
        assert response.status_code == 400
        assert "future" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_date_of_birth_rejects_age_under_10(self, auth_client):
        """PATCH /me rejects date_of_birth representing age < 10."""
        young_date = (date.today() - timedelta(days=365 * 5)).isoformat()  # ~5 years old
        response = await auth_client.patch("/api/me", json={"date_of_birth": young_date})
        assert response.status_code == 400
        assert "10" in response.json()["detail"] and "100" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_date_of_birth_rejects_age_over_100(self, auth_client):
        """PATCH /me rejects date_of_birth representing age > 100."""
        old_date = (date.today() - timedelta(days=365 * 110)).isoformat()  # ~110 years old
        response = await auth_client.patch("/api/me", json={"date_of_birth": old_date})
        assert response.status_code == 400
        assert "10" in response.json()["detail"] and "100" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_weight_kg_rejects_zero(self, auth_client):
        """PATCH /me rejects weight_kg of 0."""
        response = await auth_client.patch("/api/me", json={"weight_kg": 0})
        assert response.status_code == 400
        assert "positive" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_weight_kg_rejects_negative(self, auth_client):
        """PATCH /me rejects negative weight_kg."""
        response = await auth_client.patch("/api/me", json={"weight_kg": -70})
        assert response.status_code == 400
        assert "positive" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_weight_kg_rejects_unrealistic_value(self, auth_client):
        """PATCH /me rejects weight_kg > 500."""
        response = await auth_client.patch("/api/me", json={"weight_kg": 600})
        assert response.status_code == 400
        assert "500" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_profile_fields_persist(self, auth_client):
        """Profile fields persist across requests."""
        # Set values
        response = await auth_client.patch(
            "/api/me", json={"date_of_birth": "1992-03-20", "weight_kg": 68.5}
        )
        assert response.status_code == 200

        # Verify they persist
        response = await auth_client.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["date_of_birth"] == "1992-03-20"
        assert data["weight_kg"] == 68.5

    @pytest.mark.asyncio
    async def test_profile_update_requires_auth(self, app_client):
        """PATCH /me requires authentication."""
        response = await app_client.patch("/api/me", json={"weight_kg": 70})
        assert response.status_code == 401



class TestThresholdHistory:
    """Tests for threshold management (FTP, LTHR, HRmax)."""

    @pytest.mark.asyncio
    async def test_get_thresholds_empty_when_no_dob(self, auth_client):
        """GET /me/thresholds returns empty list when user has no DOB (no defaults created)."""
        response = await auth_client.get("/api/me/thresholds")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_thresholds_creates_defaults_when_dob_set(self, auth_client):
        """GET /me/thresholds auto-creates defaults when user has DOB."""
        # First set DOB
        await auth_client.patch("/api/me", json={"date_of_birth": "1990-01-01"})
        
        response = await auth_client.get("/api/me/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        
        # Check defaults match Tanaka formula: HRmax = 208 - 0.7 * age
        # Age ~36 (in 2026), HRmax ~183, LTHR ~170
        threshold = data[0]
        assert "id" in threshold
        assert "effective_date" in threshold
        assert threshold["ftp_watts"] == 200  # Default when no weight
        assert 160 <= threshold["hrmax_bpm"] <= 190  # Age-based range
        assert threshold["lthr_bpm"] < threshold["hrmax_bpm"]

    @pytest.mark.asyncio
    async def test_get_thresholds_uses_weight_for_ftp_default(self, auth_client):
        """Default FTP is weight_kg * 2.5 when weight is set."""
        # Set DOB and weight
        await auth_client.patch("/api/me", json={"date_of_birth": "1990-01-01", "weight_kg": 80})
        
        response = await auth_client.get("/api/me/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["ftp_watts"] == 200  # 80 * 2.5 = 200

    @pytest.mark.asyncio
    async def test_create_threshold(self, auth_client):
        """POST /me/thresholds creates a new threshold entry."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 280, "lthr_bpm": 165, "hrmax_bpm": 185}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ftp_watts"] == 280
        assert data["lthr_bpm"] == 165
        assert data["hrmax_bpm"] == 185
        assert "effective_date" in data
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_threshold_with_effective_date(self, auth_client):
        """POST /me/thresholds accepts custom effective_date."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2025-06-01",
                "ftp_watts": 290,
                "lthr_bpm": 168,
                "hrmax_bpm": 188
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["effective_date"] == "2025-06-01"
        assert data["ftp_watts"] == 290

    @pytest.mark.asyncio
    async def test_get_thresholds_returns_most_recent_first(self, auth_client):
        """GET /me/thresholds returns entries sorted by effective_date desc."""
        # Create multiple thresholds
        await auth_client.post(
            "/api/me/thresholds",
            json={"effective_date": "2025-01-01", "ftp_watts": 250, "lthr_bpm": 160, "hrmax_bpm": 180}
        )
        await auth_client.post(
            "/api/me/thresholds",
            json={"effective_date": "2025-06-01", "ftp_watts": 270, "lthr_bpm": 165, "hrmax_bpm": 185}
        )
        await auth_client.post(
            "/api/me/thresholds",
            json={"effective_date": "2025-03-01", "ftp_watts": 260, "lthr_bpm": 162, "hrmax_bpm": 182}
        )
        
        response = await auth_client.get("/api/me/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Should be sorted desc by effective_date
        assert data[0]["effective_date"] == "2025-06-01"
        assert data[1]["effective_date"] == "2025-03-01"
        assert data[2]["effective_date"] == "2025-01-01"

    @pytest.mark.asyncio
    async def test_create_threshold_rejects_zero_ftp(self, auth_client):
        """POST /me/thresholds rejects ftp_watts <= 0."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 0, "lthr_bpm": 160, "hrmax_bpm": 180}
        )
        assert response.status_code == 400
        assert "ftp_watts" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_threshold_rejects_unrealistic_ftp(self, auth_client):
        """POST /me/thresholds rejects ftp_watts > 2000."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 2500, "lthr_bpm": 160, "hrmax_bpm": 180}
        )
        assert response.status_code == 400
        assert "2000" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_threshold_rejects_zero_lthr(self, auth_client):
        """POST /me/thresholds rejects lthr_bpm <= 0."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 250, "lthr_bpm": 0, "hrmax_bpm": 180}
        )
        assert response.status_code == 400
        assert "lthr_bpm" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_threshold_rejects_unrealistic_hrmax(self, auth_client):
        """POST /me/thresholds rejects hrmax_bpm > 250."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 250, "lthr_bpm": 160, "hrmax_bpm": 300}
        )
        assert response.status_code == 400
        assert "250" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_threshold_rejects_lthr_exceeding_hrmax(self, auth_client):
        """POST /me/thresholds rejects lthr_bpm > hrmax_bpm."""
        response = await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 250, "lthr_bpm": 190, "hrmax_bpm": 180}
        )
        assert response.status_code == 400
        assert "exceed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_threshold_endpoints_require_auth(self, app_client):
        """Threshold endpoints require authentication."""
        response = await app_client.get("/api/me/thresholds")
        assert response.status_code == 401

        response = await app_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 250, "lthr_bpm": 160, "hrmax_bpm": 180}
        )
        assert response.status_code == 401



class TestZones:
    """Tests for power and HR zone management."""

    @pytest.mark.asyncio
    async def test_get_zones_empty_when_no_thresholds(self, auth_client):
        """GET /me/zones returns empty lists when user has no thresholds."""
        response = await auth_client.get("/api/me/zones")
        assert response.status_code == 200
        data = response.json()
        assert data["power_zones"] == []
        assert data["hr_zones"] == []

    @pytest.mark.asyncio
    async def test_get_zones_creates_defaults_from_thresholds(self, auth_client):
        """GET /me/zones auto-creates default zones when thresholds exist."""
        # First set DOB to trigger default thresholds
        await auth_client.patch("/api/me", json={"date_of_birth": "1990-01-01"})
        # Fetch thresholds to trigger creation
        await auth_client.get("/api/me/thresholds")
        
        response = await auth_client.get("/api/me/zones")
        assert response.status_code == 200
        data = response.json()
        
        # Should have 7 power zones (Coggan)
        assert len(data["power_zones"]) == 7
        assert data["power_zones"][0]["zone_number"] == 1
        assert data["power_zones"][0]["name"] == "Recovery"
        assert data["power_zones"][6]["zone_number"] == 7
        assert data["power_zones"][6]["name"] == "Neuromuscular"
        
        # Should have 5 HR zones (Friel)
        assert len(data["hr_zones"]) == 5
        assert data["hr_zones"][0]["zone_number"] == 1
        assert data["hr_zones"][4]["zone_number"] == 5

    @pytest.mark.asyncio
    async def test_zones_calculated_from_ftp(self, auth_client):
        """Power zones are calculated as percentages of FTP."""
        # Create explicit threshold with known FTP
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        
        response = await auth_client.get("/api/me/zones")
        assert response.status_code == 200
        data = response.json()
        
        # Zone 1 Recovery: 0-55% of 200 = 0-110W
        assert data["power_zones"][0]["min_watts"] == 0
        assert data["power_zones"][0]["max_watts"] == 110
        
        # Zone 4 Threshold: 90-105% of 200 = 180-210W
        assert data["power_zones"][3]["min_watts"] == 180
        assert data["power_zones"][3]["max_watts"] == 210
        
        # Zone 7 Neuromuscular: 150%+ = 300W+, no upper limit
        assert data["power_zones"][6]["min_watts"] == 300
        assert data["power_zones"][6]["max_watts"] is None

    @pytest.mark.asyncio
    async def test_hr_zones_calculated_from_lthr(self, auth_client):
        """HR zones are calculated as percentages of LTHR."""
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        
        response = await auth_client.get("/api/me/zones")
        assert response.status_code == 200
        data = response.json()
        
        # Zone 1: 0-81% of 170 = 0-137 bpm
        assert data["hr_zones"][0]["min_bpm"] == 0
        assert data["hr_zones"][0]["max_bpm"] == 137
        
        # Zone 5: 100%+ = 170+ bpm, no upper limit
        assert data["hr_zones"][4]["min_bpm"] == 170
        assert data["hr_zones"][4]["max_bpm"] is None

    @pytest.mark.asyncio
    async def test_update_zone_marks_as_custom(self, auth_client):
        """PUT /me/zones with zone updates marks zones as custom."""
        # Create thresholds and zones
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        await auth_client.get("/api/me/zones")  # Trigger zone creation
        
        # Update a power zone
        response = await auth_client.put(
            "/api/me/zones",
            json={
                "power_zones": [
                    {"zone_number": 4, "name": "Sweet Spot", "min_value": 175, "max_value": 195}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Zone 4 should be updated and marked custom
        zone4 = next(z for z in data["power_zones"] if z["zone_number"] == 4)
        assert zone4["name"] == "Sweet Spot"
        assert zone4["min_watts"] == 175
        assert zone4["max_watts"] == 195
        assert zone4["is_custom"] is True

    @pytest.mark.asyncio
    async def test_reset_zones_to_defaults(self, auth_client):
        """PUT /me/zones with reset_to_defaults recalculates from thresholds."""
        # Create thresholds and zones
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        await auth_client.get("/api/me/zones")
        
        # Customize a zone
        await auth_client.put(
            "/api/me/zones",
            json={"power_zones": [{"zone_number": 4, "name": "Custom Zone"}]}
        )
        
        # Reset to defaults
        response = await auth_client.put(
            "/api/me/zones",
            json={"reset_to_defaults": True}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Zone 4 should be back to default name and not custom
        zone4 = next(z for z in data["power_zones"] if z["zone_number"] == 4)
        assert zone4["name"] == "Threshold"
        assert zone4["is_custom"] is False

    @pytest.mark.asyncio
    async def test_new_threshold_regenerates_non_custom_zones(self, auth_client):
        """Creating a new threshold regenerates zones that aren't custom."""
        # Create initial thresholds and zones
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        response = await auth_client.get("/api/me/zones")
        initial_zone4 = next(z for z in response.json()["power_zones"] if z["zone_number"] == 4)
        assert initial_zone4["max_watts"] == 210  # 105% of 200
        
        # Create new threshold with higher FTP
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 250, "lthr_bpm": 175, "hrmax_bpm": 190}
        )
        
        # Zones should be regenerated
        response = await auth_client.get("/api/me/zones")
        new_zone4 = next(z for z in response.json()["power_zones"] if z["zone_number"] == 4)
        assert new_zone4["max_watts"] == 262  # 105% of 250

    @pytest.mark.asyncio
    async def test_new_threshold_preserves_custom_zones(self, auth_client):
        """Creating a new threshold preserves zones marked as custom."""
        # Create initial thresholds and zones
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        await auth_client.get("/api/me/zones")
        
        # Customize a zone
        await auth_client.put(
            "/api/me/zones",
            json={"power_zones": [{"zone_number": 4, "name": "My Custom Zone"}]}
        )
        
        # Create new threshold
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 250, "lthr_bpm": 175, "hrmax_bpm": 190}
        )
        
        # Custom zone should be preserved
        response = await auth_client.get("/api/me/zones")
        zone4 = next(z for z in response.json()["power_zones"] if z["zone_number"] == 4)
        assert zone4["name"] == "My Custom Zone"
        assert zone4["is_custom"] is True

    @pytest.mark.asyncio
    async def test_update_nonexistent_zone_returns_error(self, auth_client):
        """PUT /me/zones with invalid zone_number returns error."""
        await auth_client.post(
            "/api/me/thresholds",
            json={"ftp_watts": 200, "lthr_bpm": 170, "hrmax_bpm": 185}
        )
        await auth_client.get("/api/me/zones")
        
        response = await auth_client.put(
            "/api/me/zones",
            json={"power_zones": [{"zone_number": 99, "name": "Invalid"}]}
        )
        assert response.status_code == 400
        assert "99" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_zones_endpoints_require_auth(self, app_client):
        """Zone endpoints require authentication."""
        response = await app_client.get("/api/me/zones")
        assert response.status_code == 401

        response = await app_client.put("/api/me/zones", json={"reset_to_defaults": True})
        assert response.status_code == 401
