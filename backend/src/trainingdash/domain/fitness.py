"""
Fitness model computation using 2-parameter Critical Power model.

The classic hyperbolic power-duration model:
    P(t) = CP + W' / t

Where:
- CP: Critical Power (the asymptote — maximal metabolic steady state)
- W': Anaerobic Work Capacity (finite work available above CP, in joules)
- t: duration in seconds
- P: power output in watts

Scientific basis:
- CP represents the boundary between heavy and severe exercise domains
- The model is fitted using nonlinear regression on maximal efforts
- Valid duration range for fitting: 2-12 minutes (per Spragg et al. 2023)
- Efforts beyond ~20 minutes include pacing effects and should be excluded

References:
- Morton RH (1996). A 3-parameter critical power model. Ergonomics.
- Spragg et al. (2023). Estimating CP from MMP data. J Sports Sci.
- Frontiers in Physiology (2021). CP vs FTP relationship study.
"""

import math
from datetime import UTC, datetime

import numpy as np

# Key durations for breakthrough detection (seconds)
BREAKTHROUGH_DURATIONS = [5, 60, 300, 1200]  # 5s, 1min, 5min, 20min

# Decay half-life in days for weighting recent activities
DECAY_HALF_LIFE_DAYS = 42  # 6 weeks

# Duration bounds for CP model fitting (seconds)
# Based on scientific literature: 2-12 minutes is the validated range
CP_FIT_MIN_DURATION = 120  # 2 minutes
CP_FIT_MAX_DURATION = 720  # 12 minutes


def compute_decay_weight(activity_date: datetime, reference_date: datetime) -> float:
    """
    Compute exponential decay weight for an activity.

    More recent activities are weighted higher.
    Weight = 0.5^(days_old / half_life)
    """
    # Normalize both to naive UTC for comparison
    if activity_date.tzinfo is not None:
        activity_date = activity_date.replace(tzinfo=None)
    if reference_date.tzinfo is not None:
        reference_date = reference_date.replace(tzinfo=None)

    days_old = (reference_date - activity_date).days
    if days_old < 0:
        days_old = 0
    return math.pow(0.5, days_old / DECAY_HALF_LIFE_DAYS)


def _hyperbolic_model(t: np.ndarray, cp: float, w_prime: float) -> np.ndarray:
    """
    2-parameter hyperbolic critical power model.

    P(t) = CP + W' / t

    Args:
        t: Duration in seconds (array)
        cp: Critical Power in watts
        w_prime: W' in joules

    Returns:
        Power output in watts (array)
    """
    return cp + w_prime / t


def _fit_2_parameter_model(
    durations: np.ndarray,
    powers: np.ndarray,
    weights: np.ndarray | None = None,
) -> tuple[float, float] | None:
    """
    Fit the 2-parameter CP model using Gauss-Newton nonlinear least squares.

    The model: P(t) = CP + W'/t

    Uses a pure numpy implementation to avoid scipy dependency.

    Args:
        durations: Array of durations in seconds
        powers: Array of power values in watts
        weights: Optional weights for each data point

    Returns:
        Tuple of (CP, W') or None if fitting fails
    """
    if len(durations) < 2:
        return None

    # Initial guesses based on data
    # CP ~ power at longest duration
    # W' ~ (power at shortest - power at longest) * shortest duration
    cp = float(np.min(powers))
    w_prime = float((np.max(powers) - cp) * np.min(durations))

    # Clamp initial guesses to bounds
    cp = max(50.0, min(600.0, cp))
    w_prime = max(1000.0, min(50000.0, w_prime))

    # Set up weights (default to uniform)
    if weights is None:
        w = np.ones_like(powers)
    else:
        w = weights

    # Gauss-Newton iteration
    max_iter = 50
    tol = 1e-6

    try:
        for _ in range(max_iter):
            # Model prediction: P(t) = cp + w_prime / t
            pred = cp + w_prime / durations

            # Residuals (weighted)
            residuals = (powers - pred) * np.sqrt(w)

            # Jacobian: dP/d(cp) = 1, dP/d(w_prime) = 1/t
            J = np.column_stack([np.ones_like(durations), 1.0 / durations])
            # Apply weights to Jacobian
            J_weighted = J * np.sqrt(w)[:, np.newaxis]

            # Gauss-Newton step: solve J^T J delta = J^T r
            JTJ = J_weighted.T @ J_weighted
            JTr = J_weighted.T @ residuals

            # Add small regularization for numerical stability
            JTJ += np.eye(2) * 1e-8

            delta = np.linalg.solve(JTJ, JTr)

            # Update parameters
            cp_new = cp + delta[0]
            w_prime_new = w_prime + delta[1]

            # Apply bounds
            cp_new = max(50.0, min(600.0, cp_new))
            w_prime_new = max(1000.0, min(50000.0, w_prime_new))

            # Check convergence
            if abs(cp_new - cp) < tol and abs(w_prime_new - w_prime) < tol * 100:
                cp, w_prime = cp_new, w_prime_new
                break

            cp, w_prime = cp_new, w_prime_new

        return float(cp), float(w_prime)

    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        # Fitting failed, fall back to linear regression on work-time model
        return _fit_linear_work_model(durations, powers)


def _fit_linear_work_model(
    durations: np.ndarray,
    powers: np.ndarray,
) -> tuple[float, float] | None:
    """
    Fallback: fit the work-time linear model.

    W = CP * t + W'

    This is a linear regression where:
    - Work (W = P * t) is the dependent variable
    - Duration (t) is the independent variable
    - CP is the slope
    - W' is the intercept
    """
    if len(durations) < 2:
        return None

    work = powers * durations

    # Linear regression: W = CP * t + W'
    # Using numpy's polyfit (degree 1)
    try:
        coeffs = np.polyfit(durations, work, 1)
        cp = float(coeffs[0])  # slope
        w_prime = float(coeffs[1])  # intercept

        # Sanity check
        if cp < 50 or cp > 600 or w_prime < 1000 or w_prime > 50000:
            return None

        return cp, w_prime

    except (np.linalg.LinAlgError, ValueError):
        return None


def fit_cp_model(
    peak_powers: list[dict],
    activity_dates: list[datetime] | None = None,
    reference_date: datetime | None = None,
) -> dict | None:
    """
    Fit 2-parameter Critical Power model to peak power data.

    Uses nonlinear least squares regression on the hyperbolic model:
    P(t) = CP + W'/t

    Only uses data points in the scientifically validated range (2-12 minutes)
    for CP/W' fitting. Peak power is estimated separately from short efforts.

    Args:
        peak_powers: List of {duration_seconds: watts} dicts, one per activity
        activity_dates: Optional list of activity dates for decay weighting
        reference_date: Reference date for decay calculation (default: now)

    Returns:
        Dict with pp_watts, w_prime_joules, cp_watts, or None if insufficient data
    """
    if not peak_powers:
        return None

    # Aggregate best power at each duration across all activities
    best_by_duration: dict[int, tuple[int, float]] = {}  # duration -> (watts, weight)

    reference_date = reference_date or datetime.now(UTC)

    for i, peaks in enumerate(peak_powers):
        weight = 1.0
        if activity_dates and i < len(activity_dates):
            weight = compute_decay_weight(activity_dates[i], reference_date)

        for duration, watts in peaks.items():
            if watts is None:
                continue
            duration = int(duration)
            watts = int(watts)

            if duration not in best_by_duration or watts > best_by_duration[duration][0]:
                best_by_duration[duration] = (watts, weight)

    if len(best_by_duration) < 3:
        return None

    # Estimate PP (peak power) from short durations (1-10s)
    pp_watts = 0
    for dur in [1, 5, 10]:
        if dur in best_by_duration:
            pp_watts = max(pp_watts, best_by_duration[dur][0])

    if pp_watts == 0:
        # Fallback to shortest available
        shortest = min(best_by_duration.keys())
        pp_watts = best_by_duration[shortest][0]

    # Filter data points for CP model fitting (2-12 minute range)
    fit_data = [
        (dur, watts, weight)
        for dur, (watts, weight) in best_by_duration.items()
        if CP_FIT_MIN_DURATION <= dur <= CP_FIT_MAX_DURATION
    ]

    # If not enough points in the ideal range, expand to 1-20 minutes
    if len(fit_data) < 2:
        fit_data = [(dur, watts, weight) for dur, (watts, weight) in best_by_duration.items() if 60 <= dur <= 1200]

    if len(fit_data) < 2:
        # Still not enough data, use simple estimation
        return _fallback_estimation(best_by_duration, pp_watts)

    # Prepare arrays for curve fitting
    durations = np.array([d[0] for d in fit_data], dtype=float)
    powers = np.array([d[1] for d in fit_data], dtype=float)
    weights = np.array([d[2] for d in fit_data], dtype=float)

    # Fit the model
    result = _fit_2_parameter_model(durations, powers, weights)

    if result is None:
        return _fallback_estimation(best_by_duration, pp_watts)

    cp_watts, w_prime_joules = result

    # Round to integers
    cp_watts = int(round(cp_watts))
    w_prime_joules = int(round(w_prime_joules))

    # Final sanity bounds
    w_prime_joules = max(5000, min(40000, w_prime_joules))

    return {
        "pp_watts": pp_watts,
        "w_prime_joules": w_prime_joules,
        "cp_watts": cp_watts,
    }


def _fallback_estimation(
    best_by_duration: dict[int, tuple[int, float]],
    pp_watts: int,
) -> dict | None:
    """
    Fallback CP estimation when curve fitting isn't possible.

    Uses the traditional 95% of 20-minute power rule, or similar heuristics.
    """
    cp_watts = 0

    # Try 20-minute power first (the FTP test duration)
    if 1200 in best_by_duration:
        # CP ≈ 20-minute power (already maximal effort)
        cp_watts = best_by_duration[1200][0]
    elif 300 in best_by_duration:
        # CP ≈ 95% of 5-minute power
        cp_watts = int(best_by_duration[300][0] * 0.95)
    elif 600 in best_by_duration:
        # CP ≈ 10-minute power
        cp_watts = best_by_duration[600][0]
    elif 60 in best_by_duration:
        # Very rough: CP ≈ 80% of 1-minute power
        cp_watts = int(best_by_duration[60][0] * 0.80)

    if cp_watts == 0:
        return None

    # Estimate W' from difference between short efforts and CP
    w_prime_estimates = []
    for dur in [60, 120, 180, 300]:
        if dur in best_by_duration:
            p = best_by_duration[dur][0]
            if p > cp_watts:
                w_prime = (p - cp_watts) * dur
                w_prime_estimates.append(w_prime)

    if w_prime_estimates:
        w_prime_joules = int(sum(w_prime_estimates) / len(w_prime_estimates))
    else:
        w_prime_joules = cp_watts * 60

    w_prime_joules = max(5000, min(40000, w_prime_joules))

    return {
        "pp_watts": pp_watts,
        "w_prime_joules": w_prime_joules,
        "cp_watts": cp_watts,
    }


def detect_breakthrough(
    activity_peaks: dict[int, int],
    all_time_bests: dict[int, int],
) -> bool:
    """
    Detect if an activity is a breakthrough (sets PRs at key durations).

    Args:
        activity_peaks: {duration_seconds: watts} for the new activity
        all_time_bests: {duration_seconds: watts} best powers before this activity

    Returns:
        True if the activity sets a new PR at any breakthrough duration
    """
    for duration in BREAKTHROUGH_DURATIONS:
        if duration in activity_peaks:
            new_power = activity_peaks[duration]
            old_best = all_time_bests.get(duration, 0)
            if new_power > old_best:
                return True
    return False


def get_all_time_bests(
    peak_powers_by_activity: list[dict[int, int]],
) -> dict[int, int]:
    """
    Get all-time best power at each duration.

    Args:
        peak_powers_by_activity: List of {duration: watts} dicts

    Returns:
        {duration: best_watts} across all activities
    """
    bests: dict[int, int] = {}
    for peaks in peak_powers_by_activity:
        for duration, watts in peaks.items():
            if watts is not None:
                duration = int(duration)
                watts = int(watts)
                if duration not in bests or watts > bests[duration]:
                    bests[duration] = watts
    return bests
