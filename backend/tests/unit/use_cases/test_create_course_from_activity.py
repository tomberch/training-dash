"""Unit tests for CreateCourseFromActivity use case."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.course_repo import FakeCourseRepo
from tests.fakes.record_repo import FakeRecordRepo
from trainingdash.repositories.postgres.models import Activity, Record
from trainingdash.use_cases.create_course_from_activity import (
    CourseFromActivityError,
    CreateCourseFromActivity,
)


@pytest.fixture
def activity_repo():
    return FakeActivityRepo()


@pytest.fixture
def record_repo():
    return FakeRecordRepo()


@pytest.fixture
def course_repo():
    return FakeCourseRepo()


@pytest.fixture
def use_case(activity_repo, record_repo, course_repo):
    return CreateCourseFromActivity(activity_repo, record_repo, course_repo)


@pytest.fixture
def sample_activity() -> Activity:
    """Create a sample activity."""
    return Activity(
        id=uuid4(),
        user_id=1,
        title="Morning Ride",
        started_at=datetime(2024, 6, 15, 8, 0, 0, tzinfo=UTC),
        total_distance_m=10000.0,
        elapsed_time_s=1800,
        source="manual",
        source_ref="test-activity-001",
    )


def make_records(activity_id: UUID, count: int = 100, with_elevation: bool = True) -> list[Record]:
    """Generate test records with GPS data along a simple route.

    Creates a route going roughly northeast with gradual elevation changes.
    """
    records = []
    base_lat = 47.0
    base_lon = 8.0
    base_time = datetime(2024, 6, 15, 8, 0, 0, tzinfo=UTC)

    for i in range(count):
        # Move northeast, roughly 100m per point
        lat = base_lat + (i * 0.0009)  # ~100m north per point
        lon = base_lon + (i * 0.0012)  # ~100m east per point
        distance = i * 100.0  # 100m spacing

        # Create some elevation variation (climbing then descending)
        if with_elevation:
            if i < count // 2:
                elevation = 400 + (i * 2)  # Climb 2m per point
            else:
                elevation = 400 + ((count - i) * 2)  # Descend
        else:
            elevation = None

        record = Record(
            id=i + 1,
            activity_id=activity_id,
            timestamp=base_time + timedelta(seconds=i * 10),
            lat=lat,
            lon=lon,
            distance_m=distance,
            altitude_m=elevation,
            speed_mps=10.0,
        )
        records.append(record)

    return records


class TestCreateCourseFromActivitySuccess:
    """Tests for successful course creation from activity."""

    @pytest.mark.asyncio
    async def test_creates_course_from_activity(
        self, use_case, activity_repo, record_repo, course_repo, sample_activity
    ):
        """Successfully creates a course from an activity with GPS data."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        assert result.course is not None
        assert result.course.user_id == 1
        assert result.course.source_type == "activity"
        assert result.course.name == "Morning Ride"
        assert result.course.distance_m > 0
        assert result.warnings == []

        # Verify course was saved
        saved = await course_repo.get_by_id(result.course.id, 1)
        assert saved is not None

    @pytest.mark.asyncio
    async def test_uses_custom_name_when_provided(self, use_case, activity_repo, record_repo, sample_activity):
        """Uses provided name instead of activity title."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
            name="My Race Course",
        )

        assert result.course.name == "My Race Course"

    @pytest.mark.asyncio
    async def test_calculates_elevation_metrics(self, use_case, activity_repo, record_repo, sample_activity):
        """Calculates elevation gain, loss, min, and max."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50, with_elevation=True)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        assert result.course.elevation_gain_m >= 0
        assert result.course.elevation_loss_m >= 0
        assert result.course.min_elevation_m is not None
        assert result.course.max_elevation_m is not None
        assert result.course.min_elevation_m <= result.course.max_elevation_m

    @pytest.mark.asyncio
    async def test_warns_when_no_elevation_data(self, use_case, activity_repo, record_repo, sample_activity):
        """Adds warning when activity has no elevation data."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50, with_elevation=False)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        assert result.course is not None
        assert len(result.warnings) == 1
        assert "elevation" in result.warnings[0].lower()


class TestCourseSegmentsAndClimbs:
    """Tests for segment and climb detection."""

    @pytest.mark.asyncio
    async def test_creates_segments(self, use_case, activity_repo, record_repo, sample_activity):
        """Creates course segments from activity data."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=100)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        assert result.course.segments is not None
        assert isinstance(result.course.segments, list)

    @pytest.mark.asyncio
    async def test_segments_have_correct_structure(self, use_case, activity_repo, record_repo, sample_activity):
        """Segment dicts have the expected keys for JSONB storage."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=100)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        if result.course.segments:
            segment = result.course.segments[0]
            # These are the keys expected by the frontend and other use cases
            assert "start_m" in segment
            assert "end_m" in segment
            assert "distance_m" in segment
            assert "avg_grade_pct" in segment
            assert "elevation_gain_m" in segment
            assert "elevation_loss_m" in segment
            assert "terrain_type" in segment

    @pytest.mark.asyncio
    async def test_climbs_have_correct_structure(self, use_case, activity_repo, record_repo, sample_activity):
        """Climb dicts have the expected keys for JSONB storage."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=100)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        # Climbs list exists (may be empty for flat courses)
        assert result.course.climbs is not None
        assert isinstance(result.course.climbs, list)

        if result.course.climbs:
            climb = result.course.climbs[0]
            assert "name" in climb
            assert "start_m" in climb
            assert "end_m" in climb
            assert "distance_m" in climb
            assert "avg_grade_pct" in climb
            assert "elevation_gain_m" in climb
            assert "max_grade_pct" in climb
            assert "category" in climb


class TestElevationProfile:
    """Tests for elevation profile generation."""

    @pytest.mark.asyncio
    async def test_creates_elevation_profile(self, use_case, activity_repo, record_repo, sample_activity):
        """Creates elevation profile for charting."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        assert result.course.elevation_profile is not None
        assert len(result.course.elevation_profile) > 0

    @pytest.mark.asyncio
    async def test_elevation_profile_structure(self, use_case, activity_repo, record_repo, sample_activity):
        """Elevation profile entries have correct structure."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        point = result.course.elevation_profile[0]
        assert "distance_m" in point
        assert "elevation_m" in point
        assert "grade_pct" in point


class TestErrorCases:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_activity_not_found_raises_error(self, use_case):
        """Raises error when activity doesn't exist."""
        with pytest.raises(CourseFromActivityError) as exc_info:
            await use_case.execute(
                user_id=1,
                activity_id=str(uuid4()),
            )

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_insufficient_gps_points_raises_error(self, use_case, activity_repo, record_repo, sample_activity):
        """Raises error when activity has too few GPS points."""
        await activity_repo.save(sample_activity)
        # Only add 5 records (minimum is 10)
        records = make_records(sample_activity.id, count=5)
        record_repo.add_many(records)

        with pytest.raises(CourseFromActivityError) as exc_info:
            await use_case.execute(
                user_id=1,
                activity_id=str(sample_activity.id),
            )

        assert "few" in str(exc_info.value).lower() or "insufficient" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_no_gps_data_raises_error(self, use_case, activity_repo, record_repo, sample_activity):
        """Raises error when activity has no GPS coordinates."""
        await activity_repo.save(sample_activity)

        # Add records without GPS data
        records = []
        base_time = datetime(2024, 6, 15, 8, 0, 0, tzinfo=UTC)
        for i in range(50):
            record = Record(
                id=i + 1,
                activity_id=sample_activity.id,
                timestamp=base_time + timedelta(seconds=i * 10),
                lat=None,  # No GPS
                lon=None,
                distance_m=i * 100.0,
                altitude_m=400.0,
            )
            records.append(record)
        record_repo.add_many(records)

        with pytest.raises(CourseFromActivityError) as exc_info:
            await use_case.execute(
                user_id=1,
                activity_id=str(sample_activity.id),
            )

        assert "gps" in str(exc_info.value).lower() or "insufficient" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_wrong_user_cannot_access_activity(self, use_case, activity_repo, record_repo, sample_activity):
        """User cannot create course from another user's activity."""
        await activity_repo.save(sample_activity)  # user_id=1
        records = make_records(sample_activity.id, count=50)
        record_repo.add_many(records)

        with pytest.raises(CourseFromActivityError) as exc_info:
            await use_case.execute(
                user_id=999,  # Different user
                activity_id=str(sample_activity.id),
            )

        assert "not found" in str(exc_info.value).lower()


class TestGeometry:
    """Tests for PostGIS geometry creation."""

    @pytest.mark.asyncio
    async def test_creates_geometry(self, use_case, activity_repo, record_repo, sample_activity):
        """Creates PostGIS geometry from GPS track."""
        await activity_repo.save(sample_activity)
        records = make_records(sample_activity.id, count=50)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            activity_id=str(sample_activity.id),
        )

        assert result.course.geometry is not None
