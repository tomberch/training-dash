"""Direction detection for same-route comparison.

This module provides utilities for determining if two activities on the same route
were ridden in the same or opposite direction.

Two approaches are provided:

1. Direction Bearing (recommended): A single bearing value (0-360°) computed from
   the start point to the 25% distance point. Simple, robust, and fast to compare.
   Two activities are considered same-direction if bearings are within 90°.

2. Direction Hash (legacy): An MD5 hash of cardinal direction sequence. More
   sensitive to GPS noise due to boundary effects at 45°/135°/225°/315°.
"""

import hashlib
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
        True if bearings are within threshold degrees of each other.
        Returns True if either bearing is None (can't determine, assume same).
    """
    if bearing1 is None or bearing2 is None:
        return True

    # Calculate angular difference (handles wraparound at 360°)
    diff = abs(bearing1 - bearing2)
    if diff > 180:
        diff = 360 - diff

    return diff < threshold


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


def _quantize_bearing_coarse(bearing: float) -> str:
    """Quantize bearing to 4 cardinal directions.

    Args:
        bearing: Bearing in degrees (0-360)

    Returns:
        Single character: N, E, S, or W
    """
    # Each direction covers 90 degrees
    # N: 315-45, E: 45-135, S: 135-225, W: 225-315
    if bearing >= 315 or bearing < 45:
        return "N"
    elif bearing >= 45 and bearing < 135:
        return "E"
    elif bearing >= 135 and bearing < 225:
        return "S"
    else:
        return "W"


# =============================================================================
# Direction Hash (legacy - kept for backwards compatibility)
# =============================================================================


def compute_direction_hash(
    gps_points: list[tuple[float, float, float | None]],
    segment_distance_m: float = 500.0,
    min_segments: int = 3,
) -> str | None:
    """Compute a direction hash from GPS coordinates.

    The hash is computed by sampling the GPS track at regular distance intervals
    and recording the dominant direction for each segment. Two activities going
    in the same direction will produce the same hash; activities going in 
    opposite directions will produce different hashes.

    Args:
        gps_points: List of (lat, lon, distance_m) tuples. distance_m can be None.
        segment_distance_m: Distance interval for sampling (default 500m)
        min_segments: Minimum number of segments required (default 3)

    Returns:
        32-character hex hash string, or None if insufficient GPS data
    """
    if len(gps_points) < 10:
        return None

    # Filter to valid GPS points with lat/lon
    valid_points = [(lat, lon, dist) for lat, lon, dist in gps_points if lat is not None and lon is not None]

    if len(valid_points) < 10:
        return None

    # If we have distance data, use it; otherwise compute cumulative distance
    has_distance = valid_points[0][2] is not None

    if has_distance:
        # Use provided distance values
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

    # Get total distance
    total_distance = points_with_dist[-1][2]
    if total_distance < segment_distance_m * min_segments:
        return None

    # Sample at regular distance intervals
    sample_distances = []
    d = 0.0
    while d <= total_distance:
        sample_distances.append(d)
        d += segment_distance_m

    if len(sample_distances) < min_segments + 1:
        return None

    # Find GPS points closest to each sample distance
    sampled_points: list[tuple[float, float]] = []
    point_idx = 0
    
    for target_dist in sample_distances:
        # Find the point with distance closest to target
        while point_idx < len(points_with_dist) - 1:
            curr_dist = points_with_dist[point_idx][2]
            next_dist = points_with_dist[point_idx + 1][2]
            
            if next_dist >= target_dist:
                # Use whichever is closer
                if abs(curr_dist - target_dist) <= abs(next_dist - target_dist):
                    sampled_points.append((points_with_dist[point_idx][0], points_with_dist[point_idx][1]))
                else:
                    sampled_points.append((points_with_dist[point_idx + 1][0], points_with_dist[point_idx + 1][1]))
                break
            point_idx += 1
        else:
            # Use last point
            sampled_points.append((points_with_dist[-1][0], points_with_dist[-1][1]))

    if len(sampled_points) < min_segments + 1:
        return None

    # Compute direction for each segment
    directions: list[str] = []
    for i in range(len(sampled_points) - 1):
        lat1, lon1 = sampled_points[i]
        lat2, lon2 = sampled_points[i + 1]
        
        # Skip if points are too close (GPS noise)
        dist = _haversine_distance(lat1, lon1, lat2, lon2)
        if dist < 10:  # Less than 10m apart
            continue
            
        bearing = _haversine_bearing(lat1, lon1, lat2, lon2)
        direction = _quantize_bearing_coarse(bearing)
        directions.append(direction)

    if len(directions) < min_segments:
        return None

    # Create a stable string representation
    direction_str = "".join(directions)

    # Hash to fixed-length string
    return hashlib.md5(direction_str.encode()).hexdigest()


def directions_match(hash1: str | None, hash2: str | None) -> bool:
    """Check if two direction hashes indicate the same direction.

    Args:
        hash1: First direction hash (or None)
        hash2: Second direction hash (or None)

    Returns:
        True if both hashes are non-None and equal, False otherwise.
        Returns True if either hash is None (can't determine, assume same).
    """
    if hash1 is None or hash2 is None:
        # If we can't determine direction, assume same (fail open)
        return True
    return hash1 == hash2
