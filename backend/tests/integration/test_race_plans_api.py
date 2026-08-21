"""Integration tests for the Race Plans API router."""

import pytest
from geoalchemy2 import WKTElement

from trainingdash.repositories.postgres.models import Bike, RaceCourse


@pytest.fixture
def sample_segments():
    """Sample course segments for testing."""
    return [
        {
            "start_m": 0,
            "end_m": 1000,
            "distance_m": 1000,
            "avg_grade_pct": 0.0,
            "elevation_gain_m": 0,
            "elevation_loss_m": 0,
            "terrain_type": "flat",
        },
        {
            "start_m": 1000,
            "end_m": 2000,
            "distance_m": 1000,
            "avg_grade_pct": 5.0,
            "elevation_gain_m": 50,
            "elevation_loss_m": 0,
            "terrain_type": "climb",
        },
        {
            "start_m": 2000,
            "end_m": 3000,
            "distance_m": 1000,
            "avg_grade_pct": -3.0,
            "elevation_gain_m": 0,
            "elevation_loss_m": 30,
            "terrain_type": "descent",
        },
    ]


@pytest.fixture
async def test_course(db_session, seed_user, sample_segments):
    """Create a test course with segments."""
    # Simple 3km course geometry (LineStringZ with elevation)
    geometry = WKTElement(
        "LINESTRINGZ(0 0 100, 0.01 0 100, 0.02 0 150, 0.03 0 120)",
        srid=4326,
    )
    course = RaceCourse(
        user_id=seed_user.id,
        name="Test Course",
        source_type="gpx",
        source_filename="test.gpx",
        distance_m=3000.0,
        elevation_gain_m=50.0,
        elevation_loss_m=30.0,
        min_elevation_m=100.0,
        max_elevation_m=150.0,
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
async def test_bike(db_session, seed_user):
    """Create a test bike."""
    from decimal import Decimal

    bike = Bike(
        user_id=seed_user.id,
        name="Test TT Bike",
        bike_type="tt",
        weight_kg=Decimal("8.5"),
        cda=Decimal("0.220"),
        crr=Decimal("0.0030"),
    )
    db_session.add(bike)
    await db_session.commit()
    await db_session.refresh(bike)
    return bike


class TestRacePlansAPI:
    """Tests for /api/race-plans endpoints."""

    @pytest.mark.asyncio
    async def test_generate_plan_minimal(self, auth_client, test_course):
        """Generate plan with minimal parameters."""
        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": test_course.id,
                "ftp_watts": 250,
            },
        )
        assert response.status_code == 201
        data = response.json()

        assert data["id"] is not None
        assert data["course_id"] == test_course.id
        assert data["total_time_s"] > 0
        assert data["total_time_formatted"]  # e.g., "5:30" or "1:23:45"
        assert data["avg_power_w"] > 0
        assert "comparison" in data
        assert isinstance(data["warnings"], list)

    @pytest.mark.asyncio
    async def test_generate_plan_full_params(self, auth_client, test_course, test_bike):
        """Generate plan with all parameters specified."""
        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": test_course.id,
                "bike_id": test_bike.id,
                "rider_weight_kg": 70.0,
                "ftp_watts": 280,
                "cp_watts": 270,
                "w_prime_joules": 22000,
                "target_intensity": 0.90,
                "use_optimizer": False,
                "name": "Race Day Plan",
            },
        )
        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "Race Day Plan"
        assert data["avg_power_w"] > 0
        # No warnings about defaults since we provided all params
        warnings_text = " ".join(data["warnings"]).lower()
        assert "cp estimated" not in warnings_text
        assert "w' using default" not in warnings_text

    @pytest.mark.asyncio
    async def test_generate_plan_with_optimizer(self, auth_client, test_course):
        """Generate plan using optimizer mode."""
        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": test_course.id,
                "ftp_watts": 250,
                "use_optimizer": True,
            },
        )
        assert response.status_code == 201
        data = response.json()

        # Optimizer mode should include improvement percentages
        comparison = data["comparison"]
        assert "improvement_vs_heuristic_pct" in comparison or "optimized_time_s" in comparison

    @pytest.mark.asyncio
    async def test_generate_plan_course_not_found(self, auth_client):
        """Generate plan with non-existent course returns 400."""
        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": 99999,
                "ftp_watts": 250,
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_generate_plan_invalid_ftp(self, auth_client, test_course):
        """Generate plan with out-of-range FTP returns 422."""
        # FTP too low
        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": test_course.id,
                "ftp_watts": 50,  # Below minimum of 100
            },
        )
        assert response.status_code == 422

        # FTP too high
        response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": test_course.id,
                "ftp_watts": 700,  # Above maximum of 600
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_plans_empty(self, auth_client):
        """List plans returns empty when user has no plans."""
        response = await auth_client.get("/api/race-plans")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_plans_returns_created(self, auth_client, test_course):
        """List plans returns plans created by the user."""
        # Create two plans
        await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250, "name": "Plan A"},
        )
        await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 260, "name": "Plan B"},
        )

        response = await auth_client.get("/api/race-plans")
        assert response.status_code == 200
        plans = response.json()
        assert len(plans) >= 2

        # Check structure
        for plan in plans:
            assert "id" in plan
            assert "course_id" in plan
            assert "total_time_s" in plan
            assert "total_time_formatted" in plan
            assert "avg_power_w" in plan
            assert "optimization_method" in plan
            assert "created_at" in plan

    @pytest.mark.asyncio
    async def test_list_plans_filter_by_course(self, auth_client, test_course, db_session, seed_user, sample_segments):
        """List plans filtered by course_id."""
        # Create another course
        geometry2 = WKTElement(
            "LINESTRINGZ(0 0 100, 0.01 0 100, 0.02 0 150, 0.03 0 120, 0.04 0 100)",
            srid=4326,
        )
        other_course = RaceCourse(
            user_id=seed_user.id,
            name="Other Course",
            source_type="gpx",
            source_filename="other.gpx",
            distance_m=5000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=100.0,
            geometry=geometry2,
            segments=sample_segments,
            climbs=[],
            elevation_profile=[],
        )
        db_session.add(other_course)
        await db_session.commit()
        await db_session.refresh(other_course)

        # Create plans for different courses
        await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250},
        )
        await auth_client.post(
            "/api/race-plans",
            json={"course_id": other_course.id, "ftp_watts": 250},
        )

        # Filter by course_id
        response = await auth_client.get(f"/api/race-plans?course_id={test_course.id}")
        assert response.status_code == 200
        plans = response.json()
        assert all(p["course_id"] == test_course.id for p in plans)

    @pytest.mark.asyncio
    async def test_list_plans_with_limit(self, auth_client, test_course):
        """List plans respects limit parameter."""
        # Create multiple plans
        for i in range(5):
            await auth_client.post(
                "/api/race-plans",
                json={"course_id": test_course.id, "ftp_watts": 250 + i},
            )

        response = await auth_client.get("/api/race-plans?limit=3")
        assert response.status_code == 200
        plans = response.json()
        assert len(plans) <= 3

    @pytest.mark.asyncio
    async def test_get_plan_detail(self, auth_client, test_course):
        """Get plan detail includes segment targets."""
        # Create a plan
        create_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250},
        )
        plan_id = create_response.json()["id"]

        # Get detail
        response = await auth_client.get(f"/api/race-plans/{plan_id}")
        assert response.status_code == 200
        data = response.json()

        # Check detail-specific fields
        assert "segment_targets" in data
        assert isinstance(data["segment_targets"], list)
        assert len(data["segment_targets"]) > 0

        # Check segment target structure
        for target in data["segment_targets"]:
            assert "segment_idx" in target
            assert "power_w" in target
            assert "time_s" in target
            assert "speed_mps" in target

        # Check rider/bike params
        assert "rider_params" in data
        assert "weight_kg" in data["rider_params"]
        assert "ftp_watts" in data["rider_params"]

        assert "bike_params" in data
        assert "cda" in data["bike_params"]
        assert "crr" in data["bike_params"]

        # Check W'bal prediction
        assert "wbal_prediction" in data

    @pytest.mark.asyncio
    async def test_get_plan_not_found(self, auth_client):
        """Get non-existent plan returns 404."""
        response = await auth_client.get("/api/race-plans/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_plan(self, auth_client, test_course):
        """Delete a plan."""
        # Create a plan
        create_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250},
        )
        plan_id = create_response.json()["id"]

        # Delete it
        response = await auth_client.delete(f"/api/race-plans/{plan_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = await auth_client.get(f"/api/race-plans/{plan_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_plan_not_found(self, auth_client):
        """Delete non-existent plan returns 404."""
        response = await auth_client.delete("/api/race-plans/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_regenerate_plan(self, auth_client, test_course):
        """Regenerate plan with updated parameters."""
        # Create initial plan
        create_response = await auth_client.post(
            "/api/race-plans",
            json={
                "course_id": test_course.id,
                "ftp_watts": 250,
                "target_intensity": 0.85,
                "name": "Original Plan",
            },
        )
        original_plan = create_response.json()
        original_id = original_plan["id"]

        # Regenerate with different FTP
        response = await auth_client.post(
            f"/api/race-plans/{original_id}/regenerate",
            json={
                "ftp_watts": 280,
                "target_intensity": 0.90,
                "name": "Regenerated Plan",
            },
        )
        assert response.status_code == 201
        new_plan = response.json()

        # New plan should have a different ID
        assert new_plan["id"] != original_id
        assert new_plan["name"] == "Regenerated Plan"

        # Original plan should still exist
        original_response = await auth_client.get(f"/api/race-plans/{original_id}")
        assert original_response.status_code == 200

    @pytest.mark.asyncio
    async def test_regenerate_plan_not_found(self, auth_client):
        """Regenerate non-existent plan returns 404."""
        response = await auth_client.post(
            "/api/race-plans/99999/regenerate",
            json={"ftp_watts": 280},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_regenerate_plan_no_updates(self, auth_client, test_course):
        """Regenerate plan with no updates creates clone."""
        # Create initial plan
        create_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250},
        )
        original_id = create_response.json()["id"]

        # Regenerate with no changes
        response = await auth_client.post(f"/api/race-plans/{original_id}/regenerate")
        assert response.status_code == 201
        assert response.json()["id"] != original_id


class TestRacePlansAuth:
    """Tests for authentication and authorization."""

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access(self, app_client):
        """Unauthenticated user cannot access race plans endpoints."""
        response = await app_client.get("/api/race-plans")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_create(self, app_client, test_course):
        """Unauthenticated user cannot create race plans."""
        response = await app_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250},
        )
        assert response.status_code == 401


class TestRacePlansIsolation:
    """Tests for multi-user plan isolation."""

    @pytest.mark.asyncio
    async def test_plans_scoped_to_user(self, auth_client, app_client, test_course, db_session):
        """User cannot see another user's plans."""
        # Create plan as test user
        create_response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": test_course.id, "ftp_watts": 250},
        )
        plan_id = create_response.json()["id"]

        # Create another user and login
        from tests.integration.fixtures import CACHED_HASH_TESTPASS
        from trainingdash.repositories.postgres.models import User

        other_user = User(
            email="other_race_plan_user@example.com",
            password_hash=CACHED_HASH_TESTPASS,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Login as other user
        login_response = await app_client.post(
            "/api/login",
            json={"email": "other_race_plan_user@example.com", "password": "testpass"},
        )
        assert login_response.status_code == 200

        # Other user's list should not include first user's plan
        list_response = await app_client.get("/api/race-plans")
        assert list_response.status_code == 200
        plan_ids = [p["id"] for p in list_response.json()]
        assert plan_id not in plan_ids

        # Other user cannot access first user's plan directly
        get_response = await app_client.get(f"/api/race-plans/{plan_id}")
        assert get_response.status_code == 404

        # Other user cannot delete first user's plan
        delete_response = await app_client.delete(f"/api/race-plans/{plan_id}")
        assert delete_response.status_code == 404

        # Other user cannot regenerate first user's plan
        regen_response = await app_client.post(
            f"/api/race-plans/{plan_id}/regenerate",
            json={"ftp_watts": 280},
        )
        assert regen_response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_generate_plan_for_other_users_course(
        self, auth_client, app_client, db_session, sample_segments
    ):
        """User cannot generate plan for another user's course."""
        # Create another user with a course
        from tests.integration.fixtures import CACHED_HASH_TESTPASS
        from trainingdash.repositories.postgres.models import User

        other_user = User(
            email="course_owner@example.com",
            password_hash=CACHED_HASH_TESTPASS,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        geometry3 = WKTElement(
            "LINESTRINGZ(0 0 100, 0.01 0 100, 0.02 0 150, 0.03 0 120, 0.04 0 100)",
            srid=4326,
        )
        other_course = RaceCourse(
            user_id=other_user.id,
            name="Private Course",
            source_type="gpx",
            source_filename="private.gpx",
            distance_m=5000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=100.0,
            geometry=geometry3,
            segments=sample_segments,
            climbs=[],
            elevation_profile=[],
        )
        db_session.add(other_course)
        await db_session.commit()
        await db_session.refresh(other_course)

        # Auth user tries to create plan for other user's course
        response = await auth_client.post(
            "/api/race-plans",
            json={"course_id": other_course.id, "ftp_watts": 250},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()
