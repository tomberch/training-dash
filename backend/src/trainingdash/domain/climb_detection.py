"""Climb detection algorithm for identifying climbs from GPS records.

This module provides automatic detection of climbs from activity GPS data,
including categorization using the standard length × grade formula used in
professional cycling.

The algorithm:
1. Smooths elevation data to remove GPS noise
2. Computes gradient at fixed intervals (default 50m)
3. Identifies sections with grade >= 3%
4. Merges nearby climbs if gap is small and elevation drop is minimal
5. Filters by minimum length
6. Categorizes using the standard climb scoring formula
"""

from dataclasses import dataclass

import numpy as np

from trainingdash.domain.elevation import smooth_elevation as savgol_smooth


@dataclass
class GradientSegment:
    """A segment of road with a specific gradient.

    Used to represent the gradient profile of a climb, typically
    at 50m intervals for display and analysis.
    """

    distance_m: float
    grade_pct: float


@dataclass
class DetectedClimb:
    """A detected climb with its characteristics.

    Contains all the information needed to create a Segment entity
    from automatically detected climb data.
    """

    start_index: int
    end_index: int
    distance_m: float
    elevation_gain_m: float
    avg_grade_pct: float
    max_grade_pct: float
    category: str  # 'hc', '1', '2', '3', '4', 'nc'
    gradient_segments: list[GradientSegment]


def categorize_climb(distance_m: float, avg_grade_pct: float) -> str:
    """Categorize a climb using the length × grade formula.

    This is the standard formula used in professional cycling to
    categorize climbs. The score is calculated as distance (m) × grade (%).

    Thresholds (based on Tour de France categorization):
    - HC (Hors Catégorie): >= 80,000 (e.g., 10km at 8%)
    - Cat 1: >= 64,000 (e.g., 8km at 8%)
    - Cat 2: >= 32,000 (e.g., 4km at 8%)
    - Cat 3: >= 16,000 (e.g., 2km at 8%)
    - Cat 4: >= 8,000 (e.g., 1km at 8%)
    - NC (uncategorized): < 8,000

    Args:
        distance_m: Climb length in meters.
        avg_grade_pct: Average gradient as percentage (5.0 = 5%).

    Returns:
        Category string: 'hc', '1', '2', '3', '4', or 'nc'.
    """
    score = distance_m * avg_grade_pct

    if score >= 80000:
        return "hc"
    if score >= 64000:
        return "1"
    if score >= 32000:
        return "2"
    if score >= 16000:
        return "3"
    if score >= 8000:
        return "4"
    return "nc"


def smooth_elevation_simple(altitudes: list[float], window: int = 5) -> list[float]:
    """Apply simple moving average smoothing to elevation data.

    This is a lightweight alternative to Savitzky-Golay filtering,
    useful when scipy is not available or for quick processing.

    Args:
        altitudes: Raw elevation values in meters.
        window: Window size for moving average (should be odd).

    Returns:
        Smoothed elevation values.
    """
    if len(altitudes) < window:
        return altitudes.copy() if isinstance(altitudes, list) else list(altitudes)

    result = []
    half = window // 2

    for i in range(len(altitudes)):
        start = max(0, i - half)
        end = min(len(altitudes), i + half + 1)
        result.append(sum(altitudes[start:end]) / (end - start))

    return result


def compute_gradient_segments(
    records: list[dict],
    segment_length_m: float = 50.0,
) -> list[GradientSegment]:
    """Compute gradient at fixed distance intervals.

    Divides the route into fixed-length segments and calculates
    the average gradient for each segment. This provides a consistent
    representation of the gradient profile regardless of GPS point density.

    Args:
        records: List of dicts with 'distance_m' and 'altitude_m' keys.
        segment_length_m: Length of each segment in meters.

    Returns:
        List of GradientSegment objects representing the gradient profile.
    """
    if len(records) < 2:
        return []

    # Extract arrays
    distances = np.array([r["distance_m"] for r in records], dtype=np.float64)
    altitudes = np.array([r["altitude_m"] for r in records], dtype=np.float64)

    # Smooth elevations using Savitzky-Golay filter
    smoothed = savgol_smooth(altitudes)

    total_distance = distances[-1] - distances[0]
    if total_distance < segment_length_m:
        # Single segment for very short distances
        elev_gain = smoothed[-1] - smoothed[0]
        grade_pct = (elev_gain / total_distance) * 100 if total_distance > 0 else 0.0
        return [GradientSegment(distance_m=total_distance, grade_pct=grade_pct)]

    segments = []
    start_dist = distances[0]

    while start_dist < distances[-1]:
        end_dist = min(start_dist + segment_length_m, distances[-1])

        # Find indices for start and end of this segment
        start_idx = np.searchsorted(distances, start_dist)
        end_idx = np.searchsorted(distances, end_dist)

        # Ensure we have valid indices
        start_idx = min(start_idx, len(distances) - 1)
        end_idx = min(end_idx, len(distances) - 1)

        # Interpolate elevations at exact segment boundaries
        if start_idx > 0 and distances[start_idx] != start_dist:
            # Linear interpolation for start elevation
            idx = start_idx - 1
            frac = (start_dist - distances[idx]) / (distances[start_idx] - distances[idx])
            start_elev = smoothed[idx] + frac * (smoothed[start_idx] - smoothed[idx])
        else:
            start_elev = smoothed[start_idx]

        if end_idx > 0 and distances[end_idx] != end_dist:
            idx = end_idx - 1
            if distances[end_idx] != distances[idx]:
                frac = (end_dist - distances[idx]) / (distances[end_idx] - distances[idx])
                end_elev = smoothed[idx] + frac * (smoothed[end_idx] - smoothed[idx])
            else:
                end_elev = smoothed[end_idx]
        else:
            end_elev = smoothed[end_idx]

        segment_dist = end_dist - start_dist
        elev_change = end_elev - start_elev
        grade_pct = (elev_change / segment_dist) * 100 if segment_dist > 0 else 0.0

        segments.append(GradientSegment(distance_m=segment_dist, grade_pct=grade_pct))

        start_dist = end_dist

    return segments


def _find_climbing_sections(
    distances: np.ndarray,
    smoothed: np.ndarray,
    min_grade_pct: float,
) -> list[tuple[int, int]]:
    """Find sections where grade exceeds minimum threshold.

    Returns list of (start_idx, end_idx) tuples for climbing sections.
    """
    n = len(distances)
    if n < 2:
        return []

    # Calculate point-to-point grades
    grades = np.zeros(n)
    for i in range(1, n):
        d_dist = distances[i] - distances[i - 1]
        if d_dist > 0:
            grades[i] = ((smoothed[i] - smoothed[i - 1]) / d_dist) * 100

    # Find sections above threshold
    climbing = grades >= min_grade_pct
    sections = []
    in_section = False
    start_idx = 0

    for i in range(n):
        if climbing[i] and not in_section:
            start_idx = i
            in_section = True
        elif not climbing[i] and in_section:
            if i > start_idx:
                sections.append((start_idx, i - 1))
            in_section = False

    # Handle section that extends to end
    if in_section:
        sections.append((start_idx, n - 1))

    return sections


def _merge_sections(
    sections: list[tuple[int, int]],
    distances: np.ndarray,
    smoothed: np.ndarray,
    merge_gap_m: float,
    merge_max_drop_m: float,
) -> list[tuple[int, int]]:
    """Merge climbing sections if gaps are small enough.

    Two sections are merged if:
    1. The gap distance is <= merge_gap_m
    2. The elevation drop in the gap is <= merge_max_drop_m
    """
    if len(sections) <= 1:
        return sections

    merged = [sections[0]]

    for current in sections[1:]:
        prev_end = merged[-1][1]
        curr_start = current[0]

        gap_distance = distances[curr_start] - distances[prev_end]
        elev_drop = smoothed[prev_end] - smoothed[curr_start]

        # Merge if gap is small and elevation drop is minimal
        if gap_distance <= merge_gap_m and elev_drop <= merge_max_drop_m:
            # Extend previous section to include current
            merged[-1] = (merged[-1][0], current[1])
        else:
            merged.append(current)

    return merged


def _calculate_climb_metrics(
    start_idx: int,
    end_idx: int,
    distances: np.ndarray,
    smoothed: np.ndarray,
    segment_length_m: float,
) -> DetectedClimb:
    """Calculate all metrics for a detected climb section."""
    # Total distance
    distance_m = distances[end_idx] - distances[start_idx]

    # Elevation gain (net gain, handling any small dips)
    total_gain = 0.0
    max_grade_pct = 0.0

    for i in range(start_idx + 1, end_idx + 1):
        d_dist = distances[i] - distances[i - 1]
        d_elev = smoothed[i] - smoothed[i - 1]

        if d_elev > 0:
            total_gain += d_elev

        if d_dist > 0:
            grade = (d_elev / d_dist) * 100
            max_grade_pct = max(max_grade_pct, grade)

    # Average grade
    net_elevation = smoothed[end_idx] - smoothed[start_idx]
    avg_grade_pct = (net_elevation / distance_m) * 100 if distance_m > 0 else 0.0

    # Generate gradient segments for this climb
    gradient_segments = []
    seg_start_dist = distances[start_idx]
    seg_end_dist = distances[end_idx]

    current_dist = seg_start_dist
    while current_dist < seg_end_dist:
        next_dist = min(current_dist + segment_length_m, seg_end_dist)

        # Find elevation at current and next distance
        curr_idx = np.searchsorted(distances, current_dist)
        next_idx = np.searchsorted(distances, next_dist)

        curr_idx = min(curr_idx, len(distances) - 1)
        next_idx = min(next_idx, len(distances) - 1)

        # Interpolate elevations
        if curr_idx > 0 and distances[curr_idx] != current_dist:
            idx = curr_idx - 1
            if distances[curr_idx] != distances[idx]:
                frac = (current_dist - distances[idx]) / (distances[curr_idx] - distances[idx])
                curr_elev = smoothed[idx] + frac * (smoothed[curr_idx] - smoothed[idx])
            else:
                curr_elev = smoothed[curr_idx]
        else:
            curr_elev = smoothed[curr_idx]

        if next_idx > 0 and distances[next_idx] != next_dist:
            idx = next_idx - 1
            if distances[next_idx] != distances[idx]:
                frac = (next_dist - distances[idx]) / (distances[next_idx] - distances[idx])
                next_elev = smoothed[idx] + frac * (smoothed[next_idx] - smoothed[idx])
            else:
                next_elev = smoothed[next_idx]
        else:
            next_elev = smoothed[next_idx]

        seg_dist = next_dist - current_dist
        seg_elev = next_elev - curr_elev
        seg_grade = (seg_elev / seg_dist) * 100 if seg_dist > 0 else 0.0

        gradient_segments.append(GradientSegment(distance_m=seg_dist, grade_pct=seg_grade))
        current_dist = next_dist

    # Categorize the climb
    category = categorize_climb(distance_m, avg_grade_pct)

    return DetectedClimb(
        start_index=start_idx,
        end_index=end_idx,
        distance_m=distance_m,
        elevation_gain_m=total_gain,
        avg_grade_pct=avg_grade_pct,
        max_grade_pct=max_grade_pct,
        category=category,
        gradient_segments=gradient_segments,
    )


def detect_climbs(
    records: list[dict],
    min_grade_pct: float = 3.0,
    min_length_m: float = 300.0,
    merge_gap_m: float = 500.0,
    merge_max_drop_m: float = 20.0,
    segment_length_m: float = 50.0,
) -> list[DetectedClimb]:
    """Detect climbs from GPS records.

    Algorithm:
    1. Smooth elevation data using Savitzky-Golay filter
    2. Identify sections where grade >= min_grade_pct
    3. Merge nearby sections if gap <= merge_gap_m and elevation drop <= merge_max_drop_m
    4. Filter by minimum length (>= min_length_m)
    5. Calculate metrics and categorize each climb

    Args:
        records: List of dicts with keys:
            - 'lat': Latitude (optional, not used for detection)
            - 'lon': Longitude (optional, not used for detection)
            - 'altitude_m': Elevation in meters
            - 'distance_m': Cumulative distance in meters
        min_grade_pct: Minimum grade percentage to consider as climbing.
            Default 3.0% is standard for cycling climbs.
        min_length_m: Minimum climb length in meters.
            Default 300m filters out very short steep sections.
        merge_gap_m: Maximum gap distance to merge adjacent climbs.
            Default 500m handles brief flat/descent sections mid-climb.
        merge_max_drop_m: Maximum elevation drop in gap to allow merging.
            Default 20m prevents merging climbs separated by real descent.
        segment_length_m: Length of gradient segments for profile.
            Default 50m provides good detail without being too granular.

    Returns:
        List of DetectedClimb objects, ordered by start distance.
        Empty list if no climbs found or insufficient data.

    Example:
        >>> records = [
        ...     {'distance_m': 0, 'altitude_m': 100},
        ...     {'distance_m': 500, 'altitude_m': 125},
        ...     {'distance_m': 1000, 'altitude_m': 150},
        ... ]
        >>> climbs = detect_climbs(records, min_grade_pct=3.0)
        >>> len(climbs)
        1
        >>> climbs[0].avg_grade_pct
        5.0
    """
    if len(records) < 2:
        return []

    # Extract arrays
    distances = np.array([r["distance_m"] for r in records], dtype=np.float64)
    altitudes = np.array([r["altitude_m"] for r in records], dtype=np.float64)

    # Check for valid data
    if np.isnan(distances).any() or np.isnan(altitudes).any():
        # Filter out NaN values
        valid = ~(np.isnan(distances) | np.isnan(altitudes))
        if valid.sum() < 2:
            return []
        distances = distances[valid]
        altitudes = altitudes[valid]

    # Smooth elevations
    smoothed = savgol_smooth(altitudes)

    # Step 1: Find sections where grade >= min_grade_pct
    sections = _find_climbing_sections(distances, smoothed, min_grade_pct)

    if not sections:
        return []

    # Step 2: Merge nearby sections
    sections = _merge_sections(sections, distances, smoothed, merge_gap_m, merge_max_drop_m)

    # Step 3: Filter by minimum length and calculate metrics
    climbs = []
    for start_idx, end_idx in sections:
        length = distances[end_idx] - distances[start_idx]
        if length >= min_length_m:
            climb = _calculate_climb_metrics(
                start_idx, end_idx, distances, smoothed, segment_length_m
            )
            climbs.append(climb)

    return climbs
