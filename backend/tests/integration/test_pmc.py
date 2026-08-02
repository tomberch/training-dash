"""Integration tests for PMC endpoint (#21)."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from trainingdash.models import Activity  # noqa: E402


class TestPMCEndpoint:
    """Tests for GET /pmc endpoint."""

    @pytest.mark.asyncio
    async def test_pmc_empty_without_activities(self, auth_client):
        """GET /pmc returns zeros when no activities."""
        response = await auth_client.get("/api/pmc")
        assert response.status_code == 200
        data = response.json()
        
        # Should return data (empty activities = all zeros)
        assert isinstance(data, list)
        # Default is 12 weeks = 84 days
        assert len(data) == 84 or len(data) == 85  # May include today
        
        # All values should be 0 when no activities
        for day in data:
            assert day["ctl"] == 0.0
            assert day["atl"] == 0.0
            assert day["tsb"] == 0.0

    @pytest.mark.asyncio
    async def test_pmc_with_date_range(self, auth_client):
        """GET /pmc respects start/end date params."""
        start = date.today() - timedelta(days=7)
        end = date.today()
        
        response = await auth_client.get(
            f"/api/pmc?start={start.isoformat()}&end={end.isoformat()}"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return exactly 8 days (start to end inclusive)
        assert len(data) == 8
        
        # Check dates are correct
        assert data[0]["date"] == start.isoformat()
        assert data[-1]["date"] == end.isoformat()

    @pytest.mark.asyncio
    async def test_pmc_includes_date_ctl_atl_tsb(self, auth_client):
        """PMC response includes all required fields."""
        response = await auth_client.get("/api/pmc")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) > 0
        day = data[0]
        assert "date" in day
        assert "ctl" in day
        assert "atl" in day
        assert "tsb" in day

    @pytest.mark.asyncio
    async def test_pmc_with_activity_tss(self, auth_client, db_session):
        """PMC reflects TSS from activities."""
        # First set up threshold to enable TSS computation
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 250,
                "lthr_bpm": 165,
                "hrmax_bpm": 185
            }
        )
        
        # Upload a FIT file (will compute TSS)
        fit_data = make_test_fit(num_records=120)
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        # Get PMC - the activity date is 2024-03-15 (from test FIT)
        response = await auth_client.get(
            "/api/pmc?start=2024-03-01&end=2024-03-31"
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find the day of the activity (March 15)
        day_of_activity = next(
            (d for d in data if d["date"] == "2024-03-15"),
            None
        )
        
        # After the activity day, CTL and ATL should be non-zero
        # (ATL responds faster than CTL)
        days_after = [d for d in data if d["date"] > "2024-03-15"]
        if days_after:
            # ATL should be elevated shortly after
            assert any(d["atl"] > 0 for d in days_after[:3])

    @pytest.mark.asyncio
    async def test_pmc_requires_auth(self, app_client):
        """GET /pmc requires authentication."""
        response = await app_client.get("/api/pmc")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pmc_tsb_is_ctl_minus_atl(self, auth_client):
        """TSB equals CTL minus ATL."""
        response = await auth_client.get("/api/pmc")
        assert response.status_code == 200
        data = response.json()
        
        for day in data:
            expected_tsb = round(day["ctl"] - day["atl"], 1)
            assert day["tsb"] == expected_tsb


class TestPMCComputation:
    """Unit tests for PMC computation functions."""

    def test_compute_pmc_empty_tss(self):
        """PMC with no TSS data returns all zeros."""
        from trainingdash.pmc import compute_pmc
        
        start = date(2024, 1, 1)
        end = date(2024, 1, 7)
        
        result = compute_pmc({}, start, end)
        
        assert len(result) == 7
        for day in result:
            assert day["ctl"] == 0.0
            assert day["atl"] == 0.0
            assert day["tsb"] == 0.0

    def test_compute_pmc_single_activity(self):
        """PMC with single activity shows ATL spike."""
        from trainingdash.pmc import compute_pmc
        
        activity_date = date(2024, 1, 5)
        daily_tss = {activity_date: 100.0}  # 100 TSS
        
        start = date(2024, 1, 1)
        end = date(2024, 1, 14)
        
        result = compute_pmc(daily_tss, start, end)
        
        # Before activity, all zeros
        for day in result[:4]:  # Jan 1-4
            assert day["ctl"] == 0.0
            assert day["atl"] == 0.0
        
        # Day after activity, ATL should be higher than CTL
        # (ATL has 7-day constant, CTL has 42-day)
        day_after = next(d for d in result if d["date"] == "2024-01-06")
        assert day_after["atl"] > day_after["ctl"]
        assert day_after["tsb"] < 0  # Negative TSB = fatigued

    def test_compute_pmc_atl_decays_faster_than_ctl(self):
        """ATL decays faster than CTL after activity."""
        from trainingdash.pmc import compute_pmc
        
        activity_date = date(2024, 1, 1)
        daily_tss = {activity_date: 100.0}
        
        start = date(2024, 1, 1)
        end = date(2024, 1, 30)
        
        result = compute_pmc(daily_tss, start, end)
        
        # Get values at different points
        day_1 = next(d for d in result if d["date"] == "2024-01-02")
        day_7 = next(d for d in result if d["date"] == "2024-01-08")
        day_14 = next(d for d in result if d["date"] == "2024-01-15")
        
        # ATL should decay significantly by day 14
        assert day_14["atl"] < day_7["atl"] < day_1["atl"]
        
        # CTL decays slower
        ctl_decay_7_days = (day_1["ctl"] - day_7["ctl"]) / day_1["ctl"] if day_1["ctl"] > 0 else 0
        atl_decay_7_days = (day_1["atl"] - day_7["atl"]) / day_1["atl"] if day_1["atl"] > 0 else 0
        
        # ATL decays faster (higher percentage drop)
        assert atl_decay_7_days > ctl_decay_7_days

    def test_aggregate_daily_tss(self):
        """Aggregates multiple activities on same day."""
        from trainingdash.pmc import aggregate_daily_tss
        from datetime import datetime
        
        activities = [
            {"started_at": datetime(2024, 1, 5, 8, 0), "tss": 50.0},
            {"started_at": datetime(2024, 1, 5, 18, 0), "tss": 30.0},  # Same day
            {"started_at": datetime(2024, 1, 6, 8, 0), "tss": 80.0},
        ]
        
        result = aggregate_daily_tss(activities)
        
        assert result[date(2024, 1, 5)] == 80.0  # 50 + 30
        assert result[date(2024, 1, 6)] == 80.0

    def test_aggregate_daily_tss_skips_none(self):
        """Aggregation skips activities without TSS."""
        from trainingdash.pmc import aggregate_daily_tss
        from datetime import datetime
        
        activities = [
            {"started_at": datetime(2024, 1, 5, 8, 0), "tss": 50.0},
            {"started_at": datetime(2024, 1, 5, 18, 0), "tss": None},  # No TSS
            {"started_at": None, "tss": 100.0},  # No date
        ]
        
        result = aggregate_daily_tss(activities)
        
        assert result[date(2024, 1, 5)] == 50.0  # Only first activity
        assert len(result) == 1

    def test_ewma_factor(self):
        """EWMA factor is correct for time constants."""
        from trainingdash.pmc import compute_ewma_factor
        
        # 7-day: factor ≈ 0.857
        assert abs(compute_ewma_factor(7) - (1 - 1/7)) < 0.001
        
        # 42-day: factor ≈ 0.976
        assert abs(compute_ewma_factor(42) - (1 - 1/42)) < 0.001
