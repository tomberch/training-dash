"""Historical NP stats domain types.

Pure domain types for historical ride NP statistics.
Repository implementations handle the actual data fetching.
"""

from dataclasses import dataclass


@dataclass
class HistoricalNpStats:
    """NP statistics from historical rides on a matched route."""

    ride_count: int
    avg_np_w: float
    min_np_w: float
    best_np_w: float  # Renamed from max_np_w per spec
    avg_power_w: float  # Average of avg_power across rides
