"""Unit tests for garmin.py with mocked HTTP responses.

Tests cover:
- Authentication flow (login success, MFA required, invalid credentials)
- MFA completion (success, invalid code, no MFA in progress)
- Activity listing (parsing responses, empty list, date filtering)
- FIT download (ZIP extraction, missing FIT file, errors)
"""

import io
import zipfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from trainingdash.integrations.garmin import (
    GarminActivity,
    GarminAPIError,
    GarminClient,
    GarminMFARequired,
)


class TestGarminLogin:
    """Tests for GarminClient.login()."""

    def test_login_success_returns_true(self):
        """Successful login without MFA returns True."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            result = client.login("user@example.com", "password123")

            assert result is True
            mock_garmin.assert_called_once()
            mock_instance.login.assert_called_once()

    def test_login_mfa_required_raises_exception(self):
        """Login requiring MFA raises GarminMFARequired."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance
            # Simulate MFA callback being triggered
            mock_instance.login.side_effect = lambda: client._mfa_callback()

            with pytest.raises(GarminMFARequired, match="MFA code required"):
                client.login("user@example.com", "password123")

            assert client._awaiting_mfa is True

    def test_login_invalid_credentials_raises_api_error(self):
        """Invalid credentials raise GarminAPIError with clear message."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance
            mock_instance.login.side_effect = Exception("Invalid credentials provided")

            with pytest.raises(GarminAPIError, match="Invalid Garmin credentials"):
                client.login("user@example.com", "wrongpassword")

    def test_login_generic_error_raises_api_error(self):
        """Other login errors raise GarminAPIError with details."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance
            mock_instance.login.side_effect = Exception("Network timeout")

            with pytest.raises(GarminAPIError, match="Garmin login failed"):
                client.login("user@example.com", "password123")

    def test_login_mfa_error_message_triggers_mfa_required(self):
        """Error messages containing 'mfa' trigger MFA flow."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance
            mock_instance.login.side_effect = Exception("MFA verification required")

            with pytest.raises(GarminMFARequired):
                client.login("user@example.com", "password123")

            assert client._awaiting_mfa is True


class TestGarminMFA:
    """Tests for GarminClient.complete_mfa()."""

    def test_complete_mfa_success(self):
        """Valid MFA code completes authentication."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            # First login triggers MFA
            mock_instance.login.side_effect = lambda: client._mfa_callback()
            with pytest.raises(GarminMFARequired):
                client.login("user@example.com", "password123")

            # Reset mock for MFA completion
            mock_instance.login.side_effect = None

            # Complete MFA
            client.complete_mfa("123456")

            assert client._awaiting_mfa is False
            assert client._mfa_code == "123456"

    def test_complete_mfa_invalid_code_raises_error(self):
        """Invalid MFA code raises GarminAPIError."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            # First login triggers MFA
            mock_instance.login.side_effect = lambda: client._mfa_callback()
            with pytest.raises(GarminMFARequired):
                client.login("user@example.com", "password123")

            # MFA completion fails with invalid code error
            mock_instance.login.side_effect = Exception("Invalid MFA code")

            with pytest.raises(GarminAPIError, match="Invalid MFA code"):
                client.complete_mfa("000000")

    def test_complete_mfa_without_login_raises_error(self):
        """Calling complete_mfa without login raises GarminAPIError."""
        client = GarminClient()

        with pytest.raises(GarminAPIError, match="No MFA in progress"):
            client.complete_mfa("123456")

    def test_complete_mfa_when_not_awaiting_raises_error(self):
        """Calling complete_mfa after successful login raises error."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            # Successful login (no MFA)
            client.login("user@example.com", "password123")

            with pytest.raises(GarminAPIError, match="No MFA in progress"):
                client.complete_mfa("123456")


class TestGarminListActivities:
    """Tests for GarminClient.list_activities()."""

    def test_list_activities_parses_response(self):
        """Activities are parsed correctly from API response."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            # Login first
            client.login("user@example.com", "password123")

            # Mock activity response
            mock_instance.get_activities_by_date.return_value = [
                {
                    "activityId": 12345678,
                    "activityName": "Morning Ride",
                    "startTimeLocal": "2024-03-15 07:30:00",
                    "activityType": {"typeKey": "cycling"},
                    "distance": 42500.0,
                    "duration": 5400.0,
                },
                {
                    "activityId": 12345679,
                    "activityName": "Evening Run",
                    "startTimeLocal": "2024-03-15 18:00:00",
                    "activityType": {"typeKey": "running"},
                    "distance": 10000.0,
                    "duration": 3600.0,
                },
            ]

            start = datetime(2024, 3, 1)
            end = datetime(2024, 3, 31)
            activities = client.list_activities(start, end)

            assert len(activities) == 2

            assert activities[0].id == "12345678"
            assert activities[0].name == "Morning Ride"
            assert activities[0].started_at == datetime(2024, 3, 15, 7, 30, 0)
            assert activities[0].activity_type == "cycling"
            assert activities[0].distance_m == 42500.0
            assert activities[0].duration_s == 5400.0

            assert activities[1].id == "12345679"
            assert activities[1].name == "Evening Run"

            # Verify date format passed to API
            mock_instance.get_activities_by_date.assert_called_once_with("2024-03-01", "2024-03-31")

    def test_list_activities_empty_list(self):
        """Empty activity list is handled correctly."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")
            mock_instance.get_activities_by_date.return_value = []

            activities = client.list_activities(datetime(2024, 1, 1), datetime(2024, 1, 31))

            assert activities == []

    def test_list_activities_handles_missing_fields(self):
        """Activities with missing optional fields are handled gracefully."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")

            # Response with minimal/missing fields
            mock_instance.get_activities_by_date.return_value = [
                {
                    "activityId": 999,
                    # Missing activityName, startTimeLocal, activityType, distance, duration
                },
            ]

            activities = client.list_activities(datetime(2024, 1, 1), datetime(2024, 1, 31))

            assert len(activities) == 1
            assert activities[0].id == "999"
            assert activities[0].name == ""
            assert activities[0].activity_type == ""
            assert activities[0].distance_m == 0
            assert activities[0].duration_s == 0

    def test_list_activities_handles_null_distance(self):
        """Null distance values are converted to 0."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")

            mock_instance.get_activities_by_date.return_value = [
                {
                    "activityId": 123,
                    "distance": None,
                    "duration": None,
                },
            ]

            activities = client.list_activities(datetime(2024, 1, 1), datetime(2024, 1, 31))

            assert activities[0].distance_m == 0
            assert activities[0].duration_s == 0

    def test_list_activities_not_authenticated_raises_error(self):
        """Calling list_activities without login raises error."""
        client = GarminClient()

        with pytest.raises(GarminAPIError, match="Not authenticated"):
            client.list_activities(datetime(2024, 1, 1), datetime(2024, 1, 31))

    def test_list_activities_api_error(self):
        """API errors are wrapped in GarminAPIError."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")
            mock_instance.get_activities_by_date.side_effect = Exception("Rate limited")

            with pytest.raises(GarminAPIError, match="Failed to list activities"):
                client.list_activities(datetime(2024, 1, 1), datetime(2024, 1, 31))


class TestGarminDownloadFit:
    """Tests for GarminClient.download_fit()."""

    def _create_fit_zip(self, fit_content: bytes, filename: str = "activity.fit") -> bytes:
        """Helper to create a ZIP file containing a FIT file."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr(filename, fit_content)
        return buffer.getvalue()

    def test_download_fit_extracts_from_zip(self):
        """FIT file is correctly extracted from downloaded ZIP."""
        client = GarminClient()
        fit_content = b"\x0e\x10\x00\x00.FIT file content..."

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")

            # Mock download returning ZIP with FIT file
            mock_instance.download_activity.return_value = self._create_fit_zip(fit_content, "12345678.fit")

            result = client.download_fit("12345678")

            assert result == fit_content
            mock_instance.download_activity.assert_called_once_with(
                "12345678",
                dl_fmt=mock_instance.ActivityDownloadFormat.ORIGINAL,
            )

    def test_download_fit_handles_uppercase_extension(self):
        """FIT files with .FIT extension are found."""
        client = GarminClient()
        fit_content = b"FIT data"

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")
            mock_instance.download_activity.return_value = self._create_fit_zip(fit_content, "ACTIVITY.FIT")

            result = client.download_fit("12345678")

            assert result == fit_content

    def test_download_fit_no_fit_in_zip_raises_error(self):
        """ZIP without FIT file raises GarminAPIError."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")

            # ZIP with non-FIT file
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as zf:
                zf.writestr("activity.gpx", b"GPX content")
            mock_instance.download_activity.return_value = buffer.getvalue()

            with pytest.raises(GarminAPIError, match="No FIT file found"):
                client.download_fit("12345678")

    def test_download_fit_not_authenticated_raises_error(self):
        """Calling download_fit without login raises error."""
        client = GarminClient()

        with pytest.raises(GarminAPIError, match="Not authenticated"):
            client.download_fit("12345678")

    def test_download_fit_api_error(self):
        """Download errors are wrapped in GarminAPIError."""
        client = GarminClient()

        with patch("trainingdash.integrations.garmin.client.Garmin") as mock_garmin:
            mock_instance = MagicMock()
            mock_garmin.return_value = mock_instance

            client.login("user@example.com", "password123")
            mock_instance.download_activity.side_effect = Exception("Activity not found")

            with pytest.raises(GarminAPIError, match="Failed to download FIT"):
                client.download_fit("99999999")


class TestGarminClientFactory:
    """Tests for client factory functions."""

    def test_get_garmin_client_returns_instance(self):
        """get_garmin_client returns a GarminClient instance."""
        from trainingdash.integrations.garmin import get_garmin_client

        client = get_garmin_client()
        assert isinstance(client, GarminClient)

    def test_set_garmin_client_factory_replaces_default(self):
        """set_garmin_client_factory allows injecting mock client."""
        from trainingdash.integrations.garmin import (
            get_garmin_client,
            set_garmin_client_factory,
        )

        class MockGarminClient:
            pass

        original_factory = GarminClient

        try:
            set_garmin_client_factory(MockGarminClient)
            client = get_garmin_client()
            assert isinstance(client, MockGarminClient)
        finally:
            # Restore original
            set_garmin_client_factory(original_factory)


class TestGarminActivity:
    """Tests for GarminActivity dataclass."""

    def test_garmin_activity_fields(self):
        """GarminActivity stores all fields correctly."""
        activity = GarminActivity(
            id="12345",
            name="Test Ride",
            started_at=datetime(2024, 3, 15, 10, 30),
            activity_type="cycling",
            distance_m=50000.0,
            duration_s=7200.0,
        )

        assert activity.id == "12345"
        assert activity.name == "Test Ride"
        assert activity.started_at == datetime(2024, 3, 15, 10, 30)
        assert activity.activity_type == "cycling"
        assert activity.distance_m == 50000.0
        assert activity.duration_s == 7200.0
