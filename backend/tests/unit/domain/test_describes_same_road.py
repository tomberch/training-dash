"""Tests for describes_same_road — containment-based dedup for suggested climbs.

Two auto-detected climbs describe the same road when one path essentially
contains the other (>= 90% of the *shorter* path lies within 35 m of the
longer one). Unlike is_same_segment (exact-duplicate gate for approval),
this tolerates climb-boundary wobble between rides: detectors may start
or end the same climb metres apart, or extend it partway down the descent.
"""

from trainingdash.domain.polyline import encode_polyline
from trainingdash.domain.segment_matching import describes_same_road


def encode(points: list[tuple[float, float]]) -> str:
    return encode_polyline(points)


def straight_climb(
    start_lat: float, start_lon: float, dlat: float, dlon: float, steps: int = 50
) -> list[tuple[float, float]]:
    """A polyline from (start_lat, start_lon) with per-step (dlat, dlon)."""
    return [(start_lat + dlat * i / steps, start_lon + dlon * i / steps) for i in range(steps + 1)]


class TestDescribesSameRoad:
    def test_identical_paths_match(self):
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        assert describes_same_road(polyline=encode(pts), other_polyline=encode(pts)) is True

    def test_jittered_sampling_matches(self):
        """Same road, points sampled differently (GPS jitter + resampling)."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        # same road, offset by ~2m and skipping every other point
        b = [(lat + 0.00002, lon + 0.00002) for lat, lon in a[::2]]
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b)) is True

    def test_longer_variant_contains_shorter(self):
        """Detector A caught the climb plus part of the descent; B only the climb.

        B's whole path lies on A's path, so it's the same road even though
        A is much longer and their endpoints are far apart.
        """
        full = straight_climb(46.900, 7.400, 0.090, 0.0)  # 10km
        partial = straight_climb(46.901, 7.400, 0.072, 0.0)  # last 8km, 1km offset start
        assert describes_same_road(polyline=encode(full), other_polyline=encode(partial)) is True

    def test_start_extension_only(self):
        """One detection starts 300 m before the other on the same road."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.8973, 7.400, 0.0477, 0.0)  # 300m earlier start
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b)) is True

    def test_diverging_end_is_not_same_road(self):
        """Shared start but the paths part ways midway — different roads."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.900, 7.400, 0.0225, 0.045)  # turns east after ~5km
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b)) is False

    def test_parallel_road_is_not_same(self):
        """Parallel road 500m away must not match, even at high resampling density."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.900, 7.406, 0.045, 0.0)  # ~450m east
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b)) is False

    def test_crossing_roads_are_not_same(self):
        """Two roads crossing at one point are not the same road."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.9225, 7.3775, -0.045, 0.045)  # diagonal crossing
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b)) is False

    def test_very_short_tail_extension_still_matches(self):
        """A road with a tiny extra stub at the end still matches."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.900, 7.400, 0.0459, 0.0)  # 20m longer
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b)) is True

    def test_symmetry(self):
        """Containment criterion must be direction-independent."""
        full = straight_climb(46.900, 7.400, 0.090, 0.0)
        partial = straight_climb(46.901, 7.400, 0.072, 0.0)
        args = {"polyline": encode(full), "other_polyline": encode(partial)}
        swapped = {"polyline": encode(partial), "other_polyline": encode(full)}
        assert describes_same_road(**args) == describes_same_road(**swapped)

    def test_empty_polyline_does_not_match(self):
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        assert describes_same_road(polyline="", other_polyline=encode(pts)) is False
        assert describes_same_road(polyline=encode(pts), other_polyline="") is False

    def test_corrupt_polyline_does_not_match(self):
        """Polylines that decode to unrealistic paths (millions of metres) are rejected."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        # This decodes but produces garbage coordinates ~12,000 km apart
        assert describes_same_road(polyline="not-a-valid-polyline!!!", other_polyline=encode(pts)) is False

    def test_undecodable_polyline_does_not_match(self):
        """Polylines that raise exceptions during decode are rejected."""
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        # These cause IndexError in decode_polyline (incomplete byte sequences)
        assert describes_same_road(polyline="x", other_polyline=encode(pts)) is False
        assert describes_same_road(polyline="@@@", other_polyline=encode(pts)) is False

    def test_single_point_path_does_not_match(self):
        pts = straight_climb(46.900, 7.400, 0.045, 0.0)
        assert describes_same_road(polyline=encode([pts[0]]), other_polyline=encode(pts)) is False

    def test_custom_thresholds(self):
        """Looser containment still rejects genuinely different roads."""
        a = straight_climb(46.900, 7.400, 0.045, 0.0)
        b = straight_climb(46.900, 7.402, 0.045, 0.0)  # ~150m east
        assert describes_same_road(polyline=encode(a), other_polyline=encode(b), buffer_m=200.0) is True


class TestDescribesSameRoadRealWorld:
    """Regression tests modelled on the actual 6-duplicate Gantrisch climb."""

    def test_partial_overlap_variants_merge(self):
        """Real-world pattern: base extension + summit truncation (85% containment)."""
        full = straight_climb(46.900, 7.400, 0.090, 0.0)  # 10km climb
        # 8km variant: starts 2km in, ends 0km before summit
        shorter = straight_climb(46.918, 7.400, 0.072, 0.0)
        assert describes_same_road(polyline=encode(full), other_polyline=encode(shorter)) is True
        # 85%-ish coverage variant: starts 1.5km in
        almost = straight_climb(46.9135, 7.400, 0.0765, 0.0)
        assert describes_same_road(polyline=encode(full), other_polyline=encode(almost)) is True

    def test_82_percent_containment_is_not_same(self):
        """Road sharing only ~82% of the longer path — different road.

        The shorter path must itself lie almost entirely on the longer
        one; a road that overlaps just 82% of the other (e.g. a climb
        that branches off midway) does not.
        """
        full = straight_climb(46.900, 7.400, 0.090, 0.0)  # 10km
        # Starts at the same point but peels off after ~8.2km onto a
        # parallel road: only 82% of `other` lies on `full`.
        detour = [(46.900 + (0.082 if i < 41 else 0.090 - 0.045), 7.400 if i < 41 else 7.405) for i in range(51)]
        assert describes_same_road(polyline=encode(full), other_polyline=encode(detour)) is False
