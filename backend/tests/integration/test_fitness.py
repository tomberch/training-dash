"""Integration tests for fitness model and breakthrough detection (#20)."""
import sys
from pathlib import Path
from uuid import UUID as UUIDType

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from trainingdash.models import Activity, FitnessHistory  # noqa: E402


class TestBreakthroughDetection:
    """Tests for breakthrough detection during ingest."""

    @pytest.mark.asyncio
    async def test_first_activity_is_breakthrough(self, auth_client, db_session):
        """First activity with power data is always a breakthrough (sets initial PRs)."""
        # Upload first FIT file
        fit_data = make_test_fit(num_records=120)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = UUIDType(response.json()["id"])
        
        # Check activity is marked as breakthrough
        result = await db_session.execute(
            select(Activity).where(Activity.id == activity_id)
        )
        activity = result.scalar_one()
        assert activity.is_breakthrough is True

    @pytest.mark.asyncio
    async def test_second_activity_not_breakthrough_if_no_pr(self, auth_client, db_session):
        """Second activity is NOT a breakthrough if it doesn't set any PRs."""
        # Upload first FIT file (sets initial PRs)
        fit_data1 = make_test_fit(num_records=120)
        await auth_client.post(
            "/api/upload",
            files={"file": ("first.fit", fit_data1, "application/octet-stream")},
        )
        
        # Upload second FIT with same power pattern (no new PRs)
        fit_data2 = make_test_fit(num_records=120)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("second.fit", fit_data2, "application/octet-stream")},
        )
        activity_id = UUIDType(response.json()["id"])
        
        # Check second activity is NOT a breakthrough
        result = await db_session.execute(
            select(Activity).where(Activity.id == activity_id)
        )
        activity = result.scalar_one()
        assert activity.is_breakthrough is False

    @pytest.mark.asyncio
    async def test_activity_summary_includes_is_breakthrough(self, auth_client):
        """Activity list includes is_breakthrough field."""
        # Upload a FIT file
        fit_data = make_test_fit(num_records=120)
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        # Get activity list
        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        data = response.json()
        activities = data["activities"]
        
        assert len(activities) >= 1
        assert "is_breakthrough" in activities[0]

    @pytest.mark.asyncio
    async def test_activity_detail_includes_is_breakthrough(self, auth_client):
        """Activity detail includes is_breakthrough field."""
        # Upload a FIT file
        fit_data = make_test_fit(num_records=120)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        
        # Get activity detail
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "is_breakthrough" in data
        assert data["is_breakthrough"] is True  # First activity is breakthrough


class TestFitnessModel:
    """Tests for fitness model computation and API."""

    @pytest.mark.asyncio
    async def test_fitness_empty_without_activities(self, auth_client):
        """GET /fitness returns empty when no activities."""
        response = await auth_client.get("/api/fitness")
        assert response.status_code == 200
        data = response.json()
        
        assert data["current"] is None
        assert data["history"] == []

    @pytest.mark.asyncio
    async def test_fitness_computed_after_breakthrough(self, auth_client, db_session):
        """Fitness model is computed after a breakthrough activity."""
        # Upload a FIT file (breakthrough)
        fit_data = make_test_fit(num_records=120)
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        # Check fitness was computed
        response = await auth_client.get("/api/fitness")
        assert response.status_code == 200
        data = response.json()
        
        assert data["current"] is not None
        assert "pp_watts" in data["current"]
        assert "w_prime_joules" in data["current"]
        assert "cp_watts" in data["current"]
        assert "computed_at" in data["current"]
        
        # Values should be positive
        assert data["current"]["pp_watts"] > 0
        assert data["current"]["w_prime_joules"] > 0
        assert data["current"]["cp_watts"] > 0

    @pytest.mark.asyncio
    async def test_fitness_history_populated(self, auth_client, db_session):
        """Fitness history is populated after breakthrough."""
        # Upload a FIT file
        fit_data = make_test_fit(num_records=120)
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        response = await auth_client.get("/api/fitness")
        data = response.json()
        
        assert len(data["history"]) >= 1
        assert data["history"][0]["pp_watts"] == data["current"]["pp_watts"]

    @pytest.mark.asyncio
    async def test_fitness_model_values_reasonable(self, auth_client):
        """Fitness model values are in reasonable ranges."""
        # Upload FIT with power ranging 200-279W (200 + i % 80)
        fit_data = make_test_fit(num_records=300)  # 5 minutes of data
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        response = await auth_client.get("/api/fitness")
        data = response.json()
        
        # PP should be highest peak (around 279W for test data)
        assert 200 <= data["current"]["pp_watts"] <= 350
        
        # CP should be lower than PP
        assert data["current"]["cp_watts"] < data["current"]["pp_watts"]
        
        # W' should be in reasonable range (5-40 kJ)
        assert 5000 <= data["current"]["w_prime_joules"] <= 40000

    @pytest.mark.asyncio
    async def test_fitness_requires_auth(self, app_client):
        """GET /fitness requires authentication."""
        response = await app_client.get("/api/fitness")
        assert response.status_code == 401


class TestFitnessModelUnit:
    """Unit tests for fitness model computation functions."""

    def test_detect_breakthrough_first_activity(self):
        """First activity is always a breakthrough."""
        from trainingdash.fitness import detect_breakthrough
        
        activity_peaks = {5: 400, 60: 350, 300: 280, 1200: 250}
        all_time_bests = {}  # No previous data
        
        assert detect_breakthrough(activity_peaks, all_time_bests) is True

    def test_detect_breakthrough_new_pr(self):
        """Activity with new PR at key duration is breakthrough."""
        from trainingdash.fitness import detect_breakthrough
        
        activity_peaks = {5: 450, 60: 350, 300: 280, 1200: 250}  # 5s PR
        all_time_bests = {5: 400, 60: 360, 300: 290, 1200: 260}
        
        assert detect_breakthrough(activity_peaks, all_time_bests) is True

    def test_detect_breakthrough_no_pr(self):
        """Activity without PRs at key durations is not breakthrough."""
        from trainingdash.fitness import detect_breakthrough
        
        activity_peaks = {5: 380, 60: 340, 300: 270, 1200: 240}  # All below best
        all_time_bests = {5: 400, 60: 360, 300: 290, 1200: 260}
        
        assert detect_breakthrough(activity_peaks, all_time_bests) is False

    def test_fit_cp_model_insufficient_data(self):
        """Model returns None with insufficient data."""
        from trainingdash.fitness import fit_cp_model
        
        # Less than 3 points
        result = fit_cp_model([{5: 400, 60: 350}])
        assert result is None

    def test_fit_cp_model_basic(self):
        """Model fits with sufficient data."""
        from trainingdash.fitness import fit_cp_model
        
        peak_powers = [
            {1: 800, 5: 600, 60: 400, 300: 320, 1200: 280},
        ]
        
        result = fit_cp_model(peak_powers)
        
        assert result is not None
        assert "pp_watts" in result
        assert "w_prime_joules" in result
        assert "cp_watts" in result
        assert result["pp_watts"] >= result["cp_watts"]

    def test_decay_weight(self):
        """Decay weight is higher for recent activities."""
        from datetime import datetime, timedelta
        from trainingdash.fitness import compute_decay_weight
        
        reference = datetime(2024, 6, 1)
        recent = datetime(2024, 5, 25)  # 7 days ago
        old = datetime(2024, 3, 1)  # 92 days ago
        
        recent_weight = compute_decay_weight(recent, reference)
        old_weight = compute_decay_weight(old, reference)
        
        assert recent_weight > old_weight
        assert 0 < old_weight < recent_weight <= 1

    def test_get_all_time_bests(self):
        """Get all-time bests aggregates across activities."""
        from trainingdash.fitness import get_all_time_bests
        
        peak_powers = [
            {5: 400, 60: 350},
            {5: 420, 60: 340},  # Higher 5s
            {5: 380, 60: 360},  # Higher 60s
        ]
        
        bests = get_all_time_bests(peak_powers)
        
        assert bests[5] == 420
        assert bests[60] == 360
