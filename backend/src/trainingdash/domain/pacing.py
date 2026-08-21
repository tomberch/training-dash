"""
Grade-based pacing heuristics for race planning.

This module provides a simple heuristic approach to pacing that adjusts
target power based on terrain grade. It's the MVP approach per decision #530,
prioritizing simplicity and predictability over optimal performance.

Key insight: Variable pacing (harder uphill, easier downhill) beats constant
power due to the v³ relationship between power and aerodynamic drag. On climbs,
speed is low so aero losses are small - extra watts go to climbing. On descents,
speed is high so extra watts are mostly lost to drag.

The heuristic approach:
- Base power = FTP × target_intensity
- Scale power by terrain type using empirically-derived multipliers
- Use physics model to calculate resulting speed and time

This is intentionally simple. The scipy optimizer (#561) provides a more
sophisticated approach that respects W'bal constraints.
"""

from dataclasses import dataclass

import numpy as np

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.physics import (
    EnvironmentParams,
    RiderParams,
    speed_from_power,
)


@dataclass
class PacingTarget:
    """Power target for a single course segment."""

    segment_idx: int
    start_distance_m: float
    end_distance_m: float
    distance_m: float
    grade_pct: float
    target_power_w: float
    terrain_type: str
    estimated_speed_mps: float
    estimated_time_s: float


@dataclass
class PacingPlan:
    """Complete pacing plan for a course."""

    targets: list[PacingTarget]
    total_time_s: float
    total_distance_m: float
    avg_power_w: float
    normalized_power_w: float
    intensity_factor: float  # NP / FTP


# Terrain-based power multipliers
# These adjust power relative to base (FTP × target_intensity)
# Values derived from pacing research and cycling coach recommendations
TERRAIN_POWER_MULTIPLIERS = {
    "steep_descent": 0.55,    # < -6%: mostly coasting, light pedaling
    "descent": 0.70,          # -6% to -2%: soft pedaling, stay aero
    "flat": 1.00,             # -2% to 2%: base power
    "false_flat": 1.07,       # 2% to 4%: slight increase
    "climb": 1.12,            # 4% to 8%: push harder
    "steep_climb": 1.18,      # > 8%: near FTP but not over
}


def get_terrain_multiplier(terrain_type: str) -> float:
    """Get power multiplier for terrain type.

    Args:
        terrain_type: One of steep_descent, descent, flat, false_flat, climb, steep_climb

    Returns:
        Power multiplier (1.0 = base power)
    """
    return TERRAIN_POWER_MULTIPLIERS.get(terrain_type, 1.0)


def generate_heuristic_pacing(
    segments: list[CourseSegment],
    rider_ftp: float,
    target_intensity: float = 0.85,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
) -> PacingPlan:
    """
    Generate pacing plan using grade-based heuristics.

    Per #530 MVP decision: Start with grade-based heuristic.

    Strategy:
    - Base power = FTP × target_intensity
    - Adjust by terrain using TERRAIN_POWER_MULTIPLIERS
    - Cap power at FTP to avoid unsustainable efforts
    - Use physics model to calculate speed and time

    Args:
        segments: Course segments from course_segmentation module.
        rider_ftp: Rider's Functional Threshold Power in watts.
        target_intensity: Target Intensity Factor (IF), default 0.85.
            Common values: 0.70-0.75 (endurance), 0.85 (tempo),
            0.95-1.0 (threshold/race).
        rider_params: Rider physical parameters for physics calculations.
            If None, uses typical values (83kg, 0.32 CdA, 0.004 Crr).
        env_params: Environmental conditions. If None, uses sea level.

    Returns:
        PacingPlan with per-segment targets and overall metrics.

    Raises:
        ValueError: If segments is empty or rider_ftp <= 0.
    """
    if not segments:
        raise ValueError("segments cannot be empty")
    if rider_ftp <= 0:
        raise ValueError("rider_ftp must be positive")
    if not 0 < target_intensity <= 1.5:
        raise ValueError("target_intensity must be between 0 and 1.5")

    # Default rider params if not provided
    if rider_params is None:
        rider_params = RiderParams(mass_kg=83, cda=0.32, crr=0.004)

    if env_params is None:
        env_params = EnvironmentParams()

    base_power = rider_ftp * target_intensity
    targets: list[PacingTarget] = []

    for idx, segment in enumerate(segments):
        terrain_type = segment.terrain_type
        multiplier = get_terrain_multiplier(terrain_type)

        # Calculate target power, capped at FTP
        target_power = base_power * multiplier
        target_power = min(target_power, rider_ftp)

        # Use physics model to get speed and time
        speed_mps = speed_from_power(
            target_power,
            segment.avg_grade_pct,
            rider_params,
            env_params,
        )

        # Calculate time for segment
        if speed_mps > 0:
            time_s = segment.length_m / speed_mps
        else:
            time_s = float("inf")

        targets.append(
            PacingTarget(
                segment_idx=idx,
                start_distance_m=segment.start_distance_m,
                end_distance_m=segment.end_distance_m,
                distance_m=segment.length_m,
                grade_pct=segment.avg_grade_pct,
                target_power_w=target_power,
                terrain_type=terrain_type,
                estimated_speed_mps=speed_mps,
                estimated_time_s=time_s,
            )
        )

    # Calculate plan metrics
    total_time = sum(t.estimated_time_s for t in targets)
    total_distance = sum(t.distance_m for t in targets)

    # Time-weighted average power
    total_energy_j = sum(t.target_power_w * t.estimated_time_s for t in targets)
    avg_power = total_energy_j / total_time if total_time > 0 else 0

    # Calculate NP from the segment powers and times
    np_power = calculate_normalized_power_from_segments(targets)
    intensity_factor = np_power / rider_ftp if rider_ftp > 0 else 0

    return PacingPlan(
        targets=targets,
        total_time_s=total_time,
        total_distance_m=total_distance,
        avg_power_w=avg_power,
        normalized_power_w=np_power,
        intensity_factor=intensity_factor,
    )


def calculate_normalized_power(powers: np.ndarray, sample_rate_hz: float = 1.0) -> float:
    """
    Calculate Normalized Power using the standard algorithm.

    NP = (mean(rolling_30s_power^4))^0.25

    The 30-second rolling average smooths short spikes, then the 4th power
    weighting emphasizes intensity. This makes NP reflect the physiological
    cost better than simple average power.

    Args:
        powers: Array of power values in watts (one per sample).
        sample_rate_hz: Sample frequency in Hz. Default 1.0 (1 sample/sec).

    Returns:
        Normalized Power in watts. Returns 0 if insufficient data.
    """
    powers = np.asarray(powers, dtype=np.float64)

    if len(powers) < 30:
        # Not enough data for 30s average - return regular average
        return float(np.mean(powers)) if len(powers) > 0 else 0.0

    # Window size for 30-second rolling average
    window_size = int(30 * sample_rate_hz)
    window_size = max(1, min(window_size, len(powers)))

    # Calculate 30-second rolling average
    cumsum = np.cumsum(np.insert(powers, 0, 0))
    rolling_avg = (cumsum[window_size:] - cumsum[:-window_size]) / window_size

    if len(rolling_avg) == 0:
        return float(np.mean(powers))

    # 4th power mean, then 4th root
    np_power = (np.mean(rolling_avg**4)) ** 0.25

    return float(np_power)


def calculate_normalized_power_from_segments(targets: list[PacingTarget]) -> float:
    """
    Calculate Normalized Power from segment-based pacing targets.

    For segment-based plans, we can't do true 30s rolling average.
    Instead, we use time-weighted 4th power mean which gives a good
    approximation when segments are reasonably long.

    Args:
        targets: List of PacingTarget with power and time.

    Returns:
        Approximate Normalized Power in watts.
    """
    if not targets:
        return 0.0

    total_time = sum(t.estimated_time_s for t in targets)
    if total_time <= 0:
        return 0.0

    # Time-weighted 4th power mean
    weighted_4th_power = sum(
        t.target_power_w**4 * t.estimated_time_s for t in targets
    ) / total_time

    return weighted_4th_power**0.25


def calculate_intensity_factor(np_watts: float, ftp: float) -> float:
    """
    Calculate Intensity Factor (IF).

    IF = NP / FTP

    IF provides a normalized measure of ride intensity:
    - < 0.75: Recovery/Endurance
    - 0.75-0.85: Tempo
    - 0.85-0.95: Threshold
    - 0.95-1.05: VO2max intervals
    - > 1.05: Anaerobic

    Args:
        np_watts: Normalized Power in watts.
        ftp: Functional Threshold Power in watts.

    Returns:
        Intensity Factor (dimensionless).
    """
    if ftp <= 0:
        return 0.0
    return np_watts / ftp


def estimate_tss(np_watts: float, ftp: float, duration_s: float) -> float:
    """
    Estimate Training Stress Score (TSS) for a planned effort.

    TSS = (duration_s × NP × IF) / (FTP × 3600) × 100

    TSS quantifies training load:
    - < 150: Low (easy recovery next day)
    - 150-300: Medium (some residual fatigue)
    - 300-450: High (2+ days recovery)
    - > 450: Very high (extended recovery needed)

    Args:
        np_watts: Normalized Power in watts.
        ftp: Functional Threshold Power in watts.
        duration_s: Duration in seconds.

    Returns:
        Training Stress Score.
    """
    if ftp <= 0 or duration_s <= 0:
        return 0.0

    intensity_factor = np_watts / ftp
    tss = (duration_s * np_watts * intensity_factor) / (ftp * 3600) * 100

    return tss
