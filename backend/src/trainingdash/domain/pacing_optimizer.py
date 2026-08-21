"""
Scipy-based pacing optimizer for race planning.

This module provides numerical optimization of power distribution across
a course to minimize total time while respecting physiological constraints.

Per #530 decision: Use scipy.optimize with W'bal constraints.

The optimizer improves on the heuristic pacing (#559) by finding the
mathematically optimal power distribution, not just a grade-based heuristic.

Key insight: Variable pacing beats constant power due to the v³ relationship
between power and aerodynamic drag. The optimizer finds *how much* to vary
power on each segment to minimize total time.

Approach:
- Objective: Minimize total time
- Decision variables: Power for each segment
- Constraints:
  1. Total energy = budget (equality)
  2. W'bal >= 0 at all points (inequality)
  3. Power bounds: configurable % of FTP per segment

Uses SLSQP (Sequential Least Squares Programming) which handles both
equality and inequality constraints efficiently.

Future enhancement (#573): Optimize W'bal trajectory, not just constrain it.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import (
    PacingPlan,
    PacingTarget,
    generate_heuristic_pacing,
)
from trainingdash.domain.physics import (
    EnvironmentParams,
    RiderParams,
    speed_from_power,
)
from trainingdash.domain.wbal import check_wbal_feasibility


@dataclass(frozen=True)
class OptimizationConfig:
    """Configuration for the pacing optimizer.

    Attributes:
        method: Scipy optimization method. Default 'SLSQP'.
        max_iterations: Maximum optimizer iterations. Default 1000.
        tolerance: Convergence tolerance. Default 1e-6.
        power_bounds_pct: Min/max power as fraction of FTP. Default (0.5, 1.2).
        wbal_min_threshold: Minimum W'bal to maintain (joules). Default 0.
    """

    method: str = "SLSQP"
    max_iterations: int = 1000
    tolerance: float = 1e-6
    power_bounds_pct: tuple[float, float] = (0.5, 1.2)
    wbal_min_threshold: float = 0.0


@dataclass
class OptimizedPlan:
    """Result of pacing optimization.

    Attributes:
        targets: Per-segment pacing targets.
        total_time_s: Total time to complete the course.
        total_distance_m: Total course distance.
        avg_power_w: Time-weighted average power.
        normalized_power_w: Normalized power (NP).
        intensity_factor: NP / FTP.
        improvement_vs_constant_pct: Time saved vs constant power (%).
        improvement_vs_heuristic_pct: Time saved vs heuristic pacing (%).
        wbal_min: Minimum W'bal reached during the plan.
        converged: Whether the optimizer converged.
        iterations: Number of optimizer iterations.
        message: Optimizer termination message.
    """

    targets: list[PacingTarget]
    total_time_s: float
    total_distance_m: float
    avg_power_w: float
    normalized_power_w: float
    intensity_factor: float
    improvement_vs_constant_pct: float
    improvement_vs_heuristic_pct: float
    wbal_min: float
    converged: bool
    iterations: int
    message: str = ""


@dataclass
class _OptimizationContext:
    """Internal context passed to objective/constraint functions."""

    segments: list[CourseSegment]
    rider_params: RiderParams
    env_params: EnvironmentParams
    target_energy_j: float
    cp: float
    w_prime: float
    ftp: float
    config: OptimizationConfig
    # Cache for computed values
    _cache: dict = field(default_factory=dict)


def optimize_pacing(
    segments: list[CourseSegment],
    rider_ftp: float,
    rider_cp: float,
    rider_w_prime: float,
    target_energy_kj: float,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
    config: OptimizationConfig | None = None,
    initial_guess: PacingPlan | None = None,
) -> OptimizedPlan:
    """
    Optimize power distribution to minimize total time.

    Uses scipy.optimize.minimize with SLSQP to find the optimal power
    for each segment while respecting energy budget and W'bal constraints.

    Args:
        segments: Course segments from course_segmentation module.
        rider_ftp: Rider's Functional Threshold Power in watts.
        rider_cp: Rider's Critical Power in watts.
        rider_w_prime: Rider's W' (anaerobic capacity) in joules.
        target_energy_kj: Total energy budget in kilojoules.
        rider_params: Rider physical parameters. Defaults to typical values.
        env_params: Environmental conditions. Defaults to sea level.
        config: Optimizer configuration. Defaults to standard settings.
        initial_guess: Starting pacing plan. Defaults to heuristic.

    Returns:
        OptimizedPlan with per-segment targets and optimization metrics.

    Raises:
        ValueError: If inputs are invalid.
    """
    # Validate inputs
    if not segments:
        raise ValueError("segments cannot be empty")
    if rider_ftp <= 0:
        raise ValueError("rider_ftp must be positive")
    if rider_cp <= 0:
        raise ValueError("rider_cp must be positive")
    if rider_w_prime <= 0:
        raise ValueError("rider_w_prime must be positive")
    if target_energy_kj <= 0:
        raise ValueError("target_energy_kj must be positive")

    # Defaults
    if rider_params is None:
        rider_params = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
    if env_params is None:
        env_params = EnvironmentParams()
    if config is None:
        config = OptimizationConfig()

    # Build optimization context
    ctx = _OptimizationContext(
        segments=segments,
        rider_params=rider_params,
        env_params=env_params,
        target_energy_j=target_energy_kj * 1000,
        cp=rider_cp,
        w_prime=rider_w_prime,
        ftp=rider_ftp,
        config=config,
    )

    n_segments = len(segments)

    # Generate initial guess from heuristic if not provided
    if initial_guess is None:
        # Estimate intensity from energy budget and typical course time
        # This is approximate - the optimizer will adjust
        estimated_time_s = sum(seg.length_m / 8.0 for seg in segments)  # ~30 km/h avg
        estimated_avg_power = target_energy_kj * 1000 / estimated_time_s
        target_intensity = min(1.0, estimated_avg_power / rider_ftp)

        initial_guess = generate_heuristic_pacing(
            segments,
            rider_ftp=rider_ftp,
            target_intensity=target_intensity,
            rider_params=rider_params,
            env_params=env_params,
        )

    # Extract initial powers
    x0 = np.array([t.target_power_w for t in initial_guess.targets])

    # Power bounds per segment
    min_power = rider_ftp * config.power_bounds_pct[0]
    max_power = rider_ftp * config.power_bounds_pct[1]
    bounds = [(min_power, max_power) for _ in range(n_segments)]

    # Constraints
    constraints = [
        # Energy equality constraint
        {
            "type": "eq",
            "fun": lambda x, c=ctx: _energy_constraint(x, c),
        },
        # W'bal inequality constraint (min_wbal >= threshold)
        {
            "type": "ineq",
            "fun": lambda x, c=ctx: _wbal_constraint(x, c),
        },
    ]

    # Calculate baseline times for comparison
    constant_power = target_energy_kj * 1000 / _estimate_time_at_power(
        np.full(n_segments, rider_ftp * 0.85), ctx
    )
    # Recalculate with actual constant power
    constant_time = _estimate_time_at_power(np.full(n_segments, constant_power), ctx)
    heuristic_time = initial_guess.total_time_s

    # Run optimization
    result = minimize(
        fun=lambda x, c=ctx: _objective(x, c),
        x0=x0,
        method=config.method,
        bounds=bounds,
        constraints=constraints,
        options={
            "maxiter": config.max_iterations,
            "ftol": config.tolerance,
            "disp": False,
        },
    )

    # Extract optimized powers
    optimized_powers = result.x

    # Build pacing targets from optimized powers
    targets = _build_targets(optimized_powers, ctx)
    total_time = sum(t.estimated_time_s for t in targets)
    total_distance = sum(t.distance_m for t in targets)

    # Calculate metrics
    total_energy_j = sum(t.target_power_w * t.estimated_time_s for t in targets)
    avg_power = total_energy_j / total_time if total_time > 0 else 0

    # NP approximation (time-weighted 4th power mean)
    weighted_4th = sum(
        t.target_power_w**4 * t.estimated_time_s for t in targets
    ) / total_time
    np_power = weighted_4th**0.25

    intensity_factor = np_power / rider_ftp if rider_ftp > 0 else 0

    # W'bal check
    times = np.array([t.estimated_time_s for t in targets])
    _, wbal_min = check_wbal_feasibility(
        optimized_powers, times, rider_cp, rider_w_prime
    )

    # Calculate improvements
    improvement_vs_constant = (
        (constant_time - total_time) / constant_time * 100
        if constant_time > 0
        else 0
    )
    improvement_vs_heuristic = (
        (heuristic_time - total_time) / heuristic_time * 100
        if heuristic_time > 0
        else 0
    )

    return OptimizedPlan(
        targets=targets,
        total_time_s=total_time,
        total_distance_m=total_distance,
        avg_power_w=avg_power,
        normalized_power_w=np_power,
        intensity_factor=intensity_factor,
        improvement_vs_constant_pct=improvement_vs_constant,
        improvement_vs_heuristic_pct=improvement_vs_heuristic,
        wbal_min=wbal_min,
        converged=result.success,
        iterations=result.nit,
        message=result.message,
    )


def _objective(powers: np.ndarray, ctx: _OptimizationContext) -> float:
    """Objective function: total time to complete course."""
    return _estimate_time_at_power(powers, ctx)


def _estimate_time_at_power(
    powers: np.ndarray, ctx: _OptimizationContext
) -> float:
    """Calculate total time for given power distribution."""
    total_time = 0.0
    for i, seg in enumerate(ctx.segments):
        speed = speed_from_power(
            powers[i], seg.avg_grade_pct, ctx.rider_params, ctx.env_params
        )
        if speed > 0:
            total_time += seg.length_m / speed
        else:
            total_time += 1e6  # Penalty for zero speed
    return total_time


def _energy_constraint(powers: np.ndarray, ctx: _OptimizationContext) -> float:
    """
    Energy equality constraint.

    Returns 0 when total energy equals target.
    Constraint: sum(power * time) = target_energy_j
    """
    total_energy = 0.0
    for i, seg in enumerate(ctx.segments):
        speed = speed_from_power(
            powers[i], seg.avg_grade_pct, ctx.rider_params, ctx.env_params
        )
        if speed > 0:
            time = seg.length_m / speed
            total_energy += powers[i] * time
    return total_energy - ctx.target_energy_j


def _wbal_constraint(powers: np.ndarray, ctx: _OptimizationContext) -> float:
    """
    W'bal inequality constraint.

    Returns min_wbal - threshold, which must be >= 0.
    This ensures W'bal never drops below the threshold.
    """
    # Calculate segment times
    times = []
    for i, seg in enumerate(ctx.segments):
        speed = speed_from_power(
            powers[i], seg.avg_grade_pct, ctx.rider_params, ctx.env_params
        )
        if speed > 0:
            times.append(seg.length_m / speed)
        else:
            times.append(1e6)

    _, min_wbal = check_wbal_feasibility(
        powers, np.array(times), ctx.cp, ctx.w_prime
    )

    return min_wbal - ctx.config.wbal_min_threshold


def _build_targets(
    powers: np.ndarray, ctx: _OptimizationContext
) -> list[PacingTarget]:
    """Build PacingTarget list from optimized powers."""
    targets = []
    for i, seg in enumerate(ctx.segments):
        speed = speed_from_power(
            powers[i], seg.avg_grade_pct, ctx.rider_params, ctx.env_params
        )
        time = seg.length_m / speed if speed > 0 else float("inf")

        targets.append(
            PacingTarget(
                segment_idx=i,
                start_distance_m=seg.start_distance_m,
                end_distance_m=seg.end_distance_m,
                distance_m=seg.length_m,
                grade_pct=seg.avg_grade_pct,
                target_power_w=float(powers[i]),
                terrain_type=seg.terrain_type,
                estimated_speed_mps=speed,
                estimated_time_s=time,
            )
        )
    return targets
