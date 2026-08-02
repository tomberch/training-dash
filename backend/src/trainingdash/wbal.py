"""
W'bal (W-prime balance) computation using the Skiba differential method.

W'bal tracks the depletion and recovery of anaerobic work capacity (W') during exercise.
"""

from typing import Sequence
import math


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
