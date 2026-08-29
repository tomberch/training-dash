"""
Pacing plan generators.

This module owns the two plan-generator interfaces (ADR 0004):
- generate_heuristic_pacing: discrete terrain multipliers, VI-corrected NP
- generate_terrain_adapted_pacing: continuous grade-power formula, which
  routes to the fine-grained (~25m) engine when an elevation profile exists

The power model itself (coefficients, grade-power formula, NP core,
ride-type presets) lives in pacing_model.py — this module consumes it.
"""

from dataclasses import dataclass

import numpy as np

from trainingdash.domain.course_segmentation import CourseSegment, calculate_course_punchiness
from trainingdash.domain.fine_grained_pacing import generate_fine_grained_plan
from trainingdash.domain.pacing_model import (
    DEFAULT_RIDER_CDA,
    DEFAULT_RIDER_CRR,
    DEFAULT_RIDER_MASS_KG,
    DESCENT_GRADE_PCT,
    MAX_POWER_MULTIPLIER,
    MIN_POWER_MULTIPLIER,
    RIDE_TYPE_PRESETS,
    PacingCoefficients,
    RideTypeParams,
    RideTypePreset,
    calculate_intensity_factor,
    calculate_normalized_power,
    effective_descent_power_multiplier,
    estimate_tss,
    get_grade_power_multiplier,
    resolve_ride_type_params,
)
from trainingdash.domain.physics import (
    EnvironmentParams,
    RiderParams,
    speed_from_power,
)

# Backward-compatible re-exports (moved to pacing_model.py; import sites unchanged)
__all__ = [
    "MAX_POWER_MULTIPLIER",
    "MIN_POWER_MULTIPLIER",
    "RIDE_TYPE_PRESETS",
    "PacingCoefficients",
    "RideTypeParams",
    "RideTypePreset",
    "calculate_intensity_factor",
    "calculate_normalized_power",
    "estimate_tss",
    "get_grade_power_multiplier",
    "resolve_ride_type_params",
]


def _default_rider_params() -> RiderParams:
    """Default rider params shared by all plan generators."""
    return RiderParams(mass_kg=DEFAULT_RIDER_MASS_KG, cda=DEFAULT_RIDER_CDA, crr=DEFAULT_RIDER_CRR)


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


def get_terrain_multiplier(terrain_type: str) -> float:
    """Get power multiplier for terrain type.

    Args:
        terrain_type: One of steep_descent, descent, flat, false_flat, climb, steep_climb

    Returns:
        Power multiplier (1.0 = base power)
    """
    # Terrain-based power multipliers (used by generate_heuristic_pacing)
    # These adjust power relative to base (FTP × target_intensity)
    # Values derived from pacing research and cycling coach recommendations
    TERRAIN_POWER_MULTIPLIERS = {
        "steep_descent": 0.55,  # < -6%: mostly coasting, light pedaling
        "descent": 0.70,  # -6% to -2%: soft pedaling, stay aero
        "flat": 1.00,  # -2% to 2%: base power
        "false_flat": 1.07,  # 2% to 4%: slight increase
        "climb": 1.12,  # 4% to 8%: push harder
        "steep_climb": 1.18,  # > 8%: near FTP but not over
    }
    return TERRAIN_POWER_MULTIPLIERS.get(terrain_type, 1.0)


def generate_heuristic_pacing(
    segments: list[CourseSegment],
    rider_ftp: float,
    target_intensity: float = 0.85,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
    segment_env_params: list[EnvironmentParams] | None = None,
    max_descent_speed_mps: float | None = None,
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
        segment_env_params: Optional per-segment environment params (for wind).
        max_descent_speed_mps: Maximum descent speed cap in m/s. If None, no cap.
            Typical values: 15-18 m/s (54-65 km/h).

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
        rider_params = _default_rider_params()

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

        # Use per-segment env params if provided
        seg_env = segment_env_params[idx] if segment_env_params else env_params

        # Use physics model to get speed and time
        speed_mps = speed_from_power(
            target_power,
            segment.avg_grade_pct,
            rider_params,
            seg_env,
            max_descent_speed_mps=max_descent_speed_mps,
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

    # Calculate course punchiness to get expected VI for NP correction
    punchiness = calculate_course_punchiness(segments)

    # Calculate NP using VI correction for terrain variability
    np_power = calculate_normalized_power_from_segments(targets, expected_vi=punchiness.expected_vi)
    intensity_factor = calculate_intensity_factor(np_power, rider_ftp)

    return PacingPlan(
        targets=targets,
        total_time_s=total_time,
        total_distance_m=total_distance,
        avg_power_w=avg_power,
        normalized_power_w=np_power,
        intensity_factor=intensity_factor,
    )


def calculate_normalized_power_from_segments(
    targets: list[PacingTarget],
    expected_vi: float | None = None,
) -> float:
    """
    Calculate Normalized Power from segment-based pacing targets.

    For segment-based plans, we can't do true 30s rolling average.
    Instead, we use time-weighted 4th power mean which gives a good
    approximation when segments are reasonably long.

    However, this segment-based calculation assumes constant power within
    each segment, yielding VI (NP/Avg) ≈ 1.0. Real riding has intra-segment
    power variability that increases NP significantly on variable terrain.

    When expected_vi is provided (from course punchiness analysis), we apply
    it as a correction factor: NP = Avg Power × expected_vi. This gives
    much more accurate NP predictions on hilly/mountain courses.

    Args:
        targets: List of PacingTarget with power and time.
        expected_vi: Expected Variability Index from course punchiness analysis.
            If provided, NP = avg_power × expected_vi instead of 4th power calc.
            Typical values: 1.02-1.05 (flat), 1.05-1.10 (rolling),
            1.10-1.15 (hilly), 1.15-1.25 (mountain).

    Returns:
        Normalized Power in watts.
    """
    if not targets:
        return 0.0

    total_time = sum(t.estimated_time_s for t in targets)
    if total_time <= 0:
        return 0.0

    # Calculate time-weighted average power
    total_energy = sum(t.target_power_w * t.estimated_time_s for t in targets)
    avg_power = total_energy / total_time

    if expected_vi is not None:
        # Apply VI correction for terrain variability
        # This accounts for intra-segment power variations not captured
        # by constant-power segment modeling
        return avg_power * expected_vi

    # Fallback: time-weighted 4th power mean (underestimates NP on variable terrain)
    weighted_4th_power = sum(t.target_power_w**4 * t.estimated_time_s for t in targets) / total_time
    return weighted_4th_power**0.25


def generate_terrain_adapted_pacing(
    segments: list[CourseSegment],
    rider_ftp: float,
    target_intensity: float = 0.85,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
    segment_env_params: list[EnvironmentParams] | None = None,
    max_descent_speed_mps: float | None = None,
    power_cap_ftp_pct: float = 1.05,
    coefficients: PacingCoefficients | None = None,
    elevation_profile: list[dict] | None = None,
    ride_type: str = "training",
    descent_aggressiveness: int = 70,
    wind_speed_mps: float | None = None,
    wind_direction_deg: float | None = None,
) -> PacingPlan:
    """
    Generate pacing plan using continuous grade-based power allocation.

    Unlike generate_heuristic_pacing which uses discrete terrain categories,
    this function uses a continuous formula calibrated from real ride data:

        power_mult = intercept + slope × grade%

    This gives more realistic power targets, especially on steep climbs where
    riders naturally push harder (aero drag is low, so extra watts are efficient).

    Coefficients can be personalized per user/bike via the calibration pipeline,
    or the global defaults are used.

    When elevation_profile is provided, uses fine-grained pacing (~25m resolution)
    for accurate speed predictions. This runs physics calculations at each fine
    point, then aggregates back to display segments. Without elevation_profile,
    falls back to segment-based calculations.

    Args:
        segments: Course segments for display structure (used for output format).
        rider_ftp: Rider's Functional Threshold Power in watts.
        target_intensity: Target Intensity Factor (IF), default 0.85.
        rider_params: Rider physical parameters for physics calculations.
        env_params: Environmental conditions. If None, uses sea level.
        segment_env_params: Optional per-segment environment params (for wind).
            Note: Wind adjustment not yet supported with fine-grained mode.
        max_descent_speed_mps: Maximum descent speed cap in m/s.
            If None, uses coefficients.max_descent_speed_mps.
        power_cap_ftp_pct: Cap power at this fraction of FTP (default 1.05).
            Prevents unsustainably high targets on steep climbs.
        coefficients: Personalized pacing coefficients. If None, uses defaults.
        elevation_profile: Course elevation profile from RaceCourse.elevation_profile.
            If provided, enables fine-grained (~25m) pacing for accurate speed
            predictions. If None, uses segment-based calculation.
        ride_type: "training" or "race" (interface compat; cornering is driven
            by descent_aggressiveness).
        descent_aggressiveness: 0-100; maps to lateral acceleration for the
            cornering-speed limit on descents (B1). Default 70 = "training".
        wind_speed_mps: Meteorological wind speed (m/s); decomposed per point
            from GPS bearings in fine-grained mode. None/0 = no wind.
        wind_direction_deg: Meteorological wind direction (FROM, degrees).

    Returns:
        PacingPlan with per-segment targets and overall metrics.
        The normalized_power_w is calculated from the actual variable
        power profile, not using VI correction.

    Raises:
        ValueError: If segments is empty or rider_ftp <= 0.
    """
    if not segments:
        raise ValueError("segments cannot be empty")
    if rider_ftp <= 0:
        raise ValueError("rider_ftp must be positive")
    if not 0 < target_intensity <= 1.5:
        raise ValueError("target_intensity must be between 0 and 1.5")

    # Use default coefficients if not provided
    if coefficients is None:
        coefficients = PacingCoefficients.defaults()

    # Default rider params if not provided
    if rider_params is None:
        rider_params = _default_rider_params()

    if env_params is None:
        env_params = EnvironmentParams()

    # Use coefficients' max descent speed if not explicitly provided
    effective_max_descent_speed = (
        max_descent_speed_mps if max_descent_speed_mps is not None else coefficients.max_descent_speed_mps
    )

    # =========================================================================
    # Fine-grained mode: Use elevation profile for accurate speed predictions
    # =========================================================================
    if elevation_profile is not None and len(elevation_profile) >= 2:
        return _generate_fine_grained_adapted_pacing(
            segments=segments,
            elevation_profile=elevation_profile,
            rider_ftp=rider_ftp,
            target_intensity=target_intensity,
            rider_params=rider_params,
            env_params=env_params,
            effective_max_descent_speed=effective_max_descent_speed,
            power_cap_ftp_pct=power_cap_ftp_pct,
            coefficients=coefficients,
            ride_type=ride_type,
            descent_aggressiveness=descent_aggressiveness,
            wind_speed_mps=wind_speed_mps,
            wind_direction_deg=wind_direction_deg,
        )

    # =========================================================================
    # Fallback: Segment-based calculation (original behavior)
    # =========================================================================
    base_power = rider_ftp * target_intensity
    power_cap = rider_ftp * power_cap_ftp_pct
    targets: list[PacingTarget] = []

    for idx, segment in enumerate(segments):
        # Descent Multiplier on descents, shared grade-power formula elsewhere
        # (ADR 0005 #634 — the fine-grained path applies it per point)
        if segment.avg_grade_pct < DESCENT_GRADE_PCT:
            multiplier = effective_descent_power_multiplier(coefficients)
        else:
            multiplier = get_grade_power_multiplier(segment.avg_grade_pct, coefficients)

        # Calculate target power, capped at power_cap
        target_power = base_power * multiplier
        target_power = min(target_power, power_cap)
        target_power = max(target_power, 0)  # Don't go negative

        # Use per-segment env params if provided
        seg_env = segment_env_params[idx] if segment_env_params else env_params

        # Use physics model to get speed and time
        speed_mps = speed_from_power(
            target_power,
            segment.avg_grade_pct,
            rider_params,
            seg_env,
            max_descent_speed_mps=effective_max_descent_speed,
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
                terrain_type=segment.terrain_type,
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

    # Calculate NP from actual variable power profile (no VI correction needed)
    # With fine-grained segments and variable power, the 4th power calculation
    # naturally captures the variability that VI correction was approximating
    np_power = calculate_normalized_power_from_variable_targets(targets)
    intensity_factor = np_power / rider_ftp if rider_ftp > 0 else 0

    return PacingPlan(
        targets=targets,
        total_time_s=total_time,
        total_distance_m=total_distance,
        avg_power_w=avg_power,
        normalized_power_w=np_power,
        intensity_factor=intensity_factor,
    )


def calculate_normalized_power_from_variable_targets(
    targets: list[PacingTarget],
) -> float:
    """
    Calculate Normalized Power from variable power targets.

    With fine-grained segments (e.g., 25m) and terrain-adapted power
    allocation, the power varies realistically across the course.
    This function calculates NP using the standard 4th power weighting,
    which naturally captures the physiological cost of variable efforts.

    For segments shorter than 30 seconds of riding time, we expand
    each segment into per-second power samples to enable proper
    30-second rolling average calculation.

    Args:
        targets: List of PacingTarget with variable power and time.

    Returns:
        Normalized Power in watts.
    """
    if not targets:
        return 0.0

    total_time = sum(t.estimated_time_s for t in targets)
    if total_time <= 0:
        return 0.0

    # Expand segments into per-second power samples
    # This enables proper 30s rolling average for NP calculation
    power_samples: list[float] = []

    for target in targets:
        # Number of 1-second samples for this segment
        n_samples = max(1, int(round(target.estimated_time_s)))
        power_samples.extend([target.target_power_w] * n_samples)

    if len(power_samples) < 30:
        # Too short for proper NP - return average
        return sum(t.target_power_w * t.estimated_time_s for t in targets) / total_time

    # Calculate NP using standard algorithm
    return calculate_normalized_power(np.array(power_samples), sample_rate_hz=1.0)


def _generate_fine_grained_adapted_pacing(
    segments: list[CourseSegment],
    elevation_profile: list[dict],
    rider_ftp: float,
    target_intensity: float,
    rider_params: RiderParams,
    env_params: EnvironmentParams,
    effective_max_descent_speed: float,
    power_cap_ftp_pct: float,
    coefficients: PacingCoefficients,
    ride_type: str = "training",
    descent_aggressiveness: int = 70,
    wind_speed_mps: float | None = None,
    wind_direction_deg: float | None = None,
) -> PacingPlan:
    """
    Internal helper: Generate pacing plan using fine-grained elevation profile.

    Runs physics calculations at ~25m resolution for accurate speed predictions,
    then maps the results back onto the original segment structure.

    This gives:
    - Accurate per-segment speeds (not averaged over coarse segments)
    - Accurate total time (sum of fine-grained segments)
    - Accurate NP (from actual variable power profile)
    """
    # Generate fine-grained plan (~25m resolution)
    fine_plan = generate_fine_grained_plan(
        elevation_profile=elevation_profile,
        rider_ftp=rider_ftp,
        target_intensity=target_intensity,
        rider_params=rider_params,
        env_params=env_params,
        grade_power_intercept=coefficients.grade_power_intercept,
        grade_power_slope=coefficients.grade_power_slope,
        max_descent_speed_mps=effective_max_descent_speed,
        power_cap_ftp_pct=power_cap_ftp_pct,
        target_spacing_m=25.0,
        descent_power_multiplier=effective_descent_power_multiplier(coefficients),
        ride_type=ride_type,
        descent_aggressiveness=descent_aggressiveness,
        wind_speed_mps=wind_speed_mps,
        wind_direction_deg=wind_direction_deg,
        coefficients=coefficients,
    )

    if not fine_plan.points:
        # Fallback: return empty plan structure
        return PacingPlan(
            targets=[],
            total_time_s=0,
            total_distance_m=0,
            avg_power_w=0,
            normalized_power_w=0,
            intensity_factor=0,
        )

    # Map fine-grained results onto original segment structure
    # For each segment, find all fine points within it and aggregate
    targets: list[PacingTarget] = []
    fine_idx = 0
    n_fine = len(fine_plan.points)

    for seg_idx, segment in enumerate(segments):
        seg_start = segment.start_distance_m
        seg_end = segment.end_distance_m

        # Find fine points within this segment
        seg_powers: list[float] = []
        seg_times: list[float] = []
        seg_speeds: list[float] = []

        while fine_idx < n_fine:
            fp = fine_plan.points[fine_idx]
            # Check if this fine point is within the segment
            # Use a small tolerance for boundary conditions
            if fp.distance_m < seg_start - 1.0:
                fine_idx += 1
                continue
            if fp.distance_m >= seg_end + 1.0:
                break

            seg_powers.append(fp.power_w)
            seg_times.append(fp.time_s)
            seg_speeds.append(fp.speed_mps)
            fine_idx += 1

        # If we found fine points for this segment, aggregate them
        if seg_powers and seg_times:
            total_seg_time = sum(seg_times)
            if total_seg_time > 0:
                # Time-weighted averages
                avg_power = sum(p * t for p, t in zip(seg_powers, seg_times)) / total_seg_time
                avg_speed = sum(s * t for s, t in zip(seg_speeds, seg_times)) / total_seg_time
            else:
                avg_power = sum(seg_powers) / len(seg_powers) if seg_powers else 0
                avg_speed = sum(seg_speeds) / len(seg_speeds) if seg_speeds else 1.0
                total_seg_time = segment.length_m / avg_speed if avg_speed > 0 else 0
        else:
            # No fine points found - fall back to segment-based calculation
            # This can happen if segment boundaries don't align with fine points
            multiplier = get_grade_power_multiplier(segment.avg_grade_pct, coefficients)
            base_power = rider_ftp * target_intensity
            power_cap = rider_ftp * power_cap_ftp_pct
            avg_power = min(base_power * multiplier, power_cap)
            avg_power = max(0, avg_power)

            avg_speed = speed_from_power(
                avg_power,
                segment.avg_grade_pct,
                rider_params,
                env_params,
                max_descent_speed_mps=effective_max_descent_speed,
            )
            total_seg_time = segment.length_m / avg_speed if avg_speed > 0 else 0

        targets.append(
            PacingTarget(
                segment_idx=seg_idx,
                start_distance_m=seg_start,
                end_distance_m=seg_end,
                distance_m=segment.length_m,
                grade_pct=segment.avg_grade_pct,
                target_power_w=avg_power,
                terrain_type=segment.terrain_type,
                estimated_speed_mps=avg_speed,
                estimated_time_s=total_seg_time,
            )
        )

        # Reset fine_idx to allow overlap at segment boundaries
        # (fine points exactly at segment boundary could belong to either)
        if fine_idx > 0:
            fine_idx -= 1

    # Use aggregated metrics from fine-grained plan (more accurate)
    intensity_factor = calculate_intensity_factor(fine_plan.normalized_power_w, rider_ftp)

    return PacingPlan(
        targets=targets,
        total_time_s=fine_plan.total_time_s,
        total_distance_m=fine_plan.total_distance_m,
        avg_power_w=fine_plan.avg_power_w,
        normalized_power_w=fine_plan.normalized_power_w,
        intensity_factor=intensity_factor,
    )
