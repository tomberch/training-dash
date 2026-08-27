"""Tests for segment geometry utilities."""

import math

import pytest

from trainingdash.domain.segment_geometry import (
    GradientSegment,
    SegmentGeometry,
    compute_bearing,
    compute_bounds,
    compute_elevation_stats,
    compute_gradient_segments,
    compute_segment_geometry,
    decode_polyline,
    encode_polyline,
    haversine_distance,
)


# =============================================================================
# Haversine Distance Tests
# =============================================================================


class TestHaversineDistance:
    """Tests for haversine_distance function."""

    def test_same_point_returns_zero(self):
        """Distance from a point to itself is zero."""
        dist = haversine_distance(46.95, 7.45, 46.95, 7.45)
        assert dist == 0.0

    def test_known_distance_bern_to_zurich(self):
        """Bern to Zurich is approximately 95km."""
        # Bern: 46.9480, 7.4474
        # Zurich: 47.3769, 8.5417
        dist = haversine_distance(46.9480, 7.4474, 47.3769, 8.5417)
        # Should be approximately 95km (allow 5% tolerance)
        assert 90000 < dist < 100000

    def test_known_distance_short(self):
        """Test a short distance (~100m)."""
        # Moving ~0.001 degrees lat at ~46°N is roughly 111m
        dist = haversine_distance(46.95, 7.45, 46.951, 7.45)
        assert 100 < dist < 120

    def test_equator_one_degree_longitude(self):
        """One degree longitude at equator is ~111km."""
        dist = haversine_distance(0.0, 0.0, 0.0, 1.0)
        assert 110000 < dist < 112000

    def test_symmetry(self):
        """Distance A to B equals distance B to A."""
        dist1 = haversine_distance(46.95, 7.45, 47.0, 7.5)
        dist2 = haversine_distance(47.0, 7.5, 46.95, 7.45)
        assert dist1 == pytest.approx(dist2)


# =============================================================================
# Bearing Tests
# =============================================================================


class TestComputeBearing:
    """Tests for compute_bearing function."""

    def test_north(self):
        """Moving due north should give bearing ~0°."""
        bearing = compute_bearing(46.0, 7.0, 47.0, 7.0)
        assert bearing == pytest.approx(0.0, abs=1.0)

    def test_east(self):
        """Moving due east should give bearing ~90°."""
        bearing = compute_bearing(46.0, 7.0, 46.0, 8.0)
        assert bearing == pytest.approx(90.0, abs=1.0)

    def test_south(self):
        """Moving due south should give bearing ~180°."""
        bearing = compute_bearing(47.0, 7.0, 46.0, 7.0)
        assert bearing == pytest.approx(180.0, abs=1.0)

    def test_west(self):
        """Moving due west should give bearing ~270°."""
        bearing = compute_bearing(46.0, 8.0, 46.0, 7.0)
        assert bearing == pytest.approx(270.0, abs=1.0)

    def test_northeast(self):
        """Moving northeast should give bearing ~45°."""
        bearing = compute_bearing(46.0, 7.0, 46.5, 7.5)
        assert 30 < bearing < 60

    def test_bearing_always_positive(self):
        """Bearing should always be 0-360."""
        bearing = compute_bearing(46.0, 7.0, 45.5, 6.5)  # Southwest
        assert 0 <= bearing < 360
        assert 200 < bearing < 250  # Should be around 225°

    def test_same_point(self):
        """Same point should return 0 (or any valid bearing)."""
        bearing = compute_bearing(46.0, 7.0, 46.0, 7.0)
        assert 0 <= bearing < 360


# =============================================================================
# Bounds Tests
# =============================================================================


class TestComputeBounds:
    """Tests for compute_bounds function."""

    def test_single_point(self):
        """Single point has bounds equal to itself."""
        bounds = compute_bounds([(46.0, 7.0)])
        assert bounds == (46.0, 7.0, 46.0, 7.0)

    def test_two_points(self):
        """Two points define the bounding box."""
        bounds = compute_bounds([(46.0, 7.0), (47.0, 8.0)])
        assert bounds == (46.0, 7.0, 47.0, 8.0)

    def test_multiple_points(self):
        """Multiple points find the extremes."""
        points = [
            (46.5, 7.5),  # middle
            (46.0, 7.0),  # SW
            (47.0, 8.0),  # NE
            (46.2, 7.8),  # another middle point
        ]
        bounds = compute_bounds(points)
        assert bounds == (46.0, 7.0, 47.0, 8.0)

    def test_empty_list_raises(self):
        """Empty list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            compute_bounds([])

    def test_order_independent(self):
        """Bounds should be same regardless of point order."""
        points1 = [(46.0, 7.0), (47.0, 8.0), (46.5, 7.5)]
        points2 = [(46.5, 7.5), (47.0, 8.0), (46.0, 7.0)]
        assert compute_bounds(points1) == compute_bounds(points2)


# =============================================================================
# Elevation Stats Tests
# =============================================================================


class TestComputeElevationStats:
    """Tests for compute_elevation_stats function."""

    def test_steady_climb(self):
        """Steady 10% climb over 1000m should show correct stats."""
        altitudes = [0, 25, 50, 75, 100]  # 100m gain
        distances = [0, 250, 500, 750, 1000]  # 1000m distance
        gain, avg, max_grade = compute_elevation_stats(altitudes, distances)

        assert gain == pytest.approx(100.0)
        assert avg == pytest.approx(10.0)  # 100m / 1000m = 10%
        assert max_grade == pytest.approx(10.0)

    def test_variable_grade(self):
        """Variable grade should track max correctly."""
        altitudes = [0, 10, 30, 40, 50]  # gains: 10, 20, 10, 10
        distances = [0, 100, 200, 300, 400]  # each segment 100m
        gain, avg, max_grade = compute_elevation_stats(altitudes, distances)

        assert gain == pytest.approx(50.0)
        assert avg == pytest.approx(12.5)  # 50m / 400m = 12.5%
        assert max_grade == pytest.approx(20.0)  # 20m / 100m = 20%

    def test_climb_with_descent(self):
        """Descent should not count toward gain."""
        altitudes = [0, 50, 30, 60]  # +50, -20, +30 = 80m gain
        distances = [0, 100, 200, 300]
        gain, avg, max_grade = compute_elevation_stats(altitudes, distances)

        assert gain == pytest.approx(80.0)  # Only positive changes
        assert avg == pytest.approx(20.0)  # 60m net / 300m = 20%

    def test_flat_segment(self):
        """Flat segment should have 0% grade."""
        altitudes = [100, 100, 100]
        distances = [0, 500, 1000]
        gain, avg, max_grade = compute_elevation_stats(altitudes, distances)

        assert gain == 0.0
        assert avg == 0.0
        assert max_grade == 0.0

    def test_descent_only(self):
        """Pure descent has no gain but negative avg grade."""
        altitudes = [100, 75, 50, 25, 0]
        distances = [0, 250, 500, 750, 1000]
        gain, avg, max_grade = compute_elevation_stats(altitudes, distances)

        assert gain == 0.0  # No positive elevation change
        assert avg == pytest.approx(-10.0)  # -100m / 1000m = -10%
        assert max_grade == 0.0  # Max of negative grades is 0

    def test_different_lengths_raises(self):
        """Different length lists should raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            compute_elevation_stats([0, 100], [0, 500, 1000])

    def test_single_point_raises(self):
        """Single point should raise ValueError."""
        with pytest.raises(ValueError, match="at least 2"):
            compute_elevation_stats([100], [0])


# =============================================================================
# Gradient Segments Tests
# =============================================================================


class TestComputeGradientSegments:
    """Tests for compute_gradient_segments function."""

    def test_even_segments(self):
        """Records divide evenly into segments."""
        records = [
            {"altitude_m": 0, "distance_m": 0},
            {"altitude_m": 5, "distance_m": 50},
            {"altitude_m": 10, "distance_m": 100},
            {"altitude_m": 15, "distance_m": 150},
            {"altitude_m": 20, "distance_m": 200},
        ]
        segments = compute_gradient_segments(records, segment_length_m=50)

        assert len(segments) == 4
        for seg in segments:
            assert seg.distance_m == pytest.approx(50, abs=1)
            assert seg.grade_pct == pytest.approx(10.0)  # 5m / 50m = 10%

    def test_uneven_final_segment(self):
        """Final segment may be shorter than target length."""
        records = [
            {"altitude_m": 0, "distance_m": 0},
            {"altitude_m": 5, "distance_m": 50},
            {"altitude_m": 7, "distance_m": 70},  # Only 20m more
        ]
        segments = compute_gradient_segments(records, segment_length_m=50)

        assert len(segments) == 2
        assert segments[0].distance_m == pytest.approx(50)
        assert segments[1].distance_m == pytest.approx(20)

    def test_variable_grades(self):
        """Variable grades should be computed per segment."""
        records = [
            {"altitude_m": 0, "distance_m": 0},
            {"altitude_m": 10, "distance_m": 100},  # 10%
            {"altitude_m": 15, "distance_m": 200},  # 5%
            {"altitude_m": 30, "distance_m": 300},  # 15%
        ]
        segments = compute_gradient_segments(records, segment_length_m=100)

        assert len(segments) == 3
        assert segments[0].grade_pct == pytest.approx(10.0)
        assert segments[1].grade_pct == pytest.approx(5.0)
        assert segments[2].grade_pct == pytest.approx(15.0)

    def test_empty_records(self):
        """Empty records returns empty list."""
        segments = compute_gradient_segments([])
        assert segments == []

    def test_single_record(self):
        """Single record returns empty list."""
        segments = compute_gradient_segments([{"altitude_m": 0, "distance_m": 0}])
        assert segments == []

    def test_segment_shorter_than_threshold(self):
        """Very short segment should still be included."""
        records = [
            {"altitude_m": 0, "distance_m": 0},
            {"altitude_m": 1, "distance_m": 10},  # Only 10m
        ]
        segments = compute_gradient_segments(records, segment_length_m=50)

        # Should have one short segment
        assert len(segments) == 1
        assert segments[0].distance_m == pytest.approx(10)


# =============================================================================
# Polyline Encode/Decode Tests
# =============================================================================


class TestPolylineEncoding:
    """Tests for polyline encode/decode (re-exported from polyline.py)."""

    def test_round_trip(self):
        """Encoding then decoding should return original coords."""
        original = [(46.95, 7.45), (46.96, 7.46), (46.97, 7.47)]
        encoded = encode_polyline(original)
        decoded = decode_polyline(encoded)

        assert len(decoded) == len(original)
        for (lat1, lon1), (lat2, lon2) in zip(original, decoded):
            assert lat1 == pytest.approx(lat2, abs=0.00001)
            assert lon1 == pytest.approx(lon2, abs=0.00001)

    def test_empty_list(self):
        """Empty list encodes to empty string."""
        assert encode_polyline([]) == ""
        assert decode_polyline("") == []

    def test_single_point(self):
        """Single point round-trips correctly."""
        original = [(46.95, 7.45)]
        encoded = encode_polyline(original)
        decoded = decode_polyline(encoded)

        assert len(decoded) == 1
        assert decoded[0][0] == pytest.approx(46.95, abs=0.00001)
        assert decoded[0][1] == pytest.approx(7.45, abs=0.00001)


# =============================================================================
# Compute Segment Geometry Tests
# =============================================================================


class TestComputeSegmentGeometry:
    """Tests for compute_segment_geometry main function."""

    @pytest.fixture
    def sample_records(self) -> list[dict]:
        """Sample GPS records for a short climb."""
        return [
            {"lat": 46.90, "lon": 7.40, "altitude_m": 500, "distance_m": 0},
            {"lat": 46.91, "lon": 7.41, "altitude_m": 510, "distance_m": 150},
            {"lat": 46.92, "lon": 7.42, "altitude_m": 525, "distance_m": 300},
            {"lat": 46.93, "lon": 7.43, "altitude_m": 545, "distance_m": 450},
            {"lat": 46.94, "lon": 7.44, "altitude_m": 570, "distance_m": 600},
            {"lat": 46.95, "lon": 7.45, "altitude_m": 600, "distance_m": 750},
        ]

    def test_basic_geometry(self, sample_records):
        """Test basic geometry computation."""
        geom = compute_segment_geometry(sample_records, start_index=0, end_index=5)

        assert geom.start_lat == 46.90
        assert geom.start_lon == 7.40
        assert geom.end_lat == 46.95
        assert geom.end_lon == 7.45
        assert geom.distance_m == pytest.approx(750.0)
        assert geom.elevation_gain_m == pytest.approx(100.0)

    def test_bounds_computed(self, sample_records):
        """Test bounding box computation."""
        geom = compute_segment_geometry(sample_records, start_index=0, end_index=5)

        min_lat, min_lon, max_lat, max_lon = geom.bounds
        assert min_lat == 46.90
        assert min_lon == 7.40
        assert max_lat == 46.95
        assert max_lon == 7.45

    def test_bearing_computed(self, sample_records):
        """Test bearing is computed and normalized."""
        geom = compute_segment_geometry(sample_records, start_index=0, end_index=5)

        # Going NE from (46.90, 7.40) to (46.95, 7.45)
        assert 0 < geom.direction_bearing < 90  # NE quadrant

    def test_polyline_generated(self, sample_records):
        """Test polyline is generated and decodable."""
        geom = compute_segment_geometry(sample_records, start_index=0, end_index=5)

        assert geom.polyline  # Not empty
        decoded = decode_polyline(geom.polyline)
        assert len(decoded) == 6  # All 6 points

    def test_gradient_segments_generated(self, sample_records):
        """Test gradient segments are generated."""
        geom = compute_segment_geometry(
            sample_records, start_index=0, end_index=5, gradient_segment_length_m=150
        )

        # 750m / 150m = 5 segments expected
        assert len(geom.gradient_segments) == 5

    def test_subset_of_records(self, sample_records):
        """Test using a subset via start/end indices."""
        geom = compute_segment_geometry(sample_records, start_index=1, end_index=4)

        assert geom.start_lat == 46.91
        assert geom.end_lat == 46.94
        # Index 1 has distance_m=150, index 4 has distance_m=600 → 450m
        assert geom.distance_m == pytest.approx(600.0 - 150.0)  # 450m

    def test_invalid_start_index_raises(self, sample_records):
        """Negative start index should raise."""
        with pytest.raises(ValueError, match="Invalid indices"):
            compute_segment_geometry(sample_records, start_index=-1, end_index=5)

    def test_invalid_end_index_raises(self, sample_records):
        """End index beyond records should raise."""
        with pytest.raises(ValueError, match="Invalid indices"):
            compute_segment_geometry(sample_records, start_index=0, end_index=10)

    def test_start_equals_end_raises(self, sample_records):
        """Start >= end should raise."""
        with pytest.raises(ValueError, match="less than"):
            compute_segment_geometry(sample_records, start_index=3, end_index=3)

    def test_start_greater_than_end_raises(self, sample_records):
        """Start > end should raise."""
        with pytest.raises(ValueError, match="less than"):
            compute_segment_geometry(sample_records, start_index=4, end_index=2)

    def test_minimum_two_points(self):
        """Minimum two points required."""
        records = [
            {"lat": 46.90, "lon": 7.40, "altitude_m": 500, "distance_m": 0},
            {"lat": 46.91, "lon": 7.41, "altitude_m": 510, "distance_m": 150},
        ]
        geom = compute_segment_geometry(records, start_index=0, end_index=1)
        assert geom.distance_m == pytest.approx(150.0)

    def test_missing_altitude_handled(self):
        """Records without altitude should still compute geometry."""
        records = [
            {"lat": 46.90, "lon": 7.40, "distance_m": 0},
            {"lat": 46.91, "lon": 7.41, "distance_m": 150},
            {"lat": 46.92, "lon": 7.42, "distance_m": 300},
        ]
        geom = compute_segment_geometry(records, start_index=0, end_index=2)

        assert geom.distance_m == pytest.approx(300.0)
        assert geom.elevation_gain_m == 0.0  # No altitude data
        assert geom.avg_grade_pct == 0.0
        assert geom.max_grade_pct == 0.0

    def test_avg_and_max_grade(self, sample_records):
        """Test grade calculations."""
        geom = compute_segment_geometry(sample_records, start_index=0, end_index=5)

        # 100m elevation over 750m = 13.3% average
        assert geom.avg_grade_pct == pytest.approx(13.33, abs=0.1)
        # Max segment has the steepest grade
        assert geom.max_grade_pct > 0

    def test_distance_computed_from_gps_if_missing(self):
        """Distance computed from GPS when distance_m not available."""
        records = [
            {"lat": 46.90, "lon": 7.40, "altitude_m": 500},
            {"lat": 46.91, "lon": 7.40, "altitude_m": 510},  # ~1.1km north
        ]
        geom = compute_segment_geometry(records, start_index=0, end_index=1)

        # Should be roughly 1.1km (0.01 degrees latitude)
        assert 1000 < geom.distance_m < 1200


class TestSegmentGeometryDataclass:
    """Tests for SegmentGeometry dataclass."""

    def test_dataclass_fields(self):
        """Verify all expected fields exist."""
        geom = SegmentGeometry(
            polyline="test",
            start_lat=46.0,
            start_lon=7.0,
            end_lat=47.0,
            end_lon=8.0,
            bounds=(46.0, 7.0, 47.0, 8.0),
            direction_bearing=45.0,
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[GradientSegment(500.0, 10.0)],
        )

        assert geom.polyline == "test"
        assert geom.start_lat == 46.0
        assert geom.bounds == (46.0, 7.0, 47.0, 8.0)
        assert len(geom.gradient_segments) == 1


class TestGradientSegmentDataclass:
    """Tests for GradientSegment dataclass."""

    def test_dataclass_fields(self):
        """Verify fields exist and are correct types."""
        seg = GradientSegment(distance_m=100.0, grade_pct=8.5)
        assert seg.distance_m == 100.0
        assert seg.grade_pct == 8.5
