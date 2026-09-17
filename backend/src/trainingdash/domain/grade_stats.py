"""Shared grade statistics.

Max grade over sliding distance windows. Used by activity ingest
(_compute_extended_metrics); segment geometry adopts it in a follow-up so
the "Max Grade" shown for a segment will match its source activity.

A raw record-to-record grade is dominated by altitude noise (a 0.5m barometric
wobble over 2m of distance reads as 25%). Windows of ~200m suppress that noise
while still catching real steep pitches.
"""

from __future__ import annotations

MIN_RECORDS = 10


def compute_max_grade_pct(
    records: list[tuple[float, float]],
    window_m: float = 200.0,
) -> float | None:
    """
    Compute the steepest grade over sliding distance windows.

    Args:
        records: (distance_m, altitude_m) pairs, ascending by distance.
            None altitudes must be filtered out by the caller.
        window_m: Minimum distance span for each grade window.

    Returns:
        The maximum grade in percent over all windows, or None if there are
        too few records (at most MIN_RECORDS) or no window spans window_m.
        Negative grades never count; a route with no climbing returns None.
    """
    if len(records) <= MIN_RECORDS:
        return None

    max_grade = 0.0
    i = 0
    while i < len(records):
        start_dist, start_alt = records[i]
        # Find end of window
        j = i + 1
        while j < len(records):
            end_dist, end_alt = records[j]
            dist_diff = end_dist - start_dist
            if dist_diff >= window_m:
                if dist_diff > 0:
                    grade = ((end_alt - start_alt) / dist_diff) * 100
                    if grade > max_grade:
                        max_grade = grade
                break
            j += 1
        i += 1

    if max_grade > 0:
        return max_grade
    return None