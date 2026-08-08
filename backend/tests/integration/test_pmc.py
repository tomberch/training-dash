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
