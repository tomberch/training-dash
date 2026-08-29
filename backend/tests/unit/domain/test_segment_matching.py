"""Unit tests for segment matching algorithm."""

from uuid import uuid4

from trainingdash.domain.polyline import encode_polyline
from trainingdash.domain.segment_geometry import compute_bearing, haversine_distance
from trainingdash.domain.segment_matching import (
    SegmentCandidate,
    bearings_match,
    compute_path_overlap,
    match_activity_to_segments,
    point_to_segment_distance,
)

# =============================================================================
# Test Helpers
# =============================================================================


def make_records(coords: list[tuple[float, float]], start_distance: float = 0) -> list[dict]:
    """Create activity records from lat/lon coordinates.

    Automatically computes cumulative distance_m.
    """
    records = []
    cumulative_dist = start_distance

    for i, (lat, lon) in enumerate(coords):
        if i > 0:
            prev_lat, prev_lon = coords[i - 1]
            cumulative_dist += haversine_distance(prev_lat, prev_lon, lat, lon)

        records.append(
            {
                "lat": lat,
                "lon": lon,
                "distance_m": cumulative_dist,
            }
        )

    return records


def make_candidate(
    coords: list[tuple[float, float]],
    segment_id=None,
    direction_bearing: float | None = None,
) -> SegmentCandidate:
    """Create a segment candidate from coordinates."""
    if segment_id is None:
        segment_id = uuid4()

    polyline = encode_polyline(coords)
    start_lat, start_lon = coords[0]
    end_lat, end_lon = coords[-1]

    # Compute total distance
    total_dist = 0.0
    for i in range(1, len(coords)):
        total_dist += haversine_distance(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])

    if direction_bearing is None:
        direction_bearing = compute_bearing(start_lat, start_lon, end_lat, end_lon)

    return SegmentCandidate(
        id=segment_id,
        polyline=polyline,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        direction_bearing=direction_bearing,
        distance_m=total_dist,
    )


def offset_coords(
    coords: list[tuple[float, float]], lat_offset: float = 0, lon_offset: float = 0
) -> list[tuple[float, float]]:
    """Offset coordinates by given amounts (in degrees)."""
    return [(lat + lat_offset, lon + lon_offset) for lat, lon in coords]


# =============================================================================
# bearings_match tests
# =============================================================================


class TestBearingsMatch:
    """Tests for bearings_match function."""

    def test_same_bearing(self):
        """Identical bearings match."""
        assert bearings_match(45, 45, tolerance=30) is True

    def test_within_tolerance(self):
        """Bearings within tolerance match."""
        assert bearings_match(45, 60, tolerance=30) is True
        assert bearings_match(45, 20, tolerance=30) is True

    def test_outside_tolerance(self):
        """Bearings outside tolerance don't match."""
        assert bearings_match(45, 100, tolerance=30) is False
        assert bearings_match(0, 180, tolerance=30) is False

    def test_wraparound_near_zero(self):
        """Handles 360° wraparound correctly."""
        assert bearings_match(10, 350, tolerance=30) is True
        assert bearings_match(350, 10, tolerance=30) is True
        assert bearings_match(5, 355, tolerance=30) is True

    def test_wraparound_outside_tolerance(self):
        """Wraparound outside tolerance doesn't match."""
        assert bearings_match(10, 330, tolerance=30) is False
        assert bearings_match(330, 10, tolerance=30) is False

    def test_opposite_directions(self):
        """Opposite directions don't match."""
        assert bearings_match(0, 180, tolerance=30) is False
        assert bearings_match(90, 270, tolerance=30) is False
        assert bearings_match(45, 225, tolerance=30) is False

    def test_exact_tolerance_boundary(self):
        """Exact tolerance boundary matches."""
        assert bearings_match(0, 30, tolerance=30) is True
        assert bearings_match(0, 31, tolerance=30) is False

    def test_negative_normalization(self):
        """Handles bearings needing normalization."""
        # These would be unusual inputs but should work
        assert bearings_match(370, 10, tolerance=30) is True  # 370 % 360 = 10
        assert bearings_match(-10, 350, tolerance=30) is True  # -10 % 360 = 350


# =============================================================================
# point_to_segment_distance tests
# =============================================================================


class TestPointToSegmentDistance:
    """Tests for point_to_segment_distance function."""

    def test_point_at_segment_start(self):
        """Point at segment start has zero distance."""
        dist = point_to_segment_distance(
            47.0,
            8.0,  # point
            47.0,
            8.0,  # segment start
            47.001,
            8.001,  # segment end
        )
        assert dist < 1  # Within 1 meter

    def test_point_at_segment_end(self):
        """Point at segment end has zero distance."""
        dist = point_to_segment_distance(
            47.001,
            8.001,  # point
            47.0,
            8.0,  # segment start
            47.001,
            8.001,  # segment end
        )
        assert dist < 1

    def test_point_perpendicular_to_segment(self):
        """Point perpendicular to segment middle."""
        # Horizontal segment at lat 47.0 from lon 8.0 to 8.001
        # Point directly north of segment center
        dist = point_to_segment_distance(
            47.0001,
            8.0005,  # point north of center
            47.0,
            8.0,
            47.0,
            8.001,
        )
        # 0.0001 degrees latitude ≈ 11 meters
        assert 10 < dist < 15

    def test_point_beyond_segment_start(self):
        """Point beyond segment start projects to start."""
        # Horizontal segment
        dist = point_to_segment_distance(
            47.0,
            7.999,  # point west of segment start
            47.0,
            8.0,
            47.0,
            8.001,
        )
        # Should be distance to start point
        from trainingdash.domain.segment_geometry import haversine_distance

        expected = haversine_distance(47.0, 7.999, 47.0, 8.0)
        assert abs(dist - expected) < 5  # Within 5 meters

    def test_point_beyond_segment_end(self):
        """Point beyond segment end projects to end."""
        dist = point_to_segment_distance(
            47.0,
            8.002,  # point east of segment end
            47.0,
            8.0,
            47.0,
            8.001,
        )
        from trainingdash.domain.segment_geometry import haversine_distance

        expected = haversine_distance(47.0, 8.002, 47.0, 8.001)
        assert abs(dist - expected) < 5

    def test_zero_length_segment(self):
        """Zero-length segment returns distance to that point."""
        from trainingdash.domain.segment_geometry import haversine_distance

        dist = point_to_segment_distance(
            47.001,
            8.001,
            47.0,
            8.0,
            47.0,
            8.0,  # same as start
        )
        expected = haversine_distance(47.001, 8.001, 47.0, 8.0)
        assert abs(dist - expected) < 1

    def test_diagonal_segment(self):
        """Point near diagonal segment."""
        # Diagonal segment from (47.0, 8.0) to (47.001, 8.001)
        # Point slightly off the line
        dist = point_to_segment_distance(
            47.0005,
            8.0006,  # slightly east of center
            47.0,
            8.0,
            47.001,
            8.001,
        )
        # Should be small but nonzero
        assert 0 < dist < 20


# =============================================================================
# compute_path_overlap tests
# =============================================================================


class TestComputePathOverlap:
    """Tests for compute_path_overlap function."""

    def test_exact_overlap(self):
        """Activity exactly follows segment."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        records = make_records(segment_coords)
        polyline = encode_polyline(segment_coords)

        overlap = compute_path_overlap(records, 0, 2, polyline, buffer_m=35)
        assert overlap == 100.0

    def test_with_gps_wobble(self):
        """Activity with GPS wobble still matches."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        # Activity wobbles slightly but stays within 35m
        activity_coords = [
            (47.0, 8.00001),  # ~1m east
            (47.001, 7.99998),  # ~2m west
            (47.002, 8.00002),  # ~2m east
        ]
        records = make_records(activity_coords)
        polyline = encode_polyline(segment_coords)

        overlap = compute_path_overlap(records, 0, 2, polyline, buffer_m=35)
        assert overlap >= 90.0

    def test_parallel_road_no_overlap(self):
        """Parallel road 50m away has low overlap."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        # Activity 50m east (about 0.0005 degrees longitude at this latitude)
        activity_coords = offset_coords(segment_coords, lon_offset=0.0006)
        records = make_records(activity_coords)
        polyline = encode_polyline(segment_coords)

        overlap = compute_path_overlap(records, 0, 2, polyline, buffer_m=35)
        assert overlap < 90.0

    def test_partial_overlap(self):
        """Activity covers only part of segment."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        # Activity only covers first half
        activity_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
        ]
        records = make_records(activity_coords)
        polyline = encode_polyline(segment_coords)

        overlap = compute_path_overlap(records, 0, 1, polyline, buffer_m=35)
        # Should be around 50% (2 of 4 points covered)
        assert 40 < overlap < 60

    def test_empty_polyline(self):
        """Empty polyline returns 0."""
        records = make_records([(47.0, 8.0), (47.001, 8.0)])
        overlap = compute_path_overlap(records, 0, 1, "", buffer_m=35)
        assert overlap == 0.0

    def test_single_record(self):
        """Single record returns 0."""
        records = [{"lat": 47.0, "lon": 8.0, "distance_m": 0}]
        polyline = encode_polyline([(47.0, 8.0), (47.001, 8.0)])
        overlap = compute_path_overlap(records, 0, 0, polyline, buffer_m=35)
        assert overlap == 0.0


# =============================================================================
# match_activity_to_segments tests
# =============================================================================


class TestMatchActivityToSegments:
    """Tests for match_activity_to_segments function."""

    def test_exact_match(self):
        """Activity exactly follows segment."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        records = make_records(segment_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 1
        assert matches[0].segment_id == candidate.id
        assert matches[0].start_index == 0
        assert matches[0].end_index == 3
        assert matches[0].overlap_pct >= 90

    def test_match_with_gps_wobble(self):
        """Activity with GPS wobble within 35m buffer matches."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        # Wobbling activity (within buffer)
        activity_coords = [
            (47.0, 8.00002),
            (47.001, 7.99998),
            (47.002, 8.00003),
            (47.003, 7.99999),
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 1
        assert matches[0].overlap_pct >= 90

    def test_no_match_parallel_road(self):
        """Parallel road 50m away doesn't match."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        # Activity 60m east
        activity_coords = offset_coords(segment_coords, lon_offset=0.0008)
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 0

    def test_no_match_opposite_direction(self):
        """Opposite direction doesn't match."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        # Activity goes in reverse
        activity_coords = list(reversed(segment_coords))
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 0

    def test_multiple_crossings_loop_ride(self):
        """Loop ride crossing same segment twice produces multiple matches."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        # Activity: approach, cross segment, loop away far enough, cross again
        # The loop must be far enough that the full loop path doesn't match
        activity_coords = [
            # First crossing
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            # Loop away (far enough to break overlap)
            (47.002, 8.003),
            (47.001, 8.003),
            (47.0, 8.003),
            # Come back
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        # Should find at least two matches (may find more depending on overlap)
        assert len(matches) >= 2
        assert all(m.segment_id == candidate.id for m in matches)
        # First and last match should have different start indices
        assert matches[0].start_index < matches[-1].start_index

    def test_partial_overlap_below_threshold(self):
        """Less than 90% overlap doesn't match."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
            (47.004, 8.0),
        ]
        # Activity only covers first 40%
        activity_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),  # ends here, missing 40%
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate], min_overlap_pct=90)

        assert len(matches) == 0

    def test_segment_at_activity_start(self):
        """Segment at the start of activity."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
        ]
        # Activity continues past segment
        activity_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 1
        assert matches[0].start_index == 0
        assert matches[0].end_index == 1

    def test_segment_at_activity_end(self):
        """Segment at the end of activity."""
        segment_coords = [
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        activity_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 1
        assert matches[0].start_index == 2
        assert matches[0].end_index == 3

    def test_very_short_segment(self):
        """Very short segment can match."""
        # ~100m segment
        segment_coords = [
            (47.0, 8.0),
            (47.0009, 8.0),  # about 100m north
        ]
        activity_coords = [
            (46.999, 8.0),
            (47.0, 8.0),
            (47.0009, 8.0),
            (47.002, 8.0),
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        assert len(matches) == 1

    def test_no_candidates(self):
        """Empty candidates returns empty matches."""
        records = make_records([(47.0, 8.0), (47.001, 8.0)])
        matches = match_activity_to_segments(records, [])
        assert matches == []

    def test_single_record(self):
        """Single record returns empty matches."""
        records = [{"lat": 47.0, "lon": 8.0, "distance_m": 0}]
        candidate = make_candidate([(47.0, 8.0), (47.001, 8.0)])
        matches = match_activity_to_segments(records, [candidate])
        assert matches == []

    def test_records_missing_coordinates(self):
        """Records with missing coordinates are skipped."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        records = [
            {"lat": 47.0, "lon": 8.0, "distance_m": 0},
            {"lat": None, "lon": None, "distance_m": 100},  # bad record
            {"lat": 47.001, "lon": 8.0, "distance_m": 111},
            {"lat": 47.002, "lon": 8.0, "distance_m": 222},
        ]
        candidate = make_candidate(segment_coords)

        matches = match_activity_to_segments(records, [candidate])

        # Should still match despite bad record
        assert len(matches) == 1

    def test_multiple_segments_same_location(self):
        """Can match multiple different segments in same area."""
        # Two segments that share start but diverge
        segment1_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        segment2_coords = [
            (47.002, 8.0),
            (47.003, 8.0),
            (47.004, 8.0),
        ]

        # Activity covers both
        activity_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
            (47.004, 8.0),
        ]
        records = make_records(activity_coords)
        candidate1 = make_candidate(segment1_coords)
        candidate2 = make_candidate(segment2_coords)

        matches = match_activity_to_segments(records, [candidate1, candidate2])

        assert len(matches) == 2
        segment_ids = {m.segment_id for m in matches}
        assert candidate1.id in segment_ids
        assert candidate2.id in segment_ids

    def test_custom_tolerances(self):
        """Custom tolerances are respected."""
        segment_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        # Activity starts 30m away from segment start
        activity_coords = [
            (47.00027, 8.0),  # ~30m north
            (47.001, 8.0),
            (47.002, 8.0),
        ]
        records = make_records(activity_coords)
        candidate = make_candidate(segment_coords)

        # With default 25m tolerance, shouldn't match
        matches_default = match_activity_to_segments(records, [candidate])
        assert len(matches_default) == 0

        # With 35m tolerance, should match
        matches_custom = match_activity_to_segments(records, [candidate], start_tolerance_m=35)
        assert len(matches_custom) == 1

    def test_direction_tolerance(self):
        """Direction tolerance is respected."""
        # Segment going due north
        segment_coords = [
            (47.0, 8.0),
            (47.003, 8.0),
            (47.006, 8.0),
        ]
        # Activity also going north (same path) - will definitely match
        activity_coords = segment_coords.copy()
        records = make_records(activity_coords)

        # Create candidate with explicit bearing = 0 (north)
        candidate_north = make_candidate(segment_coords, direction_bearing=0)

        # With default 30° tolerance, north activity vs north segment matches
        matches_default = match_activity_to_segments(records, [candidate_north])
        assert len(matches_default) == 1

        # Now create same segment but with NE bearing (45°)
        candidate_ne = make_candidate(segment_coords, direction_bearing=45)

        # North activity (0°) vs NE segment (45°) with 30° tolerance should not match
        matches_ne_30 = match_activity_to_segments(records, [candidate_ne], direction_tolerance_deg=30)
        assert len(matches_ne_30) == 0  # 45° diff > 30°

        # North activity vs NE segment with 50° tolerance should match
        matches_ne_50 = match_activity_to_segments(records, [candidate_ne], direction_tolerance_deg=50)
        assert len(matches_ne_50) == 1  # 45° diff < 50°

    def test_matches_sorted_by_start_index(self):
        """Returned matches are sorted by start_index."""
        # Create an activity that crosses 3 segments
        activity_coords = [
            (47.0, 8.0),
            (47.001, 8.0),
            (47.002, 8.0),
            (47.003, 8.0),
            (47.004, 8.0),
            (47.005, 8.0),
        ]
        records = make_records(activity_coords)

        # Create segments in reverse order
        seg1 = make_candidate([(47.004, 8.0), (47.005, 8.0)])  # last
        seg2 = make_candidate([(47.0, 8.0), (47.001, 8.0)])  # first
        seg3 = make_candidate([(47.002, 8.0), (47.003, 8.0)])  # middle

        matches = match_activity_to_segments(records, [seg1, seg2, seg3])

        # Should be sorted by start_index
        assert len(matches) == 3
        for i in range(len(matches) - 1):
            assert matches[i].start_index < matches[i + 1].start_index
