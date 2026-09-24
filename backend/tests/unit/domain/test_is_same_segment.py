"""Tests for is_same_segment — shared duplicate-segment comparison.

Criteria (ticket #473): start within 25m, end within 25m, and >= 95% path
overlap. Used by suggestion approval and climb-detection dedup so both
flows agree on what "the same segment" means.
"""

from trainingdash.domain.segment_matching import is_same_segment


def encode(points: list[tuple[float, float]]) -> str:
    """Encode (lat, lon) points with the production polyline codec."""
    from trainingdash.domain.polyline import encode_polyline

    return encode_polyline(points)


# A 1km straight climb due north near Bern
CLIMB_A = [(46.9000, 7.4000), (46.9045, 7.4000), (46.9090, 7.4000)]

# Same climb, points sampled slightly differently (GPS jitter)
CLIMB_A_JITTER = [(46.90005, 7.40002), (46.90455, 7.40001), (46.90905, 7.40003)]

# A different climb 2km away
CLIMB_B = [(46.9300, 7.4000), (46.9345, 7.4000), (46.9390, 7.4000)]


class TestIsSameSegment:
    def test_identical_segments_match(self):
        assert (
            is_same_segment(
                start_lat=46.9000,
                start_lon=7.4000,
                end_lat=46.9090,
                end_lon=7.4000,
                polyline=encode(CLIMB_A),
                other_start_lat=46.9000,
                other_start_lon=7.4000,
                other_end_lat=46.9090,
                other_end_lon=7.4000,
                other_polyline=encode(CLIMB_A),
            )
            is True
        )

    def test_gps_jitter_still_matches(self):
        """Real-world jitter (<25m) is tolerated."""
        assert (
            is_same_segment(
                start_lat=46.9000,
                start_lon=7.4000,
                end_lat=46.9090,
                end_lon=7.4000,
                polyline=encode(CLIMB_A),
                other_start_lat=46.90005,
                other_start_lon=7.40002,
                other_end_lat=46.90905,
                other_end_lon=7.40003,
                other_polyline=encode(CLIMB_A_JITTER),
            )
            is True
        )

    def test_different_location_does_not_match(self):
        assert (
            is_same_segment(
                start_lat=46.9000,
                start_lon=7.4000,
                end_lat=46.9090,
                end_lon=7.4000,
                polyline=encode(CLIMB_A),
                other_start_lat=46.9300,
                other_start_lon=7.4000,
                other_end_lat=46.9390,
                other_end_lon=7.4000,
                other_polyline=encode(CLIMB_B),
            )
            is False
        )

    def test_same_start_different_end_does_not_match(self):
        """Shared start point but diverging path — not the same segment."""
        # CLIMB_A goes north from (46.90, 7.40); this one turns east early
        diverging = [(46.9000, 7.4000), (46.9010, 7.4050), (46.9090, 7.4200)]
        assert (
            is_same_segment(
                start_lat=46.9000,
                start_lon=7.4000,
                end_lat=46.9090,
                end_lon=7.4000,
                polyline=encode(CLIMB_A),
                other_start_lat=46.9000,
                other_start_lon=7.4000,
                other_end_lat=46.9090,
                other_end_lon=7.4200,
                other_polyline=encode(diverging),
            )
            is False
        )

    def test_empty_other_polyline_does_not_match(self):
        assert (
            is_same_segment(
                start_lat=46.9000,
                start_lon=7.4000,
                end_lat=46.9090,
                end_lon=7.4000,
                polyline=encode(CLIMB_A),
                other_start_lat=46.9000,
                other_start_lon=7.4000,
                other_end_lat=46.9090,
                other_end_lon=7.4000,
                other_polyline="",
            )
            is False
        )

    def test_decoding_failure_is_not_a_match(self):
        """A corrupt polyline must not crash or match."""
        assert (
            is_same_segment(
                start_lat=46.9000,
                start_lon=7.4000,
                end_lat=46.9090,
                end_lon=7.4000,
                polyline=encode(CLIMB_A),
                other_start_lat=46.9000,
                other_start_lon=7.4000,
                other_end_lat=46.9090,
                other_end_lon=7.4000,
                other_polyline="not-a-valid-polyline!!!",
            )
            is False
        )
