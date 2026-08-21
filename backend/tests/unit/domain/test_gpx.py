"""Unit tests for GPX and FIT course parsing."""

from pathlib import Path

import pytest

from trainingdash.domain.gpx import (
    CoursePoint,
    FITParseError,
    GPXParseError,
    ParsedCourse,
    parse_fit_course,
    parse_gpx,
    _haversine_distance,
)


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "courses"


class TestHaversineDistance:
    """Tests for the Haversine distance calculation."""

    def test_same_point_zero_distance(self):
        """Same point should have zero distance."""
        dist = _haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
        assert dist == 0.0

    def test_known_distance(self):
        """Test against a known distance (SF to LA ~559km)."""
        # San Francisco
        sf_lat, sf_lon = 37.7749, -122.4194
        # Los Angeles
        la_lat, la_lon = 34.0522, -118.2437

        dist = _haversine_distance(sf_lat, sf_lon, la_lat, la_lon)
        # Should be approximately 559 km
        assert 550_000 < dist < 570_000

    def test_short_distance(self):
        """Test a short distance (~150m)."""
        # Two points roughly 150m apart
        dist = _haversine_distance(37.7749, -122.4194, 37.7759, -122.4184)
        assert 140 < dist < 160


class TestParseGPX:
    """Tests for GPX parsing."""

    def test_parse_gpx_with_elevation(self):
        """Parse a GPX file with elevation data."""
        gpx_path = FIXTURES_DIR / "simple_with_elevation.gpx"
        gpx_content = gpx_path.read_text()

        result = parse_gpx(gpx_content)

        assert result.name == "Test Course With Elevation"
        assert len(result.points) == 4
        assert result.has_elevation is True
        assert result.total_distance_m > 0

        # Check first point
        assert result.points[0].latitude == 37.7749
        assert result.points[0].longitude == -122.4194
        assert result.points[0].elevation_m == 10.0
        assert result.points[0].distance_m == 0.0

        # Check cumulative distance increases
        for i in range(1, len(result.points)):
            assert result.points[i].distance_m > result.points[i - 1].distance_m

    def test_parse_gpx_without_elevation(self):
        """Parse a GPX file without elevation data."""
        gpx_path = FIXTURES_DIR / "simple_no_elevation.gpx"
        gpx_content = gpx_path.read_text()

        result = parse_gpx(gpx_content)

        assert result.name == "Flat Course"
        assert len(result.points) == 3
        assert result.has_elevation is False

        # All elevations should be None
        for point in result.points:
            assert point.elevation_m is None

    def test_parse_gpx_multiple_tracks(self):
        """Parse a GPX file with multiple tracks (uses first track only)."""
        gpx_path = FIXTURES_DIR / "multiple_tracks.gpx"
        gpx_content = gpx_path.read_text()

        result = parse_gpx(gpx_content)

        # Should only have points from first track
        assert len(result.points) == 2
        assert result.has_elevation is True
        # Name comes from metadata
        assert result.name == "Multi-Track Course"

    def test_parse_gpx_bytes_input(self):
        """Parse GPX from bytes input."""
        gpx_path = FIXTURES_DIR / "simple_with_elevation.gpx"
        gpx_content = gpx_path.read_bytes()

        result = parse_gpx(gpx_content)

        assert result.name == "Test Course With Elevation"
        assert len(result.points) == 4

    def test_parse_gpx_malformed_raises_error(self):
        """Malformed GPX should raise GPXParseError."""
        gpx_path = FIXTURES_DIR / "malformed.gpx"
        gpx_content = gpx_path.read_text()

        with pytest.raises(GPXParseError, match="Failed to parse GPX"):
            parse_gpx(gpx_content)

    def test_parse_gpx_empty_track_raises_error(self):
        """Empty GPX track should raise GPXParseError."""
        gpx_path = FIXTURES_DIR / "empty_track.gpx"
        gpx_content = gpx_path.read_text()

        with pytest.raises(GPXParseError, match="no track points"):
            parse_gpx(gpx_content)

    def test_parse_gpx_name_fallback_to_track(self):
        """If no metadata name, should use track name."""
        gpx_path = FIXTURES_DIR / "simple_no_elevation.gpx"
        gpx_content = gpx_path.read_text()

        result = parse_gpx(gpx_content)

        # No metadata name, should use track name
        assert result.name == "Flat Course"


class TestParseFITCourse:
    """Tests for FIT course parsing."""

    def test_parse_fit_activity_as_course(self):
        """Parse a FIT activity file as a course."""
        fit_path = FIXTURES_DIR / "activity_as_course.fit"
        fit_content = fit_path.read_bytes()

        result = parse_fit_course(fit_content)

        # Should have extracted points from record_mesgs
        assert len(result.points) > 0
        assert result.total_distance_m > 0
        # Activity files typically have elevation
        assert result.has_elevation is True

        # Check first point has valid coordinates
        first_point = result.points[0]
        assert -90 <= first_point.latitude <= 90
        assert -180 <= first_point.longitude <= 180

    def test_parse_fit_invalid_content(self):
        """Invalid FIT content should raise FITParseError."""
        with pytest.raises(FITParseError, match="FIT"):
            parse_fit_course(b"not a fit file")

    def test_parse_fit_empty_course(self):
        """FIT file with no records should raise FITParseError."""
        # This is a minimal valid-ish FIT header but no records
        # In practice this would fail decoding, but tests the error path
        with pytest.raises(FITParseError):
            parse_fit_course(b"\x0e\x10\x00\x00")


class TestCoursePointDataclass:
    """Tests for CoursePoint dataclass."""

    def test_course_point_creation(self):
        """Can create a CoursePoint."""
        point = CoursePoint(
            latitude=37.7749,
            longitude=-122.4194,
            elevation_m=100.5,
            distance_m=1500.0,
        )

        assert point.latitude == 37.7749
        assert point.longitude == -122.4194
        assert point.elevation_m == 100.5
        assert point.distance_m == 1500.0

    def test_course_point_none_elevation(self):
        """CoursePoint can have None elevation."""
        point = CoursePoint(
            latitude=37.7749,
            longitude=-122.4194,
            elevation_m=None,
            distance_m=0.0,
        )

        assert point.elevation_m is None


class TestParsedCourseDataclass:
    """Tests for ParsedCourse dataclass."""

    def test_parsed_course_creation(self):
        """Can create a ParsedCourse."""
        points = [
            CoursePoint(37.7749, -122.4194, 10.0, 0.0),
            CoursePoint(37.7759, -122.4184, 20.0, 150.0),
        ]

        course = ParsedCourse(
            name="Test Course",
            points=points,
            total_distance_m=150.0,
            has_elevation=True,
        )

        assert course.name == "Test Course"
        assert len(course.points) == 2
        assert course.total_distance_m == 150.0
        assert course.has_elevation is True

    def test_parsed_course_none_name(self):
        """ParsedCourse can have None name."""
        course = ParsedCourse(
            name=None,
            points=[],
            total_distance_m=0.0,
            has_elevation=False,
        )

        assert course.name is None
