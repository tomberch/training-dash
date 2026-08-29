"""Scale-to-time solver: terrain-shaped target-time plans (ADR 0005 #637).

A target-time plan scales the rider's terrain-shaped profile on pedaling
segments until riding time hits the target; descents stay at coast level
(unchanged by scaling — pedaling a descent harder buys almost nothing).
Replaces the constant-power Mode A optimizer, which promised NP ≈ avg
for rides that actually cost far more NP at the same pace.

The solver binary-searches the pedaling power scale over the fine-grained
physics engine (monotone: more power → less time), freezing descent-point
powers at their baseline (unscaled) values.
"""

from dataclasses import dataclass

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.fine_grained_pacing import (
    calculate_np_from_fine_grained,
    calculate_speeds_and_times,
    resample_elevation_profile,
)
from trainingdash.domain.pacing import PacingPlan, PacingTarget
from trainingdash.domain.pacing_model import (
    DESCENT_GRADE_PCT,
    PacingCoefficients,
    RideTypeParams,
    effective_descent_power_multiplier,
    get_grade_power_multiplier,
    modulate_descent_power_multiplier,
)
from trainingdash.domain.physics import EnvironmentParams, RiderParams

# Solver bounds on the pedaling-power scale (relative to the baseline shape)
DEFAULT_MIN_SCALE = 0.5
DEFAULT_MAX_SCALE = 2.0

# Convergence: riding time within this fraction of the target is solved
TIME_TOLERANCE = 0.005

# Binary-search iteration budget (2^-24 precision — plenty)
MAX_ITERATIONS = 30


@dataclass
class ScaleSolveResult:
    """Result of the scale-to-time solve."""

    plan: PacingPlan
    solved_intensity: float  # # the intensity that hits the target
    converged: bool
    fine_powers: list[float] | None = None  # per-point powers (solver internals)
    fine_points: list | None = None  # resampled points (distance/grade)


def solve_target_time(
    segments: list[CourseSegment],
    rider_ftp: float,
    target_time_s: float,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
    coefficients: PacingCoefficients | None = None,
    elevation_profile: list[dict] | None = None,
    baseline_intensity: float = 0.85,
    power_cap_ftp_pct: float = 1.05,
    max_descent_speed_mps: float | None = None,
    min_intensity: float = 0.3,
    max_intensity: float = 1.5,
    ride_type_params: "RideTypeParams | None" = None,
    wind_speed_mps: float | None = None,
    wind_direction_deg: float | None = None,
) -> ScaleSolveResult:
    """
    Solve for the terrain-shaped plan that rides the course in target_time_s.

    The rider's shaped profile is evaluated at the baseline intensity; the
    solver then binary-searches a pedaling-power scale that hits the target
    riding time. Descent-point powers stay at their baseline (coast-level)
    values — scaling moves pedaling segments only.

    Args:
        segments: Course segments (display structure).
        rider_ftp: Rider FTP in watts.
        target_time_s: Desired riding time (excluding stops).
        baseline_intensity: IF defining the reference shape (default 0.85).
        min_intensity / max_intensity: solver bounds on the scaled
            intensity; outside them the target is infeasible (hard error).
        ride_type_params: Plan-Type modulation (#636), applied to the
            descent multiplier before freezing descent powers.

    Returns:
        ScaleSolveResult with the plan, the solved intensity, and
        convergence flag.

    Raises:
        ValueError: If the target time is faster/slower than achievable
            within the intensity bounds (message states the achievable
            extreme at those bounds).
    """
    if elevation_profile is None or len(elevation_profile) < 2:
        raise ValueError("scale-to-time requires an elevation profile (fine-grained path)")

    if coefficients is None:
        coefficients = PacingCoefficients.defaults()
    if rider_params is None:
        rider_params = RiderParams()
    if env_params is None:
        env_params = EnvironmentParams()

    base_power = rider_ftp * baseline_intensity
    # The cap follows the solver's intensity bound: scaling toward
    # max_intensity must not be clipped by a tighter power cap (the two
    # bounds would fight and feasibility would lie).
    power_cap = rider_ftp * max(power_cap_ftp_pct, max_intensity)
    descent_mult = modulate_descent_power_multiplier(effective_descent_power_multiplier(coefficients), ride_type_params)

    # Baseline fine plan: powers per point + descent mask
    points = resample_elevation_profile(elevation_profile)
    if not points:
        raise ValueError("empty elevation profile")

    baseline_powers = _shape_powers(points, base_power, power_cap, coefficients, descent_mult)
    descent_mask = [p.grade_pct < DESCENT_GRADE_PCT for p in points]

    def ride_time_at(intensity: float) -> tuple[float, list[float], list[float], list[float]]:
        """Evaluate the shape at an intensity; descents stay frozen."""
        scale = intensity / baseline_intensity
        powers = [pw if is_descent else pw * scale for pw, is_descent in zip(baseline_powers, descent_mask)]
        powers = [min(pw, power_cap) for pw in powers]
        speeds, times = calculate_speeds_and_times(
            points=points,
            powers=powers,
            rider_params=rider_params,
            env_params=env_params,
            max_descent_speed_mps=max_descent_speed_mps or coefficients.max_descent_speed_mps,
            ride_type="training",
            descent_aggressiveness=70,
            coefficients=coefficients,
            wind_speed_mps=wind_speed_mps,
            wind_direction_deg=wind_direction_deg,
        )
        return sum(times), powers, speeds, times

    # Feasibility at the bounds
    time_at_max, *_ = ride_time_at(max_intensity)
    time_at_min, *_ = ride_time_at(min_intensity)
    if target_time_s < time_at_max:
        raise ValueError(
            f"Target time {target_time_s:.0f}s is too fast. Minimum achievable at "
            f"intensity {max_intensity:.2f} (with descents coasted) is {time_at_max:.0f}s"
        )
    if target_time_s > time_at_min:
        raise ValueError(
            f"Target time {target_time_s:.0f}s is too slow. Maximum achievable at "
            f"intensity {min_intensity:.2f} is {time_at_min:.0f}s"
        )

    # Binary search on intensity (monotone decreasing time)
    lo, hi = min_intensity, max_intensity
    solved = None
    for _ in range(MAX_ITERATIONS):
        mid = (lo + hi) / 2
        t, powers, speeds, times = ride_time_at(mid)
        if abs(t - target_time_s) <= TIME_TOLERANCE * target_time_s:
            solved = (mid, powers, speeds, times, t)
            break
        if t > target_time_s:  # too slow → ride harder
            lo = mid
        else:  # too fast → ride easier
            hi = mid
        solved = (mid, powers, speeds, times, t)

    if solved is None:  # unreachable; loop always sets solved
        solved = (hi, *ride_time_at(hi)[1:], ride_time_at(hi)[0])  # type: ignore[misc]

    intensity, powers, speeds, times, riding_time = solved
    converged = bool(abs(riding_time - target_time_s) <= max(TIME_TOLERANCE * target_time_s, 1.0))

    # Aggregate to segments + compute metrics
    targets = _aggregate_to_segments(points, powers, speeds, times, segments, rider_ftp, power_cap)
    total_time = sum(t.estimated_time_s for t in targets)
    np_power, _ = calculate_np_from_fine_grained(powers, times)
    avg_power = sum(p * t for p, t in zip(powers, times)) / total_time if total_time > 0 else 0.0

    plan = PacingPlan(
        targets=targets,
        total_time_s=total_time,
        total_distance_m=targets[-1].end_distance_m if targets else 0.0,
        avg_power_w=avg_power,
        normalized_power_w=np_power,
        intensity_factor=np_power / rider_ftp if rider_ftp > 0 else 0.0,
    )
    return ScaleSolveResult(
        plan=plan,
        solved_intensity=intensity,
        converged=converged,
        fine_powers=powers,
        fine_points=points,
    )


def _shape_powers(
    points,
    base_power: float,
    power_cap: float,
    coefficients: PacingCoefficients,
    descent_mult: float,
) -> list[float]:
    """Baseline shape: grade-power formula on pedaling points, descent
    multiplier on descent points (mirrors calculate_power_targets)."""
    powers = []
    for p in points:
        if p.grade_pct < DESCENT_GRADE_PCT:
            mult = descent_mult
        else:
            mult = get_grade_power_multiplier(p.grade_pct, coefficients)
        powers.append(min(base_power * mult, power_cap))
    return powers


def _aggregate_to_segments(points, powers, speeds, times, segments, rider_ftp, power_cap) -> list[PacingTarget]:
    """Map fine-grained results onto the display segment structure."""
    targets: list[PacingTarget] = []
    fine_idx = 0
    n_fine = len(points)
    for seg_idx, segment in enumerate(segments):
        seg_p, seg_t, seg_s = [], [], []
        while fine_idx < n_fine:
            pt = points[fine_idx]
            if pt.distance_m < segment.start_distance_m - 1.0:
                fine_idx += 1
                continue
            if pt.distance_m >= segment.end_distance_m + 1.0:
                break
            seg_p.append(powers[fine_idx])
            seg_t.append(times[fine_idx])
            seg_s.append(speeds[fine_idx])
            fine_idx += 1
        if seg_p and seg_t:
            total_t = sum(seg_t)
            avg_p = sum(p * t for p, t in zip(seg_p, seg_t)) / total_t if total_t > 0 else 0.0
            avg_s = sum(s * t for s, t in zip(seg_s, seg_t)) / total_t if total_t > 0 else 1.0
            seg_time = total_t
        else:
            avg_p, avg_s, seg_time = 0.0, 1.0, segment.length_m / 1.0
        targets.append(
            PacingTarget(
                segment_idx=seg_idx,
                start_distance_m=segment.start_distance_m,
                end_distance_m=segment.end_distance_m,
                distance_m=segment.length_m,
                grade_pct=segment.avg_grade_pct,
                target_power_w=avg_p,
                terrain_type=segment.terrain_type,
                estimated_speed_mps=avg_s,
                estimated_time_s=seg_time,
            )
        )
    return targets
