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

from dataclasses import dataclass

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
        max_iterations: Maximum optimizer iterations. Default 200.
        tolerance: Convergence tolerance. Default 1e-4.
        power_bounds_pct: Min/max power as fraction of FTP. Default (0.5, 1.2).
        wbal_min_threshold: Minimum W'bal to maintain (joules). Default 0.
    """

    method: str = "SLSQP"
    max_iterations: int = 200
    tolerance: float = 1e-4
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


def _compute_segment_times(
    powers: np.ndarray,
    segments: list[CourseSegment],
    rider_params: RiderParams,
    env_params: EnvironmentParams,
    _cache: dict | None = None,
) -> np.ndarray:
    """Compute time for each segment given power distribution.
    
    Optionally uses a cache keyed by (power, grade) tuples.
    """
    times = np.zeros(len(segments))
    for i, seg in enumerate(segments):
        power = powers[i]
        grade = seg.avg_grade_pct
        
        # Check cache
        if _cache is not None:
            cache_key = (round(power, 1), round(grade, 2))
            if cache_key in _cache:
                times[i] = seg.length_m / _cache[cache_key]
                continue
        
        speed = speed_from_power(power, grade, rider_params, env_params)
        
        # Store in cache
        if _cache is not None:
            _cache[cache_key] = speed
            
        times[i] = seg.length_m / speed if speed > 0 else 1e6
    return times


def _compute_wbal_min_fast(
    powers: np.ndarray,
    times: np.ndarray,
    cp: float,
    w_prime: float,
) -> float:
    """
    Fast W'bal minimum calculation for optimizer.

    Uses segment-level approximation instead of per-second expansion.
    For segments where power > CP, W'bal depletes.
    For segments where power < CP, W'bal recovers exponentially.

    This is an approximation but runs in O(n_segments) instead of O(total_seconds).
    """
    wbal = w_prime
    min_wbal = w_prime

    for power, time in zip(powers, times, strict=True):
        if power > cp:
            # Depletion: linear drain
            depletion = (power - cp) * time
            wbal = max(0.0, wbal - depletion)
        elif power < cp:
            # Recovery: exponential approach to W'
            # Using average recovery over segment
            deficit = cp - power
            if deficit > 0 and time > 0:
                tau = w_prime / deficit
                # Exponential recovery: wbal approaches w_prime
                wbal = w_prime - (w_prime - wbal) * np.exp(-time / tau)
                wbal = min(w_prime, wbal)
        # At exactly CP: no change

        min_wbal = min(min_wbal, wbal)

    return min_wbal


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

    target_energy_j = target_energy_kj * 1000
    n_segments = len(segments)

    # Generate initial guess from heuristic if not provided
    if initial_guess is None:
        # Estimate intensity from energy budget and typical course time
        estimated_time_s = sum(seg.length_m / 8.0 for seg in segments)  # ~30 km/h avg
        estimated_avg_power = target_energy_j / estimated_time_s
        target_intensity = max(0.5, min(1.0, estimated_avg_power / rider_ftp))

        initial_guess = generate_heuristic_pacing(
            segments,
            rider_ftp=rider_ftp,
            target_intensity=target_intensity,
            rider_params=rider_params,
            env_params=env_params,
        )

    # Extract initial powers and scale to match energy budget
    x0 = np.array([t.target_power_w for t in initial_guess.targets])

    # Scale initial guess to roughly match energy budget
    init_times = _compute_segment_times(x0, segments, rider_params, env_params)
    init_energy = np.sum(x0 * init_times)
    if init_energy > 0:
        scale_factor = target_energy_j / init_energy
        # Don't scale too aggressively
        scale_factor = max(0.5, min(1.5, scale_factor))
        x0 = x0 * scale_factor

    # Power bounds per segment
    min_power = rider_ftp * config.power_bounds_pct[0]
    max_power = rider_ftp * config.power_bounds_pct[1]
    bounds = [(min_power, max_power) for _ in range(n_segments)]

    # Clip initial guess to bounds
    x0 = np.clip(x0, min_power, max_power)

    # Speed cache for performance - keyed by (power, grade)
    speed_cache: dict[tuple[float, float], float] = {}

    # Objective function
    def objective(powers: np.ndarray) -> float:
        times = _compute_segment_times(powers, segments, rider_params, env_params, speed_cache)
        return np.sum(times)

    # Energy equality constraint: sum(power * time) = target
    def energy_constraint(powers: np.ndarray) -> float:
        times = _compute_segment_times(powers, segments, rider_params, env_params, speed_cache)
        total_energy = np.sum(powers * times)
        return total_energy - target_energy_j

    # W'bal inequality constraint: min_wbal >= threshold
    def wbal_constraint(powers: np.ndarray) -> float:
        times = _compute_segment_times(powers, segments, rider_params, env_params, speed_cache)
        min_wbal = _compute_wbal_min_fast(powers, times, rider_cp, rider_w_prime)
        return min_wbal - config.wbal_min_threshold

    constraints = [
        {"type": "eq", "fun": energy_constraint},
        {"type": "ineq", "fun": wbal_constraint},
    ]

    # Calculate baseline times for comparison
    constant_power_guess = target_energy_j / sum(
        seg.length_m / 8.0 for seg in segments
    )
    constant_power_guess = np.clip(constant_power_guess, min_power, max_power)
    constant_powers = np.full(n_segments, constant_power_guess)
    constant_time = objective(constant_powers)
    heuristic_time = initial_guess.total_time_s

    # Run optimization with reduced iterations for performance
    # The heuristic initial guess is already good; optimizer refines it
    result = minimize(
        fun=objective,
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
    optimized_powers = np.array(result.x)

    # Build pacing targets from optimized powers
    targets = _build_targets(optimized_powers, segments, rider_params, env_params)
    total_time = sum(t.estimated_time_s for t in targets)
    total_distance = sum(t.distance_m for t in targets)

    # Calculate metrics
    total_energy_j_actual = sum(t.target_power_w * t.estimated_time_s for t in targets)
    avg_power = total_energy_j_actual / total_time if total_time > 0 else 0

    # NP approximation (time-weighted 4th power mean)
    weighted_4th = sum(
        t.target_power_w**4 * t.estimated_time_s for t in targets
    ) / total_time
    np_power = weighted_4th**0.25

    intensity_factor = np_power / rider_ftp if rider_ftp > 0 else 0

    # W'bal check using accurate method for final result
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
        message=result.message if hasattr(result, "message") else "",
    )


def _build_targets(
    powers: np.ndarray,
    segments: list[CourseSegment],
    rider_params: RiderParams,
    env_params: EnvironmentParams,
) -> list[PacingTarget]:
    """Build PacingTarget list from optimized powers."""
    targets = []
    for i, seg in enumerate(segments):
        speed = speed_from_power(powers[i], seg.avg_grade_pct, rider_params, env_params)
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
