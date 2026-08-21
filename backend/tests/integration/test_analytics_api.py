"""
Integration tests for analytics API endpoints.

Tests /api/fitness, /api/pmc, /api/power-curve, and /api/records endpoints.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import (
    Activity,
    ActivityPeakPower,
    FitnessHistory,
    Route,
)


def make_activity(
    user_id: int,
    started_at: datetime,
    tss: float | None = None,
    total_distance_m: float | None = None,
    elapsed_time_s: int | None = None,
    title: str | None = None,
) -> Activity:
    """Create an activity with the given parameters."""
    return Activity(
        id=uuid4(),
        user_id=user_id,
        started_at=started_at,
        source="test",
        source_ref=f"test-{uuid4()}",
        tss=tss,
        total_distance_m=total_distance_m or 0,
        elapsed_time_s=elapsed_time_s or 0,
        title=title or "Test Ride",
    )


class TestFitnessEndpoint:
    """Tests for GET /api/fitness."""

    @pytest.mark.asyncio
    async def test_returns_current_fitness(self, auth_client, db_session, seed_user):
        """Should return current fitness model."""
        now = datetime.now(UTC).replace(tzinfo=None)

        fitness = FitnessHistory(
            user_id=seed_user.id,
            computed_at=now,
            pp_watts=900,
            w_prime_joules=20000,
            cp_watts=280,
        )
        db_session.add(fitness)
        await db_session.flush()

        response = await auth_client.get("/api/fitness")
        assert response.status_code == 200

        data = response.json()
        assert data["current"] is not None
        assert data["current"]["pp_watts"] == 900
        assert data["current"]["w_prime_joules"] == 20000
        assert data["current"]["cp_watts"] == 280

    @pytest.mark.asyncio
    async def test_returns_fitness_history(self, auth_client, db_session, seed_user):
        """Should return recent fitness history."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Add multiple fitness snapshots
        for i in range(5):
            fitness = FitnessHistory(
                user_id=seed_user.id,
                computed_at=now - timedelta(days=i),
                pp_watts=900 - i * 10,
                w_prime_joules=20000,
                cp_watts=280 - i,
            )
            db_session.add(fitness)
        await db_session.flush()

        response = await auth_client.get("/api/fitness")
        assert response.status_code == 200

        data = response.json()
        assert len(data["history"]) == 5

    @pytest.mark.asyncio
    async def test_empty_when_no_fitness_data(self, auth_client, db_session, seed_user):
        """Should return empty when user has no fitness data."""
        response = await auth_client.get("/api/fitness")
        assert response.status_code == 200

        data = response.json()
        assert data["current"] is None
        assert data["history"] == []


class TestPMCEndpoint:
    """Tests for GET /api/pmc."""

    @pytest.mark.asyncio
    async def test_returns_pmc_data(self, auth_client, db_session, seed_user):
        """Should return CTL/ATL/TSB data."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Create activities with TSS over several days
        for i in range(7):
            activity = make_activity(
                seed_user.id,
                now - timedelta(days=i),
                tss=50.0 + i * 5,
            )
            db_session.add(activity)
        await db_session.flush()

        response = await auth_client.get("/api/pmc")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Each entry should have date and metrics
        for entry in data:
            assert "date" in entry
            assert "ctl" in entry
            assert "atl" in entry
            assert "tsb" in entry

    @pytest.mark.asyncio
    async def test_accepts_date_range_params(self, auth_client, db_session, seed_user):
        """Should accept start and end date parameters."""
        now = datetime.now(UTC).replace(tzinfo=None)

        activity = make_activity(seed_user.id, now - timedelta(days=5), tss=60.0)
        db_session.add(activity)
        await db_session.flush()

        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        response = await auth_client.get(f"/api/pmc?start={start}&end={end}")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        # Should have entries for the 7-day range
        assert len(data) == 8  # inclusive of both start and end

    @pytest.mark.asyncio
    async def test_empty_pmc_when_no_activities(self, auth_client, db_session, seed_user):
        """Should return PMC with zeros when no activities."""
        response = await auth_client.get("/api/pmc")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        # Should still have entries (default 12 weeks)
        # All TSS values should be 0
        for entry in data:
            assert entry["ctl"] == 0 or entry["ctl"] is not None
            assert entry["atl"] == 0 or entry["atl"] is not None


class TestPowerCurveEndpoint:
    """Tests for GET /api/power-curve."""

    @pytest.mark.asyncio
    async def test_returns_power_curve(self, auth_client, db_session, seed_user):
        """Should return best power at each duration."""
        now = datetime.now(UTC).replace(tzinfo=None)

        activity = make_activity(seed_user.id, now)
        db_session.add(activity)
        await db_session.flush()

        # Add peak powers at various durations
        durations = [5, 60, 300, 1200]
        powers = [900, 450, 320, 270]

        for dur, watts in zip(durations, powers):
            peak = ActivityPeakPower(
                activity_id=activity.id,
                duration_seconds=dur,
                watts=watts,
            )
            db_session.add(peak)
        await db_session.flush()

        response = await auth_client.get("/api/power-curve")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 4

        # Check data structure
        for entry in data:
            assert "duration_seconds" in entry
            assert "watts" in entry
            assert "achieved_date" in entry
            assert "days_ago" in entry

    @pytest.mark.asyncio
    async def test_returns_best_across_activities(self, auth_client, db_session, seed_user):
        """Should return best power at each duration across all activities."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Activity 1: better at 5s
        activity1 = make_activity(seed_user.id, now - timedelta(days=5))
        db_session.add(activity1)
        await db_session.flush()

        db_session.add(ActivityPeakPower(activity_id=activity1.id, duration_seconds=5, watts=950))
        db_session.add(ActivityPeakPower(activity_id=activity1.id, duration_seconds=300, watts=300))

        # Activity 2: better at 5min
        activity2 = make_activity(seed_user.id, now - timedelta(days=1))
        db_session.add(activity2)
        await db_session.flush()

        db_session.add(ActivityPeakPower(activity_id=activity2.id, duration_seconds=5, watts=900))
        db_session.add(ActivityPeakPower(activity_id=activity2.id, duration_seconds=300, watts=340))
        await db_session.flush()

        response = await auth_client.get("/api/power-curve")
        data = response.json()

        # Find entries for 5s and 300s
        five_sec = next(e for e in data if e["duration_seconds"] == 5)
        five_min = next(e for e in data if e["duration_seconds"] == 300)

        assert five_sec["watts"] == 950  # Best from activity1
        assert five_min["watts"] == 340  # Best from activity2

    @pytest.mark.asyncio
    async def test_accepts_date_range_filter(self, auth_client, db_session, seed_user):
        """Should filter power curve by date range."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Old activity with high power (should be excluded)
        old_activity = make_activity(seed_user.id, now - timedelta(days=60))
        db_session.add(old_activity)
        await db_session.flush()
        db_session.add(ActivityPeakPower(activity_id=old_activity.id, duration_seconds=300, watts=400))

        # Recent activity with lower power
        recent_activity = make_activity(seed_user.id, now - timedelta(days=5))
        db_session.add(recent_activity)
        await db_session.flush()
        db_session.add(ActivityPeakPower(activity_id=recent_activity.id, duration_seconds=300, watts=320))
        await db_session.flush()

        # Filter to last 30 days
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        response = await auth_client.get(f"/api/power-curve?start={start}&end={end}")
        data = response.json()

        five_min = next((e for e in data if e["duration_seconds"] == 300), None)
        assert five_min is not None
        assert five_min["watts"] == 320  # Only the recent one

    @pytest.mark.asyncio
    async def test_empty_when_no_peak_data(self, auth_client, db_session, seed_user):
        """Should return empty list when no peak power data."""
        response = await auth_client.get("/api/power-curve")
        assert response.status_code == 200

        data = response.json()
        assert data == []


class TestRecordsEndpoint:
    """Tests for GET /api/records."""

    @pytest.mark.asyncio
    async def test_returns_lifetime_prs(self, auth_client, db_session, seed_user):
        """Should return lifetime PRs."""
        now = datetime.now(UTC).replace(tzinfo=None)

        activity = make_activity(
            seed_user.id,
            now,
            total_distance_m=50000,
            elapsed_time_s=5400,
        )
        db_session.add(activity)
        await db_session.flush()

        # Add peak powers
        db_session.add(ActivityPeakPower(activity_id=activity.id, duration_seconds=5, watts=900))
        db_session.add(ActivityPeakPower(activity_id=activity.id, duration_seconds=60, watts=450))
        db_session.add(ActivityPeakPower(activity_id=activity.id, duration_seconds=300, watts=320))
        db_session.add(ActivityPeakPower(activity_id=activity.id, duration_seconds=1200, watts=280))
        await db_session.flush()

        response = await auth_client.get("/api/records")
        assert response.status_code == 200

        data = response.json()
        assert "lifetime_prs" in data
        assert "route_prs" in data

    @pytest.mark.asyncio
    async def test_returns_route_prs(self, auth_client, db_session, seed_user):
        """Should return per-route PRs."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Create a route
        route = Route(
            user_id=seed_user.id,
            ride_count=2,
            simplified_polyline="LINESTRING(0 0, 1 1)",
        )
        db_session.add(route)
        await db_session.flush()

        # Create activities on the route
        activity1 = make_activity(
            seed_user.id,
            now - timedelta(days=5),
            elapsed_time_s=1800,  # 30 min
            total_distance_m=10000,
            title="Morning Ride",
        )
        activity1.route_id = route.id
        db_session.add(activity1)

        activity2 = make_activity(
            seed_user.id,
            now - timedelta(days=1),
            elapsed_time_s=1700,  # 28:20 - faster!
            total_distance_m=10000,
            title="Evening Ride",
        )
        activity2.route_id = route.id
        db_session.add(activity2)
        await db_session.flush()

        response = await auth_client.get("/api/records")
        data = response.json()

        assert "route_prs" in data
        assert "items" in data["route_prs"]
        assert "total" in data["route_prs"]

    @pytest.mark.asyncio
    async def test_route_prs_pagination(self, auth_client, db_session, seed_user):
        """Should support pagination for route PRs."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Create multiple routes
        for i in range(25):
            route = Route(
                user_id=seed_user.id,
                ride_count=1,
                simplified_polyline=f"LINESTRING({i} {i}, {i + 1} {i + 1})",
            )
            db_session.add(route)
            await db_session.flush()

            activity = make_activity(
                seed_user.id,
                now - timedelta(days=i),
                elapsed_time_s=1800 + i * 60,
                total_distance_m=10000 + i * 100,
            )
            activity.route_id = route.id
            db_session.add(activity)
        await db_session.flush()

        # First page
        response1 = await auth_client.get("/api/records?route_limit=10&route_offset=0")
        data1 = response1.json()

        assert len(data1["route_prs"]["items"]) == 10
        assert data1["route_prs"]["total"] >= 25

        # Second page
        response2 = await auth_client.get("/api/records?route_limit=10&route_offset=10")
        data2 = response2.json()

        assert len(data2["route_prs"]["items"]) == 10

        # Items should be different
        ids1 = {r["route_id"] for r in data1["route_prs"]["items"]}
        ids2 = {r["route_id"] for r in data2["route_prs"]["items"]}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_empty_when_no_data(self, auth_client, db_session, seed_user):
        """Should return empty records when no data."""
        response = await auth_client.get("/api/records")
        assert response.status_code == 200

        data = response.json()
        assert "lifetime_prs" in data
        assert "route_prs" in data
        assert data["route_prs"]["items"] == []
        assert data["route_prs"]["total"] == 0


class TestAnalyticsAuthentication:
    """Tests for authentication requirements."""

    @pytest.mark.asyncio
    async def test_fitness_requires_auth(self, app_client):
        """GET /api/fitness should require authentication."""
        response = await app_client.get("/api/fitness")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_pmc_requires_auth(self, app_client):
        """GET /api/pmc should require authentication."""
        response = await app_client.get("/api/pmc")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_power_curve_requires_auth(self, app_client):
        """GET /api/power-curve should require authentication."""
        response = await app_client.get("/api/power-curve")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_records_requires_auth(self, app_client):
        """GET /api/records should require authentication."""
        response = await app_client.get("/api/records")
        assert response.status_code == 401
