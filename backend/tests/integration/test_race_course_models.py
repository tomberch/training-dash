"""Integration tests for RaceCourse model."""

import pytest
from geoalchemy2.functions import ST_AsText
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trainingdash.repositories.postgres.models import RaceCourse, User


class TestRaceCourseModel:
    """Tests for RaceCourse model CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_race_course_minimal(self, db_session, seed_user):
        """Can create a race course with required fields."""
        # WKT for LineStringZ: LINESTRINGZ(lon lat elev, ...)
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200, 2 2 150)"

        course = RaceCourse(
            user_id=seed_user.id,
            name="Test Course",
            source_type="gpx",
            distance_m=5000.0,
            elevation_gain_m=150.0,
            elevation_loss_m=100.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)

        assert course.id is not None
        assert course.name == "Test Course"
        assert course.source_type == "gpx"
        assert course.distance_m == 5000.0
        assert course.elevation_gain_m == 150.0
        assert course.elevation_loss_m == 100.0
        assert course.created_at is not None
        assert course.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_race_course_all_fields(self, db_session, seed_user):
        """Can create a race course with all optional fields."""
        wkt = "SRID=4326;LINESTRINGZ(-122.4 37.8 10, -122.3 37.9 500, -122.2 38.0 50)"

        elevation_profile = [
            {"distance_m": 0, "elevation_m": 10, "grade_pct": 0},
            {"distance_m": 5000, "elevation_m": 500, "grade_pct": 9.8},
            {"distance_m": 10000, "elevation_m": 50, "grade_pct": -9.0},
        ]
        segments = [
            {"start_m": 0, "end_m": 5000, "avg_grade_pct": 9.8, "distance_m": 5000},
            {"start_m": 5000, "end_m": 10000, "avg_grade_pct": -9.0, "distance_m": 5000},
        ]
        climbs = [
            {
                "name": "Mount Test",
                "start_m": 0,
                "end_m": 5000,
                "distance_m": 5000,
                "avg_grade_pct": 9.8,
                "elevation_gain_m": 490,
                "category": "2",
            }
        ]

        course = RaceCourse(
            user_id=seed_user.id,
            name="Full Test Course",
            description="A challenging test course",
            source_type="fit",
            source_filename="test_course.fit",
            distance_m=10000.0,
            elevation_gain_m=490.0,
            elevation_loss_m=450.0,
            min_elevation_m=10.0,
            max_elevation_m=500.0,
            geometry=wkt,
            elevation_profile=elevation_profile,
            segments=segments,
            climbs=climbs,
        )
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)

        assert course.description == "A challenging test course"
        assert course.source_filename == "test_course.fit"
        assert course.min_elevation_m == 10.0
        assert course.max_elevation_m == 500.0
        assert course.elevation_profile == elevation_profile
        assert course.segments == segments
        assert course.climbs == climbs

    @pytest.mark.asyncio
    async def test_source_types_valid(self, db_session, seed_user):
        """All valid source types can be created."""
        valid_types = ["gpx", "fit", "manual"]
        wkt = "SRID=4326;LINESTRINGZ(0 0 0, 1 1 100)"

        for i, source_type in enumerate(valid_types):
            course = RaceCourse(
                user_id=seed_user.id,
                name=f"Test {source_type}",
                source_type=source_type,
                distance_m=1000.0,
                elevation_gain_m=100.0,
                elevation_loss_m=0.0,
                geometry=wkt,
            )
            db_session.add(course)

        await db_session.commit()

        result = await db_session.execute(
            select(RaceCourse).where(RaceCourse.user_id == seed_user.id)
        )
        courses = result.scalars().all()
        assert len(courses) >= 3

    @pytest.mark.asyncio
    async def test_invalid_source_type_rejected(self, db_session, seed_user):
        """Invalid source type is rejected by database constraint."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 0, 1 1 100)"

        course = RaceCourse(
            user_id=seed_user.id,
            name="Invalid Source",
            source_type="strava",  # not a valid type
            distance_m=1000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_course_deleted_with_user(self, db_session):
        """Course is deleted when user is deleted (CASCADE)."""
        # Create a separate user for this test
        user = User(email="course-cascade-test@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        wkt = "SRID=4326;LINESTRINGZ(0 0 0, 1 1 100)"
        course = RaceCourse(
            user_id=user.id,
            name="Cascade Test",
            source_type="gpx",
            distance_m=1000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        course_id = course.id

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Course should be gone
        result = await db_session.execute(select(RaceCourse).where(RaceCourse.id == course_id))
        assert result.scalar_one_or_none() is None


class TestRaceCourseGeometry:
    """Tests for PostGIS geometry operations."""

    @pytest.mark.asyncio
    async def test_geometry_stored_correctly(self, db_session, seed_user):
        """Geometry is stored and can be retrieved as WKT."""
        # San Francisco to Oakland coordinates
        wkt = "SRID=4326;LINESTRINGZ(-122.4194 37.7749 10, -122.2711 37.8044 50)"

        course = RaceCourse(
            user_id=seed_user.id,
            name="SF to Oakland",
            source_type="gpx",
            distance_m=15000.0,
            elevation_gain_m=40.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)

        # Query geometry as text
        result = await db_session.execute(
            select(ST_AsText(RaceCourse.geometry)).where(RaceCourse.id == course.id)
        )
        geom_text = result.scalar_one()

        # Check that geometry contains expected coordinates
        assert "LINESTRING Z" in geom_text or "LINESTRINGZ" in geom_text.replace(" ", "")
        assert "-122.4194" in geom_text
        assert "37.7749" in geom_text

    @pytest.mark.asyncio
    async def test_geometry_with_many_points(self, db_session, seed_user):
        """Geometry can store many points (simulating real course)."""
        # Create 100-point linestring
        points = [f"{-122.4 + i * 0.01} {37.7 + i * 0.005} {100 + i * 10}" for i in range(100)]
        wkt = f"SRID=4326;LINESTRINGZ({', '.join(points)})"

        course = RaceCourse(
            user_id=seed_user.id,
            name="Long Course",
            source_type="gpx",
            distance_m=50000.0,
            elevation_gain_m=1000.0,
            elevation_loss_m=500.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)

        assert course.id is not None


class TestRaceCourseJSONB:
    """Tests for JSONB field serialization/deserialization."""

    @pytest.mark.asyncio
    async def test_elevation_profile_serialization(self, db_session, seed_user):
        """Elevation profile JSONB serializes and deserializes correctly."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        profile = [
            {"distance_m": 0, "elevation_m": 100.5, "grade_pct": 0.0},
            {"distance_m": 1000, "elevation_m": 150.25, "grade_pct": 5.0},
            {"distance_m": 2000, "elevation_m": 200.0, "grade_pct": 4.97},
        ]

        course = RaceCourse(
            user_id=seed_user.id,
            name="Profile Test",
            source_type="gpx",
            distance_m=2000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
            elevation_profile=profile,
        )
        db_session.add(course)
        await db_session.commit()

        # Re-fetch from database
        result = await db_session.execute(select(RaceCourse).where(RaceCourse.id == course.id))
        fetched = result.scalar_one()

        assert fetched.elevation_profile == profile
        assert fetched.elevation_profile[0]["elevation_m"] == 100.5
        assert fetched.elevation_profile[2]["grade_pct"] == 4.97

    @pytest.mark.asyncio
    async def test_segments_serialization(self, db_session, seed_user):
        """Segments JSONB serializes and deserializes correctly."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200, 2 2 150)"
        segments = [
            {
                "start_m": 0,
                "end_m": 5000,
                "avg_grade_pct": 8.5,
                "distance_m": 5000,
                "min_elevation_m": 100,
                "max_elevation_m": 525,
            },
            {
                "start_m": 5000,
                "end_m": 8000,
                "avg_grade_pct": -5.0,
                "distance_m": 3000,
                "min_elevation_m": 375,
                "max_elevation_m": 525,
            },
        ]

        course = RaceCourse(
            user_id=seed_user.id,
            name="Segments Test",
            source_type="fit",
            distance_m=8000.0,
            elevation_gain_m=425.0,
            elevation_loss_m=150.0,
            geometry=wkt,
            segments=segments,
        )
        db_session.add(course)
        await db_session.commit()

        # Re-fetch from database
        result = await db_session.execute(select(RaceCourse).where(RaceCourse.id == course.id))
        fetched = result.scalar_one()

        assert len(fetched.segments) == 2
        assert fetched.segments[0]["avg_grade_pct"] == 8.5
        assert fetched.segments[1]["avg_grade_pct"] == -5.0

    @pytest.mark.asyncio
    async def test_climbs_with_categories(self, db_session, seed_user):
        """Climbs JSONB with category data serializes correctly."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 1000)"
        climbs = [
            {
                "name": "Alpe d'Huez",
                "start_m": 0,
                "end_m": 13800,
                "distance_m": 13800,
                "avg_grade_pct": 8.1,
                "elevation_gain_m": 1118,
                "category": "HC",
            },
            {
                "name": "Small Hill",
                "start_m": 20000,
                "end_m": 21000,
                "distance_m": 1000,
                "avg_grade_pct": 4.0,
                "elevation_gain_m": 40,
                "category": "4",
            },
        ]

        course = RaceCourse(
            user_id=seed_user.id,
            name="Climbs Test",
            source_type="manual",
            distance_m=50000.0,
            elevation_gain_m=1200.0,
            elevation_loss_m=1200.0,
            geometry=wkt,
            climbs=climbs,
        )
        db_session.add(course)
        await db_session.commit()

        # Re-fetch from database
        result = await db_session.execute(select(RaceCourse).where(RaceCourse.id == course.id))
        fetched = result.scalar_one()

        assert len(fetched.climbs) == 2
        assert fetched.climbs[0]["name"] == "Alpe d'Huez"
        assert fetched.climbs[0]["category"] == "HC"
        assert fetched.climbs[1]["category"] == "4"

    @pytest.mark.asyncio
    async def test_null_jsonb_fields(self, db_session, seed_user):
        """Course can be created with NULL JSONB fields."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"

        course = RaceCourse(
            user_id=seed_user.id,
            name="No JSONB Test",
            source_type="gpx",
            distance_m=1000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
            elevation_profile=None,
            segments=None,
            climbs=None,
        )
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)

        assert course.elevation_profile is None
        assert course.segments is None
        assert course.climbs is None
