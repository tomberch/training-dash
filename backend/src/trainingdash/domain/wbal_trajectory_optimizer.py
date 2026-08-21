"""
W'bal trajectory optimization prototype for research (#573).

This module extends the basic pacing optimizer by making W'bal trajectory
part of the optimization objective, not just a constraint.

Key insight: Optimal pacing should:
1. Deplete W' strategically on climbs before descents (where recovery happens)
2. Finish with W'bal ≈ 0 (empty tank = no time left on course)
3. Plan depletion/recovery cycles across the course

Approach:
- Add a "finish empty" penalty to the objective function
- Optionally reward strategic depletion before recovery opportunities
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import generate_heuristic_pacing
from trainingdash.domain.pacing_optimizer import (
    OptimizationConfig,
    OptimizedPlan,
    _build_targets,
    _compute_segment_times,
    _compute_wbal_min_fast,
)
from trainingdash.domain.physics import EnvironmentParams, RiderParams
from trainingdash.domain.wbal import check_wbal_feasibility


@dataclass(frozen=True)
class TrajectoryOptConfig(OptimizationConfig):
    """Extended config for trajectory optimization.

    Attributes:
        finish_empty_weight: Weight for "finish with W'bal near 0" objective.
            Higher = more aggressive depletion. Default 0.001.
        target_final_wbal_pct: Target final W'bal as fraction of W'.
            Default 0.05 (5% remaining = nearly empty).
        strategic_depletion_weight: Weight for depleting before descents.
            Default 0.0 (disabled - experimental).
    """

    finish_empty_weight: float = 0.001
    target_final_wbal_pct: float = 0.05
    strategic_depletion_weight: float = 0.0


def _compute_wbal_trajectory(
    powers: np.ndarray,
    times: np.ndarray,
    cp: float,
    w_prime: float,
) -> tuple[float, float, np.ndarray]:
    """
    Compute full W'bal trajectory for optimizer.

    Returns:
        Tuple of (min_wbal, final_wbal, wbal_at_each_segment_end)
    """
    wbal = w_prime
    min_wbal = w_prime
    wbal_series = np.zeros(len(powers))

    for i, (power, time) in enumerate(zip(powers, times, strict=True)):
        if power > cp:
            # Depletion
            depletion = (power - cp) * time
            wbal = max(0.0, wbal - depletion)
        elif power < cp:
            # Recovery
            deficit = cp - power
            if deficit > 0 and time > 0:
                tau = w_prime / deficit
                wbal = w_prime - (w_prime - wbal) * np.exp(-time / tau)
                wbal = min(w_prime, wbal)

        min_wbal = min(min_wbal, wbal)
        wbal_series[i] = wbal

    return min_wbal, wbal, wbal_series


def _identify_recovery_opportunities(
    segments: list[CourseSegment],
) -> np.ndarray:
    """
    Identify segments that are followed by recovery opportunities.

    A recovery opportunity is a descent or flat where power < CP is expected.
    Returns a binary mask: 1 if segment precedes recovery, 0 otherwise.
    """
    n = len(segments)
    precedes_recovery = np.zeros(n)

    for i in range(n - 1):
        next_seg = segments[i + 1]
        # Descent (negative grade) or gentle downhill is a recovery opportunity
        if next_seg.avg_grade_pct < -1.0:
            precedes_recovery[i] = 1.0
        # Also count long flat sections as partial recovery
        elif next_seg.avg_grade_pct < 0.5 and next_seg.length_m > 500:
            precedes_recovery[i] = 0.5

    return precedes_recovery


def optimize_with_trajectory(
    segments: list[CourseSegment],
    rider_ftp: float,
    rider_cp: float,
    rider_w_prime: float,
    target_energy_kj: float,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
    config: TrajectoryOptConfig | None = None,
) -> OptimizedPlan:
    """
    Optimize pacing with W'bal trajectory as part of the objective.

    This extends optimize_pacing() by adding:
    1. "Finish empty" penalty - encourages using all W' by the finish
    2. Optional strategic depletion bonus before recovery segments

    Args:
        segments: Course segments from course_segmentation module.
        rider_ftp: Rider's Functional Threshold Power in watts.
        rider_cp: Rider's Critical Power in watts.
        rider_w_prime: Rider's W' (anaerobic capacity) in joules.
        target_energy_kj: Total energy budget in kilojoules.
        rider_params: Rider physical parameters.
        env_params: Environmental conditions.
        config: Trajectory optimizer configuration.

    Returns:
        OptimizedPlan with per-segment targets and optimization metrics.
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
        config = TrajectoryOptConfig()

    target_energy_j = target_energy_kj * 1000
    n_segments = len(segments)

    # Identify recovery opportunities for strategic depletion
    recovery_mask = _identify_recovery_opportunities(segments)

    # Generate initial guess from heuristic
    estimated_time_s = sum(seg.length_m / 8.0 for seg in segments)
    estimated_avg_power = target_energy_j / estimated_time_s
    target_intensity = max(0.5, min(1.0, estimated_avg_power / rider_ftp))

    initial_guess = generate_heuristic_pacing(
        segments,
        rider_ftp=rider_ftp,
        target_intensity=target_intensity,
        rider_params=rider_params,
        env_params=env_params,
    )

    x0 = np.array([t.target_power_w for t in initial_guess.targets])

    # Scale initial guess to match energy budget
    init_times = _compute_segment_times(x0, segments, rider_params, env_params)
    init_energy = np.sum(x0 * init_times)
    if init_energy > 0:
        scale_factor = np.clip(target_energy_j / init_energy, 0.5, 1.5)
        x0 = x0 * scale_factor

    # Power bounds
    min_power = rider_ftp * config.power_bounds_pct[0]
    max_power = rider_ftp * config.power_bounds_pct[1]
    bounds = [(min_power, max_power) for _ in range(n_segments)]
    x0 = np.clip(x0, min_power, max_power)

    # Speed cache
    speed_cache: dict[tuple[float, float], float] = {}

    # Target final W'bal (finish nearly empty)
    target_final_wbal = rider_w_prime * config.target_final_wbal_pct

    def objective(powers: np.ndarray) -> float:
        """
        Combined objective: minimize time + finish empty penalty.

        The finish empty penalty encourages depleting W' by the end.
        """
        times = _compute_segment_times(powers, segments, rider_params, env_params, speed_cache)
        total_time = np.sum(times)

        # W'bal trajectory
        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, rider_cp, rider_w_prime)

        # Penalty for not finishing empty (leftover W' = wasted potential)
        # Quadratic penalty encourages final_wbal → target_final_wbal
        finish_penalty = config.finish_empty_weight * ((final_wbal - target_final_wbal) ** 2)

        # Optional: bonus for strategic depletion before recovery
        # This rewards depleting W' right before a descent
        strategic_bonus = 0.0
        if config.strategic_depletion_weight > 0:
            # Reward low W'bal at segments that precede recovery
            for i, (wbal, mask) in enumerate(zip(wbal_series, recovery_mask)):
                if mask > 0:
                    # Lower W'bal before recovery = better
                    # Normalize by W' so it's scale-independent
                    depletion_ratio = 1.0 - (wbal / rider_w_prime)
                    strategic_bonus -= config.strategic_depletion_weight * depletion_ratio * mask

        return total_time + finish_penalty + strategic_bonus

    # Energy equality constraint
    def energy_constraint(powers: np.ndarray) -> float:
        times = _compute_segment_times(powers, segments, rider_params, env_params, speed_cache)
        total_energy = np.sum(powers * times)
        return total_energy - target_energy_j

    # W'bal feasibility constraint (still need W'bal >= 0)
    def wbal_constraint(powers: np.ndarray) -> float:
        times = _compute_segment_times(powers, segments, rider_params, env_params, speed_cache)
        min_wbal = _compute_wbal_min_fast(powers, times, rider_cp, rider_w_prime)
        return min_wbal - config.wbal_min_threshold

    constraints = [
        {"type": "eq", "fun": energy_constraint},
        {"type": "ineq", "fun": wbal_constraint},
    ]

    # Baseline times for comparison
    constant_power = target_energy_j / sum(seg.length_m / 8.0 for seg in segments)
    constant_power = np.clip(constant_power, min_power, max_power)
    constant_powers = np.full(n_segments, constant_power)
    constant_times = _compute_segment_times(constant_powers, segments, rider_params, env_params)
    constant_time = np.sum(constant_times)
    heuristic_time = initial_guess.total_time_s

    # Run optimization
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

    optimized_powers = np.array(result.x)
    targets = _build_targets(optimized_powers, segments, rider_params, env_params)
    total_time = sum(t.estimated_time_s for t in targets)
    total_distance = sum(t.distance_m for t in targets)

    # Metrics
    total_energy_j_actual = sum(t.target_power_w * t.estimated_time_s for t in targets)
    avg_power = total_energy_j_actual / total_time if total_time > 0 else 0

    weighted_4th = sum(t.target_power_w**4 * t.estimated_time_s for t in targets) / total_time
    np_power = weighted_4th**0.25
    intensity_factor = np_power / rider_ftp if rider_ftp > 0 else 0

    # Final W'bal check
    times_arr = np.array([t.estimated_time_s for t in targets])
    _, wbal_min = check_wbal_feasibility(optimized_powers, times_arr, rider_cp, rider_w_prime)

    improvement_vs_constant = (constant_time - total_time) / constant_time * 100 if constant_time > 0 else 0
    improvement_vs_heuristic = (heuristic_time - total_time) / heuristic_time * 100 if heuristic_time > 0 else 0

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
