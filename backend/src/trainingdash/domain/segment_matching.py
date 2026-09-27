"""Segment matching algorithm for GPS activity records.

This module matches activity GPS tracks against known segments:
1. Filter candidates by direction (bearing within tolerance)
2. Find activity points near segment start/end
3. Compute path overlap percentage
4. Accept matches meeting minimum overlap threshold

The algorithm handles GPS wobble, multiple crossings of the same segment,
and correctly rejects parallel roads or opposite-direction travel.

Performance note: compute_path_overlap uses Shapely's buffer + prepared geometry
approach for O(n log m) complexity instead of O(n*m) brute force. This enables
sub-second matching for segments with 5000 points against activities with 20000 records.
"""

import math
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from shapely import LineString, contains_xy, prepare

from trainingdash.domain.polyline import decode_polyline
from trainingdash.domain.segment_geometry import compute_bearing, haversine_distance

__all__ = [
    "SAME_SEGMENT_ENDPOINT_TOLERANCE_M",
    "SAME_SEGMENT_MIN_OVERLAP_PCT",
    "SUGGESTION_VISIBILITY_THRESHOLD",
    "SegmentCandidate",
    "SegmentMatch",
    "bearings_match",
    "compute_path_overlap",
    "describes_same_road",
    "is_same_segment",
    "is_suggestion_visible",
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


def _meters_to_degrees(meters: float, latitude: float) -> float:
    """
    Convert meters to approximate degrees at a given latitude.

    Uses the WGS84 approximation where 1 degree latitude ≈ 111,320m
    and 1 degree longitude ≈ 111,320m * cos(latitude).

    For a buffer, we use the smaller dimension (longitude at high latitudes)
    to ensure the buffer covers at least the specified distance in all directions.

    Args:
        meters: Distance in meters
        latitude: Reference latitude in degrees

    Returns:
        Approximate degrees (conservative estimate)
    """
    # Meters per degree latitude (roughly constant)
    meters_per_deg_lat = 111320.0
    # Meters per degree longitude (varies with latitude)
    meters_per_deg_lon = 111320.0 * math.cos(math.radians(latitude))

    # Use the smaller scale factor (more degrees needed) for conservative buffer
    meters_per_deg = min(meters_per_deg_lat, meters_per_deg_lon)

    return meters / meters_per_deg


def _simplify_path(
    points: list[tuple[float, float]], tolerance_m: float, center_lat: float
) -> list[tuple[float, float]]:
    """
    Simplify a path using Douglas-Peucker algorithm.

    Args:
        points: List of (lat, lon) tuples
        tolerance_m: Simplification tolerance in meters
        center_lat: Reference latitude for meter-to-degree conversion

    Returns:
        Simplified list of (lat, lon) tuples
    """
    if len(points) < 3:
        return points

    # Convert to (lon, lat) for Shapely
    coords = [(lon, lat) for lat, lon in points]
    line = LineString(coords)

    # Convert tolerance from meters to degrees
    tolerance_deg = _meters_to_degrees(tolerance_m, center_lat)

    simplified = line.simplify(tolerance_deg, preserve_topology=True)

    # Convert back to (lat, lon)
    return [(lat, lon) for lon, lat in simplified.coords]


def compute_path_overlap(
    activity_records: list[dict],
    start_index: int,
    end_index: int,
    segment_polyline: str,
    buffer_m: float = 35,
    max_segment_points: int = 500,  # Kept for API compatibility, but not used in new algorithm
) -> float:
    """
    Compute what percentage of segment path is covered by activity.

    Uses Shapely's buffer + prepared geometry approach for O(n log m) complexity
    instead of O(n*m) brute force. The algorithm:
    1. Simplifies both paths using Douglas-Peucker (10m tolerance)
    2. Creates a buffer polygon around the activity path
    3. Uses vectorized point-in-polygon tests via shapely.contains_xy()

    Args:
        activity_records: Activity records with lat/lon
        start_index: Start index in activity
        end_index: End index in activity (inclusive)
        segment_polyline: Google-encoded polyline of segment
        buffer_m: Buffer distance in meters (default 35m)
        max_segment_points: Unused, kept for API compatibility

    Returns:
        Overlap percentage (0-100)
    """
    # Decode segment polyline
    segment_points = decode_polyline(segment_polyline)
    if not segment_points or len(segment_points) < 2:
        return 0.0

    # Extract activity section
    activity_section = activity_records[start_index : end_index + 1]
    if len(activity_section) < 2:
        return 0.0

    # Extract activity coordinates
    activity_points: list[tuple[float, float]] = []
    for r in activity_section:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is not None and lon is not None:
            activity_points.append((lat, lon))

    if len(activity_points) < 2:
        return 0.0

    # Calculate center latitude for coordinate conversions
    center_lat = sum(p[0] for p in segment_points) / len(segment_points)

    # Simplify paths for performance (10m tolerance is safe for 35m buffer)
    simplify_tolerance_m = 10.0
    segment_simplified = _simplify_path(segment_points, simplify_tolerance_m, center_lat)
    activity_simplified = _simplify_path(activity_points, simplify_tolerance_m, center_lat)

    if len(segment_simplified) < 2 or len(activity_simplified) < 2:
        return 0.0

    # Create activity LineString (Shapely uses lon, lat order)
    activity_coords = [(lon, lat) for lat, lon in activity_simplified]
    activity_line = LineString(activity_coords)

    # Create buffer around activity path
    # Convert buffer distance from meters to degrees
    buffer_deg = _meters_to_degrees(buffer_m, center_lat)
    activity_buffer = activity_line.buffer(buffer_deg, cap_style="round", join_style="round")

    # Prepare the buffer for fast repeated point-in-polygon tests
    # This builds an R-tree index on the polygon boundary
    prepare(activity_buffer)

    # Extract segment coordinates as numpy arrays for vectorized testing
    seg_lons = np.array([lon for lat, lon in segment_simplified])
    seg_lats = np.array([lat for lat, lon in segment_simplified])

    # Vectorized point-in-polygon test
    # contains_xy returns a boolean array indicating which points are inside the buffer
    covered = contains_xy(activity_buffer, seg_lons, seg_lats)

    # Calculate coverage percentage
    covered_count = int(np.sum(covered))
    return (covered_count / len(segment_simplified)) * 100.0


# Duplicate-segment criteria (ticket #473)
SAME_SEGMENT_ENDPOINT_TOLERANCE_M = 25.0
SAME_SEGMENT_MIN_OVERLAP_PCT = 95.0

# Same-road criteria for suggestion dedup (ticket #473 follow-up).
# Auto-detected climb boundaries wobble between rides: the detector may
# start the same climb metres apart, or extend it partway down the descent.
# Endpoint gates (is_same_segment) reject those near-duplicates, so repeat
# rides never reach the 3-repetition visibility threshold. Instead we ask
# whether one path essentially *contains* the other: >= 90% of the shorter
# path's resampled points lie within 35 m of the longer path.
SAME_ROAD_MIN_CONTAINMENT_PCT = 90.0
SAME_ROAD_BUFFER_M = 35.0
SAME_ROAD_RESAMPLE_SPACING_M = 15.0

# Suggestion visibility: climbs are proposed after 3+ repeat rides
# (CONTEXT.md — Segment Suggestion lifecycle)
SUGGESTION_VISIBILITY_THRESHOLD = 3


def is_suggestion_visible(repetition_count: int, expires_at, now) -> bool:
    """
    Visibility rule shared by listing, counting, and dismissal.

    A suggestion is visible when the user has ridden the climb at least
    SUGGESTION_VISIBILITY_THRESHOLD times and the suggestion has not
    expired (CONTEXT.md: expires 90 days after last ride).
    """
    if repetition_count < SUGGESTION_VISIBILITY_THRESHOLD:
        return False
    # Check if suggestion has expired
    if expires_at is not None and now is not None:
        return expires_at >= now
    return True


def is_same_segment(
    *,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    polyline: str,
    other_start_lat: float,
    other_start_lon: float,
    other_end_lat: float,
    other_end_lon: float,
    other_polyline: str,
    endpoint_tolerance_m: float = SAME_SEGMENT_ENDPOINT_TOLERANCE_M,
    min_overlap_pct: float = SAME_SEGMENT_MIN_OVERLAP_PCT,
) -> bool:
    """
    Decide whether two segments describe the same stretch of road.

    Duplicate criteria (ticket #473): start points within 25m, end points
    within 25m, and >= 95% path overlap (with the caller's polyline
    measured against the other's). Used by suggestion approval and
    climb-detection dedup so every flow agrees on "the same segment".

    Returns False on empty or undecodable polylines — a corrupt candidate
    is never a duplicate.
    """
    # Endpoint proximity gates — cheap and directional by construction
    if haversine_distance(start_lat, start_lon, other_start_lat, other_start_lon) > endpoint_tolerance_m:
        return False
    if haversine_distance(end_lat, end_lon, other_end_lat, other_end_lon) > endpoint_tolerance_m:
        return False

    # Path overlap — measure the other's coverage of the caller's polyline
    try:
        other_points = decode_polyline(other_polyline)
    except Exception:
        return False
    if not other_points:
        return False

    fake_records = [{"lat": lat, "lon": lon} for lat, lon in other_points]
    overlap = compute_path_overlap(
        activity_records=fake_records,
        start_index=0,
        end_index=len(fake_records) - 1,
        segment_polyline=polyline,
        buffer_m=endpoint_tolerance_m,
    )

    return overlap >= min_overlap_pct


def _resample_path(
    points: list[tuple[float, float]], spacing_m: float
) -> list[tuple[float, float]]:
    """Resample a path to roughly fixed spacing (keeps endpoints).

    Thins dense GPS captures by keeping the first point at least spacing_m
    past the last kept point, and *densifies* sparse paths by interpolating
    between vertices so a 2-point polyline is measured like its dense
    real-world shape.
    """
    if len(points) < 2:
        return list(points)

    out = [points[0]]
    kept = points[0]
    acc = 0.0  # distance walked since the last kept point
    for curr in points[1:]:
        acc += haversine_distance(kept[0], kept[1], curr[0], curr[1])
        if acc < spacing_m:
            continue
        # Reached spacing: interpolate from kept toward curr at spacing_m,
        # then keep curr itself as the new anchor.
        seg_d = haversine_distance(kept[0], kept[1], curr[0], curr[1])
        if seg_d > 0:
            n_steps = int(acc / spacing_m)
            for k in range(1, n_steps + 1):
                frac = min(k * spacing_m / seg_d, 1.0)
                out.append(
                    (
                        kept[0] + (curr[0] - kept[0]) * frac,
                        kept[1] + (curr[1] - kept[1]) * frac,
                    )
                )
        out.append(curr)
        kept = curr
        acc = 0.0
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def _path_containment_pct(
    shorter: list[tuple[float, float]],
    longer: list[tuple[float, float]],
    buffer_m: float,
) -> float:
    """Percentage of `shorter` path points within buffer_m of `longer` path.

    Distance is point-to-*segment* (projection onto each of the longer
    path's segments), not point-to-vertex: vertex-only measurement with
    100 m-spaced vertices undercounts by up to ~50 m even on identical
    roads, which breaks the containment test.
    """
    covered = 0
    segments = list(zip(longer, longer[1:]))
    for lat, lon in shorter:
        for (s_lat, s_lon), (e_lat, e_lon) in segments:
            d = point_to_segment_distance(lat, lon, s_lat, s_lon, e_lat, e_lon)
            if d <= buffer_m:
                covered += 1
                break
    return (covered / len(shorter)) * 100


def describes_same_road(
    polyline: str,
    other_polyline: str,
    min_containment_pct: float = SAME_ROAD_MIN_CONTAINMENT_PCT,
    buffer_m: float = SAME_ROAD_BUFFER_M,
) -> bool:
    """
    Decide whether two auto-detected segments describe the same road.

    Containment criterion: resample both paths to fixed spacing, then check
    whether >= min_containment_pct of the *shorter* path lies within
    buffer_m of the *longer* one. Symmetric by construction (the shorter
    is always the one measured). Tolerates boundary wobble between rides
    — start/end may differ by hundreds of metres — while rejecting
    diverging, parallel, or merely crossing roads.

    Used by climb-detection dedup (find_similar_suggested). Strict
    endpoint+overlap matching (is_same_segment) remains the gate for
    suggestion approval, where exact-duplicate protection matters.

    Returns False on empty or undecodable polylines — a corrupt candidate
    is never a duplicate.
    """
    try:
        points = decode_polyline(polyline)
        other_points = decode_polyline(other_polyline)
    except Exception:
        return False
    if len(points) < 2 or len(other_points) < 2:
        return False

    points = _resample_path(points, SAME_ROAD_RESAMPLE_SPACING_M)
    other_points = _resample_path(other_points, SAME_ROAD_RESAMPLE_SPACING_M)

    # Measure containment in both directions and take the max: one detection
    # may cover only part of the other's road (e.g. climb caught with or
    # without its run-in), and equal point counts don't imply equal length.
    containment = max(
        _path_containment_pct(points, other_points, buffer_m),
        _path_containment_pct(other_points, points, buffer_m),
    )

    return containment >= min_containment_pct


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

    # Deduplicate overlapping matches for the same segment
    # Keep the match with highest overlap when ranges overlap significantly
    matches = _deduplicate_matches(matches)

    return matches


def _deduplicate_matches(matches: list[SegmentMatch]) -> list[SegmentMatch]:
    """
    Remove duplicate matches for the same segment that overlap significantly.

    When multiple matches exist for the same segment with overlapping index ranges,
    keep only the one with the highest overlap percentage. Two matches are considered
    overlapping if their index ranges share more than 50% of the smaller range.

    Args:
        matches: List of matches sorted by start_index

    Returns:
        Deduplicated list of matches
    """
    if len(matches) <= 1:
        return matches

    # Group matches by segment_id
    by_segment: dict[UUID, list[SegmentMatch]] = {}
    for match in matches:
        if match.segment_id not in by_segment:
            by_segment[match.segment_id] = []
        by_segment[match.segment_id].append(match)

    result = []

    for segment_id, segment_matches in by_segment.items():
        if len(segment_matches) == 1:
            result.append(segment_matches[0])
            continue

        # Sort by overlap descending to prefer better matches
        segment_matches.sort(key=lambda m: -m.overlap_pct)

        kept: list[SegmentMatch] = []
        for match in segment_matches:
            # Check if this match overlaps significantly with any kept match
            overlaps_existing = False
            for kept_match in kept:
                if _ranges_overlap_significantly(
                    match.start_index,
                    match.end_index,
                    kept_match.start_index,
                    kept_match.end_index,
                ):
                    overlaps_existing = True
                    break

            if not overlaps_existing:
                kept.append(match)

        result.extend(kept)

    # Re-sort by start index
    result.sort(key=lambda m: m.start_index)
    return result


def _ranges_overlap_significantly(start1: int, end1: int, start2: int, end2: int, threshold: float = 0.5) -> bool:
    """
    Check if two index ranges overlap by more than threshold of the smaller range.

    Args:
        start1, end1: First range (inclusive)
        start2, end2: Second range (inclusive)
        threshold: Minimum overlap fraction to consider significant (default 0.5)

    Returns:
        True if ranges overlap significantly
    """
    # Calculate overlap
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)

    if overlap_start > overlap_end:
        # No overlap
        return False

    overlap_size = overlap_end - overlap_start + 1

    # Size of smaller range
    size1 = end1 - start1 + 1
    size2 = end2 - start2 + 1
    smaller_size = min(size1, size2)

    return (overlap_size / smaller_size) >= threshold
