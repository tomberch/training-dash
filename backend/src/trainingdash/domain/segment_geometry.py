"""Segment geometry computation utilities.

This module provides utilities for computing segment geometry from GPS records:
- Polyline encoding (reuses polyline.py)
- Bounding box calculation
- Bearing (direction) calculation
- Elevation statistics (gain, avg grade, max grade)
- Gradient segments at fixed intervals

Used when creating segments from activity selections or climb detection.
"""

import math
from dataclasses import dataclass

from trainingdash.domain.polyline import decode_polyline, encode_polyline

# Re-export for convenience
__all__ = [
    "GradientSegment",
    "SegmentGeometry",
    "compute_bearing",
    "compute_bounds",
    "compute_elevation_stats",
    "compute_gradient_segments",
    "compute_segment_geometry",
    "decode_polyline",
    "encode_polyline",
    "haversine_distance",
]


@dataclass
class GradientSegment:
    """A fixed-distance section with its average grade."""

    distance_m: float
    grade_pct: float


@dataclass
class SegmentGeometry:
    """Complete geometry and statistics for a segment."""

    polyline: str  # Google encoded polyline
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    bounds: tuple[float, float, float, float]  # min_lat, min_lon, max_lat, max_lon
    direction_bearing: float  # 0-360 degrees
    distance_m: float
    elevation_gain_m: float
    avg_grade_pct: float
    max_grade_pct: float
    gradient_segments: list[GradientSegment]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in meters between two points using the Haversine formula.

    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def compute_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute initial bearing from point 1 to point 2.

    Args:
        lat1, lon1: Start point coordinates in degrees
        lat2, lon2: End point coordinates in degrees

    Returns:
        Bearing in degrees (0-360), where 0=North, 90=East, 180=South, 270=West
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    x = math.sin(delta_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    theta = math.atan2(x, y)
    bearing = math.degrees(theta)

    # Normalize to 0-360
    return (bearing + 360) % 360


def compute_bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """
    Compute bounding box for a list of points.

    Args:
        points: List of (lat, lon) tuples

    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon)

    Raises:
        ValueError: If points list is empty
    """
    if not points:
        raise ValueError("Cannot compute bounds for empty points list")

    lats = [p[0] for p in points]
    lons = [p[1] for p in points]

    return (min(lats), min(lons), max(lats), max(lons))


def compute_elevation_stats(
    altitudes: list[float],
    distances: list[float],
) -> tuple[float, float, float]:
    """
    Compute elevation gain and grade statistics.

    Args:
        altitudes: List of altitude values in meters
        distances: List of cumulative distance values in meters

    Returns:
        Tuple of (elevation_gain_m, avg_grade_pct, max_grade_pct)

    Raises:
        ValueError: If lists have different lengths or fewer than 2 points
    """
    if len(altitudes) != len(distances):
        raise ValueError("Altitudes and distances must have the same length")
    if len(altitudes) < 2:
        raise ValueError("Need at least 2 points to compute elevation stats")

    elevation_gain = 0.0
    max_grade = 0.0
    grades = []

    for i in range(1, len(altitudes)):
        delta_alt = altitudes[i] - altitudes[i - 1]
        delta_dist = distances[i] - distances[i - 1]

        # Only count positive elevation changes for gain
        if delta_alt > 0:
            elevation_gain += delta_alt

        # Compute grade for this segment
        if delta_dist > 0:
            grade = (delta_alt / delta_dist) * 100
            grades.append(grade)
            if grade > max_grade:
                max_grade = grade

    # Average grade is total elevation change over total distance
    total_elevation_change = altitudes[-1] - altitudes[0]
    total_distance = distances[-1] - distances[0]

    if total_distance > 0:
        avg_grade = (total_elevation_change / total_distance) * 100
    else:
        avg_grade = 0.0

    return (elevation_gain, avg_grade, max_grade)


def compute_gradient_segments(
    records: list[dict],
    segment_length_m: float = 50.0,
) -> list[GradientSegment]:
    """
    Compute gradient at fixed distance intervals.

    Args:
        records: List of record dicts with 'altitude_m' and 'distance_m' keys
        segment_length_m: Target length for each gradient segment

    Returns:
        List of GradientSegment with distance and grade for each interval
    """
    if len(records) < 2:
        return []

    segments = []
    start_idx = 0
    start_distance = records[0].get("distance_m", 0.0)
    start_altitude = records[0].get("altitude_m", 0.0)

    for i in range(1, len(records)):
        current_distance = records[i].get("distance_m", 0.0)
        segment_dist = current_distance - start_distance

        if segment_dist >= segment_length_m:
            current_altitude = records[i].get("altitude_m", 0.0)
            delta_alt = current_altitude - start_altitude

            if segment_dist > 0:
                grade = (delta_alt / segment_dist) * 100
            else:
                grade = 0.0

            segments.append(GradientSegment(distance_m=segment_dist, grade_pct=round(grade, 1)))

            start_idx = i
            start_distance = current_distance
            start_altitude = current_altitude

    # Handle remaining distance (final partial segment)
    if start_idx < len(records) - 1:
        final_distance = records[-1].get("distance_m", 0.0)
        final_altitude = records[-1].get("altitude_m", 0.0)
        remaining_dist = final_distance - start_distance

        if remaining_dist > 0:
            delta_alt = final_altitude - start_altitude
            grade = (delta_alt / remaining_dist) * 100
            segments.append(GradientSegment(distance_m=remaining_dist, grade_pct=round(grade, 1)))

    return segments


def compute_segment_geometry(
    records: list[dict],
    start_index: int,
    end_index: int,
    gradient_segment_length_m: float = 50.0,
) -> SegmentGeometry:
    """
    Compute all geometry and stats for a segment from activity records.

    Used when:
    - Creating manual segment from activity selection
    - Creating suggested segment from climb detection

    Args:
        records: List of record dicts with keys:
            - lat: latitude in degrees
            - lon: longitude in degrees
            - altitude_m: altitude in meters
            - distance_m: cumulative distance in meters
        start_index: Start index in records (inclusive)
        end_index: End index in records (inclusive)
        gradient_segment_length_m: Length for gradient segments

    Returns:
        SegmentGeometry with all computed values

    Raises:
        ValueError: If indices are invalid or insufficient data
    """
    if start_index < 0 or end_index >= len(records):
        raise ValueError(f"Invalid indices: start={start_index}, end={end_index}, records={len(records)}")
    if start_index >= end_index:
        raise ValueError(f"Start index must be less than end index: {start_index} >= {end_index}")

    # Extract segment records
    segment_records = records[start_index : end_index + 1]

    if len(segment_records) < 2:
        raise ValueError("Segment must contain at least 2 records")

    # Extract coordinates for polyline and bounds
    points = []
    for r in segment_records:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is not None and lon is not None:
            points.append((lat, lon))

    if len(points) < 2:
        raise ValueError("Segment must contain at least 2 valid GPS points")

    # Encode polyline
    polyline = encode_polyline(points)

    # Start and end points
    start_lat, start_lon = points[0]
    end_lat, end_lon = points[-1]

    # Bounding box
    bounds = compute_bounds(points)

    # Direction bearing (from start to end)
    direction_bearing = compute_bearing(start_lat, start_lon, end_lat, end_lon)

    # Distance
    start_dist = segment_records[0].get("distance_m", 0.0)
    end_dist = segment_records[-1].get("distance_m", 0.0)
    distance_m = end_dist - start_dist

    # Fallback: compute distance from GPS if distance_m not available
    if distance_m <= 0:
        distance_m = 0.0
        for i in range(1, len(points)):
            distance_m += haversine_distance(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])

    # Elevation stats
    altitudes = []
    distances = []
    base_distance = segment_records[0].get("distance_m", 0.0)

    for r in segment_records:
        alt = r.get("altitude_m")
        dist = r.get("distance_m", 0.0)
        if alt is not None:
            altitudes.append(alt)
            distances.append(dist - base_distance)

    if len(altitudes) >= 2:
        elevation_gain_m, avg_grade_pct, max_grade_pct = compute_elevation_stats(altitudes, distances)
    else:
        elevation_gain_m = 0.0
        avg_grade_pct = 0.0
        max_grade_pct = 0.0

    # Gradient segments
    gradient_segments = compute_gradient_segments(segment_records, gradient_segment_length_m)

    return SegmentGeometry(
        polyline=polyline,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        bounds=bounds,
        direction_bearing=round(direction_bearing, 1),
        distance_m=round(distance_m, 1),
        elevation_gain_m=round(elevation_gain_m, 1),
        avg_grade_pct=round(avg_grade_pct, 2),
        max_grade_pct=round(max_grade_pct, 2),
        gradient_segments=gradient_segments,
    )
