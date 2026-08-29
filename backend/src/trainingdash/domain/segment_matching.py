"""Segment matching algorithm for GPS activity records.

This module matches activity GPS tracks against known segments:
1. Filter candidates by direction (bearing within tolerance)
2. Find activity points near segment start/end
3. Compute path overlap percentage
4. Accept matches meeting minimum overlap threshold

The algorithm handles GPS wobble, multiple crossings of the same segment,
and correctly rejects parallel roads or opposite-direction travel.
"""

import math
from dataclasses import dataclass
from uuid import UUID

from trainingdash.domain.polyline import decode_polyline
from trainingdash.domain.segment_geometry import compute_bearing, haversine_distance

__all__ = [
    "SegmentCandidate",
    "SegmentMatch",
    "bearings_match",
    "compute_path_overlap",
    "match_activity_to_segments",
    "point_to_segment_distance",
]


@dataclass
class SegmentMatch:
    """A matched segment within an activity.

    Attributes:
        segment_id: UUID of the matched segment
        start_index: Index of first activity record in the match
        end_index: Index of last activity record in the match (inclusive)
        overlap_pct: Percentage of segment path covered by activity (0-100)
    """

    segment_id: UUID
    start_index: int
    end_index: int
    overlap_pct: float


@dataclass
class SegmentCandidate:
    """A segment to match against an activity.

    Attributes:
        id: Segment UUID
        polyline: Google-encoded polyline of segment path
        start_lat: Latitude of segment start
        start_lon: Longitude of segment start
        end_lat: Latitude of segment end
        end_lon: Longitude of segment end
        direction_bearing: Direction of travel (0-360 degrees)
        distance_m: Total segment distance in meters
    """

    id: UUID
    polyline: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    direction_bearing: float
    distance_m: float


def bearings_match(bearing1: float, bearing2: float, tolerance: float = 30) -> bool:
    """
    Check if two bearings are within tolerance, handling 360° wraparound.

    Args:
        bearing1: First bearing in degrees (0-360)
        bearing2: Second bearing in degrees (0-360)
        tolerance: Maximum allowed difference in degrees

    Returns:
        True if bearings are within tolerance

    Examples:
        >>> bearings_match(10, 350, 30)  # 20° difference across 0
        True
        >>> bearings_match(90, 270, 30)  # 180° difference
        False
    """
    # Normalize bearings to 0-360
    b1 = bearing1 % 360
    b2 = bearing2 % 360

    # Calculate difference, handling wraparound
    diff = abs(b1 - b2)
    if diff > 180:
        diff = 360 - diff

    return diff <= tolerance


def point_to_segment_distance(
    point_lat: float,
    point_lon: float,
    seg_start_lat: float,
    seg_start_lon: float,
    seg_end_lat: float,
    seg_end_lon: float,
) -> float:
    """
    Compute minimum distance from a point to a line segment.

    Uses projection to find the closest point on the segment,
    clamped to segment endpoints.

    Args:
        point_lat, point_lon: Point coordinates
        seg_start_lat, seg_start_lon: Segment start coordinates
        seg_end_lat, seg_end_lon: Segment end coordinates

    Returns:
        Distance in meters from point to nearest point on segment
    """
    # Convert to approximate Cartesian (works for small distances)
    # Use cosine correction for longitude at the latitude
    avg_lat = (seg_start_lat + seg_end_lat) / 2
    cos_lat = math.cos(math.radians(avg_lat))

    # Scale factor: degrees to approximate meters
    lat_scale = 111320  # meters per degree latitude
    lon_scale = 111320 * cos_lat  # meters per degree longitude

    # Convert to local coordinates
    px = (point_lon - seg_start_lon) * lon_scale
    py = (point_lat - seg_start_lat) * lat_scale
    sx = 0  # Segment start at origin
    sy = 0
    ex = (seg_end_lon - seg_start_lon) * lon_scale
    ey = (seg_end_lat - seg_start_lat) * lat_scale

    # Vector from start to end
    dx = ex - sx
    dy = ey - sy

    # Segment length squared
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        # Segment is a point
        return haversine_distance(point_lat, point_lon, seg_start_lat, seg_start_lon)

    # Project point onto line, clamped to [0, 1]
    t = max(0, min(1, ((px - sx) * dx + (py - sy) * dy) / seg_len_sq))

    # Closest point on segment
    closest_x = sx + t * dx
    closest_y = sy + t * dy

    # Distance from point to closest point
    dist_local = math.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)

    return dist_local


def _find_points_near_location(
    records: list[dict],
    target_lat: float,
    target_lon: float,
    tolerance_m: float,
    start_from: int = 0,
) -> list[int]:
    """
    Find all record indices within tolerance of a target location.

    Args:
        records: Activity records with lat/lon
        target_lat, target_lon: Target coordinates
        tolerance_m: Maximum distance in meters
        start_from: Start searching from this index

    Returns:
        List of record indices within tolerance
    """
    indices = []
    for i in range(start_from, len(records)):
        lat = records[i].get("lat")
        lon = records[i].get("lon")
        if lat is None or lon is None:
            continue

        dist = haversine_distance(lat, lon, target_lat, target_lon)
        if dist <= tolerance_m:
            indices.append(i)

    return indices


def _compute_activity_bearing(records: list[dict], start_idx: int, end_idx: int) -> float:
    """
    Compute the overall bearing of activity section.

    Args:
        records: Activity records
        start_idx: Start index
        end_idx: End index

    Returns:
        Bearing in degrees (0-360)
    """
    start_lat = records[start_idx].get("lat", 0)
    start_lon = records[start_idx].get("lon", 0)
    end_lat = records[end_idx].get("lat", 0)
    end_lon = records[end_idx].get("lon", 0)

    return compute_bearing(start_lat, start_lon, end_lat, end_lon)


def compute_path_overlap(
    activity_records: list[dict],
    start_index: int,
    end_index: int,
    segment_polyline: str,
    buffer_m: float = 35,
) -> float:
    """
    Compute what percentage of segment path is covered by activity.

    Decodes the segment polyline and checks what fraction of segment
    points are within buffer_m of the activity path.

    Args:
        activity_records: Activity records with lat/lon
        start_index: Start index in activity
        end_index: End index in activity (inclusive)
        segment_polyline: Google-encoded polyline of segment
        buffer_m: Buffer distance in meters

    Returns:
        Overlap percentage (0-100)
    """
    # Decode segment polyline
    segment_points = decode_polyline(segment_polyline)
    if not segment_points:
        return 0.0

    # Extract activity section
    activity_section = activity_records[start_index : end_index + 1]
    if len(activity_section) < 2:
        return 0.0

    # Build activity path segments for distance checking
    activity_points = []
    for r in activity_section:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is not None and lon is not None:
            activity_points.append((lat, lon))

    if len(activity_points) < 2:
        return 0.0

    # Check each segment point against activity path
    covered_count = 0

    for seg_lat, seg_lon in segment_points:
        # Find minimum distance to any activity path segment
        min_dist = float("inf")

        for i in range(len(activity_points) - 1):
            dist = point_to_segment_distance(
                seg_lat,
                seg_lon,
                activity_points[i][0],
                activity_points[i][1],
                activity_points[i + 1][0],
                activity_points[i + 1][1],
            )
            if dist < min_dist:
                min_dist = dist

        if min_dist <= buffer_m:
            covered_count += 1

    return (covered_count / len(segment_points)) * 100


def match_activity_to_segments(
    records: list[dict],
    candidates: list[SegmentCandidate],
    start_tolerance_m: float = 25,
    end_tolerance_m: float = 25,
    direction_tolerance_deg: float = 30,
    min_overlap_pct: float = 90,
    buffer_m: float = 35,
) -> list[SegmentMatch]:
    """
    Match activity against candidate segments.

    For each candidate:
    1. Find activity points within start_tolerance_m of segment start
    2. Find activity points within end_tolerance_m of segment end
    3. For each valid start/end pair (start before end):
       a. Check direction within tolerance
       b. Compute path overlap
       c. Accept if overlap >= min_overlap_pct

    Args:
        records: Activity records with lat, lon, distance_m keys
        candidates: List of segment candidates to match against
        start_tolerance_m: Max distance from segment start (default 25m)
        end_tolerance_m: Max distance from segment end (default 25m)
        direction_tolerance_deg: Max bearing difference (default 30°)
        min_overlap_pct: Minimum overlap percentage (default 90%)
        buffer_m: Buffer for path overlap calculation (default 35m)

    Returns:
        List of SegmentMatch objects for all matches found.
        May include multiple matches for the same segment (loop rides).
    """
    if len(records) < 2:
        return []

    matches = []

    for candidate in candidates:
        # Find all activity points near segment start
        start_points = _find_points_near_location(records, candidate.start_lat, candidate.start_lon, start_tolerance_m)

        if not start_points:
            continue

        # Find all activity points near segment end
        end_points = _find_points_near_location(records, candidate.end_lat, candidate.end_lon, end_tolerance_m)

        if not end_points:
            continue

        # Try all valid start/end combinations
        for start_idx in start_points:
            for end_idx in end_points:
                # End must be after start
                if end_idx <= start_idx:
                    continue

                # Check minimum distance traveled (avoid false matches on very short sections)
                start_dist = records[start_idx].get("distance_m", 0)
                end_dist = records[end_idx].get("distance_m", 0)
                traveled = end_dist - start_dist

                # Activity section should be at least 50% of segment distance
                if traveled < candidate.distance_m * 0.5:
                    continue

                # Check direction
                activity_bearing = _compute_activity_bearing(records, start_idx, end_idx)
                if not bearings_match(activity_bearing, candidate.direction_bearing, direction_tolerance_deg):
                    continue

                # Compute path overlap
                overlap = compute_path_overlap(records, start_idx, end_idx, candidate.polyline, buffer_m)

                if overlap >= min_overlap_pct:
                    matches.append(
                        SegmentMatch(
                            segment_id=candidate.id,
                            start_index=start_idx,
                            end_index=end_idx,
                            overlap_pct=round(overlap, 1),
                        )
                    )

    # Sort by start index
    matches.sort(key=lambda m: m.start_index)

    return matches
