"""
Performance Management Chart (PMC) computation.

Computes daily training load metrics:
- CTL (Chronic Training Load): 42-day EWMA of daily TSS
- ATL (Acute Training Load): 7-day EWMA of daily TSS  
- TSB (Training Stress Balance): CTL - ATL (form indicator)
"""

from datetime import date, timedelta
from typing import Sequence


# Standard time constants for PMC
CTL_TIME_CONSTANT = 42  # days (chronic/fitness)
ATL_TIME_CONSTANT = 7   # days (acute/fatigue)


def compute_ewma_factor(time_constant: int) -> float:
    """
    Compute the EWMA decay factor for a given time constant.
    
    factor = exp(-1/tc) ≈ 1 - 1/tc for typical tc values
    """
    return 1.0 - (1.0 / time_constant)


def compute_pmc(
    daily_tss: dict[date, float],
    start_date: date,
    end_date: date,
    initial_ctl: float = 0.0,
    initial_atl: float = 0.0,
) -> list[dict]:
    """
    Compute PMC values for a date range.
    
    Args:
        daily_tss: Dict mapping dates to TSS values
        start_date: First date to include in results
        end_date: Last date to include in results
        initial_ctl: Starting CTL value (for warmup)
        initial_atl: Starting ATL value (for warmup)
    
    Returns:
        List of dicts with date, ctl, atl, tsb for each day
    """
    # EWMA factors
    ctl_factor = compute_ewma_factor(CTL_TIME_CONSTANT)
    atl_factor = compute_ewma_factor(ATL_TIME_CONSTANT)
    
    # We need to compute EWMA from the earliest data point
    # to properly warm up the averages
    all_dates = set(daily_tss.keys())
    if all_dates:
        warmup_start = min(min(all_dates), start_date - timedelta(days=CTL_TIME_CONSTANT))
    else:
        warmup_start = start_date - timedelta(days=CTL_TIME_CONSTANT)
    
    # Initialize
    ctl = initial_ctl
    atl = initial_atl
    
    results = []
    current_date = warmup_start
    
    while current_date <= end_date:
        # Get TSS for this day (0 if no activity)
        tss = daily_tss.get(current_date, 0.0)
        
        # Update EWMA values
        # EWMA_new = EWMA_old * factor + value * (1 - factor)
        ctl = ctl * ctl_factor + tss * (1 - ctl_factor)
        atl = atl * atl_factor + tss * (1 - atl_factor)
        
        # TSB (form) = fitness - fatigue
        tsb = ctl - atl
        
        # Only include in results if within requested range
        if current_date >= start_date:
            results.append({
                "date": current_date.isoformat(),
                "ctl": round(ctl, 1),
                "atl": round(atl, 1),
                "tsb": round(tsb, 1),
            })
        
        current_date += timedelta(days=1)
    
    return results


def aggregate_daily_tss(
    activities: Sequence[dict],
) -> dict[date, float]:
    """
    Aggregate TSS by date from a list of activities.
    
    Args:
        activities: List of dicts with 'started_at' (date or datetime) and 'tss' (float or None)
    
    Returns:
        Dict mapping dates to total TSS for that day
    """
    daily_tss: dict[date, float] = {}
    
    for activity in activities:
        started_at = activity.get("started_at")
        tss = activity.get("tss")
        
        if started_at is None or tss is None:
            continue
        
        # Handle both date and datetime
        if hasattr(started_at, "date"):
            activity_date = started_at.date()
        else:
            activity_date = started_at
        
        if activity_date not in daily_tss:
            daily_tss[activity_date] = 0.0
        daily_tss[activity_date] += tss
    
    return daily_tss
