"""
Pure computation functions for activity calories.

These functions have no database dependencies and are designed for unit testing.

Energy conversion: For cycling, mechanical work (kJ) ≈ metabolic energy (kcal)
because typical cycling efficiency is ~24% and 1 kcal = 4.184 kJ:
    kJ_work / (4.184 × 0.24) ≈ kJ_work × 0.995 ≈ kJ_work

This is a standard approximation used by power-based training platforms.
"""

from datetime import datetime

# Maximum interval between records before we consider it a gap (seconds).
# Matches the convention in ingest._compute_moving_time.
MAX_RECORD_INTERVAL_S = 30


def compute_calories_from_power(records: list[dict]) -> int | None:
    """
    Compute calories from power records using the work integral.

    Integrates power × time over consecutive records:
        work_kJ = Σ (power_w × Δt_s) / 1000
        calories_kcal ≈ work_kJ (standard cycling approximation)

    Records without power contribute nothing but advance the timestamp.
    Gaps > 30 seconds are capped to avoid counting pauses.

    Args:
        records: List of record dicts with 'timestamp' (datetime) and
                 optional 'power_w' (int/float or None).

    Returns:
        Calories as integer, or None if no power data available.
    """
    if len(records) < 2:
        return None

    total_work_joules = 0.0
    has_power = False

    for i in range(1, len(records)):
        curr = records[i]
        prev = records[i - 1]

        # Get power for this interval (use current record's power)
        power_w = curr.get("power_w")
        if power_w is None or power_w < 0:
            continue

        has_power = True

        # Compute time delta
        curr_ts = curr.get("timestamp")
        prev_ts = prev.get("timestamp")

        if curr_ts is None or prev_ts is None:
            # No timestamps, assume 1 second
            delta_s = 1.0
        else:
            try:
                delta_s = (curr_ts - prev_ts).total_seconds()
                # Cap at MAX_RECORD_INTERVAL_S to handle gaps
                delta_s = min(delta_s, MAX_RECORD_INTERVAL_S)
                # Skip negative intervals (out-of-order records)
                if delta_s <= 0:
                    continue
            except (TypeError, AttributeError):
                delta_s = 1.0

        # Accumulate work: W = P × t (joules)
        total_work_joules += power_w * delta_s

    if not has_power:
        return None

    # Convert joules to kJ, then kJ ≈ kcal
    work_kj = total_work_joules / 1000.0
    return int(round(work_kj))


def resolve_calories(
    session_calories: int | None,
    records: list[dict],
) -> tuple[int | None, str | None]:
    """
    Resolve final calorie value and provenance.

    Device-reported calories (from FIT session message) take precedence.
    If not available, compute from power records.

    Args:
        session_calories: total_calories from FIT session message, or None.
        records: List of record dicts for power-based computation.

    Returns:
        Tuple of (calories, source) where:
        - calories: int value or None if unavailable
        - source: 'device' | 'computed_power' | None
    """
    # Device value takes precedence
    if session_calories is not None and session_calories > 0:
        return session_calories, "device"

    # Fall back to power computation
    computed = compute_calories_from_power(records)
    if computed is not None:
        return computed, "computed_power"

    return None, None
