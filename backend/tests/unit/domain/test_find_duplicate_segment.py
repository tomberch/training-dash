"""Tests for find_duplicate_segment — unified duplicate detection for segments.

This function is the single entry point for all segment duplicate detection,
consolidating logic previously scattered across use cases and repositories.

Two modes:
- "strict": 25m endpoint tolerance + 95% path overlap (approval/manual creation)
- "same_road": 90% containment of shorter path within 35m (suggestion merging)
"""

from uuid import uuid4

import pytest

from trainingdash.domain.polyline import encode_polyline
from trainingdash.domain.segment_geometry import SegmentGeometry
from trainingdash.domain.segment_matching import SegmentForDedup, find_duplicate_segment


def encode(points: list[tuple[float, float]]) -> str:
    """Encode (lat, lon) points with the production polyline codec."""
    return encode_polyline(points)


def make_geometry(points: list[tuple[float, float]]) -> SegmentGeometry:
    """Create a minimal SegmentGeometry from coordinates."""
    return SegmentGeometry(
        polyline=encode(points),
        start_lat=points[0][0],
        start_lon=points[0][1],
        end_lat=points[-1][0],
        end_lon=points[-1][1],
        bounds=(0, 0, 0, 0),  # Not used in duplicate detection
        direction_bearing=0.0,
        distance_m=0.0,
        elevation_gain_m=0.0,
        avg_grade_pct=0.0,
        max_grade_pct=0.0,
        elevation_profile=[],
    )


def make_dedup(points: list[tuple[float, float]], segment_id=None) -> SegmentForDedup:
    """Create a SegmentForDedup from coordinates."""
    return SegmentForDedup(
        id=segment_id or uuid4(),
        start_lat=points[0][0],
        start_lon=points[0][1],
        end_lat=points[-1][0],
        end_lon=points[-1][1],
        polyline=encode(points),
    )


def straight_climb(
    start_lat: float, start_lon: float, dlat: float, dlon: float, steps: int = 50
) -> list[tuple[float, float]]:
    """A polyline from (start_lat, start_lon) with per-step (dlat, dlon)."""
    return [
        (start_lat + dlat * i / steps, start_lon + dlon * i / steps)
        for i in range(steps + 1)
    ]


# Test fixtures: 1km climb near Bern
CLIMB_A = [(46.9000, 7.4000), (46.9045, 7.4000), (46.9090, 7.4000)]
CLIMB_A_JITTER = [(46.90005, 7.40002), (46.90455, 7.40001), (46.90905, 7.40003)]
CLIMB_B = [(46.9300, 7.4000), (46.9345, 7.4000), (46.9390, 7.4000)]  # 2km away


class TestFindDuplicateSegmentStrictMode:
    """Tests for mode='strict' — exact duplicate gate for approval/creation."""

    def test_identical_segment_is_duplicate(self):
        """Identical segment should be detected as duplicate."""
        candidate = make_geometry(CLIMB_A)
        existing = [make_dedup(CLIMB_A)]

        result = find_duplicate_segment(candidate, existing, mode="strict")

        assert result is not None
        assert result.id == existing[0].id

    def test_jittered_segment_is_duplicate(self):
        """GPS jitter (<25m) should still be detected as duplicate."""
        candidate = make_geometry(CLIMB_A)
        existing = [make_dedup(CLIMB_A_JITTER)]

        result = find_duplicate_segment(candidate, existing, mode="strict")

        assert result is not None

    def test_different_location_not_duplicate(self):
        """Segment 2km away should not be detected as duplicate."""
        candidate = make_geometry(CLIMB_A)
        existing = [make_dedup(CLIMB_B)]

        result = find_duplicate_segment(candidate, existing, mode="strict")

        assert result is None

    def test_empty_existing_returns_none(self):
        """No existing segments means no duplicate."""
        candidate = make_geometry(CLIMB_A)

        result = find_duplicate_segment(candidate, [], mode="strict")

        assert result is None

    def test_returns_first_match(self):
        """When multiple duplicates exist, returns the first one."""
        candidate = make_geometry(CLIMB_A)
        id1 = uuid4()
        id2 = uuid4()
        existing = [
            make_dedup(CLIMB_A, segment_id=id1),
            make_dedup(CLIMB_A_JITTER, segment_id=id2),
        ]

        result = find_duplicate_segment(candidate, existing, mode="strict")

        assert result is not None
        assert result.id == id1  # First match

    def test_diverging_path_not_duplicate(self):
        """Shared start point but diverging path is not a duplicate."""
        candidate = make_geometry(CLIMB_A)
        diverging = [(46.9000, 7.4000), (46.9010, 7.4050), (46.9090, 7.4200)]
        existing = [make_dedup(diverging)]

        result = find_duplicate_segment(candidate, existing, mode="strict")

        assert result is None

    def test_corrupt_polyline_not_duplicate(self):
        """Corrupt polyline in existing should not crash or match."""
        candidate = make_geometry(CLIMB_A)
        corrupt = SegmentForDedup(
            id=uuid4(),
            start_lat=46.9000,
            start_lon=7.4000,
            end_lat=46.9090,
            end_lon=7.4000,
            polyline="not-a-valid-polyline!!!",
        )

        result = find_duplicate_segment(candidate, [corrupt], mode="strict")

        assert result is None


class TestFindDuplicateSegmentSameRoadMode:
    """Tests for mode='same_road' — containment-based dedup for suggestions."""

    def test_identical_path_is_duplicate(self):
        """Identical path should be detected as duplicate."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        candidate = make_geometry(pts)
        existing = [make_dedup(pts)]

        result = find_duplicate_segment(candidate, existing, mode="same_road")

        assert result is not None

    def test_longer_variant_contains_shorter(self):
        """Longer path containing shorter should match (same road)."""
        full = straight_climb(46.900, 7.400, 0.090, 0.0)  # 10km
        partial = straight_climb(46.901, 7.400, 0.072, 0.0)  # 8km subset

        # Candidate is the shorter, existing is the longer
        candidate = make_geometry(partial)
        existing = [make_dedup(full)]

        result = find_duplicate_segment(candidate, existing, mode="same_road")

        assert result is not None

    def test_shorter_existing_still_matches(self):
        """Existing shorter path that's contained in candidate should match."""
        full = straight_climb(46.900, 7.400, 0.090, 0.0)  # 10km
        partial = straight_climb(46.901, 7.400, 0.072, 0.0)  # 8km subset

        # Candidate is the longer, existing is the shorter
        candidate = make_geometry(full)
        existing = [make_dedup(partial)]

        result = find_duplicate_segment(candidate, existing, mode="same_road")

        assert result is not None

    def test_parallel_road_not_duplicate(self):
        """Parallel road 500m away should not match."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.900, 7.406, 0.045, 0.0)  # ~450m east

        candidate = make_geometry(a)
        existing = [make_dedup(b)]

        result = find_duplicate_segment(candidate, existing, mode="same_road")

        assert result is None

    def test_crossing_roads_not_duplicate(self):
        """Two roads crossing at one point are not the same road."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.9225, 7.3775, -0.045, 0.045)  # diagonal crossing

        candidate = make_geometry(a)
        existing = [make_dedup(b)]

        result = find_duplicate_segment(candidate, existing, mode="same_road")

        assert result is None

    def test_empty_existing_returns_none(self):
        """No existing segments means no duplicate."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        candidate = make_geometry(pts)

        result = find_duplicate_segment(candidate, [], mode="same_road")

        assert result is None

    def test_corrupt_polyline_not_duplicate(self):
        """Corrupt polyline should not crash or match."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        candidate = make_geometry(pts)
        corrupt = SegmentForDedup(
            id=uuid4(),
            start_lat=46.900,
            start_lon=7.400,
            end_lat=46.945,
            end_lon=7.400,
            polyline="not-a-valid-polyline!!!",
        )

        result = find_duplicate_segment(candidate, [corrupt], mode="same_road")

        assert result is None


class TestFindDuplicateSegmentModeComparison:
    """Tests comparing behavior between strict and same_road modes."""

    def test_boundary_wobble_rejected_by_strict_accepted_by_same_road(self):
        """Boundary wobble (different endpoints, same road) should only match in same_road mode."""
        # Full climb
        full = straight_climb(46.900, 7.400, 0.090, 0.0)  # 10km
        # Shorter variant starting 1km in
        partial = straight_climb(46.909, 7.400, 0.081, 0.0)

        candidate = make_geometry(full)
        existing = [make_dedup(partial)]

        # strict mode: endpoints too far apart (>25m)
        strict_result = find_duplicate_segment(candidate, existing, mode="strict")
        assert strict_result is None

        # same_road mode: containment criterion passes
        same_road_result = find_duplicate_segment(candidate, existing, mode="same_road")
        assert same_road_result is not None

    def test_exact_duplicate_matches_both_modes(self):
        """An exact duplicate should match in both modes."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        candidate = make_geometry(pts)
        existing = [make_dedup(pts)]

        strict_result = find_duplicate_segment(candidate, existing, mode="strict")
        same_road_result = find_duplicate_segment(candidate, existing, mode="same_road")

        assert strict_result is not None
        assert same_road_result is not None
        assert strict_result.id == same_road_result.id


class TestFindDuplicateSegmentEdgeCases:
    """Edge cases and robustness tests."""

    def test_iterable_consumed_once(self):
        """Function should work with generators (single-pass iterables)."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        candidate = make_geometry(pts)

        def existing_generator():
            yield make_dedup(pts)

        result = find_duplicate_segment(candidate, existing_generator(), mode="strict")

        assert result is not None

    def test_many_existing_segments(self):
        """Should handle checking against many existing segments efficiently."""
        candidate = make_geometry(CLIMB_A)

        # Create 100 non-matching segments
        existing = [
            make_dedup(straight_climb(46.900 + i * 0.01, 7.400, 0.045, 0.0))
            for i in range(100)
        ]
        # Add the matching one at the end
        match_id = uuid4()
        existing.append(make_dedup(CLIMB_A, segment_id=match_id))

        result = find_duplicate_segment(candidate, existing, mode="strict")

        assert result is not None
        assert result.id == match_id
