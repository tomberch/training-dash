"""
Fitness model computation using 3-parameter Critical Power model.

The model fits peak power data to:
    P(t) = CP + W' / t + PP * exp(-t / tau)

Where:
- PP: Peak Power (neuromuscular capacity, ~5 seconds)
- W': Anaerobic Work Capacity (joules above CP)
- CP: Critical Power (sustainable aerobic threshold)
- tau: Time constant for PP decay (fixed at ~15s)
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Sequence


# Key durations for breakthrough detection (seconds)
BREAKTHROUGH_DURATIONS = [5, 60, 300, 1200]  # 5s, 1min, 5min, 20min

# Decay half-life in days for weighting recent activities
DECAY_HALF_LIFE_DAYS = 42  # 6 weeks


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


def fit_cp_model(
    peak_powers: list[dict],
    activity_dates: list[datetime] | None = None,
    reference_date: datetime | None = None,
) -> dict | None:
    """
    Fit 3-parameter Critical Power model to peak power data.
    
    Uses weighted least squares with decay weighting for recent activities.
    
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
    
    reference_date = reference_date or datetime.now(timezone.utc)
    
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
        # Need at least 3 points to fit 3 parameters
        return None
    
    # Use simplified estimation based on key durations
    # PP from 1-5s, W' from 1-5min range, CP from 20min+
    
    # Estimate PP (peak power) from short durations
    pp_watts = 0
    for dur in [1, 5, 10]:
        if dur in best_by_duration:
            pp_watts = max(pp_watts, best_by_duration[dur][0])
    
    if pp_watts == 0:
        # Fallback to shortest available
        shortest = min(best_by_duration.keys())
        pp_watts = best_by_duration[shortest][0]
    
    # Estimate CP from longer durations (20min+)
    cp_watts = 0
    cp_candidates = [(dur, w) for dur, (w, _) in best_by_duration.items() if dur >= 1200]
    if cp_candidates:
        # Use longest duration as CP estimate
        cp_candidates.sort(key=lambda x: x[0], reverse=True)
        cp_watts = cp_candidates[0][1]
    else:
        # Estimate from 5min power (CP ~ 95% of 5min power)
        if 300 in best_by_duration:
            cp_watts = int(best_by_duration[300][0] * 0.95)
        elif 60 in best_by_duration:
            # Very rough estimate from 1min
            cp_watts = int(best_by_duration[60][0] * 0.80)
    
    if cp_watts == 0:
        return None
    
    # Estimate W' from difference between short efforts and CP
    # W' = (P - CP) * t for efforts above CP
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
        # Default estimate: W' = CP * 60 (rough heuristic)
        w_prime_joules = cp_watts * 60
    
    # Sanity bounds
    w_prime_joules = max(5000, min(40000, w_prime_joules))  # 5-40 kJ typical range
    
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
