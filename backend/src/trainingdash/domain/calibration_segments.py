"""Segment selection for CdA/Crr calibration.

Selects steady-state segments from ride data that are suitable for
aerodynamic drag coefficient (CdA) estimation. Good calibration segments
have consistent power and speed, minimal gradient, and no drafting.

Selection criteria (per design #529):
- Speed >= 30 km/h (aero drag becomes significant)
- Steady power (coefficient of variation < 15%)
- Steady speed (coefficient of variation < 5%)
- Flat terrain (|grade| < 2%)
- No coasting (power > 0 throughout)
- Minimum 60s duration (enough samples for statistics)

References:
- Chung's method for CdA estimation (www.analyticcycling.com)
- Coggan's PowerTap field test protocol
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .physics import RiderParams, power_required


def calculate_grade(
    altitude: NDArray[np.floating],
    distance: NDArray[np.floating],
    window: int = 5,
) -> NDArray[np.floating]:
    """Calculate road grade from altitude and distance arrays.

    Uses a centered rolling window to smooth the grade calculation,
    reducing noise from GPS altitude jitter.

    Args:
        altitude: Elevation readings in meters.
        distance: Cumulative distance readings in meters.
        window: Half-width of the smoothing window (default 5 samples).

    Returns:
        Grade as percentage (positive = uphill) for each sample.
    """
    if len(altitude) < 2:
        return np.zeros_like(altitude)

    # Adjust window if array is too small
    if len(altitude) <= window:
        window = 1

    grade = np.zeros_like(altitude, dtype=np.float64)

    for i in range(len(altitude)):
        start = max(0, i - window)
        end = min(len(altitude), i + window + 1)

        elev_diff = altitude[end - 1] - altitude[start]
        dist_diff = distance[end - 1] - distance[start]

        if dist_diff > 0:
            grade[i] = (elev_diff / dist_diff) * 100  # Convert to percentage
        else:
            grade[i] = 0.0

    return grade


@dataclass(frozen=True, slots=True)
class CalibrationSegment:
    """A segment of ride data suitable for CdA calibration.

    Attributes:
        start_idx: Starting index in the original arrays.
        end_idx: Ending index (exclusive) in the original arrays.
        duration_s: Duration of the segment in seconds.
        mean_speed_mps: Mean ground speed in m/s.
        mean_power_w: Mean power in watts.
        mean_grade_pct: Mean road gradient as percentage.
        power_cv: Coefficient of variation for power (std/mean).
        speed_cv: Coefficient of variation for speed (std/mean).
        quality_score: Overall quality score (0-100).
    """

    start_idx: int
    end_idx: int
    duration_s: float
    mean_speed_mps: float
    mean_power_w: float
    mean_grade_pct: float
    power_cv: float
    speed_cv: float
    quality_score: float


@dataclass(frozen=True, slots=True)
class SegmentSelectionResult:
    """Result of segment selection for calibration.

    Attributes:
        segments: List of valid calibration segments.
        total_valid_duration_s: Total duration of all valid segments.
        rejection_reasons: Count of rejections by reason.
    """

    segments: list[CalibrationSegment]
    total_valid_duration_s: float
    rejection_reasons: dict[str, int]


def _coefficient_of_variation(arr: NDArray[np.floating]) -> float:
    """Calculate coefficient of variation (std/mean).

    Returns 0 if mean is 0 to avoid division by zero.
    """
    mean = np.mean(arr)
    if mean == 0:
        return 0.0
    return float(np.std(arr) / mean)


def calculate_segment_quality(segment: CalibrationSegment) -> float:
    """Score segment quality for CdA estimation (0-100).

    Factors (weighted):
    - Higher speed = better (aero dominates) - 30 points
    - Lower grade = better (less gravity noise) - 20 points
    - Lower power CV = better (steadier data) - 20 points
    - Lower speed CV = better (steadier data) - 15 points
    - Longer duration = better (more samples) - 15 points

    Args:
        segment: CalibrationSegment to score.

    Returns:
        Quality score from 0-100.
    """
    score = 0.0

    # Speed score (30 points): 30 km/h = 0, 50 km/h = 30
    # 30 km/h = 8.33 m/s, 50 km/h = 13.89 m/s
    speed_score = min(30.0, max(0.0, (segment.mean_speed_mps - 8.33) / (13.89 - 8.33) * 30))
    score += speed_score

    # Grade score (20 points): 0% = 20, 2% = 0
    grade_score = max(0.0, 20.0 - abs(segment.mean_grade_pct) * 10)
    score += grade_score

    # Power CV score (20 points): 0% CV = 20, 15% CV = 0
    power_cv_score = max(0.0, 20.0 - segment.power_cv / 0.15 * 20)
    score += power_cv_score

    # Speed CV score (15 points): 0% CV = 15, 5% CV = 0
    speed_cv_score = max(0.0, 15.0 - segment.speed_cv / 0.05 * 15)
    score += speed_cv_score

    # Duration score (15 points): 60s = 0, 180s+ = 15
    duration_score = min(15.0, max(0.0, (segment.duration_s - 60) / 120 * 15))
    score += duration_score

    return score


def select_calibration_segments(
    power: NDArray[np.floating],
    speed: NDArray[np.floating],
    grade: NDArray[np.floating],
    timestamps: NDArray[np.floating],
    min_speed_mps: float = 8.33,  # 30 km/h
    min_duration_s: float = 60.0,
    max_grade_pct: float = 2.0,
    max_power_cv: float = 0.15,
    max_speed_cv: float = 0.05,
    min_power_w: float = 50.0,  # Minimum to exclude coasting
) -> SegmentSelectionResult:
    """Select segments suitable for CdA calibration.

    Scans through the ride data using a sliding window approach to find
    contiguous regions that meet all calibration criteria.

    Args:
        power: Power readings in watts.
        speed: Speed readings in m/s.
        grade: Road gradient as percentage.
        timestamps: Unix timestamps or elapsed seconds.
        min_speed_mps: Minimum average speed (default 30 km/h = 8.33 m/s).
        min_duration_s: Minimum segment duration in seconds.
        max_grade_pct: Maximum absolute grade percentage.
        max_power_cv: Maximum coefficient of variation for power.
        max_speed_cv: Maximum coefficient of variation for speed.
        min_power_w: Minimum power to exclude coasting.

    Returns:
        SegmentSelectionResult with valid segments and rejection statistics.
    """
    if len(power) == 0:
        return SegmentSelectionResult(
            segments=[],
            total_valid_duration_s=0.0,
            rejection_reasons={"no_data": 1},
        )

    # Ensure arrays are the same length
    n = min(len(power), len(speed), len(grade), len(timestamps))
    power = power[:n]
    speed = speed[:n]
    grade = grade[:n]
    timestamps = timestamps[:n]

    segments: list[CalibrationSegment] = []
    rejection_reasons: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

    # Step 1: Create a validity mask for individual samples
    # Each sample must meet basic thresholds
    valid_mask = (
        (speed >= min_speed_mps)
        & (np.abs(grade) <= max_grade_pct)
        & (power >= min_power_w)
    )

    # Step 2: Find contiguous runs of valid samples
    # Add False at boundaries to detect edges
    padded = np.concatenate([[False], valid_mask, [False]])
    edges = np.diff(padded.astype(int))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]

    # Step 3: Evaluate each run
    for start_idx, end_idx in zip(starts, ends):
        # Calculate duration
        duration = timestamps[end_idx - 1] - timestamps[start_idx]

        # Check minimum duration
        if duration < min_duration_s:
            reject("too_short")
            continue

        # Extract segment data
        seg_power = power[start_idx:end_idx]
        seg_speed = speed[start_idx:end_idx]
        seg_grade = grade[start_idx:end_idx]

        # Calculate statistics
        mean_power = float(np.mean(seg_power))
        mean_speed = float(np.mean(seg_speed))
        mean_grade = float(np.mean(seg_grade))
        power_cv = _coefficient_of_variation(seg_power)
        speed_cv = _coefficient_of_variation(seg_speed)

        # Check power steadiness
        if power_cv > max_power_cv:
            reject("power_unsteady")
            continue

        # Check speed steadiness
        if speed_cv > max_speed_cv:
            reject("speed_unsteady")
            continue

        # Create segment (quality_score will be set after)
        segment = CalibrationSegment(
            start_idx=int(start_idx),
            end_idx=int(end_idx),
            duration_s=float(duration),
            mean_speed_mps=mean_speed,
            mean_power_w=mean_power,
            mean_grade_pct=mean_grade,
            power_cv=power_cv,
            speed_cv=speed_cv,
            quality_score=0.0,  # Temporary
        )

        # Calculate quality score using the segment
        quality = calculate_segment_quality(segment)

        # Create final segment with quality score
        segment = CalibrationSegment(
            start_idx=int(start_idx),
            end_idx=int(end_idx),
            duration_s=float(duration),
            mean_speed_mps=mean_speed,
            mean_power_w=mean_power,
            mean_grade_pct=mean_grade,
            power_cv=power_cv,
            speed_cv=speed_cv,
            quality_score=quality,
        )
        segments.append(segment)

    # Calculate total valid duration
    total_duration = sum(s.duration_s for s in segments)

    return SegmentSelectionResult(
        segments=segments,
        total_valid_duration_s=total_duration,
        rejection_reasons=rejection_reasons,
    )


def detect_drafting(
    power: NDArray[np.floating],
    speed: NDArray[np.floating],
    baseline_cda: float,
    rider_mass: float,
    threshold: float = 0.70,
) -> NDArray[np.bool_]:
    """Flag samples where rider is likely drafting.

    Drafting significantly reduces aerodynamic drag (30-40% reduction typical),
    which makes those samples unsuitable for CdA estimation.

    Detection method: Compare actual power to expected power at the same speed
    using the rider's known/estimated CdA. If actual power is less than
    threshold * expected power, flag as drafting.

    Args:
        power: Power readings in watts.
        speed: Speed readings in m/s.
        baseline_cda: Baseline CdA estimate for comparison.
        rider_mass: Total mass (rider + bike) in kg.
        threshold: Fraction of expected power below which to flag as drafting.
            Default 0.70 means flag if actual < 70% of expected.

    Returns:
        Boolean array where True indicates likely drafting.
    """
    if len(power) == 0:
        return np.array([], dtype=bool)

    n = min(len(power), len(speed))

    # Create rider params for power calculation
    rider = RiderParams(mass_kg=rider_mass, cda=baseline_cda, crr=0.004)

    # Calculate expected power for each sample (assume flat ground)
    expected_power = np.array(
        [
            power_required(float(speed[i]), 0.0, rider, None)
            for i in range(n)
        ]
    )

    # Flag as drafting if actual power is significantly below expected
    # Only consider samples where we're actually moving and pedaling
    moving_mask = (speed[:n] > 5.0) & (power[:n] > 0)
    drafting_mask = np.zeros(n, dtype=bool)

    # Where expected power is positive and we're moving
    valid_compare = moving_mask & (expected_power > 0)
    drafting_mask[valid_compare] = power[:n][valid_compare] < (
        threshold * expected_power[valid_compare]
    )

    return drafting_mask


def filter_drafting_segments(
    segments: list[CalibrationSegment],
    power: NDArray[np.floating],
    speed: NDArray[np.floating],
    baseline_cda: float,
    rider_mass: float,
    max_drafting_fraction: float = 0.1,
) -> tuple[list[CalibrationSegment], int]:
    """Filter out segments with significant drafting.

    Args:
        segments: Calibration segments to filter.
        power: Full power array.
        speed: Full speed array.
        baseline_cda: Baseline CdA estimate for comparison.
        rider_mass: Total mass (rider + bike) in kg.
        max_drafting_fraction: Maximum fraction of samples in a segment
            that can be flagged as drafting (default 10%).

    Returns:
        Tuple of (filtered segments, count of rejected segments).
    """
    drafting_mask = detect_drafting(power, speed, baseline_cda, rider_mass)

    filtered: list[CalibrationSegment] = []
    rejected_count = 0

    for seg in segments:
        seg_drafting = drafting_mask[seg.start_idx : seg.end_idx]
        drafting_fraction = np.mean(seg_drafting) if len(seg_drafting) > 0 else 0

        if drafting_fraction <= max_drafting_fraction:
            filtered.append(seg)
        else:
            rejected_count += 1

    return filtered, rejected_count
