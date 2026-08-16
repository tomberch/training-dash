"""Direction detection for same-route comparison.

This module provides utilities for determining if two activities on the same route
were ridden in the same or opposite direction.

Two direction bearings are computed:
- bearing_25: direction of travel at 25% of route distance
- bearing_75: direction of travel at 50% of route distance (stored in bearing_75 column)

The 50% point is used instead of 75% because that's typically where clockwise vs
counterclockwise loop directions diverge most clearly - at 75%, both directions
may be heading back towards the start in similar directions.

The bearing at each point is computed from the GPS track ~500m before to ~500m
after that point, capturing the actual direction of movement (not just position
relative to start).

Two activities are considered same-direction if BOTH bearings match within 90°.
This dual-bearing approach catches opposite-direction loops where both directions
initially head the same way but diverge at the midpoint.

This approach is:
- Accurate: measures actual travel direction, not position from start
- Robust: catches opposite-direction loops using the 50% divergence point
- Fast: O(1) comparison at query time
- Works for all route types: point-to-point and loops
"""

import math
from dataclasses import dataclass

# =============================================================================
# Direction Bearings (dual-bearing approach)
# =============================================================================


@dataclass
class DirectionBearings:
    """Direction bearings at 25% and 75% of route distance."""

    bearing_25: int | None
    bearing_75: int | None


def compute_direction_bearings(
    gps_points: list[tuple[float, float, float | None]],
    min_distance_m: float = 1000.0,
) -> DirectionBearings:
    """Compute direction bearings at 25% and 50% of route distance.

    These two bearings together capture direction of travel at early and mid
    points of the route. For loop routes where both directions initially head
    the same way, the 50% point is typically where clockwise vs counterclockwise
    directions diverge most clearly.

    Args:
        gps_points: List of (lat, lon, distance_m) tuples. distance_m can be None.
        min_distance_m: Minimum total distance required (default 1000m)

    Returns:
        DirectionBearings with bearing_25 and bearing_75 (actually at 50%, but
        named bearing_75 for database column compatibility)
    """
    bearing_25 = compute_direction_bearing(gps_points, target_pct=0.25, min_distance_m=min_distance_m)
    # Use 50% instead of 75% - this is where loop directions diverge most
    bearing_50 = compute_direction_bearing(gps_points, target_pct=0.50, min_distance_m=min_distance_m)
    return DirectionBearings(bearing_25=bearing_25, bearing_75=bearing_50)


def compute_direction_bearing(
    gps_points: list[tuple[float, float, float | None]],
    target_pct: float = 0.25,
    min_distance_m: float = 1000.0,
    window_m: float = 500.0,
) -> int | None:
    """Compute a direction bearing at a percentage point along the route.

    The bearing is computed as the direction of travel AT the target percentage,
    measured from a point ~500m before to ~500m after the target point.
    This captures the actual direction of movement, which is essential for
    detecting opposite directions on loop routes.

    Args:
        gps_points: List of (lat, lon, distance_m) tuples. distance_m can be None.
        target_pct: Percentage of total distance for target point (default 0.25)
        min_distance_m: Minimum total distance required (default 1000m)
        window_m: Distance window before/after target for bearing calculation (default 500m)

    Returns:
        Bearing in degrees (0-359) as integer, or None if insufficient GPS data
    """
    if len(gps_points) < 10:
        return None

    # Filter to valid GPS points
    valid_points = [(lat, lon, dist) for lat, lon, dist in gps_points if lat is not None and lon is not None]

    if len(valid_points) < 10:
        return None

    # Ensure we have distance data
    has_distance = valid_points[0][2] is not None

    if has_distance:
        points_with_dist = [(lat, lon, dist or 0) for lat, lon, dist in valid_points]
    else:
        # Compute cumulative distance
        points_with_dist = []
        cumulative_dist = 0.0
        prev_lat, prev_lon = valid_points[0][0], valid_points[0][1]
        points_with_dist.append((prev_lat, prev_lon, 0.0))

        for lat, lon, _ in valid_points[1:]:
            cumulative_dist += _haversine_distance(prev_lat, prev_lon, lat, lon)
            points_with_dist.append((lat, lon, cumulative_dist))
            prev_lat, prev_lon = lat, lon

    total_distance = points_with_dist[-1][2]
    if total_distance < min_distance_m:
        return None

    # Find the target distance
    target_dist = total_distance * target_pct

    # Find points before and after the target for direction calculation
    # Use a window of ~500m before and after (or less if near start/end)
    before_dist = max(0, target_dist - window_m)
    after_dist = min(total_distance, target_dist + window_m)

    # Find the closest points to before and after distances
    before_point = min(points_with_dist, key=lambda p: abs(p[2] - before_dist))
    after_point = min(points_with_dist, key=lambda p: abs(p[2] - after_dist))

    # If the points are too close together, fall back to start-to-target bearing
    if _haversine_distance(before_point[0], before_point[1], after_point[0], after_point[1]) < 100:
        # Points too close, use start to target
        start = points_with_dist[0]
        target = min(points_with_dist, key=lambda p: abs(p[2] - target_dist))
        bearing = _haversine_bearing(start[0], start[1], target[0], target[1])
    else:
        # Compute bearing from before to after point (direction of travel)
        bearing = _haversine_bearing(before_point[0], before_point[1], after_point[0], after_point[1])

    # Round to integer (0-359)
    return round(bearing) % 360


def bearings_match(
    bearing1: int | None,
    bearing2: int | None,
    bearing1_75: int | None = None,
    bearing2_75: int | None = None,
    threshold: int = 90,
) -> bool:
    """Check if two activities were ridden in the same direction.

    Uses dual-bearing comparison when 75% bearings are provided:
    - BOTH 25% bearings must match (within threshold)
    - AND BOTH 75% bearings must match (within threshold)

    This catches opposite-direction loops where both directions initially
    head the same way but diverge later.

    Falls back to single-bearing comparison if 75% bearings are not provided
    (for backwards compatibility during migration).

    Args:
        bearing1: First activity's 25% bearing (0-359°), or None
        bearing2: Second activity's 25% bearing (0-359°), or None
        bearing1_75: First activity's 75% bearing (0-359°), or None
        bearing2_75: Second activity's 75% bearing (0-359°), or None
        threshold: Maximum angular difference to consider same direction (default 90°)

    Returns:
        True if bearings indicate same direction of travel.
        Returns True if any required bearing is None (can't determine, assume same).
    """
    # Check 25% bearings
    if not _single_bearing_match(bearing1, bearing2, threshold):
        return False

    # If 75% bearings provided, also check those
    if bearing1_75 is not None or bearing2_75 is not None:
        if not _single_bearing_match(bearing1_75, bearing2_75, threshold):
            return False

    return True


def _single_bearing_match(bearing1: int | None, bearing2: int | None, threshold: int = 90) -> bool:
    """Check if two single bearings match within threshold.

    Args:
        bearing1: First bearing in degrees (0-359), or None
        bearing2: Second bearing in degrees (0-359), or None
        threshold: Maximum angular difference (default 90°)

    Returns:
        True if bearings are within threshold degrees of each other (inclusive).
        Returns True if either bearing is None (can't determine, assume same).
    """
    if bearing1 is None or bearing2 is None:
        return True

    # Calculate angular difference (handles wraparound at 360°)
    diff = abs(bearing1 - bearing2)
    if diff > 180:
        diff = 360 - diff

    return diff <= threshold


# =============================================================================
# Utility functions
# =============================================================================


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat_rad = math.radians(lat2 - lat1)
    dlon_rad = math.radians(lon2 - lon1)

    a = math.sin(dlat_rad / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon_rad / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def _haversine_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing from point 1 to point 2.

    Args:
        lat1, lon1: Starting point coordinates in degrees
        lat2, lon2: Ending point coordinates in degrees

    Returns:
        Bearing in degrees (0-360, where 0 is North)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon_rad = math.radians(lon2 - lon1)

    x = math.sin(dlon_rad) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360
