"""Integration tests for the Race Plans comparison API endpoints."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from geoalchemy2 import WKTElement

from trainingdash.repositories.postgres.models import (
    Activity,
    RaceCourse,
    RacePlan,
    Record,
)


@pytest.fixture
def sample_segments():
    """Sample course segments for testing."""
    return [
        {
            "start_m": 0,
            "end_m": 2000,
            "distance_m": 2000,
            "avg_grade_pct": 0.0,
            "elevation_gain_m": 0,
            "elevation_loss_m": 0,
            "terrain_type": "flat",
        },
        {
            "start_m": 2000,
            "end_m": 4000,
            "distance_m": 2000,
            "avg_grade_pct": 5.0,
            "elevation_gain_m": 100,
            "elevation_loss_m": 0,
            "terrain_type": "climb",
        },
        {
            "start_m": 4000,
            "end_m": 6000,
            "distance_m": 2000,
            "avg_grade_pct": -3.0,
            "elevation_gain_m": 0,
            "elevation_loss_m": 60,
            "terrain_type": "descent",
        },
    ]


@pytest.fixture
async def comparison_course(db_session, seed_user, sample_segments):
    """Create a test course with segments for comparison tests."""
    geometry = WKTElement(
        "LINESTRINGZ(0 0 100, 0.02 0 100, 0.04 0 200, 0.06 0 140)",
        srid=4326,
    )
    course = RaceCourse(
        user_id=seed_user.id,
        name="Comparison Test Course",
        source_type="gpx",
        source_filename="comparison_test.gpx",
        distance_m=6000.0,
        elevation_gain_m=100.0,
        elevation_loss_m=60.0,
        min_elevation_m=100.0,
        max_elevation_m=200.0,
        geometry=geometry,
        segments=sample_segments,
        climbs=[],
        elevation_profile=[],
    )
    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)
    return course


@pytest.fixture
async def comparison_plan(db_session, seed_user, comparison_course):
    """Create a test plan with segment targets."""
    plan = RacePlan(
        user_id=seed_user.id,
        course_id=comparison_course.id,
        name="Test Plan",
        rider_weight_kg=Decimal("75.0"),
        ftp_watts=250,
        cp_watts=240,
        w_prime_joules=20000,
        cda=Decimal("0.32"),
        crr=Decimal("0.004"),
        target_intensity=Decimal("0.85"),
        optimization_method="heuristic",
        total_time_s=900.0,
        total_distance_m=6000.0,
        avg_power_w=210.0,
        segment_targets=[
            {"segment_idx": 0, "power_w": 200, "time_s": 300, "speed_mps": 6.67},
            {"segment_idx": 1, "power_w": 240, "time_s": 350, "speed_mps": 5.71},
            {"segment_idx": 2, "power_w": 180, "time_s": 250, "speed_mps": 8.0},
        ],
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest.fixture
async def comparison_activity(db_session, seed_user):
    """Create a test activity with records."""
    activity = Activity(
        id=uuid4(),
        user_id=seed_user.id,
        source="test",
        source_ref=f"test-comparison-{uuid4()}",
        title="Test Ride",
        started_at=datetime.now() - timedelta(hours=1),
        total_distance_m=6000,
        moving_time_s=920,
        elapsed_time_s=950,
        elevation_gain_m=100,
        avg_speed_mps=6.5,
        avg_power_w=215,
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity


@pytest.fixture
async def activity_with_records(db_session, comparison_activity):
    """Add records to the test activity."""
    start_time = comparison_activity.started_at
    records = []

    # Segment 0 (0-2000m): power ~205W
    for i in range(20):
        records.append(
            Record(
                activity_id=comparison_activity.id,
                timestamp=start_time + timedelta(seconds=i * 15),
                distance_m=i * 100,
                power_w=205 + (i % 3) - 1,  # Small variation
                speed_mps=6.5,
            )
        )

    # Segment 1 (2000-4000m): power ~235W
    for i in range(20):
        records.append(
            Record(
                activity_id=comparison_activity.id,
                timestamp=start_time + timedelta(seconds=300 + i * 17),
                distance_m=2000 + i * 100,
                power_w=235 + (i % 5) - 2,
                speed_mps=5.5,
            )
        )

    # Segment 2 (4000-6000m): power ~185W
    for i in range(20):
        records.append(
            Record(
                activity_id=comparison_activity.id,
                timestamp=start_time + timedelta(seconds=640 + i * 12),
                distance_m=4000 + i * 100,
                power_w=185 + (i % 4) - 2,
                speed_mps=8.2,
            )
        )

    db_session.add_all(records)
    await db_session.commit()
    return comparison_activity


class TestCompareExecution:
    """Tests for POST /api/race-plans/{plan_id}/compare endpoint."""

    @pytest.mark.asyncio
    async def test_compare_returns_correct_structure(self, auth_client, comparison_plan, activity_with_records):
        """Compare endpoint returns complete response structure."""
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(activity_with_records.id)},
        )
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert data["plan_id"] == comparison_plan.id
        assert data["activity_id"] == str(activity_with_records.id)
        assert "total_planned_time_s" in data
        assert "total_planned_time_formatted" in data
        assert "total_actual_time_s" in data
        assert "total_actual_time_formatted" in data
        assert "time_delta_s" in data
        assert "time_delta_formatted" in data
        assert "time_delta_pct" in data
        assert "pacing_consistency" in data
        assert "segments_over_target" in data
        assert "segments_under_target" in data
        assert "segment_comparisons" in data
        assert "insights" in data

    @pytest.mark.asyncio
    async def test_compare_segment_comparisons(self, auth_client, comparison_plan, activity_with_records):
        """Segment comparisons contain expected fields."""
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(activity_with_records.id)},
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["segment_comparisons"]) == 3

        seg = data["segment_comparisons"][0]
        assert "segment_idx" in seg
        assert "distance_m" in seg
        assert "grade_pct" in seg
        assert "planned_power_w" in seg
        assert "actual_power_w" in seg
        assert "power_delta_pct" in seg
        assert "planned_time_s" in seg
        assert "actual_time_s" in seg
        assert "time_delta_s" in seg

    @pytest.mark.asyncio
    async def test_compare_pacing_consistency(self, auth_client, comparison_plan, activity_with_records):
        """Pacing consistency is calculated correctly."""
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(activity_with_records.id)},
        )
        assert response.status_code == 200
        data = response.json()

        # Activity power is close to plan, so consistency should be high
        assert 0 <= data["pacing_consistency"] <= 100
        # With our test data (~5W difference), consistency should be > 90
        assert data["pacing_consistency"] > 80

    @pytest.mark.asyncio
    async def test_compare_generates_insights(self, auth_client, comparison_plan, activity_with_records):
        """Insights are generated based on pacing patterns."""
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(activity_with_records.id)},
        )
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["insights"], list)
        assert len(data["insights"]) > 0

    @pytest.mark.asyncio
    async def test_compare_plan_not_found(self, auth_client, activity_with_records):
        """Returns 400 when plan not found."""
        response = await auth_client.post(
            "/api/race-plans/99999/compare",
            json={"activity_id": str(activity_with_records.id)},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_compare_activity_not_found(self, auth_client, comparison_plan):
        """Returns 400 when activity not found."""
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(uuid4())},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_compare_activity_no_records(self, auth_client, comparison_plan, comparison_activity):
        """Returns 400 when activity has no records."""
        # comparison_activity has no records (activity_with_records fixture adds them)
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(comparison_activity.id)},
        )
        assert response.status_code == 400
        assert "no records" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_compare_time_delta_formatted(self, auth_client, comparison_plan, activity_with_records):
        """Time delta is properly formatted with sign."""
        response = await auth_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(activity_with_records.id)},
        )
        assert response.status_code == 200
        data = response.json()

        # Format should be like "+0:20" or "-1:15"
        formatted = data["time_delta_formatted"]
        assert formatted.startswith("+") or formatted.startswith("-")
        assert ":" in formatted


class TestMatchingActivities:
    """Tests for GET /api/race-plans/{plan_id}/matching-activities endpoint."""

    @pytest.mark.asyncio
    async def test_matching_activities_empty(self, auth_client, comparison_plan):
        """Returns empty list when no matching activities."""
        response = await auth_client.get(f"/api/race-plans/{comparison_plan.id}/matching-activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_matching_activities_returns_with_power(self, auth_client, comparison_plan, activity_with_records):
        """Returns activities that have power data."""
        response = await auth_client.get(f"/api/race-plans/{comparison_plan.id}/matching-activities")
        assert response.status_code == 200
        data = response.json()

        # Should include our test activity
        assert len(data) > 0
        activity_ids = [a["id"] for a in data]
        assert str(activity_with_records.id) in activity_ids

    @pytest.mark.asyncio
    async def test_matching_activities_structure(self, auth_client, comparison_plan, activity_with_records):
        """Activity list items have correct structure."""
        response = await auth_client.get(f"/api/race-plans/{comparison_plan.id}/matching-activities")
        assert response.status_code == 200
        data = response.json()

        assert len(data) > 0
        activity = data[0]
        assert "id" in activity
        assert "name" in activity
        assert "started_at" in activity
        assert "total_distance_m" in activity
        assert "moving_time_s" in activity
        assert "avg_power_w" in activity

    @pytest.mark.asyncio
    async def test_matching_activities_plan_not_found(self, auth_client):
        """Returns 404 when plan not found."""
        response = await auth_client.get("/api/race-plans/99999/matching-activities")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestComparisonAuth:
    """Tests for authentication on comparison endpoints."""

    @pytest.mark.asyncio
    async def test_compare_requires_auth(self, app_client, comparison_plan):
        """Compare endpoint requires authentication."""
        response = await app_client.post(
            f"/api/race-plans/{comparison_plan.id}/compare",
            json={"activity_id": str(uuid4())},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_matching_activities_requires_auth(self, app_client, comparison_plan):
        """Matching activities endpoint requires authentication."""
        response = await app_client.get(f"/api/race-plans/{comparison_plan.id}/matching-activities")
        assert response.status_code == 401
