"""Tests for direction detection functions."""

from trainingdash.domain.direction import (
    DirectionBearings,
    bearings_match,
    compute_direction_bearing,
    compute_direction_bearings,
)


class TestComputeDirectionBearing:
    """Tests for compute_direction_bearing function."""

    def test_returns_none_for_insufficient_points(self):
        """Should return None with fewer than 10 GPS points."""
        points = [(46.79, 7.50, 0.0)] * 5
        assert compute_direction_bearing(points) is None

    def test_returns_none_for_short_distance(self):
        """Should return None for routes shorter than 1km."""
        # Points clustered in small area (~200m total)
        points = [(46.79 + i * 0.0001, 7.50 + i * 0.0001, i * 10.0) for i in range(20)]
        result = compute_direction_bearing(points)
        assert result is None

    def test_returns_bearing_for_valid_route(self):
        """Should return integer bearing 0-359 for valid GPS data."""
        # Create a ~3km route heading roughly North
        points = [(46.79 + i * 0.005, 7.50, i * 500.0) for i in range(20)]
        result = compute_direction_bearing(points)
        assert result is not None
        assert isinstance(result, int)
        assert 0 <= result < 360

    def test_northbound_route_returns_north_bearing(self):
        """Route heading north should return bearing close to 0."""
        # Create route heading North (increasing latitude)
        points = [(46.79 + i * 0.005, 7.50, i * 500.0) for i in range(20)]
        bearing = compute_direction_bearing(points)
        # Should be close to 0 (North)
        assert bearing is not None
        assert bearing < 45 or bearing > 315  # Within 45° of North

    def test_southbound_route_returns_south_bearing(self):
        """Route heading south should return bearing close to 180."""
        # Create route heading South (decreasing latitude)
        points = [(46.89 - i * 0.005, 7.50, i * 500.0) for i in range(20)]
        bearing = compute_direction_bearing(points)
        # Should be close to 180 (South)
        assert bearing is not None
        assert 135 < bearing < 225  # Within 45° of South

    def test_eastbound_route_returns_east_bearing(self):
        """Route heading east should return bearing close to 90."""
        # Create route heading East (increasing longitude)
        points = [(46.79, 7.50 + i * 0.007, i * 500.0) for i in range(20)]
        bearing = compute_direction_bearing(points)
        # Should be close to 90 (East)
        assert bearing is not None
        assert 45 < bearing < 135  # Within 45° of East

    def test_westbound_route_returns_west_bearing(self):
        """Route heading west should return bearing close to 270."""
        # Create route heading West (decreasing longitude)
        points = [(46.79, 7.60 - i * 0.007, i * 500.0) for i in range(20)]
        bearing = compute_direction_bearing(points)
        # Should be close to 270 (West)
        assert bearing is not None
        assert 225 < bearing < 315  # Within 45° of West

    def test_same_route_same_direction_produces_similar_bearings(self):
        """Two runs of same route in same direction should have similar bearings."""
        # Route A: heading NE
        points_a = [(46.79 + i * 0.004, 7.50 + i * 0.003, i * 500.0) for i in range(20)]

        # Route B: same direction, slightly different starting point
        points_b = [(46.791 + i * 0.004, 7.501 + i * 0.003, i * 500.0) for i in range(20)]

        bearing_a = compute_direction_bearing(points_a)
        bearing_b = compute_direction_bearing(points_b)

        assert bearing_a is not None
        assert bearing_b is not None
        # Bearings should be very close (within a few degrees)
        diff = abs(bearing_a - bearing_b)
        if diff > 180:
            diff = 360 - diff
        assert diff < 10  # Within 10 degrees

    def test_opposite_directions_produce_opposite_bearings(self):
        """Routes going opposite directions should have ~180° different bearings."""
        # Route A: heading North
        points_a = [(46.79 + i * 0.005, 7.50, i * 500.0) for i in range(20)]

        # Route B: heading South (reverse of A)
        points_b = [(46.89 - i * 0.005, 7.50, i * 500.0) for i in range(20)]

        bearing_a = compute_direction_bearing(points_a)
        bearing_b = compute_direction_bearing(points_b)

        assert bearing_a is not None
        assert bearing_b is not None
        # Bearings should differ by ~180°
        diff = abs(bearing_a - bearing_b)
        if diff > 180:
            diff = 360 - diff
        assert diff > 135  # At least 135° apart (opposite-ish)

    def test_handles_none_distances(self):
        """Should compute distance from coordinates when distance_m is None."""
        # Create route without distance data
        points = [(46.79 + i * 0.005, 7.50, None) for i in range(20)]
        result = compute_direction_bearing(points)
        assert result is not None
        assert isinstance(result, int)
        assert 0 <= result < 360


class TestComputeDirectionBearings:
    """Tests for compute_direction_bearings function (dual-bearing)."""

    def test_returns_dataclass_with_both_bearings(self):
        """Should return DirectionBearings with bearing_25 and bearing_75."""
        # Straight northbound route
        points = [(46.79 + i * 0.005, 7.50, i * 500.0) for i in range(20)]
        result = compute_direction_bearings(points)
        assert isinstance(result, DirectionBearings)
        assert result.bearing_25 is not None
        assert result.bearing_75 is not None

    def test_straight_route_has_similar_bearings(self):
        """A straight route should have similar 25% and 75% bearings."""
        # Straight northbound route
        points = [(46.79 + i * 0.005, 7.50, i * 500.0) for i in range(20)]
        result = compute_direction_bearings(points)
        # Both should be close to North
        assert result.bearing_25 is not None
        assert result.bearing_75 is not None
        diff = abs(result.bearing_25 - result.bearing_75)
        if diff > 180:
            diff = 360 - diff
        assert diff < 30  # Within 30° for a straight route

    def test_loop_route_has_different_bearings(self):
        """A loop route going clockwise vs counterclockwise should have different 50% bearings."""
        # Create a longer clockwise square loop with more points per side
        # Total ~20km so each side is ~5km
        points = []
        # Side 1: East (0-25%) - 25 points over 5km
        for i in range(25):
            points.append((46.79, 7.50 + i * 0.003, i * 200.0))
        # Side 2: South (25-50%) - 25 points over 5km
        for i in range(25):
            points.append((46.79 - i * 0.002, 7.575, 5000 + i * 200.0))
        # Side 3: West (50-75%) - 25 points over 5km
        for i in range(25):
            points.append((46.74, 7.575 - i * 0.003, 10000 + i * 200.0))
        # Side 4: North back to start (75-100%) - 25 points over 5km
        for i in range(25):
            points.append((46.74 + i * 0.002, 7.50, 15000 + i * 200.0))

        result = compute_direction_bearings(points)
        assert result.bearing_25 is not None
        assert result.bearing_75 is not None
        # 25% should be on side 1 (East, ~90°)
        # 50% (stored in bearing_75) should be on side 2 (South, ~180°)
        # Difference should be significant
        diff = abs(result.bearing_25 - result.bearing_75)
        if diff > 180:
            diff = 360 - diff
        assert diff >= 45  # At least 45° apart

    def test_returns_none_for_insufficient_data(self):
        """Should return None bearings for insufficient GPS data."""
        points = [(46.79, 7.50, 0.0)] * 5
        result = compute_direction_bearings(points)
        assert result.bearing_25 is None
        assert result.bearing_75 is None


class TestBearingsMatch:
    """Tests for bearings_match function."""

    def test_identical_bearings_match(self):
        """Two identical bearings should match."""
        assert bearings_match(45, 45) is True

    def test_similar_bearings_match(self):
        """Bearings within 90° should match."""
        assert bearings_match(0, 45) is True
        assert bearings_match(0, 89) is True
        assert bearings_match(180, 135) is True
        assert bearings_match(270, 225) is True

    def test_opposite_bearings_do_not_match(self):
        """Bearings ~180° apart should not match."""
        assert bearings_match(0, 180) is False
        assert bearings_match(90, 270) is False
        assert bearings_match(45, 225) is False

    def test_bearings_at_threshold_match(self):
        """Bearings exactly at 90° threshold should match."""
        assert bearings_match(0, 90) is True
        assert bearings_match(0, 270) is True  # 90° the other way

    def test_bearings_just_over_threshold_do_not_match(self):
        """Bearings just over 90° apart should not match."""
        assert bearings_match(0, 91) is False
        assert bearings_match(0, 269) is False  # 91° the other way

    def test_wraparound_at_360(self):
        """Should handle wraparound correctly (350° and 10° are 20° apart)."""
        assert bearings_match(350, 10) is True  # 20° apart
        assert bearings_match(5, 355) is True  # 10° apart
        assert bearings_match(0, 359) is True  # 1° apart

    def test_none_bearing_returns_true(self):
        """If either bearing is None, should return True (fail open)."""
        assert bearings_match(None, 45) is True
        assert bearings_match(45, None) is True
        assert bearings_match(None, None) is True

    def test_custom_threshold(self):
        """Should respect custom threshold parameter."""
        # With 45° threshold, 50° apart should not match
        assert bearings_match(0, 50, threshold=45) is False
        # But 40° apart should match
        assert bearings_match(0, 40, threshold=45) is True


class TestBearingsMatchDual:
    """Tests for dual-bearing matching (25% and 75%)."""

    def test_both_bearings_must_match(self):
        """When 75% bearings provided, both 25% and 75% must match."""
        # Same 25% bearing, different 75% bearing
        assert bearings_match(0, 0, 90, 270) is False  # 75% diff = 180°
        assert bearings_match(0, 0, 90, 91) is True  # Both within threshold

    def test_opposite_loop_detected(self):
        """Should detect opposite-direction loops via 75% bearing."""
        # Simulates the Burgistein case:
        # Loop A: 25% heading west (269°), 75% heading east (89°) - counterclockwise
        # Loop B: 25% heading west (305°), 75% heading west (251°) - clockwise
        # At 25%, both are heading "west-ish" (within 90°)
        # At 75%, they're heading opposite directions

        # Counterclockwise loop: west at 25%, east at 75%
        bearing_a_25 = 269
        bearing_a_75 = 89

        # Clockwise loop: northwest at 25%, southwest at 75%
        bearing_b_25 = 305
        bearing_b_75 = 225

        # 25% bearings match (269 vs 305 = 36° diff)
        # 75% bearings don't match (89 vs 225 = 136° diff)
        result = bearings_match(bearing_a_25, bearing_b_25, bearing_a_75, bearing_b_75)
        assert result is False

    def test_same_direction_loop_matches(self):
        """Same-direction loops should match at both checkpoints."""
        # Both clockwise loops with similar bearings
        bearing_a_25 = 305
        bearing_a_75 = 225
        bearing_b_25 = 310  # 5° diff
        bearing_b_75 = 230  # 5° diff

        result = bearings_match(bearing_a_25, bearing_b_25, bearing_a_75, bearing_b_75)
        assert result is True

    def test_backwards_compatible_single_bearing(self):
        """Should work with just 25% bearings (backwards compatibility)."""
        # No 75% bearings provided - should just check 25%
        assert bearings_match(0, 45) is True
        assert bearings_match(0, 180) is False

    def test_none_75_bearing_matches(self):
        """If either 75% bearing is None, should match (fail open)."""
        # One has 75%, other doesn't
        assert bearings_match(0, 0, 90, None) is True
        assert bearings_match(0, 0, None, 90) is True
        assert bearings_match(0, 0, None, None) is True

    def test_point_to_point_route(self):
        """Point-to-point routes should have consistent bearings that match."""
        # Northbound route: north at 25%, north at 75%
        bearing_a_25 = 5
        bearing_a_75 = 355  # Still north, slight variation

        # Another northbound run
        bearing_b_25 = 10
        bearing_b_75 = 0

        result = bearings_match(bearing_a_25, bearing_b_25, bearing_a_75, bearing_b_75)
        assert result is True

    def test_opposite_point_to_point(self):
        """Opposite direction on point-to-point should not match."""
        # Northbound: north at both checkpoints
        bearing_a_25 = 0
        bearing_a_75 = 0

        # Southbound: south at both checkpoints
        bearing_b_25 = 180
        bearing_b_75 = 180

        result = bearings_match(bearing_a_25, bearing_b_25, bearing_a_75, bearing_b_75)
        assert result is False
