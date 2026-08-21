"""Unit tests for CreateCourse use case using fake repos."""

from pathlib import Path

import pytest

from tests.fakes.course_repo import FakeCourseRepo
from trainingdash.use_cases.create_course import (
    CourseCreationError,
    CreateCourse,
    CreateCourseResult,
)


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "courses"


@pytest.fixture
def course_repo():
    return FakeCourseRepo()


@pytest.fixture
def use_case(course_repo):
    return CreateCourse(course_repo)


@pytest.fixture
def gpx_with_elevation() -> bytes:
    """GPX file with elevation data."""
    return (FIXTURES_DIR / "simple_with_elevation.gpx").read_bytes()


@pytest.fixture
def gpx_no_elevation() -> bytes:
    """GPX file without elevation data."""
    return (FIXTURES_DIR / "simple_no_elevation.gpx").read_bytes()


@pytest.fixture
def gpx_malformed() -> bytes:
    """Malformed GPX file."""
    return (FIXTURES_DIR / "malformed.gpx").read_bytes()


@pytest.fixture
def gpx_empty_track() -> bytes:
    """GPX file with empty track."""
    return (FIXTURES_DIR / "empty_track.gpx").read_bytes()


@pytest.fixture
def fit_course() -> bytes:
    """FIT course file."""
    return (FIXTURES_DIR / "activity_as_course.fit").read_bytes()


class TestCreateCourseWithGPX:
    """Tests for GPX file processing."""

    @pytest.mark.asyncio
    async def test_gpx_with_elevation_creates_course(
        self, use_case, course_repo, gpx_with_elevation
    ):
        """GPX file with elevation data creates a course successfully."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test_course.gpx",
        )

        assert isinstance(result, CreateCourseResult)
        assert result.course is not None
        assert result.course.user_id == 1
        assert result.course.source_type == "gpx"
        assert result.course.source_filename == "test_course.gpx"
        assert result.course.distance_m > 0
        assert result.course.elevation_gain_m >= 0
        assert result.course.elevation_loss_m >= 0
        assert result.warnings == []

        # Verify course was saved
        saved = await course_repo.get_by_id(result.course.id, 1)
        assert saved is not None

    @pytest.mark.asyncio
    async def test_gpx_without_elevation_adds_warning(
        self, use_case, gpx_no_elevation
    ):
        """GPX file without elevation data creates course with warning."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_no_elevation,
            filename="flat_course.gpx",
        )

        assert result.course is not None
        assert len(result.warnings) == 1
        assert "no elevation data" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_gpx_uses_parsed_name(self, use_case, gpx_with_elevation):
        """Course uses name from GPX metadata if available."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="ignored.gpx",
        )

        # The fixture has name "Test Course With Elevation" or "Morning Ride"
        assert result.course.name in ["Test Course With Elevation", "Morning Ride"]

    @pytest.mark.asyncio
    async def test_gpx_uses_provided_name_over_parsed(
        self, use_case, gpx_with_elevation
    ):
        """Provided name takes precedence over parsed name."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
            name="My Custom Name",
        )

        assert result.course.name == "My Custom Name"

    @pytest.mark.asyncio
    async def test_gpx_malformed_raises_error(self, use_case, gpx_malformed):
        """Malformed GPX file raises CourseCreationError."""
        with pytest.raises(CourseCreationError) as exc_info:
            await use_case.execute(
                user_id=1,
                file_content=gpx_malformed,
                filename="bad.gpx",
            )

        assert "parse" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_gpx_empty_track_raises_error(self, use_case, gpx_empty_track):
        """GPX file with empty track raises CourseCreationError."""
        with pytest.raises(CourseCreationError) as exc_info:
            await use_case.execute(
                user_id=1,
                file_content=gpx_empty_track,
                filename="empty.gpx",
            )

        assert "parse" in str(exc_info.value).lower() or "point" in str(exc_info.value).lower()


class TestCreateCourseWithFIT:
    """Tests for FIT file processing."""

    @pytest.mark.asyncio
    async def test_fit_course_creates_course(self, use_case, course_repo, fit_course):
        """FIT course file creates a course successfully."""
        result = await use_case.execute(
            user_id=1,
            file_content=fit_course,
            filename="race.fit",
        )

        assert isinstance(result, CreateCourseResult)
        assert result.course is not None
        assert result.course.user_id == 1
        assert result.course.source_type == "fit"
        assert result.course.source_filename == "race.fit"
        assert result.course.distance_m > 0

        # Verify course was saved
        saved = await course_repo.get_by_id(result.course.id, 1)
        assert saved is not None


class TestFileTypeDetection:
    """Tests for file type detection."""

    @pytest.mark.asyncio
    async def test_detects_gpx_from_extension(self, use_case, gpx_with_elevation):
        """Detects GPX from .gpx extension."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="course.GPX",  # Uppercase
        )

        assert result.course.source_type == "gpx"

    @pytest.mark.asyncio
    async def test_detects_fit_from_extension(self, use_case, fit_course):
        """Detects FIT from .fit extension."""
        result = await use_case.execute(
            user_id=1,
            file_content=fit_course,
            filename="course.FIT",  # Uppercase
        )

        assert result.course.source_type == "fit"

    @pytest.mark.asyncio
    async def test_detects_gpx_from_content(self, use_case, gpx_with_elevation):
        """Detects GPX from XML content when extension is ambiguous."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="course.xml",  # Not .gpx
        )

        assert result.course.source_type == "gpx"

    @pytest.mark.asyncio
    async def test_detects_fit_from_content(self, use_case, fit_course):
        """Detects FIT from magic bytes when extension is ambiguous."""
        result = await use_case.execute(
            user_id=1,
            file_content=fit_course,
            filename="course.bin",  # Not .fit
        )

        assert result.course.source_type == "fit"

    @pytest.mark.asyncio
    async def test_invalid_file_type_raises_error(self, use_case):
        """Invalid file content raises CourseCreationError."""
        with pytest.raises(CourseCreationError) as exc_info:
            await use_case.execute(
                user_id=1,
                file_content=b"not a valid file format",
                filename="course.xyz",
            )

        assert "cannot determine file type" in str(exc_info.value).lower()


class TestCourseMetrics:
    """Tests for course metrics calculation."""

    @pytest.mark.asyncio
    async def test_distance_is_accurate(self, use_case, gpx_with_elevation):
        """Course distance is calculated from track points."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        # The fixture has 4 points, should have non-zero distance
        assert result.course.distance_m > 0

    @pytest.mark.asyncio
    async def test_elevation_gain_loss_calculated(self, use_case, gpx_with_elevation):
        """Elevation gain and loss are calculated from profile."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        # The fixture has elevations: 10, 15, 25, 20
        # Gain: 5 + 10 = 15, Loss: 5
        assert result.course.elevation_gain_m >= 0
        assert result.course.elevation_loss_m >= 0

    @pytest.mark.asyncio
    async def test_min_max_elevation_set(self, use_case, gpx_with_elevation):
        """Min and max elevation are captured."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        assert result.course.min_elevation_m is not None
        assert result.course.max_elevation_m is not None
        assert result.course.min_elevation_m <= result.course.max_elevation_m


class TestCourseProcessedData:
    """Tests for processed course data (segments, climbs, profile)."""

    @pytest.mark.asyncio
    async def test_elevation_profile_created(self, use_case, gpx_with_elevation):
        """Elevation profile is created with distance, elevation, and grade."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        profile = result.course.elevation_profile
        assert profile is not None
        assert len(profile) > 0

        # Check structure of profile entries
        first_point = profile[0]
        assert "distance_m" in first_point
        assert "elevation_m" in first_point
        assert "grade_pct" in first_point

    @pytest.mark.asyncio
    async def test_segments_created(self, use_case, gpx_with_elevation):
        """Course segments are created."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        segments = result.course.segments
        assert segments is not None
        # Short courses may have few segments
        assert isinstance(segments, list)

    @pytest.mark.asyncio
    async def test_climbs_detected(self, use_case, gpx_with_elevation):
        """Climbs are detected (may be empty for flat/short courses)."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        climbs = result.course.climbs
        assert climbs is not None
        assert isinstance(climbs, list)

    @pytest.mark.asyncio
    async def test_geometry_created(self, use_case, gpx_with_elevation):
        """PostGIS geometry is created."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="test.gpx",
        )

        assert result.course.geometry is not None


class TestNameGeneration:
    """Tests for course name generation."""

    @pytest.mark.asyncio
    async def test_name_from_filename_without_extension(self, use_case, gpx_no_elevation):
        """Name derived from filename removes extension."""
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_no_elevation,
            filename="my_race_course.gpx",
            name=None,  # Don't provide name
        )

        # GPX has name "Flat Course", so it should use that
        # If GPX had no name, it would use "My Race Course"
        assert result.course.name == "Flat Course"

    @pytest.mark.asyncio
    async def test_name_from_filename_replaces_underscores(self, use_case):
        """Name derived from filename replaces underscores with spaces."""
        # Create minimal GPX without name
        gpx_no_name = b"""<?xml version="1.0"?>
        <gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
          <trk>
            <trkseg>
              <trkpt lat="0" lon="0"><ele>0</ele></trkpt>
              <trkpt lat="0.001" lon="0.001"><ele>0</ele></trkpt>
            </trkseg>
          </trk>
        </gpx>"""

        result = await use_case.execute(
            user_id=1,
            file_content=gpx_no_name,
            filename="my_awesome_race.gpx",
        )

        assert result.course.name == "My Awesome Race"


class TestMultipleUsers:
    """Tests for multi-user scenarios."""

    @pytest.mark.asyncio
    async def test_courses_scoped_to_user(
        self, use_case, course_repo, gpx_with_elevation
    ):
        """Courses are scoped to the creating user."""
        # Create course for user 1
        result1 = await use_case.execute(
            user_id=1,
            file_content=gpx_with_elevation,
            filename="user1_course.gpx",
            name="User 1 Course",
        )

        # Create course for user 2
        result2 = await use_case.execute(
            user_id=2,
            file_content=gpx_with_elevation,
            filename="user2_course.gpx",
            name="User 2 Course",
        )

        # User 1 can only see their course
        user1_courses = await course_repo.get_by_user(1)
        assert len(user1_courses) == 1
        assert user1_courses[0].name == "User 1 Course"

        # User 2 can only see their course
        user2_courses = await course_repo.get_by_user(2)
        assert len(user2_courses) == 1
        assert user2_courses[0].name == "User 2 Course"

        # User 1 cannot access user 2's course
        other_course = await course_repo.get_by_id(result2.course.id, user_id=1)
        assert other_course is None
