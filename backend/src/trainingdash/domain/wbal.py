"""
W'bal (W-prime balance) computation using the Skiba differential method.

W'bal tracks the depletion and recovery of anaerobic work capacity (W') during exercise.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class WbalPrediction:
    """Result of W'bal prediction for a power plan."""

    wbal_series: np.ndarray  # W'bal at each point in joules
    min_wbal: float  # Minimum W'bal reached during the effort
    min_wbal_distance_m: float  # Distance where minimum occurs
    time_in_deficit: float  # Seconds where W'bal < threshold (default 0)
    final_wbal: float  # W'bal at finish


def compute_wbal_series(
    power_array: Sequence[float | int | None],
    cp_watts: int,
    w_prime_joules: int,
    sample_rate_hz: float = 1.0,
) -> dict:
    """
    Compute W'bal (W-prime balance) time series using the Skiba differential method.

    The differential method:
    - When power > CP: W'bal depletes at rate (power - CP) joules per second
    - When power < CP: W'bal recovers exponentially with tau = W' / (CP - power)

    Args:
        power_array: Array of power values in watts (None values treated as 0)
        cp_watts: Critical Power in watts
        w_prime_joules: W' (anaerobic work capacity) in joules
        sample_rate_hz: Sample rate in Hz (samples per second), default 1.0

    Returns:
        Dict with:
        - series: List of W'bal values in joules at each sample point
        - min_wbal: Minimum W'bal reached during the effort
        - min_wbal_index: Index where minimum occurred
        - min_wbal_pct: Minimum as percentage of W'
    """
    if not power_array or cp_watts <= 0 or w_prime_joules <= 0:
        return {
            "series": [],
            "min_wbal": None,
            "min_wbal_index": None,
            "min_wbal_pct": None,
        }

    dt = 1.0 / sample_rate_hz  # Time step in seconds
    wbal = float(w_prime_joules)  # Start with full W'
    series = []
    min_wbal = wbal
    min_wbal_index = 0

    for i, power in enumerate(power_array):
        # Treat None as 0 (coasting/no data)
        p = float(power) if power is not None and power >= 0 else 0.0

        if p > cp_watts:
            # Above CP: deplete W'bal
            # dW'bal = -(P - CP) * dt
            depletion = (p - cp_watts) * dt
            wbal = max(0, wbal - depletion)
        elif p < cp_watts:
            # Below CP: recover W'bal exponentially
            # Recovery rate depends on how far below CP
            # tau = W' / (CP - P)
            power_deficit = cp_watts - p
            if power_deficit > 0:
                tau = w_prime_joules / power_deficit
                # Exponential recovery: W'bal approaches W' with time constant tau
                # dW'bal = (W' - W'bal) * (1 - e^(-dt/tau))
                recovery = (w_prime_joules - wbal) * (1 - math.exp(-dt / tau))
                wbal = min(w_prime_joules, wbal + recovery)
        # At exactly CP: no change

        series.append(round(wbal))

        if wbal < min_wbal:
            min_wbal = wbal
            min_wbal_index = i

    min_wbal_pct = round((min_wbal / w_prime_joules) * 100, 1) if w_prime_joules > 0 else None

    return {
        "series": series,
        "min_wbal": round(min_wbal),
        "min_wbal_index": min_wbal_index,
        "min_wbal_pct": min_wbal_pct,
    }


def estimate_w_prime(
    peak_powers: dict[int, int],
    cp_watts: int,
) -> int | None:
    """
    Estimate W' from peak power data using the 2-parameter CP model.

    W' = (P - CP) * t for efforts above CP.
    Uses the 1-minute and 5-minute peak powers to estimate.

    Args:
        peak_powers: Dict mapping duration_seconds to peak watts
        cp_watts: Critical Power in watts

    Returns:
        Estimated W' in joules, or None if insufficient data
    """
    # Need at least the 1-minute peak above CP
    p1 = peak_powers.get(60)  # 1 minute
    p5 = peak_powers.get(300)  # 5 minutes

    if p1 is None or p1 <= cp_watts:
        return None

    # Simple estimate: W' = (P1 - CP) * 60
    # This assumes the 1-minute effort fully depleted W'
    w_prime = (p1 - cp_watts) * 60

    # If we have 5-minute data, use it for a better estimate
    if p5 is not None and p5 > cp_watts:
        w_prime_5 = (p5 - cp_watts) * 300
        # Average the two estimates
        w_prime = (w_prime + w_prime_5) // 2

    return max(5000, min(w_prime, 50000))  # Clamp to realistic range (5-50 kJ)



def predict_wbal_for_plan(
    powers: np.ndarray,
    times: np.ndarray,
    cp: float,
    w_prime: float,
    method: str = "differential",
    distances: np.ndarray | None = None,
    deficit_threshold: float = 0.0,
) -> WbalPrediction:
    """
    Predict W'bal trajectory for a power plan.

    Uses existing W'bal calculation but runs forward prediction
    instead of analyzing recorded data.

    Args:
        powers: Array of power values in watts for each segment
        times: Array of time durations in seconds for each segment
        cp: Critical Power in watts
        w_prime: W' (anaerobic work capacity) in joules
        method: Calculation method - 'differential' (default) or 'integral'
        distances: Optional array of distances in meters for each segment
        deficit_threshold: W'bal threshold for counting time in deficit (default 0)

    Returns:
        WbalPrediction with trajectory and summary statistics

    Per #530: Use differential model for optimizer (faster to compute).
    """
    if len(powers) == 0 or len(times) == 0:
        return WbalPrediction(
            wbal_series=np.array([]),
            min_wbal=w_prime,
            min_wbal_distance_m=0.0,
            time_in_deficit=0.0,
            final_wbal=w_prime,
        )

    if len(powers) != len(times):
        raise ValueError("powers and times arrays must have same length")

    # Expand segments into per-second power array for compute_wbal_series
    # Each segment's power is held constant for its duration
    power_series: list[float] = []
    distance_at_second: list[float] = []
    cumulative_distance = 0.0

    for i, (power, duration) in enumerate(zip(powers, times, strict=True)):
        duration_int = max(1, int(round(duration)))
        power_series.extend([float(power)] * duration_int)

        # Track distance at each second
        if distances is not None and i < len(distances):
            segment_distance = float(distances[i])
            distance_per_second = segment_distance / duration_int if duration_int > 0 else 0
            for _ in range(duration_int):
                cumulative_distance += distance_per_second
                distance_at_second.append(cumulative_distance)
        else:
            # No distance info - use time as proxy
            for _ in range(duration_int):
                cumulative_distance += 1.0  # 1 meter per second placeholder
                distance_at_second.append(cumulative_distance)

    # Use existing compute_wbal_series with differential method
    # Note: method parameter reserved for future integral implementation
    result = compute_wbal_series(
        power_array=power_series,
        cp_watts=int(cp),
        w_prime_joules=int(w_prime),
        sample_rate_hz=1.0,
    )

    if not result["series"]:
        return WbalPrediction(
            wbal_series=np.array([]),
            min_wbal=w_prime,
            min_wbal_distance_m=0.0,
            time_in_deficit=0.0,
            final_wbal=w_prime,
        )

    wbal_series = np.array(result["series"], dtype=float)

    # Find minimum and its location
    min_idx = int(result["min_wbal_index"]) if result["min_wbal_index"] is not None else 0
    min_wbal = float(result["min_wbal"]) if result["min_wbal"] is not None else w_prime
    min_wbal_distance = distance_at_second[min_idx] if min_idx < len(distance_at_second) else 0.0

    # Calculate time in deficit (seconds where W'bal < threshold)
    time_in_deficit = float(np.sum(wbal_series < deficit_threshold))

    final_wbal = float(wbal_series[-1]) if len(wbal_series) > 0 else w_prime

    return WbalPrediction(
        wbal_series=wbal_series,
        min_wbal=min_wbal,
        min_wbal_distance_m=min_wbal_distance,
        time_in_deficit=time_in_deficit,
        final_wbal=final_wbal,
    )




def check_wbal_feasibility(
    powers: np.ndarray,
    times: np.ndarray,
    cp: float,
    w_prime: float,
    min_wbal_threshold: float = 0.0,
) -> tuple[bool, float]:
    """
    Check if power plan is feasible (W'bal stays above threshold).

    Args:
        powers: Array of power values in watts for each segment
        times: Array of time durations in seconds for each segment
        cp: Critical Power in watts
        w_prime: W' (anaerobic work capacity) in joules
        min_wbal_threshold: Minimum acceptable W'bal (default 0)

    Returns:
        Tuple of (is_feasible, min_wbal_reached)
        - is_feasible: True if W'bal never drops below threshold
        - min_wbal_reached: The minimum W'bal value during the plan
    """
    prediction = predict_wbal_for_plan(powers, times, cp, w_prime)
    return prediction.min_wbal >= min_wbal_threshold, prediction.min_wbal
