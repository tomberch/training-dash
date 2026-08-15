"""Direction detection for same-route comparison.

This module provides utilities for determining if two activities on the same route
were ridden in the same or opposite direction.

The direction bearing is a single value (0-359°) computed from the start point to
the 25% distance point. Two activities are considered same-direction if their
bearings are within 90° of each other.

This approach is:
- Simple: one integer to store and compare
- Robust: not sensitive to GPS noise at cardinal direction boundaries
- Fast: O(1) comparison at query time
- Works for all route types: point-to-point and loops
"""

import math

# =============================================================================
# Direction Bearing (recommended approach)
# =============================================================================


def compute_direction_bearing(
    gps_points: list[tuple[float, float, float | None]],
    target_pct: float = 0.25,
    min_distance_m: float = 1000.0,
) -> int | None:
    """Compute a direction bearing from GPS coordinates.

    The bearing is computed from the start point to a point at target_pct of the
    total distance. This single value robustly captures the initial direction of
    travel and works for both point-to-point and loop routes.

    Args:
        gps_points: List of (lat, lon, distance_m) tuples. distance_m can be None.
        target_pct: Percentage of total distance for target point (default 0.25)
        min_distance_m: Minimum total distance required (default 1000m)

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

    # Find point at target percentage of distance
    target_dist = total_distance * target_pct
    start = points_with_dist[0]
    target = min(points_with_dist, key=lambda p: abs(p[2] - target_dist))

    # Compute bearing from start to target
    bearing = _haversine_bearing(start[0], start[1], target[0], target[1])

    # Round to integer (0-359)
    return round(bearing) % 360


def bearings_match(bearing1: int | None, bearing2: int | None, threshold: int = 90) -> bool:
    """Check if two direction bearings indicate the same direction of travel.

    Args:
        bearing1: First bearing in degrees (0-359), or None
        bearing2: Second bearing in degrees (0-359), or None
        threshold: Maximum angular difference to consider same direction (default 90°)

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
