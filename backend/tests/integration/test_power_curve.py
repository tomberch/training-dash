"""Integration tests for power curve endpoint (#22)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit

# Pre-generate FIT bytes once per module (FitFileBuilder is expensive)
FIT_120 = make_test_fit(num_records=120)
FIT_300 = make_test_fit(num_records=300)


class TestPowerCurveEndpoint:
    """Tests for GET /power-curve endpoint."""

    @pytest.mark.asyncio
    async def test_power_curve_empty_without_activities(self, auth_client):
        """GET /power-curve returns empty array when no activities."""
        response = await auth_client.get("/api/power-curve")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_power_curve_with_activity(self, auth_client):
        """GET /power-curve returns curve data after upload."""
        # Upload a FIT file with power data
        fit_data = FIT_120  # 2 minutes
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        response = await auth_client.get("/api/power-curve")
        assert response.status_code == 200
        data = response.json()

        # Should have peaks for durations up to 120s
        assert len(data) >= 6  # 1, 5, 10, 30, 60, 120s

        # Check structure
        for point in data:
            assert "duration_seconds" in point
            assert "watts" in point
            assert "achieved_date" in point
            assert "days_ago" in point

    @pytest.mark.asyncio
    async def test_power_curve_sorted_by_duration(self, auth_client):
        """Power curve is sorted by duration."""
        fit_data = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        response = await auth_client.get("/api/power-curve")
        data = response.json()

        durations = [p["duration_seconds"] for p in data]
        assert durations == sorted(durations)

    @pytest.mark.asyncio
    async def test_power_curve_with_date_range(self, auth_client):
        """Power curve respects date range params."""
        # Upload a FIT file (test FIT date is 2024-03-15)
        fit_data = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        # Query with range that includes the activity
        response = await auth_client.get("/api/power-curve?start=2024-01-01&end=2024-12-31")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 6

        # Query with range that excludes the activity
        response = await auth_client.get("/api/power-curve?start=2025-01-01&end=2025-12-31")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_power_curve_achieved_date_correct(self, auth_client):
        """Achieved date matches activity date."""
        # Upload a FIT file (test FIT date is 2024-03-15)
        fit_data = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        response = await auth_client.get("/api/power-curve")
        data = response.json()

        # All peaks should be from 2024-03-15
        for point in data:
            assert point["achieved_date"] == "2024-03-15"

    @pytest.mark.asyncio
    async def test_power_curve_days_ago_positive(self, auth_client):
        """Days ago is positive for past activities."""
        # Upload a FIT file from 2024-03-15
        fit_data = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        response = await auth_client.get("/api/power-curve")
        data = response.json()

        # Activity from 2024 should have positive days_ago
        for point in data:
            assert point["days_ago"] > 0

    @pytest.mark.asyncio
    async def test_power_curve_picks_best_across_activities(self, auth_client, db_session):
        """Power curve picks best watts across multiple activities."""
        # Upload first activity
        fit_data1 = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("first.fit", fit_data1, "application/octet-stream")},
        )

        # Upload second activity with same power pattern
        fit_data2 = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("second.fit", fit_data2, "application/octet-stream")},
        )

        # Get curve - should have same values (picks best, which is same)
        response = await auth_client.get("/api/power-curve")
        data = response.json()

        # Both activities have same power, so we should have data
        assert len(data) >= 6

        # Check we only get one entry per duration (best)
        durations = [p["duration_seconds"] for p in data]
        assert len(durations) == len(set(durations))  # No duplicates

    @pytest.mark.asyncio
    async def test_power_curve_requires_auth(self, app_client):
        """GET /power-curve requires authentication."""
        response = await app_client.get("/api/power-curve")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_power_curve_watts_positive(self, auth_client):
        """All power values are positive."""
        fit_data = FIT_120
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        response = await auth_client.get("/api/power-curve")
        data = response.json()

        for point in data:
            assert point["watts"] > 0

    @pytest.mark.asyncio
    async def test_power_curve_shorter_durations_higher_power(self, auth_client):
        """Generally, shorter durations have higher power."""
        fit_data = FIT_300  # 5 minutes
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )

        response = await auth_client.get("/api/power-curve")
        data = response.json()

        # Find 1s and 300s peaks
        peak_1s = next((p for p in data if p["duration_seconds"] == 1), None)
        peak_300s = next((p for p in data if p["duration_seconds"] == 300), None)

        if peak_1s and peak_300s:
            # 1s peak should be >= 5min peak
            assert peak_1s["watts"] >= peak_300s["watts"]
