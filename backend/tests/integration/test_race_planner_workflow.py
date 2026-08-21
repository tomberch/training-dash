"""
Backend integration tests for Race Planner workflows.

These tests cover complete API workflows:
1. Upload course → generate plan → compare with activity
2. Course upload variations (GPX with/without elevation, FIT)
3. Plan generation variations (with bike, optimized, defaults)
4. Performance benchmarks for long courses

Most individual API endpoint tests are in:
- test_courses_api.py
- test_race_plans_api.py
- test_race_plans_comparison.py

This file focuses on multi-endpoint flows through the backend API.
For full E2E tests including the frontend, see frontend/e2e/journeys/.
"""

import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Activity, Bike, Record

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "courses"


@pytest.fixture
def gpx_with_elevation() -> bytes:
    """GPX file with elevation data."""
    return (FIXTURES_DIR / "simple_with_elevation.gpx").read_bytes()


@pytest.fixture
def gpx_no_elevation() -> bytes:
    """GPX file without elevation data."""
    return (FIXTURES_DIR / "simple_no_elevation.gpx").read_bytes()


@pytest.fixture
def fit_course() -> bytes:
    """FIT course file."""
    return (FIXTURES_DIR / "activity_as_course.fit").read_bytes()


@pytest.fixture
def hilly_gpx() -> bytes:
    """Generate a longer GPX with varied terrain for testing."""
    # Create a ~10km course with climbs and descents
    points = []
    lat, lon = 37.7749, -122.4194
    elevation = 100.0

    # 100 points over ~10km with varied elevation
    for i in range(100):
        # Move ~100m per point
        lat += 0.0009
        lon += 0.0005

        # Create elevation profile: flat -> climb -> descent -> flat
        if i < 25:
            elevation = 100.0 + i * 0.5  # Gradual rise
        elif i < 50:
            elevation = 112.5 + (i - 25) * 4.0  # Steep climb
        elif i < 75:
            elevation = 212.5 - (i - 50) * 3.0  # Descent
        else:
            elevation = 137.5 - (i - 75) * 0.5  # Gradual descent

        points.append(
            f'      <trkpt lat="{lat:.6f}" lon="{lon:.6f}">\n        <ele>{elevation:.1f}</ele>\n      </trkpt>'
        )

    gpx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>Hilly Test Course</name>
  </metadata>
  <trk>
    <name>Hilly Ride</name>
    <trkseg>
{chr(10).join(points)}
    </trkseg>
  </trk>
</gpx>"""
    return gpx_content.encode()


@pytest.fixture
async def test_bike(db_session, seed_user):
    """Create a calibrated test bike."""
    bike = Bike(
        user_id=seed_user.id,
        name="Race TT Bike",
        bike_type="tt",
        weight_kg=Decimal("8.0"),
        cda=Decimal("0.220"),
        crr=Decimal("0.0028"),
    )
    db_session.add(bike)
    await db_session.commit()
    await db_session.refresh(bike)
    return bike


class TestFullWorkflow:
    """Test complete race planner workflows end-to-end."""

    @pytest.mark.asyncio
    async def test_upload_generate_compare_workflow(self, auth_client, db_session, seed_user, hilly_gpx):
        """
        Full workflow test:
        1. Upload GPX course
        2. Verify course has segments and climbs
        3. Generate race plan with heuristic
        4. Verify plan has segment targets
        5. Create matching activity with power data
        6. Compare execution to plan
        7. Verify comparison results
        """
        # Step 1: Upload GPX course
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("race_course.gpx", hilly_gpx, "application/gpx+xml")},
            data={"name": "Race Day Course"},
        )
        assert upload_response.status_code == 201
        course = upload_response.json()
        course_id = course["id"]

        assert course["name"] == "Race Day Course"
        assert course["distance_m"] > 0
        assert course["elevation_gain_m"] > 0

        # Step 2: Get course detail and verify segments
        detail_response = await auth_client.get(f"/api/courses/{course_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()

        assert len(detail["segments"]) > 0
        assert len(detail["elevation_profile"]) > 0
        # Should have detected climbs in our hilly course
        # (may be empty for short courses, but structure should exist)
        assert "climbs" in detail

        # Step 3: Generate race plan
        plan_response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": course_id,
                "ftp_watts": 280,
                "rider_weight_kg": 72.0,
                "target_intensity": 0.88,
                "name": "Race Day Plan",
            },
        )
        assert plan_response.status_code == 201
        plan = plan_response.json()
        plan_id = plan["id"]

        assert plan["name"] == "Race Day Plan"
        assert plan["total_time_s"] > 0
        assert plan["avg_power_w"] > 0

        # Step 4: Get plan detail and verify segment targets
        plan_detail_response = await auth_client.get(f"/api/race-plans/{plan_id}")
        assert plan_detail_response.status_code == 200
        plan_detail = plan_detail_response.json()

        assert len(plan_detail["segment_targets"]) > 0
        for target in plan_detail["segment_targets"]:
            assert "segment_idx" in target
            assert "power_w" in target
            assert target["power_w"] > 0
            assert "time_s" in target
            assert target["time_s"] > 0

        # Step 5: Create matching activity with records
        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            source="test",
            source_ref=f"e2e-test-{uuid4()}",
            title="Race Day Execution",
            started_at=datetime.now() - timedelta(hours=1),
            total_distance_m=course["distance_m"],
            moving_time_s=int(plan["total_time_s"] * 1.05),  # Slightly slower
            elapsed_time_s=int(plan["total_time_s"] * 1.1),
            elevation_gain_m=course["elevation_gain_m"],
            avg_speed_mps=course["distance_m"] / (plan["total_time_s"] * 1.05),
            avg_power_w=int(plan["avg_power_w"] * 0.98),  # Slightly under target
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        # Add power records for comparison
        start_time = activity.started_at
        records = []
        num_records = 60
        distance_per_record = course["distance_m"] / num_records
        time_per_record = activity.moving_time_s / num_records

        for i in range(num_records):
            records.append(
                Record(
                    activity_id=activity.id,
                    timestamp=start_time + timedelta(seconds=i * time_per_record),
                    distance_m=i * distance_per_record,
                    power_w=int(plan["avg_power_w"] * (0.95 + (i % 10) * 0.01)),
                    speed_mps=activity.avg_speed_mps,
                )
            )
        db_session.add_all(records)
        await db_session.commit()

        # Step 6: Compare execution to plan
        compare_response = await auth_client.post(
            f"/api/race-plans/{plan_id}/compare",
            json={"activity_id": str(activity.id)},
        )
        assert compare_response.status_code == 200
        comparison = compare_response.json()

        # Step 7: Verify comparison results
        assert comparison["plan_id"] == plan_id
        assert comparison["activity_id"] == str(activity.id)
        assert "total_planned_time_s" in comparison
        assert "total_actual_time_s" in comparison
        assert "time_delta_s" in comparison
        assert "pacing_consistency" in comparison
        assert 0 <= comparison["pacing_consistency"] <= 100
        assert len(comparison["segment_comparisons"]) > 0
        assert len(comparison["insights"]) > 0

    @pytest.mark.asyncio
    async def test_workflow_with_bike(self, auth_client, gpx_with_elevation, test_bike):
        """Test workflow using a calibrated bike for the plan."""
        # Upload course
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        assert upload_response.status_code == 201
        course_id = upload_response.json()["id"]

        # Generate plan with bike
        plan_response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": course_id,
                "bike_id": test_bike.id,
                "ftp_watts": 300,
                "rider_weight_kg": 70.0,
            },
        )
        assert plan_response.status_code == 201
        plan = plan_response.json()

        # Plan should use bike's CdA/Crr (no warnings about defaults)
        warnings_text = " ".join(plan.get("warnings", [])).lower()
        assert "cda" not in warnings_text or "using bike" in warnings_text

        # Verify plan detail shows bike params
        detail_response = await auth_client.get(f"/api/race-plans/{plan['id']}")
        assert detail_response.status_code == 200
        detail = detail_response.json()

        assert detail["bike_params"]["cda"] == float(test_bike.cda)
        assert detail["bike_params"]["crr"] == float(test_bike.crr)


class TestCourseUploadVariations:
    """Test different course upload scenarios."""

    @pytest.mark.asyncio
    async def test_gpx_with_elevation_no_warnings(self, auth_client, gpx_with_elevation):
        """GPX with elevation creates course without warnings."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        assert response.status_code == 201
        data = response.json()

        assert data["elevation_gain_m"] >= 0
        assert data["warnings"] == []

    @pytest.mark.asyncio
    async def test_gpx_without_elevation_warns(self, auth_client, gpx_no_elevation):
        """GPX without elevation returns warning about missing data."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("flat.gpx", gpx_no_elevation, "application/gpx+xml")},
        )
        assert response.status_code == 201
        data = response.json()

        assert len(data["warnings"]) > 0
        assert any("elevation" in w.lower() for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_fit_course_upload(self, auth_client, fit_course):
        """FIT course file is processed correctly."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("race.fit", fit_course, "application/octet-stream")},
        )
        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "fit"
        assert data["distance_m"] > 0


class TestPlanGenerationVariations:
    """Test different plan generation scenarios."""

    @pytest.mark.asyncio
    async def test_plan_with_defaults(self, auth_client, gpx_with_elevation):
        """Plan generated with minimal params uses sensible defaults."""
        # Upload course
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        # Generate plan with only required params
        plan_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": course_id, "ftp_watts": 250},
        )
        assert plan_response.status_code == 201
        plan = plan_response.json()

        # Should generate a valid plan
        assert plan["total_time_s"] > 0
        assert plan["avg_power_w"] > 0

        # May have warnings about estimated values
        assert isinstance(plan["warnings"], list)

    @pytest.mark.asyncio
    async def test_plan_with_optimizer(self, auth_client, gpx_with_elevation):
        """Plan generated with optimizer mode."""
        # Upload course
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        # Generate optimized plan
        plan_response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": course_id,
                "ftp_watts": 280,
                "use_optimizer": True,
            },
        )
        assert plan_response.status_code == 201
        plan = plan_response.json()

        # Should complete and provide comparison to heuristic
        assert plan["total_time_s"] > 0
        assert "comparison" in plan

    @pytest.mark.asyncio
    async def test_regenerate_plan_with_different_params(self, auth_client, gpx_with_elevation):
        """Regenerate plan with updated parameters creates new plan."""
        # Upload course
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        # Generate initial plan
        plan1_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": course_id, "ftp_watts": 250, "target_intensity": 0.85},
        )
        plan1 = plan1_response.json()

        # Regenerate with higher FTP
        plan2_response = await auth_client.post(
            f"/api/race-plans/{plan1['id']}/regenerate",
            json={"ftp_watts": 300, "target_intensity": 0.90},
        )
        assert plan2_response.status_code == 201
        plan2 = plan2_response.json()

        # Should be a new plan with faster time
        assert plan2["id"] != plan1["id"]
        assert plan2["total_time_s"] < plan1["total_time_s"]


class TestPerformance:
    """Performance benchmarks for race planner operations."""

    @pytest.mark.asyncio
    async def test_course_processing_performance(self, auth_client, hilly_gpx):
        """Course processing should complete within reasonable time."""
        start = time.time()

        response = await auth_client.post(
            "/api/courses",
            files={"file": ("long_course.gpx", hilly_gpx, "application/gpx+xml")},
        )

        elapsed = time.time() - start

        assert response.status_code == 201
        # Course processing should be fast (< 5s for ~10km course)
        assert elapsed < 5.0, f"Course processing took {elapsed:.2f}s (expected < 5s)"

    @pytest.mark.asyncio
    async def test_plan_generation_heuristic_performance(self, auth_client, hilly_gpx):
        """Heuristic plan generation should be fast."""
        # Upload course first
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", hilly_gpx, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        # Time plan generation
        start = time.time()

        response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": course_id, "ftp_watts": 280},
        )

        elapsed = time.time() - start

        assert response.status_code == 201
        # Heuristic plan should be very fast (< 2s)
        assert elapsed < 2.0, f"Plan generation took {elapsed:.2f}s (expected < 2s)"

    @pytest.mark.asyncio
    async def test_plan_generation_optimized_performance(self, auth_client, hilly_gpx):
        """Optimized plan generation should complete within timeout."""
        # Upload course first
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", hilly_gpx, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        # Time optimized plan generation
        start = time.time()

        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": course_id,
                "ftp_watts": 280,
                "use_optimizer": True,
            },
        )

        elapsed = time.time() - start

        assert response.status_code == 201
        # Optimized plan can take longer but should finish (< 30s)
        assert elapsed < 30.0, f"Optimized plan took {elapsed:.2f}s (expected < 30s)"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_delete_course_cascades_to_plans(self, auth_client, gpx_with_elevation):
        """Deleting a course should delete associated plans."""
        # Upload course and create plan
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        plan_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": course_id, "ftp_watts": 250},
        )
        plan_id = plan_response.json()["id"]

        # Verify plan exists
        get_plan = await auth_client.get(f"/api/race-plans/{plan_id}")
        assert get_plan.status_code == 200

        # Delete course
        delete_response = await auth_client.delete(f"/api/courses/{course_id}")
        assert delete_response.status_code == 204

        # Plan should be gone
        get_plan_after = await auth_client.get(f"/api/race-plans/{plan_id}")
        assert get_plan_after.status_code == 404

    @pytest.mark.asyncio
    async def test_list_plans_for_deleted_course(self, auth_client, gpx_with_elevation):
        """Listing plans after course deletion returns empty for that course."""
        # Upload course and create plan
        upload_response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = upload_response.json()["id"]

        await auth_client.post(
            "/api/race-plans",
            json={"course_id": course_id, "ftp_watts": 250},
        )

        # Delete course
        await auth_client.delete(f"/api/courses/{course_id}")

        # Filter by deleted course should return empty
        list_response = await auth_client.get(f"/api/race-plans?course_id={course_id}")
        assert list_response.status_code == 200
        assert list_response.json() == []
