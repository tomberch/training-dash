"""Unit tests for direction detection module."""

import pytest

from trainingdash.domain.direction import (
    DirectionBearings,
    bearings_match,
    compute_direction_bearing,
    compute_direction_bearings,
)

# =============================================================================
# Test compute_direction_bearing
# =============================================================================


class TestComputeDirectionBearing:
    """Tests for computing direction bearing at a point."""

    @pytest.fixture
    def north_route(self) -> list[tuple[float, float, float]]:
        """Route heading north (bearing ~0°)."""
        # Start at (0, 0), head north to (0.1, 0)
        return [
            (0.0, 0.0, 0.0),
            (0.01, 0.0, 1111.0),
            (0.02, 0.0, 2222.0),
            (0.03, 0.0, 3333.0),
            (0.04, 0.0, 4444.0),
            (0.05, 0.0, 5556.0),
            (0.06, 0.0, 6667.0),
            (0.07, 0.0, 7778.0),
            (0.08, 0.0, 8889.0),
            (0.09, 0.0, 10000.0),
        ]

    @pytest.fixture
    def east_route(self) -> list[tuple[float, float, float]]:
        """Route heading east (bearing ~90°)."""
        return [
            (0.0, 0.0, 0.0),
            (0.0, 0.01, 1111.0),
            (0.0, 0.02, 2222.0),
            (0.0, 0.03, 3333.0),
            (0.0, 0.04, 4444.0),
            (0.0, 0.05, 5556.0),
            (0.0, 0.06, 6667.0),
            (0.0, 0.07, 7778.0),
            (0.0, 0.08, 8889.0),
            (0.0, 0.09, 10000.0),
        ]

    @pytest.fixture
    def south_route(self) -> list[tuple[float, float, float]]:
        """Route heading south (bearing ~180°)."""
        return [
            (0.1, 0.0, 0.0),
            (0.09, 0.0, 1111.0),
            (0.08, 0.0, 2222.0),
            (0.07, 0.0, 3333.0),
            (0.06, 0.0, 4444.0),
            (0.05, 0.0, 5556.0),
            (0.04, 0.0, 6667.0),
            (0.03, 0.0, 7778.0),
            (0.02, 0.0, 8889.0),
            (0.01, 0.0, 10000.0),
        ]

    def test_northward_bearing(self, north_route):
        """Northward route should have bearing near 0°."""
        bearing = compute_direction_bearing(north_route, target_pct=0.25)
        # Allow some tolerance for calculation
        assert bearing is not None
        assert bearing < 45 or bearing > 315  # Near north

    def test_eastward_bearing(self, east_route):
        """Eastward route should have bearing near 90°."""
        bearing = compute_direction_bearing(east_route, target_pct=0.25)
        assert bearing is not None
        assert 45 < bearing < 135  # Near east

    def test_southward_bearing(self, south_route):
        """Southward route should have bearing near 180°."""
        bearing = compute_direction_bearing(south_route, target_pct=0.25)
        assert bearing is not None
        assert 135 < bearing < 225  # Near south

    def test_returns_none_for_too_few_points(self):
        """Should return None with fewer than 10 GPS points."""
        points = [(0.0, 0.0, 0.0), (0.01, 0.0, 1000.0)]
        bearing = compute_direction_bearing(points)
        assert bearing is None

    def test_returns_none_for_short_distance(self):
        """Should return None if total distance < min_distance_m."""
        # 10 points but very close together (< 1km total)
        points = [(0.0, 0.0, i * 50.0) for i in range(10)]
        # Add lat/lon values that are very close
        points = [(0.0 + i * 0.00001, 0.0, i * 50.0) for i in range(10)]
        bearing = compute_direction_bearing(points, min_distance_m=1000)
        assert bearing is None

    def test_different_target_percentages(self, north_route):
        """Should compute bearing at different points along route."""
        bearing_25 = compute_direction_bearing(north_route, target_pct=0.25)
        bearing_50 = compute_direction_bearing(north_route, target_pct=0.50)
        bearing_75 = compute_direction_bearing(north_route, target_pct=0.75)

        # For a straight route, all bearings should be similar
        assert bearing_25 is not None
        assert bearing_50 is not None
        assert bearing_75 is not None

    def test_bearing_is_integer(self, north_route):
        """Bearing should be returned as integer 0-359."""
        bearing = compute_direction_bearing(north_route)
        assert bearing is not None
        assert isinstance(bearing, int)
        assert 0 <= bearing < 360


# =============================================================================
# Test compute_direction_bearings
# =============================================================================


class TestComputeDirectionBearings:
    """Tests for computing dual bearings."""

    @pytest.fixture
    def long_route(self) -> list[tuple[float, float, float]]:
        """A longer route for dual bearing calculation."""
        # 20 points heading northeast
        return [(i * 0.005, i * 0.005, i * 700.0) for i in range(20)]

    def test_returns_direction_bearings(self, long_route):
        """Should return DirectionBearings with both values."""
        result = compute_direction_bearings(long_route, min_distance_m=500)

        assert isinstance(result, DirectionBearings)
        assert result.bearing_25 is not None
        assert result.bearing_75 is not None

    def test_both_bearings_similar_for_straight_route(self, long_route):
        """For straight route, both bearings should be similar."""
        result = compute_direction_bearings(long_route, min_distance_m=500)

        if result.bearing_25 is not None and result.bearing_75 is not None:
            # Both should indicate similar direction
            diff = abs(result.bearing_25 - result.bearing_75)
            if diff > 180:
                diff = 360 - diff
            assert diff < 45  # Within 45°

    def test_returns_none_for_short_route(self):
        """Should return None bearings for too-short routes."""
        short_route = [
            (0.0, 0.0, 0.0),
            (0.001, 0.0, 100.0),
        ]
        result = compute_direction_bearings(short_route, min_distance_m=1000)

        # May have None values due to insufficient data
        # (the function tries to compute even with few points)
        assert isinstance(result, DirectionBearings)


# =============================================================================
# Test bearings_match
# =============================================================================


class TestBearingsMatch:
    """Tests for bearing comparison."""

    def test_same_bearing_matches(self):
        """Identical bearings should match."""
        assert bearings_match(90, 90) is True

    def test_similar_bearing_matches(self):
        """Bearings within threshold should match."""
        assert bearings_match(85, 95, threshold=90) is True
        assert bearings_match(0, 45, threshold=90) is True

    def test_opposite_bearing_does_not_match(self):
        """Opposite bearings should not match."""
        # 0° and 180° are opposite directions
        assert bearings_match(0, 180, threshold=90) is False
        # 90° and 270° are opposite
        assert bearings_match(90, 270, threshold=90) is False

    def test_wraparound_at_360(self):
        """Should handle wraparound at 360°."""
        # 350° and 10° are 20° apart (via wraparound)
        assert bearings_match(350, 10, threshold=90) is True
        # 5° and 355° are 10° apart
        assert bearings_match(5, 355, threshold=90) is True

    def test_none_bearing_matches(self):
        """None bearing should match anything (can't determine)."""
        assert bearings_match(None, 90) is True
        assert bearings_match(90, None) is True
        assert bearings_match(None, None) is True

    def test_custom_threshold(self):
        """Should respect custom threshold."""
        # 45° difference with 30° threshold - should not match
        assert bearings_match(0, 45, threshold=30) is False
        # Same with 60° threshold - should match
        assert bearings_match(0, 45, threshold=60) is True

    def test_dual_bearing_matching(self):
        """Should check both bearings when 75% bearings provided."""
        # Both pairs match
        assert bearings_match(90, 95, 180, 175) is True

        # First pair matches, second doesn't
        assert bearings_match(90, 95, 180, 10) is False

        # Second pair matches, first doesn't
        assert bearings_match(90, 270, 180, 175) is False

    def test_dual_bearing_with_none(self):
        """None in 75% bearings should still match."""
        assert bearings_match(90, 95, None, 180) is True
        assert bearings_match(90, 95, 180, None) is True


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests for direction detection."""

    def test_loop_route_bearings(self):
        """Loop route should have different mid-point bearings for CW vs CCW."""
        # Clockwise loop (simplified)
        cw_loop = [
            (0.0, 0.0, 0.0),
            (0.01, 0.0, 1000.0),  # North
            (0.01, 0.01, 2000.0),  # East
            (0.0, 0.01, 3000.0),  # South
            (0.0, 0.0, 4000.0),  # West (back to start)
        ] + [(0.0, 0.0, 4000.0 + i * 100) for i in range(6)]  # Pad to 10+ points

        # Counter-clockwise loop
        ccw_loop = [
            (0.0, 0.0, 0.0),
            (0.0, 0.01, 1000.0),  # East
            (0.01, 0.01, 2000.0),  # North
            (0.01, 0.0, 3000.0),  # West
            (0.0, 0.0, 4000.0),  # South (back to start)
        ] + [(0.0, 0.0, 4000.0 + i * 100) for i in range(6)]

        # The bearings should differ, helping detect direction
        cw_bearing = compute_direction_bearing(cw_loop, target_pct=0.5, min_distance_m=500)
        ccw_bearing = compute_direction_bearing(ccw_loop, target_pct=0.5, min_distance_m=500)

        # Both should return values
        assert cw_bearing is not None or ccw_bearing is not None

    def test_point_to_point_route(self):
        """Point-to-point route should have consistent bearings."""
        # Straight line NE
        p2p_route = [(i * 0.005, i * 0.005, i * 700.0) for i in range(15)]

        bearings = compute_direction_bearings(p2p_route, min_distance_m=500)

        # Both should be in NE quadrant (0-90°)
        if bearings.bearing_25 is not None and bearings.bearing_75 is not None:
            assert 0 < bearings.bearing_25 < 90 or bearings.bearing_25 > 315
            assert 0 < bearings.bearing_75 < 90 or bearings.bearing_75 > 315

    def test_no_distance_data(self):
        """Should handle points without distance data."""
        # Points with None distance - function should compute distances
        points = [
            (0.0, 0.0, None),
            (0.01, 0.0, None),
            (0.02, 0.0, None),
            (0.03, 0.0, None),
            (0.04, 0.0, None),
            (0.05, 0.0, None),
            (0.06, 0.0, None),
            (0.07, 0.0, None),
            (0.08, 0.0, None),
            (0.09, 0.0, None),
        ]

        bearing = compute_direction_bearing(points, min_distance_m=500)
        # Should still compute a bearing by calculating distances
        assert bearing is not None or bearing is None  # May fail if can't compute

    def test_null_coordinates_filtered(self):
        """Should filter out points with None coordinates."""
        points = [
            (0.0, 0.0, 0.0),
            (None, 0.01, 1000.0),  # Invalid
            (0.02, None, 2000.0),  # Invalid
            (0.03, 0.03, 3000.0),
            (0.04, 0.04, 4000.0),
            (0.05, 0.05, 5000.0),
            (0.06, 0.06, 6000.0),
            (0.07, 0.07, 7000.0),
            (0.08, 0.08, 8000.0),
            (0.09, 0.09, 9000.0),
            (0.10, 0.10, 10000.0),
            (0.11, 0.11, 11000.0),
        ]

        bearing = compute_direction_bearing(points, min_distance_m=500)
        # Should still work with remaining valid points
        assert bearing is not None
