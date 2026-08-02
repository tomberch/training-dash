"""
Peak power extraction for power curve analysis.

Extracts best average power at standard durations for creating power curves
and tracking personal records.
"""

from typing import Sequence
from collections import deque


# Standard durations for power curve analysis (in seconds)
PEAK_DURATIONS = [
    1,      # 1 second (peak power)
    5,      # 5 seconds (neuromuscular)
    10,     # 10 seconds
    30,     # 30 seconds (anaerobic)
    60,     # 1 minute
    120,    # 2 minutes
    300,    # 5 minutes (VO2max)
    600,    # 10 minutes
    1200,   # 20 minutes (FTP proxy)
    1800,   # 30 minutes
    3600,   # 60 minutes (hour power)
    5400,   # 90 minutes
    7200,   # 120 minutes
    18000,  # 300 minutes (5 hours)
]


def extract_peak_powers(
    power_array: Sequence[float | int | None],
    sample_rate_hz: float = 1.0,
    durations: list[int] | None = None,
) -> dict[int, int | None]:
    """
    Extract best average power at each standard duration.
    
    Uses an efficient rolling-window algorithm that processes all durations
    in a single pass through the data.
    
    Args:
        power_array: Array of power values in watts (None values treated as 0)
        sample_rate_hz: Sample rate in Hz (samples per second), default 1.0
        durations: Optional list of durations in seconds (default: PEAK_DURATIONS)
    
    Returns:
        Dict mapping duration_seconds to best average watts (or None if ride too short)
    """
    if not power_array:
        return {}
    
    if durations is None:
        durations = PEAK_DURATIONS
    
    # Convert None values to 0 and ensure floats
    clean_power = [float(p) if p is not None and p >= 0 else 0.0 for p in power_array]
    
    total_samples = len(clean_power)
    total_duration_s = total_samples / sample_rate_hz
    
    results = {}
    
    for duration_s in durations:
        # Calculate window size in samples
        window_samples = int(duration_s * sample_rate_hz)
        
        if window_samples > total_samples:
            # Ride is shorter than this duration
            results[duration_s] = None
            continue
        
        if window_samples <= 0:
            results[duration_s] = None
            continue
        
        # Use rolling sum for efficiency
        best_avg = _find_best_average(clean_power, window_samples)
        results[duration_s] = int(round(best_avg)) if best_avg is not None else None
    
    return results


def _find_best_average(data: list[float], window_size: int) -> float | None:
    """
    Find the best (maximum) average over a sliding window.
    
    Uses O(n) algorithm with running sum.
    """
    if not data or window_size <= 0 or window_size > len(data):
        return None
    
    # Calculate initial window sum
    window_sum = sum(data[:window_size])
    best_sum = window_sum
    
    # Slide the window
    for i in range(window_size, len(data)):
        # Remove element leaving window, add element entering
        window_sum = window_sum - data[i - window_size] + data[i]
        if window_sum > best_sum:
            best_sum = window_sum
    
    return best_sum / window_size


def extract_peak_power_with_index(
    power_array: Sequence[float | int | None],
    duration_seconds: int,
    sample_rate_hz: float = 1.0,
) -> tuple[int | None, int | None]:
    """
    Extract best average power for a single duration, with the starting index.
    
    Args:
        power_array: Array of power values in watts
        duration_seconds: Duration to find best average for
        sample_rate_hz: Sample rate in Hz
    
    Returns:
        Tuple of (best_avg_watts, start_index) or (None, None) if ride too short
    """
    if not power_array:
        return None, None
    
    clean_power = [float(p) if p is not None and p >= 0 else 0.0 for p in power_array]
    window_size = int(duration_seconds * sample_rate_hz)
    
    if window_size <= 0 or window_size > len(clean_power):
        return None, None
    
    # Calculate initial window sum
    window_sum = sum(clean_power[:window_size])
    best_sum = window_sum
    best_start = 0
    
    # Slide the window
    for i in range(window_size, len(clean_power)):
        window_sum = window_sum - clean_power[i - window_size] + clean_power[i]
        if window_sum > best_sum:
            best_sum = window_sum
            best_start = i - window_size + 1
    
    return int(round(best_sum / window_size)), best_start


def compute_power_curve(
    power_array: Sequence[float | int | None],
    sample_rate_hz: float = 1.0,
    max_duration_s: int | None = None,
) -> dict[int, int]:
    """
    Compute a full power curve (best power for every duration from 1s to max).
    
    This is more expensive but gives a complete picture for visualization.
    
    Args:
        power_array: Array of power values in watts
        sample_rate_hz: Sample rate in Hz
        max_duration_s: Maximum duration to compute (default: ride length)
    
    Returns:
        Dict mapping each duration_seconds to best average watts
    """
    if not power_array:
        return {}
    
    clean_power = [float(p) if p is not None and p >= 0 else 0.0 for p in power_array]
    total_samples = len(clean_power)
    
    if max_duration_s is None:
        max_duration_s = int(total_samples / sample_rate_hz)
    
    results = {}
    
    # For efficiency, only compute key durations for longer intervals
    # Full second-by-second for short durations, then sparse for long
    
    # 1-60s: every second
    for duration_s in range(1, min(61, max_duration_s + 1)):
        window_size = int(duration_s * sample_rate_hz)
        if window_size <= total_samples:
            best = _find_best_average(clean_power, window_size)
            if best is not None:
                results[duration_s] = int(round(best))
    
    # 60s+: every 30 seconds
    for duration_s in range(90, min(max_duration_s + 1, 3601), 30):
        window_size = int(duration_s * sample_rate_hz)
        if window_size <= total_samples:
            best = _find_best_average(clean_power, window_size)
            if best is not None:
                results[duration_s] = int(round(best))
    
    # 1h+: every 5 minutes
    for duration_s in range(3600, max_duration_s + 1, 300):
        window_size = int(duration_s * sample_rate_hz)
        if window_size <= total_samples:
            best = _find_best_average(clean_power, window_size)
            if best is not None:
                results[duration_s] = int(round(best))
    
    return results
