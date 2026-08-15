"""Integration tests for upload-to-provider feature.

Tests the endpoints:
- GET /activities/{id}/fit - download FIT file
- POST /activities/{id}/upload - upload to provider
- GET /fit/devices - list available devices
"""

import sys
from pathlib import Path
from uuid import UUID as UUIDType

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit


class TestGetFitFile:
    """Tests for GET /activities/{id}/fit endpoint."""

    @pytest.mark.asyncio
    async def test_returns_fit_file_for_valid_activity(self, auth_client):
        """Successfully returns FIT file for activity with raw_fit."""
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]

        response = await auth_client.get(f"/api/activities/{activity_id}/fit")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert len(response.content) == len(fit_data)

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_activity(self, auth_client):
        """Returns 404 for activity that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await auth_client.get(f"/api/activities/{fake_id}/fit")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, app_client):
        """Returns 401 without authentication."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await app_client.get(f"/api/activities/{fake_id}/fit")
        assert response.status_code == 401


class TestGetFitDevices:
    """Tests for GET /fit/devices endpoint."""

    @pytest.mark.asyncio
    async def test_returns_device_list(self, auth_client):
        """Returns list of available devices."""
        response = await auth_client.get("/api/fit/devices")
        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert isinstance(data["devices"], list)
        assert len(data["devices"]) > 100

    @pytest.mark.asyncio
    async def test_devices_have_expected_fields(self, auth_client):
        """Each device has id, name, and display_name."""
        response = await auth_client.get("/api/fit/devices")
        data = response.json()
        for device in data["devices"][:5]:
            assert "id" in device
            assert "name" in device
            assert "display_name" in device

    @pytest.mark.asyncio
    async def test_includes_common_garmin_devices(self, auth_client):
        """List includes common Garmin devices like Edge 840."""
        response = await auth_client.get("/api/fit/devices")
        data = response.json()
        device_ids = {d["id"] for d in data["devices"]}
        # Edge 840 = 4062
        assert 4062 in device_ids

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, app_client):
        """Returns 401 without authentication."""
        response = await app_client.get("/api/fit/devices")
        assert response.status_code == 401


class TestUploadToProvider:
    """Tests for POST /activities/{id}/upload endpoint."""

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_activity(self, auth_client):
        """Returns 404 for activity that doesn't exist."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await auth_client.post(
            f"/api/activities/{fake_id}/upload",
            json={"provider": "xert"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_missing_credentials(self, auth_client):
        """Returns 400 when provider credentials not configured."""
        # Upload an activity first
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]

        # Try to upload to Xert without credentials
        response = await auth_client.post(
            f"/api/activities/{activity_id}/upload",
            json={"provider": "xert"},
        )
        assert response.status_code == 400
        assert "credentials" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_provider(self, auth_client):
        """Returns 422 for invalid provider value."""
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]

        response = await auth_client.post(
            f"/api/activities/{activity_id}/upload",
            json={"provider": "invalid_provider"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_401_without_auth(self, app_client):
        """Returns 401 without authentication."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await app_client.post(
            f"/api/activities/{fake_id}/upload",
            json={"provider": "xert"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_device_product_id_parameter(self, auth_client):
        """Upload endpoint accepts optional device_product_id."""
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]

        # Without credentials, will still fail at 400 but validates the request schema
        response = await auth_client.post(
            f"/api/activities/{activity_id}/upload",
            json={"provider": "xert", "device_product_id": 4062},
        )
        # Should fail due to missing credentials, not schema validation
        assert response.status_code == 400
        assert "credentials" in response.json()["detail"].lower()
