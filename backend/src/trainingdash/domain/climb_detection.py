"""Climb detection algorithm for GPS activity records.

This module detects climbs from GPS records using gradient analysis:
1. Smooth elevation data to reduce GPS noise
2. Compute gradient at fixed intervals
3. Find sections meeting minimum grade threshold
4. Merge nearby climb sections (gaps with minimal descent)
5. Filter by minimum length
6. Categorize using standard cycling climb categories

The algorithm is designed to match how cyclists perceive climbs — short flat
sections or minor dips within a climb are merged, but significant descents
split the climb into separate segments.
"""

from dataclasses import dataclass

from trainingdash.domain.segment_geometry import GradientSegment

__all__ = [
    "DetectedClimb",
    "detect_climbs",
    "categorize_climb",
    "smooth_elevation",
]


@dataclass
class DetectedClimb:
    """A detected climb section within an activity.

    Attributes:
        start_index: Index of first record in the climb
        end_index: Index of last record in the climb (inclusive)
        distance_m: Total distance of the climb in meters
        elevation_gain_m: Total elevation gained in meters
        avg_grade_pct: Average gradient as percentage
        max_grade_pct: Maximum gradient as percentage
        category: Climb category ('hc', '1', '2', '3', '4', 'nc')
        gradient_segments: List of fixed-distance gradient segments
    """

    start_index: int
    end_index: int
    distance_m: float
    elevation_gain_m: float
    avg_grade_pct: float
    max_grade_pct: float
    category: str
    gradient_segments: list[GradientSegment]


def smooth_elevation(altitudes: list[float], window: int = 5) -> list[float]:
    """
    Apply moving average smoothing to elevation data.

    Uses a centered window where possible, falling back to available
    points at the edges.

    Args:
        altitudes: List of altitude values in meters
        window: Window size for moving average (default 5)

    Returns:
        Smoothed altitude values (same length as input)
    """
    if len(altitudes) <= 1:
        return list(altitudes)

    smoothed = []
    half_window = window // 2

    for i in range(len(altitudes)):
        # Determine window bounds
        start = max(0, i - half_window)
        end = min(len(altitudes), i + half_window + 1)

        # Compute average
        window_values = altitudes[start:end]
        smoothed.append(sum(window_values) / len(window_values))

    return smoothed


def categorize_climb(distance_m: float, avg_grade_pct: float) -> str:
    """
    Categorize a climb using the distance × grade formula.

    This follows standard cycling climb categorization where longer
    and steeper climbs receive higher categories.

    Thresholds (distance_m × avg_grade_pct):
    - HC (Hors Catégorie): >= 80,000
    - Category 1: >= 64,000
    - Category 2: >= 32,000
    - Category 3: >= 16,000
    - Category 4: >= 8,000
    - NC (Not Categorized): < 8,000

    Args:
        distance_m: Climb distance in meters
        avg_grade_pct: Average gradient as percentage

    Returns:
        Category string: 'hc', '1', '2', '3', '4', or 'nc'

    Examples:
        >>> categorize_climb(10000, 8.0)  # 80,000 = HC
        'hc'
        >>> categorize_climb(2000, 5.0)   # 10,000 = Cat 4
        '4'
        >>> categorize_climb(500, 6.0)    # 3,000 = NC
        'nc'
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


def _compute_grades_at_intervals(
    records: list[dict],
    smoothed_altitudes: list[float],
    segment_length_m: float,
) -> list[tuple[int, int, float, float]]:
    """
    Compute grades at fixed distance intervals.

    Returns list of (start_idx, end_idx, distance_m, grade_pct) tuples.
    """
    if len(records) < 2:
        return []

    segments = []
    start_idx = 0
    start_distance = records[0].get("distance_m", 0.0)
    start_altitude = smoothed_altitudes[0]

    for i in range(1, len(records)):
        current_distance = records[i].get("distance_m", 0.0)
        segment_dist = current_distance - start_distance

        if segment_dist >= segment_length_m:
            current_altitude = smoothed_altitudes[i]
            delta_alt = current_altitude - start_altitude

            if segment_dist > 0:
                grade = (delta_alt / segment_dist) * 100
            else:
                grade = 0.0

            segments.append((start_idx, i, segment_dist, grade))

            start_idx = i
            start_distance = current_distance
            start_altitude = current_altitude

    # Handle remaining distance
    if start_idx < len(records) - 1:
        final_distance = records[-1].get("distance_m", 0.0)
        remaining_dist = final_distance - start_distance

        if remaining_dist > 0:
            delta_alt = smoothed_altitudes[-1] - start_altitude
            grade = (delta_alt / remaining_dist) * 100
            segments.append((start_idx, len(records) - 1, remaining_dist, grade))

    return segments


def _find_climbing_sections(
    grade_segments: list[tuple[int, int, float, float]],
    min_grade_pct: float,
) -> list[tuple[int, int]]:
    """
    Find contiguous sections where grade >= min_grade_pct.

    Returns list of (start_segment_idx, end_segment_idx) tuples.
    """
    sections = []
    in_climb = False
    climb_start = 0

    for i, (_, _, _, grade) in enumerate(grade_segments):
        if grade >= min_grade_pct:
            if not in_climb:
                in_climb = True
                climb_start = i
        else:
            if in_climb:
                sections.append((climb_start, i - 1))
                in_climb = False

    # Close final section if still climbing
    if in_climb:
        sections.append((climb_start, len(grade_segments) - 1))

    return sections


def _merge_nearby_sections(
    sections: list[tuple[int, int]],
    grade_segments: list[tuple[int, int, float, float]],
    records: list[dict],
    smoothed_altitudes: list[float],
    merge_gap_m: float,
    merge_max_drop_m: float,
) -> list[tuple[int, int]]:
    """
    Merge climb sections that are close together with minimal descent.

    Two sections are merged if:
    1. The gap between them is <= merge_gap_m
    2. The elevation drop in the gap is <= merge_max_drop_m
    """
    if len(sections) <= 1:
        return sections

    merged = [sections[0]]

    for current in sections[1:]:
        prev = merged[-1]

        # Get record indices for gap analysis
        prev_end_segment = grade_segments[prev[1]]
        curr_start_segment = grade_segments[current[0]]

        prev_end_idx = prev_end_segment[1]  # End record index of previous section
        curr_start_idx = curr_start_segment[0]  # Start record index of current section

        # Calculate gap distance
        gap_start_dist = records[prev_end_idx].get("distance_m", 0.0)
        gap_end_dist = records[curr_start_idx].get("distance_m", 0.0)
        gap_distance = gap_end_dist - gap_start_dist

        # Calculate elevation drop in gap
        gap_start_alt = smoothed_altitudes[prev_end_idx]
        gap_end_alt = smoothed_altitudes[curr_start_idx]

        # Find minimum altitude in gap
        min_alt_in_gap = gap_start_alt
        for j in range(prev_end_idx, curr_start_idx + 1):
            if smoothed_altitudes[j] < min_alt_in_gap:
                min_alt_in_gap = smoothed_altitudes[j]

        elevation_drop = gap_start_alt - min_alt_in_gap

        # Merge if gap is small and drop is minimal
        if gap_distance <= merge_gap_m and elevation_drop <= merge_max_drop_m:
            # Extend previous section to include current
            merged[-1] = (prev[0], current[1])
        else:
            merged.append(current)

    return merged


def _compute_climb_stats(
    records: list[dict],
    smoothed_altitudes: list[float],
    start_idx: int,
    end_idx: int,
    segment_length_m: float,
) -> tuple[float, float, float, float, list[GradientSegment]]:
    """
    Compute statistics for a climb section.

    Returns (distance_m, elevation_gain_m, avg_grade_pct, max_grade_pct, gradient_segments)
    """
    # Distance
    start_dist = records[start_idx].get("distance_m", 0.0)
    end_dist = records[end_idx].get("distance_m", 0.0)
    distance_m = end_dist - start_dist

    # Elevation gain (only positive changes)
    elevation_gain = 0.0
    max_grade = 0.0

    gradient_segments = []
    seg_start_idx = start_idx
    seg_start_dist = start_dist
    seg_start_alt = smoothed_altitudes[start_idx]

    for i in range(start_idx + 1, end_idx + 1):
        curr_dist = records[i].get("distance_m", 0.0)
        curr_alt = smoothed_altitudes[i]

        # Track elevation gain
        delta_alt = curr_alt - smoothed_altitudes[i - 1]
        if delta_alt > 0:
            elevation_gain += delta_alt

        # Check if we've reached segment length
        seg_dist = curr_dist - seg_start_dist
        if seg_dist >= segment_length_m or i == end_idx:
            if seg_dist > 0:
                seg_delta_alt = curr_alt - seg_start_alt
                grade = (seg_delta_alt / seg_dist) * 100
                gradient_segments.append(GradientSegment(distance_m=round(seg_dist, 1), grade_pct=round(grade, 1)))

                if grade > max_grade:
                    max_grade = grade

            seg_start_idx = i
            seg_start_dist = curr_dist
            seg_start_alt = curr_alt

    # Average grade
    total_elevation = smoothed_altitudes[end_idx] - smoothed_altitudes[start_idx]
    if distance_m > 0:
        avg_grade = (total_elevation / distance_m) * 100
    else:
        avg_grade = 0.0

    return (distance_m, elevation_gain, avg_grade, max_grade, gradient_segments)


def detect_climbs(
    records: list[dict],
    min_grade_pct: float = 3.0,
    min_length_m: float = 300,
    merge_gap_m: float = 500,
    merge_max_drop_m: float = 20,
    segment_length_m: float = 50,
) -> list[DetectedClimb]:
    """
    Detect climbs from GPS activity records.

    Algorithm:
    1. Smooth elevation data with 5-point moving average
    2. Compute gradient at fixed intervals (segment_length_m)
    3. Find sections where gradient >= min_grade_pct
    4. Merge nearby sections if gap <= merge_gap_m and drop <= merge_max_drop_m
    5. Filter by minimum length (min_length_m)
    6. Categorize each climb by distance × grade formula

    Args:
        records: List of record dicts with keys:
            - altitude_m: Altitude in meters
            - distance_m: Cumulative distance in meters
        min_grade_pct: Minimum gradient to consider as climbing (default 3%)
        min_length_m: Minimum climb length in meters (default 300m)
        merge_gap_m: Maximum gap to merge between climb sections (default 500m)
        merge_max_drop_m: Maximum elevation drop in gap to allow merge (default 20m)
        segment_length_m: Length for gradient calculation segments (default 50m)

    Returns:
        List of DetectedClimb objects, ordered by start position
    """
    if len(records) < 2:
        return []

    # Extract and smooth altitudes
    altitudes = [r.get("altitude_m", 0.0) for r in records]
    smoothed = smooth_elevation(altitudes)

    # Compute grades at intervals
    grade_segments = _compute_grades_at_intervals(records, smoothed, segment_length_m)

    if not grade_segments:
        return []

    # Find climbing sections
    climbing_sections = _find_climbing_sections(grade_segments, min_grade_pct)

    if not climbing_sections:
        return []

    # Merge nearby sections
    merged_sections = _merge_nearby_sections(
        climbing_sections,
        grade_segments,
        records,
        smoothed,
        merge_gap_m,
        merge_max_drop_m,
    )

    # Build climb objects
    climbs = []
    for seg_start, seg_end in merged_sections:
        # Convert segment indices to record indices
        start_idx = grade_segments[seg_start][0]
        end_idx = grade_segments[seg_end][1]

        # Compute stats
        distance_m, elevation_gain, avg_grade, max_grade, gradient_segs = _compute_climb_stats(
            records, smoothed, start_idx, end_idx, segment_length_m
        )

        # Filter by minimum length
        if distance_m < min_length_m:
            continue

        # Categorize
        category = categorize_climb(distance_m, avg_grade)

        climbs.append(
            DetectedClimb(
                start_index=start_idx,
                end_index=end_idx,
                distance_m=round(distance_m, 1),
                elevation_gain_m=round(elevation_gain, 1),
                avg_grade_pct=round(avg_grade, 2),
                max_grade_pct=round(max_grade, 2),
                category=category,
                gradient_segments=gradient_segs,
            )
        )

    return climbs
