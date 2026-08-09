"""
Pure computation functions for training metrics.

These functions have no database dependencies and are designed for unit testing.
"""

from collections.abc import Sequence


def compute_normalized_power(
    power_array: Sequence[float | int | None],
    sample_rate_hz: float = 1.0,
) -> float | None:
    """
    Compute Normalized Power (NP) from a power array.

    Algorithm:
    1. Calculate 30-second rolling average of power
    2. Raise each average to the 4th power
    3. Take the average of these values
    4. Take the 4th root

    Args:
        power_array: Array of power values in watts (can contain None for missing data)
        sample_rate_hz: Sample rate in Hz (samples per second), default 1.0

    Returns:
        Normalized Power in watts, or None if insufficient data
    """
    if not power_array:
        return None

    # Filter out None values and convert to floats
    valid_power = [float(p) for p in power_array if p is not None and p >= 0]

    if len(valid_power) < 30:
        # Not enough data for 30s rolling average, return average power
        return sum(valid_power) / len(valid_power) if valid_power else None

    # Calculate window size for 30 seconds
    window_size = max(1, int(30 * sample_rate_hz))

    if len(valid_power) < window_size:
        return sum(valid_power) / len(valid_power)

    # Calculate 30-second rolling averages
    rolling_avgs = []
    for i in range(len(valid_power) - window_size + 1):
        window = valid_power[i : i + window_size]
        avg = sum(window) / len(window)
        rolling_avgs.append(avg)

    if not rolling_avgs:
        return None

    # Raise to 4th power, average, then 4th root
    fourth_powers = [avg**4 for avg in rolling_avgs]
    avg_fourth_power = sum(fourth_powers) / len(fourth_powers)
    np_watts = avg_fourth_power**0.25

    return round(np_watts, 1)


def compute_intensity_factor(np_watts: float, ftp_watts: int) -> float | None:
    """
    Compute Intensity Factor (IF) = NP / FTP.

    Args:
        np_watts: Normalized Power in watts
        ftp_watts: Functional Threshold Power in watts

    Returns:
        Intensity Factor as a decimal (e.g., 0.85), or None if FTP is 0
    """
    if ftp_watts <= 0:
        return None

    return round(np_watts / ftp_watts, 3)


def compute_tss(
    duration_seconds: int,
    np_watts: float,
    intensity_factor: float,
    ftp_watts: int,
) -> float | None:
    """
    Compute Training Stress Score (TSS).

    Formula: TSS = (duration_s × NP × IF) / (FTP × 3600) × 100

    Args:
        duration_seconds: Total duration in seconds
        np_watts: Normalized Power in watts
        intensity_factor: Intensity Factor (NP / FTP)
        ftp_watts: Functional Threshold Power in watts

    Returns:
        TSS value, or None if invalid inputs
    """
    if ftp_watts <= 0 or duration_seconds <= 0:
        return None

    tss = (duration_seconds * np_watts * intensity_factor) / (ftp_watts * 3600) * 100
    return round(tss, 1)


def compute_zone_times(
    values_array: Sequence[float | int | None],
    zones: list[dict],
    sample_rate_hz: float = 1.0,
    value_key_min: str = "min_watts",
    value_key_max: str = "max_watts",
) -> dict[int, int]:
    """
    Compute time spent in each zone.

    Args:
        values_array: Array of values (power or HR)
        zones: List of zone dicts with zone_number, min value, max value
        sample_rate_hz: Sample rate in Hz (samples per second)
        value_key_min: Key for minimum value in zone dict (e.g., "min_watts" or "min_bpm")
        value_key_max: Key for maximum value in zone dict (e.g., "max_watts" or "max_bpm")

    Returns:
        Dict mapping zone_number to seconds spent in that zone
    """
    if not values_array or not zones:
        return {}

    # Initialize counts for each zone
    zone_counts = {z["zone_number"]: 0 for z in zones}

    # Sort zones by min value for efficient lookup
    sorted_zones = sorted(zones, key=lambda z: z[value_key_min])

    seconds_per_sample = 1.0 / sample_rate_hz

    for value in values_array:
        if value is None or value < 0:
            continue

        value = float(value)

        # Find which zone this value belongs to
        for zone in sorted_zones:
            zone_min = zone[value_key_min]
            zone_max = zone.get(value_key_max)  # May be None for top zone

            if value >= zone_min:
                if zone_max is None or value < zone_max:
                    zone_counts[zone["zone_number"]] += seconds_per_sample
                    break
        else:
            # Value is above all zones, count in highest zone
            if sorted_zones:
                highest_zone = sorted_zones[-1]
                zone_counts[highest_zone["zone_number"]] += seconds_per_sample

    # Round to integers
    return {k: int(round(v)) for k, v in zone_counts.items()}


def compute_average_power(
    power_array: Sequence[float | int | None],
) -> float | None:
    """
    Compute simple average power.

    Args:
        power_array: Array of power values in watts

    Returns:
        Average power in watts, or None if no valid data
    """
    valid_power = [float(p) for p in power_array if p is not None and p >= 0]

    if not valid_power:
        return None

    return round(sum(valid_power) / len(valid_power), 1)


def compute_max_power(
    power_array: Sequence[float | int | None],
) -> int | None:
    """
    Compute maximum power.

    Args:
        power_array: Array of power values in watts

    Returns:
        Maximum power in watts, or None if no valid data
    """
    valid_power = [int(p) for p in power_array if p is not None and p >= 0]

    if not valid_power:
        return None

    return max(valid_power)
