"""Integration tests for Segments API endpoints."""

from datetime import datetime
from uuid import uuid4

import pytest
from geoalchemy2 import WKTElement

from tests.integration.fixtures import CACHED_HASH_TESTPASS
from trainingdash.repositories.postgres.models import Activity, Segment, SegmentEffort, User


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def other_user(db_session):
    """Create a second test user for ownership tests."""
    user = User(
        email="otheruser@example.com",
        password_hash=CACHED_HASH_TESTPASS,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_segment(db_session, seed_user):
    """Create a sample segment for testing."""
    segment = Segment(
        id=uuid4(),
        name="Test Climb",
        type="climb",
        status="approved",
        climb_category="3",
        polyline="test_polyline_encoded",
        start_point=WKTElement("POINT(8.5 47.4)", srid=4326),
        end_point=WKTElement("POINT(8.6 47.5)", srid=4326),
        bounds=WKTElement("POLYGON((8.4 47.3, 8.7 47.3, 8.7 47.6, 8.4 47.6, 8.4 47.3))", srid=4326),
        distance_m=5000.0,
        elevation_gain_m=300.0,
        avg_grade_pct=6.0,
        max_grade_pct=12.0,
        elevation_profile={"distances": [0, 1000, 2000], "elevations": [100, 150, 200]},
        effort_count=10,
        athlete_count=5,
        created_by=seed_user.id,
    )
    db_session.add(segment)
    await db_session.commit()
    await db_session.refresh(segment)
    return segment


@pytest.fixture
async def sample_activities(db_session, seed_user):
    """Create sample activities for segment effort testing."""
    activities = []
    for i in range(3):
        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            source="test",
            source_ref=f"test-activity-{i}",
            started_at=datetime(2024, 3, 15 + i, 9, 0, 0),  # Naive datetime for DB
            total_distance_m=50000.0,
            moving_time_s=7200,
            elapsed_time_s=7500,
            elevation_gain_m=500.0,
            avg_speed_mps=6.94,
            max_speed_mps=15.0,
        )
        db_session.add(activity)
        activities.append(activity)
    await db_session.commit()
    for activity in activities:
        await db_session.refresh(activity)
    return activities


@pytest.fixture
async def sample_efforts(db_session, seed_user, sample_segment, sample_activities):
    """Create sample segment efforts for testing."""
    efforts = []
    for i, activity in enumerate(sample_activities):
        effort = SegmentEffort(
            id=uuid4(),
            segment_id=sample_segment.id,
            activity_id=activity.id,
            user_id=seed_user.id,
            started_at=datetime(2024, 3, 15 + i, 10, 0, 0),  # Naive datetime for DB
            elapsed_time_seconds=600 + i * 30,
            moving_time_seconds=590 + i * 30,
            avg_power_watts=250 - i * 10,
            avg_hr_bpm=165 + i * 2,
            start_index=0,
            end_index=100,
            is_pr=(i == 0),  # First one is PR
        )
        db_session.add(effort)
        efforts.append(effort)

    await db_session.commit()
    return efforts


# =============================================================================
# Test List Segments
# =============================================================================


class TestListSegments:
    """Tests for GET /api/segments."""

    @pytest.mark.asyncio
    async def test_list_returns_approved_segments(self, auth_client, sample_segment):
        """Should return list of approved segments."""
        response = await auth_client.get("/api/segments")

        assert response.status_code == 200
        data = response.json()
        assert "segments" in data
        assert "pagination" in data

        # Find our sample segment
        segment_ids = [s["id"] for s in data["segments"]]
        assert str(sample_segment.id) in segment_ids

    @pytest.mark.asyncio
    async def test_list_includes_segment_summary_fields(self, auth_client, sample_segment):
        """Should include all summary fields."""
        response = await auth_client.get("/api/segments")

        assert response.status_code == 200
        data = response.json()

        segment = next(s for s in data["segments"] if s["id"] == str(sample_segment.id))
        assert segment["name"] == "Test Climb"
        assert segment["type"] == "climb"
        assert segment["climb_category"] == "3"
        assert segment["distance_m"] == 5000.0
        assert segment["elevation_gain_m"] == 300.0
        assert segment["avg_grade_pct"] == 6.0
        assert segment["effort_count"] == 10
        assert segment["athlete_count"] == 5

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, auth_client, db_session, seed_user, sample_segment):
        """Should filter segments by type."""
        # Create a sprint segment
        sprint = Segment(
            id=uuid4(),
            name="Test Sprint",
            type="sprint",
            status="approved",
            polyline="sprint_polyline",
            start_point=WKTElement("POINT(8.3 47.2)", srid=4326),
            end_point=WKTElement("POINT(8.4 47.3)", srid=4326),
            bounds=WKTElement("POLYGON((8.2 47.1, 8.5 47.1, 8.5 47.4, 8.2 47.4, 8.2 47.1))", srid=4326),
            distance_m=500.0,
            elevation_gain_m=0.0,
            avg_grade_pct=0.0,
            max_grade_pct=1.0,
            elevation_profile={"distances": [0, 500], "elevations": [100, 100]},
            effort_count=5,
            athlete_count=3,
            created_by=seed_user.id,
        )
        db_session.add(sprint)
        await db_session.commit()

        # Filter by climb
        response = await auth_client.get("/api/segments", params={"type": "climb"})
        assert response.status_code == 200
        data = response.json()

        types = {s["type"] for s in data["segments"]}
        assert types == {"climb"}

    @pytest.mark.asyncio
    async def test_list_pagination(self, auth_client, db_session, seed_user):
        """Should paginate results."""
        # Create multiple segments
        for i in range(5):
            segment = Segment(
                id=uuid4(),
                name=f"Pagination Test Segment {i}",
                type="climb",
                status="approved",
                polyline=f"polyline_{i}",
                start_point=WKTElement(f"POINT({8.0 + i * 0.1} 47.0)", srid=4326),
                end_point=WKTElement(f"POINT({8.1 + i * 0.1} 47.1)", srid=4326),
                bounds=WKTElement(f"POLYGON(({7.9 + i * 0.1} 46.9, {8.2 + i * 0.1} 46.9, {8.2 + i * 0.1} 47.2, {7.9 + i * 0.1} 47.2, {7.9 + i * 0.1} 46.9))", srid=4326),
                distance_m=1000.0,
                elevation_gain_m=50.0,
                avg_grade_pct=5.0,
                max_grade_pct=8.0,
                elevation_profile={"distances": [0, 1000], "elevations": [100, 150]},
                effort_count=1,
                athlete_count=1,
                created_by=seed_user.id,
            )
            db_session.add(segment)
        await db_session.commit()

        # Get page 1 with per_page=2
        response = await auth_client.get("/api/segments", params={"page": 1, "per_page": 2})
        assert response.status_code == 200
        data = response.json()

        assert len(data["segments"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total"] >= 5

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, app_client):
        """Should require authentication."""
        response = await app_client.get("/api/segments")
        assert response.status_code == 401


# =============================================================================
# Test Get Segment
# =============================================================================


class TestGetSegment:
    """Tests for GET /api/segments/{segment_id}."""

    @pytest.mark.asyncio
    async def test_get_returns_segment_detail(self, auth_client, sample_segment):
        """Should return segment with full details."""
        response = await auth_client.get(f"/api/segments/{sample_segment.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(sample_segment.id)
        assert data["name"] == "Test Climb"
        assert data["status"] == "approved"
        assert data["polyline"] == "test_polyline_encoded"
        assert "start_point" in data
        assert "end_point" in data
        assert "elevation_profile" in data

    @pytest.mark.asyncio
    async def test_get_includes_my_stats_when_efforts_exist(
        self, auth_client, sample_segment, sample_efforts
    ):
        """Should include user's stats when they have efforts."""
        response = await auth_client.get(f"/api/segments/{sample_segment.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["my_stats"] is not None
        assert data["my_stats"]["effort_count"] == 3
        assert data["my_stats"]["pr_time_seconds"] == 600  # First effort is PR

    @pytest.mark.asyncio
    async def test_get_returns_404_for_nonexistent(self, auth_client):
        """Should return 404 for non-existent segment."""
        response = await auth_client.get(f"/api/segments/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, app_client, sample_segment):
        """Should require authentication."""
        response = await app_client.get(f"/api/segments/{sample_segment.id}")
        assert response.status_code == 401


# =============================================================================
# Test Update Segment
# =============================================================================


class TestUpdateSegment:
    """Tests for PATCH /api/segments/{segment_id}."""

    @pytest.mark.asyncio
    async def test_update_name(self, auth_client, sample_segment):
        """Should update segment name."""
        response = await auth_client.patch(
            f"/api/segments/{sample_segment.id}",
            json={"name": "Renamed Climb"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed Climb"

    @pytest.mark.asyncio
    async def test_update_validates_name_length(self, auth_client, sample_segment):
        """Should validate name length."""
        # Too short
        response = await auth_client.patch(
            f"/api/segments/{sample_segment.id}",
            json={"name": "AB"},
        )
        assert response.status_code == 422

        # Too long
        response = await auth_client.patch(
            f"/api/segments/{sample_segment.id}",
            json={"name": "A" * 101},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_only_by_owner(self, auth_client, db_session, other_user):
        """Should only allow owner to update."""
        # Create segment owned by a different user
        other_segment = Segment(
            id=uuid4(),
            name="Other User Segment",
            type="climb",
            status="approved",
            polyline="other_polyline",
            start_point=WKTElement("POINT(8.0 47.0)", srid=4326),
            end_point=WKTElement("POINT(8.1 47.1)", srid=4326),
            bounds=WKTElement("POLYGON((7.9 46.9, 8.2 46.9, 8.2 47.2, 7.9 47.2, 7.9 46.9))", srid=4326),
            distance_m=1000.0,
            elevation_gain_m=50.0,
            avg_grade_pct=5.0,
            max_grade_pct=8.0,
            elevation_profile={"distances": [0, 1000], "elevations": [100, 150]},
            effort_count=0,
            athlete_count=0,
            created_by=other_user.id,  # Owned by other_user
        )
        db_session.add(other_segment)
        await db_session.commit()

        response = await auth_client.patch(
            f"/api/segments/{other_segment.id}",
            json={"name": "Attempted Update"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_returns_404_for_nonexistent(self, auth_client):
        """Should return 404 for non-existent segment."""
        response = await auth_client.patch(
            f"/api/segments/{uuid4()}",
            json={"name": "Update Nonexistent"},
        )
        assert response.status_code == 404


# =============================================================================
# Test Delete Segment
# =============================================================================


class TestDeleteSegment:
    """Tests for DELETE /api/segments/{segment_id}."""

    @pytest.mark.asyncio
    async def test_delete_segment(self, auth_client, sample_segment):
        """Should delete segment."""
        response = await auth_client.delete(f"/api/segments/{sample_segment.id}")
        assert response.status_code == 204

        # Verify it's deleted
        response = await auth_client.get(f"/api/segments/{sample_segment.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_only_by_owner(self, auth_client, db_session, other_user):
        """Should only allow owner to delete."""
        other_segment = Segment(
            id=uuid4(),
            name="Other User Segment",
            type="climb",
            status="approved",
            polyline="other_polyline",
            start_point=WKTElement("POINT(8.0 47.0)", srid=4326),
            end_point=WKTElement("POINT(8.1 47.1)", srid=4326),
            bounds=WKTElement("POLYGON((7.9 46.9, 8.2 46.9, 8.2 47.2, 7.9 47.2, 7.9 46.9))", srid=4326),
            distance_m=1000.0,
            elevation_gain_m=50.0,
            avg_grade_pct=5.0,
            max_grade_pct=8.0,
            elevation_profile={"distances": [0, 1000], "elevations": [100, 150]},
            effort_count=0,
            athlete_count=0,
            created_by=other_user.id,  # Owned by other_user
        )
        db_session.add(other_segment)
        await db_session.commit()

        response = await auth_client.delete(f"/api/segments/{other_segment.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_returns_404_for_nonexistent(self, auth_client):
        """Should return 404 for non-existent segment."""
        response = await auth_client.delete(f"/api/segments/{uuid4()}")
        assert response.status_code == 404


# =============================================================================
# Test List Segment Efforts
# =============================================================================


class TestListSegmentEfforts:
    """Tests for GET /api/segments/{segment_id}/efforts."""

    @pytest.mark.asyncio
    async def test_list_efforts(self, auth_client, sample_segment, sample_efforts):
        """Should return user's efforts on segment."""
        response = await auth_client.get(f"/api/segments/{sample_segment.id}/efforts")

        assert response.status_code == 200
        data = response.json()

        assert "efforts" in data
        assert "pagination" in data
        assert len(data["efforts"]) == 3

    @pytest.mark.asyncio
    async def test_list_efforts_includes_fields(
        self, auth_client, sample_segment, sample_efforts
    ):
        """Should include all effort fields."""
        response = await auth_client.get(f"/api/segments/{sample_segment.id}/efforts")

        assert response.status_code == 200
        data = response.json()

        effort = data["efforts"][0]
        assert "id" in effort
        assert "segment_id" in effort
        assert "activity_id" in effort
        assert "started_at" in effort
        assert "elapsed_time_seconds" in effort
        assert "moving_time_seconds" in effort
        assert "avg_power_watts" in effort
        assert "avg_hr_bpm" in effort
        assert "is_pr" in effort

    @pytest.mark.asyncio
    async def test_list_efforts_pagination(self, auth_client, sample_segment, sample_efforts):
        """Should paginate efforts."""
        response = await auth_client.get(
            f"/api/segments/{sample_segment.id}/efforts",
            params={"page": 1, "per_page": 2},
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["efforts"]) == 2
        assert data["pagination"]["total"] == 3

    @pytest.mark.asyncio
    async def test_list_efforts_returns_404_for_nonexistent_segment(self, auth_client):
        """Should return 404 for non-existent segment."""
        response = await auth_client.get(f"/api/segments/{uuid4()}/efforts")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_efforts_requires_auth(self, app_client, sample_segment):
        """Should require authentication."""
        response = await app_client.get(f"/api/segments/{sample_segment.id}/efforts")
        assert response.status_code == 401
