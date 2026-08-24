"""Course segmentation for pacing optimization.

This module provides utilities for splitting a course into segments
based on grade changes, and detecting/categorizing climbs.

Also provides course "punchiness" calculation for estimating expected
Variability Index (VI = NP/Avg Power) on varied terrain.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from trainingdash.domain.grade import classify_terrain


@dataclass(frozen=True)
class CoursePunchiness:
    """Metrics describing course gradient variability ("punchiness").

    Punchiness affects the expected Variability Index (VI = NP/Avg Power).
    More variable terrain requires more power surges, increasing NP relative
    to average power even at the same overall effort level.

    Research shows expected VI by course type:
    - Flat TT: 1.02-1.05
    - Rolling: 1.04-1.07
    - Hilly: 1.05-1.10
    - Mountain: 1.10-1.20+

    Attributes:
        grade_stddev: Standard deviation of segment grades (percentage points).
        grade_change_stddev: Stddev of grade changes between adjacent segments.
        climb_density: Climbing segments per km of course.
        steep_climb_fraction: Fraction of distance on grades > 8%.
        expected_vi: Estimated Variability Index for this course profile.
        course_type: Classification: flat, rolling, hilly, or mountain.
    """

    grade_stddev: float
    grade_change_stddev: float
    climb_density: float
    steep_climb_fraction: float
    expected_vi: float
    course_type: str


def calculate_course_punchiness(segments: list["CourseSegment"]) -> CoursePunchiness:
    """Calculate course punchiness metrics from segments.

    Punchiness quantifies how "punchy" or variable a course is, which
    directly affects the expected Variability Index (VI = NP/Avg Power).

    The calculation considers:
    1. Grade variability (stddev of segment grades)
    2. Grade change rate (stddev of grade differences between segments)
    3. Climb density (climbing segments per km)
    4. Steep climb fraction (% of course on grades > 8%)

    These are combined into an expected VI using empirically-derived
    coefficients based on research into course types and observed VI values.

    Args:
        segments: List of CourseSegment objects from segment_course().

    Returns:
        CoursePunchiness with metrics and expected VI.
    """
    if not segments:
        return CoursePunchiness(
            grade_stddev=0.0,
            grade_change_stddev=0.0,
            climb_density=0.0,
            steep_climb_fraction=0.0,
            expected_vi=1.02,
            course_type="flat",
        )

    grades = np.array([s.avg_grade_pct for s in segments])
    lengths = np.array([s.length_m for s in segments])
    total_distance_m = np.sum(lengths)

    # 1. Grade standard deviation (weighted by segment length)
    if total_distance_m > 0:
        weighted_mean = np.sum(grades * lengths) / total_distance_m
        grade_variance = np.sum(lengths * (grades - weighted_mean) ** 2) / total_distance_m
        grade_stddev = float(np.sqrt(grade_variance))
    else:
        grade_stddev = 0.0

    # 2. Grade change stddev (how abruptly grade changes between segments)
    if len(grades) > 1:
        grade_changes = np.diff(grades)
        grade_change_stddev = float(np.std(grade_changes))
    else:
        grade_change_stddev = 0.0

    # 3. Climb density (climbing segments per km)
    climb_segments = sum(1 for s in segments if s.avg_grade_pct > 3.0)
    total_distance_km = total_distance_m / 1000.0
    climb_density = climb_segments / total_distance_km if total_distance_km > 0 else 0.0

    # 4. Steep climb fraction (distance on grades > 8%)
    steep_distance = sum(s.length_m for s in segments if s.avg_grade_pct > 8.0)
    steep_climb_fraction = steep_distance / total_distance_m if total_distance_m > 0 else 0.0

    # Calculate expected VI using empirically-calibrated model
    #
    # Coefficients derived from regression against 31 real rides with power data:
    # - Base VI: 1.12 (accounts for natural riding variability even on flat roads)
    # - Grade stddev coefficient: 0.028 per percentage point
    #
    # The model is deliberately simple: VI = base + grade_stddev * coefficient
    # More complex models (adding steep fraction, climb density) showed diminishing
    # returns and sometimes counterintuitive coefficients due to multicollinearity.
    #
    # Calibration results (2024-08):
    # - Mean error: 5.6% (down from 10.2% with previous coefficients)
    # - Median error: 4.9%
    # - Hilly courses: 5.8% mean error (previously 13.1%)
    # - Mountain courses: 4.8% mean error
    # - Bias: -0.037 (slight underprediction, within acceptable range)

    base_vi = 1.12
    vi_from_grade_var = grade_stddev * 0.028

    expected_vi = base_vi + vi_from_grade_var

    # Clamp to reasonable range
    expected_vi = max(1.02, min(1.40, expected_vi))

    # Classify course type based on calibrated VI thresholds
    # (adjusted to reflect real-world distributions from calibration data)
    if expected_vi < 1.12:
        course_type = "flat"
    elif expected_vi < 1.18:
        course_type = "rolling"
    elif expected_vi < 1.26:
        course_type = "hilly"
    else:
        course_type = "mountain"

    return CoursePunchiness(
        grade_stddev=round(grade_stddev, 2),
        grade_change_stddev=round(grade_change_stddev, 2),
        climb_density=round(climb_density, 2),
        steep_climb_fraction=round(steep_climb_fraction, 3),
        expected_vi=round(expected_vi, 3),
        course_type=course_type,
    )


@dataclass
class CourseSegment:
    """A segment of a course with consistent grade characteristics."""

    start_distance_m: float
    end_distance_m: float
    length_m: float
    avg_grade_pct: float
    elevation_gain_m: float
    elevation_loss_m: float
    terrain_type: str  # from grade.classify_terrain
    bearing_deg: float | None = None  # Direction of travel (0=N, 90=E, 180=S, 270=W)


@dataclass
class Climb:
    """A detected climb on a course."""

    name: str | None
    start_distance_m: float
    end_distance_m: float
    length_m: float
    avg_grade_pct: float
    elevation_gain_m: float
    max_grade_pct: float
    category: str | None  # HC, 1, 2, 3, 4, or None


def segment_course(
    distances: np.ndarray | Sequence[float],
    grades: np.ndarray | Sequence[float],
    elevations: np.ndarray | Sequence[float],
    grade_threshold_pct: float = 2.0,
    min_segment_m: float = 200.0,
) -> list[CourseSegment]:
    """Segment course by grade changes.

    Creates a new segment when:
    - Grade changes by more than threshold from segment average
    - AND minimum segment length is met

    Args:
        distances: Cumulative distance in meters (monotonic increasing).
        grades: Grade at each point as decimal (0.05 = 5%).
        elevations: Elevation at each point in meters.
        grade_threshold_pct: Grade change threshold in percentage points.
            Default 2.0 means a new segment starts when grade differs
            by more than 2% from current segment average.
        min_segment_m: Minimum segment length in meters. Segments shorter
            than this will be merged with neighbors.

    Returns:
        List of CourseSegment objects covering the entire course.
    """
    distances = np.asarray(distances, dtype=np.float64)
    grades = np.asarray(grades, dtype=np.float64)
    elevations = np.asarray(elevations, dtype=np.float64)

    n = len(distances)
    if n < 2:
        return []

    # Convert threshold to decimal
    threshold = grade_threshold_pct / 100.0

    segments: list[CourseSegment] = []
    segment_start_idx = 0

    for i in range(1, n):
        # Calculate current segment stats
        segment_grades = grades[segment_start_idx : i + 1]
        segment_avg_grade = np.mean(segment_grades)
        segment_length = distances[i] - distances[segment_start_idx]

        # Check if we should start a new segment
        grade_diff = abs(grades[i] - segment_avg_grade)
        should_split = grade_diff > threshold and segment_length >= min_segment_m

        # Also split at end of course
        is_last_point = i == n - 1

        if should_split or is_last_point:
            # Finalize current segment
            end_idx = i if should_split else i + 1
            segment = _create_segment(distances, grades, elevations, segment_start_idx, end_idx)
            if segment.length_m > 0:
                segments.append(segment)

            # Start new segment
            segment_start_idx = i

    # Merge short segments
    segments = _merge_short_segments(segments, min_segment_m)

    return segments


def _create_segment(
    distances: np.ndarray,
    grades: np.ndarray,
    elevations: np.ndarray,
    start_idx: int,
    end_idx: int,
) -> CourseSegment:
    """Create a CourseSegment from array slices."""
    start_dist = distances[start_idx]
    end_dist = distances[end_idx - 1] if end_idx <= len(distances) else distances[-1]
    length = end_dist - start_dist

    segment_grades = grades[start_idx:end_idx]
    avg_grade = float(np.mean(segment_grades)) if len(segment_grades) > 0 else 0.0

    start_elev = elevations[start_idx]
    end_elev = elevations[end_idx - 1] if end_idx <= len(elevations) else elevations[-1]
    elev_change = end_elev - start_elev

    elevation_gain = max(0.0, elev_change)
    elevation_loss = max(0.0, -elev_change)

    # Classify terrain based on average grade (convert to percentage)
    terrain_type = classify_terrain(avg_grade * 100)

    return CourseSegment(
        start_distance_m=start_dist,
        end_distance_m=end_dist,
        length_m=length,
        avg_grade_pct=avg_grade * 100,
        elevation_gain_m=elevation_gain,
        elevation_loss_m=elevation_loss,
        terrain_type=terrain_type,
    )


def _merge_short_segments(segments: list[CourseSegment], min_length_m: float) -> list[CourseSegment]:
    """Merge segments shorter than minimum length with neighbors."""
    if len(segments) <= 1:
        return segments

    merged: list[CourseSegment] = []
    i = 0

    while i < len(segments):
        current = segments[i]

        # If segment is too short and not the last one, merge with next
        if current.length_m < min_length_m and i < len(segments) - 1:
            next_seg = segments[i + 1]
            merged_segment = _merge_two_segments(current, next_seg)
            # Replace next segment with merged and skip current
            segments[i + 1] = merged_segment
        else:
            merged.append(current)

        i += 1

    return merged


def _merge_two_segments(seg1: CourseSegment, seg2: CourseSegment) -> CourseSegment:
    """Merge two adjacent segments into one."""
    total_length = seg1.length_m + seg2.length_m

    # Weighted average grade
    if total_length > 0:
        avg_grade = (seg1.avg_grade_pct * seg1.length_m + seg2.avg_grade_pct * seg2.length_m) / total_length
    else:
        avg_grade = 0.0

    return CourseSegment(
        start_distance_m=seg1.start_distance_m,
        end_distance_m=seg2.end_distance_m,
        length_m=total_length,
        avg_grade_pct=avg_grade,
        elevation_gain_m=seg1.elevation_gain_m + seg2.elevation_gain_m,
        elevation_loss_m=seg1.elevation_loss_m + seg2.elevation_loss_m,
        terrain_type=classify_terrain(avg_grade),
    )


def detect_climbs(
    segments: list[CourseSegment],
    min_grade_pct: float = 3.0,
    min_length_m: float = 300.0,
) -> list[Climb]:
    """Detect and categorize climbs from segments.

    Climb detection criteria:
    - Average grade >= min_grade_pct
    - Total length >= min_length_m

    Adjacent climbing segments are merged into a single climb.

    Category scoring (UCI-inspired):
        score = length_m * avg_grade_pct / 100
        - HC: >= 80,000
        - Cat 1: >= 64,000
        - Cat 2: >= 32,000
        - Cat 3: >= 16,000
        - Cat 4: >= 8,000
        - None: < 8,000

    Args:
        segments: List of CourseSegment objects.
        min_grade_pct: Minimum average grade to consider as climbing.
        min_length_m: Minimum length for a climb.

    Returns:
        List of Climb objects, ordered by start distance.
    """
    if not segments:
        return []

    climbs: list[Climb] = []
    climb_segments: list[CourseSegment] = []

    for segment in segments:
        is_climbing = segment.avg_grade_pct >= min_grade_pct

        if is_climbing:
            climb_segments.append(segment)
        elif climb_segments:
            # End of climb - finalize if long enough
            climb = _create_climb_from_segments(climb_segments)
            if climb.length_m >= min_length_m:
                climbs.append(climb)
            climb_segments = []

    # Handle climb at end of course
    if climb_segments:
        climb = _create_climb_from_segments(climb_segments)
        if climb.length_m >= min_length_m:
            climbs.append(climb)

    return climbs


def _create_climb_from_segments(segments: list[CourseSegment]) -> Climb:
    """Create a Climb from a list of consecutive climbing segments."""
    start_dist = segments[0].start_distance_m
    end_dist = segments[-1].end_distance_m
    total_length = sum(s.length_m for s in segments)
    total_gain = sum(s.elevation_gain_m for s in segments)

    # Weighted average grade
    if total_length > 0:
        avg_grade = sum(s.avg_grade_pct * s.length_m for s in segments) / total_length
    else:
        avg_grade = 0.0

    # Max grade from any segment
    max_grade = max(s.avg_grade_pct for s in segments)

    # Calculate category
    category = _categorize_climb(total_length, avg_grade)

    return Climb(
        name=None,  # Names assigned later or by user
        start_distance_m=start_dist,
        end_distance_m=end_dist,
        length_m=total_length,
        avg_grade_pct=avg_grade,
        elevation_gain_m=total_gain,
        max_grade_pct=max_grade,
        category=category,
    )


def _categorize_climb(length_m: float, avg_grade_pct: float) -> str | None:
    """Categorize a climb using UCI-inspired scoring.

    Score = length_m * avg_grade_pct
    """
    score = length_m * avg_grade_pct

    if score >= 80_000:
        return "HC"
    elif score >= 64_000:
        return "1"
    elif score >= 32_000:
        return "2"
    elif score >= 16_000:
        return "3"
    elif score >= 8_000:
        return "4"
    else:
        return None


def assign_segment_bearings(
    segments: list[CourseSegment],
    points: list[tuple[float, float, float]],  # (lat, lon, distance_m)
) -> list[CourseSegment]:
    """Assign bearing to each segment based on GPS track points.

    For each segment, finds the track points at segment start and end distances,
    then calculates the bearing between them.

    Args:
        segments: List of CourseSegment objects (bearing_deg will be set).
        points: List of (latitude, longitude, cumulative_distance_m) tuples
            representing the GPS track.

    Returns:
        The same segments list with bearing_deg populated.
    """
    from trainingdash.domain.physics import calculate_bearing

    if not points or not segments:
        return segments

    # Build distance-indexed lookup for points
    # points are assumed sorted by distance
    point_distances = [p[2] for p in points]

    for segment in segments:
        # Find points closest to segment start and end
        start_idx = _find_closest_point_index(point_distances, segment.start_distance_m)
        end_idx = _find_closest_point_index(point_distances, segment.end_distance_m)

        # Need at least two different points
        if start_idx == end_idx:
            # Segment too short, try adjacent points
            if end_idx < len(points) - 1:
                end_idx += 1
            elif start_idx > 0:
                start_idx -= 1

        if start_idx != end_idx:
            lat1, lon1 = points[start_idx][0], points[start_idx][1]
            lat2, lon2 = points[end_idx][0], points[end_idx][1]
            segment.bearing_deg = calculate_bearing(lat1, lon1, lat2, lon2)

    return segments


def _find_closest_point_index(distances: list[float], target_distance: float) -> int:
    """Find index of point closest to target distance using binary search."""
    import bisect

    idx = bisect.bisect_left(distances, target_distance)

    if idx == 0:
        return 0
    if idx >= len(distances):
        return len(distances) - 1

    # Check which is closer: idx-1 or idx
    if abs(distances[idx - 1] - target_distance) <= abs(distances[idx] - target_distance):
        return idx - 1
    return idx
