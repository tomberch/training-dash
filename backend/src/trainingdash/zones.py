"""Zone computation utilities.

Computes power and HR zones on-the-fly from threshold values and optional
custom percentages. No zone tables needed - zones are derived from FTP/LTHR.
"""

from typing import Any

# Coggan 7-zone power percentages (min%, max%) of FTP
DEFAULT_POWER_ZONES: dict[int, tuple[int, int | None]] = {
    1: (0, 55),
    2: (56, 75),
    3: (76, 90),
    4: (91, 105),
    5: (106, 120),
    6: (121, 150),
    7: (151, None),
}

# 5-zone HR percentages (min%, max%) of LTHR
DEFAULT_HR_ZONES: dict[int, tuple[int, int | None]] = {
    1: (0, 81),
    2: (81, 90),
    3: (90, 94),
    4: (94, 100),
    5: (100, None),
}

POWER_ZONE_NAMES: dict[int, str] = {
    1: "Active Recovery",
    2: "Endurance",
    3: "Tempo",
    4: "Threshold",
    5: "VO2max",
    6: "Anaerobic",
    7: "Neuromuscular",
}

HR_ZONE_NAMES: dict[int, str] = {
    1: "Recovery",
    2: "Aerobic",
    3: "Tempo",
    4: "Threshold",
    5: "Anaerobic",
}


def _parse_custom_pct(custom_pct: dict[str, Any] | None) -> dict[int, tuple[int, int | None]] | None:
    """Parse custom percentages from JSON format to internal format.
    
    JSON format: {"1": [0, 55], "2": [56, 75], ...}
    Internal format: {1: (0, 55), 2: (56, 75), ...}
    """
    if not custom_pct:
        return None
    try:
        return {
            int(k): (v[0], v[1] if v[1] is not None else None)
            for k, v in custom_pct.items()
        }
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def compute_power_zones(ftp: int, custom_pct: dict[str, Any] | None = None) -> list[dict]:
    """Compute power zones from FTP and optional custom percentages.
    
    Args:
        ftp: Functional Threshold Power in watts
        custom_pct: Optional custom zone percentages as JSON dict
        
    Returns:
        List of zone dicts with zone, name, min_watts, max_watts
    """
    pct = _parse_custom_pct(custom_pct) or DEFAULT_POWER_ZONES
    zones = []
    for zone_num in sorted(pct.keys()):
        min_pct, max_pct = pct[zone_num]
        zones.append({
            "zone": zone_num,
            "name": POWER_ZONE_NAMES.get(zone_num, f"Zone {zone_num}"),
            "min_watts": int(ftp * min_pct / 100),
            "max_watts": int(ftp * max_pct / 100) if max_pct else None,
        })
    return zones


def compute_hr_zones(lthr: int, custom_pct: dict[str, Any] | None = None) -> list[dict]:
    """Compute HR zones from LTHR and optional custom percentages.
    
    Args:
        lthr: Lactate Threshold Heart Rate in bpm
        custom_pct: Optional custom zone percentages as JSON dict
        
    Returns:
        List of zone dicts with zone, name, min_bpm, max_bpm
    """
    pct = _parse_custom_pct(custom_pct) or DEFAULT_HR_ZONES
    zones = []
    for zone_num in sorted(pct.keys()):
        min_pct, max_pct = pct[zone_num]
        zones.append({
            "zone": zone_num,
            "name": HR_ZONE_NAMES.get(zone_num, f"Zone {zone_num}"),
            "min_bpm": int(lthr * min_pct / 100),
            "max_bpm": int(lthr * max_pct / 100) if max_pct else None,
        })
    return zones


def get_zone_for_power(watts: int, ftp: int, custom_pct: dict[str, Any] | None = None) -> int:
    """Return zone number (1-7) for a given power value.
    
    Args:
        watts: Power value in watts
        ftp: Functional Threshold Power in watts
        custom_pct: Optional custom zone percentages
        
    Returns:
        Zone number (1-7)
    """
    if watts <= 0 or ftp <= 0:
        return 1
    
    pct = _parse_custom_pct(custom_pct) or DEFAULT_POWER_ZONES
    pct_of_ftp = (watts / ftp) * 100
    
    # Find the highest zone where power >= min threshold
    zone = 1
    for zone_num in sorted(pct.keys()):
        min_pct, max_pct = pct[zone_num]
        if pct_of_ftp >= min_pct:
            zone = zone_num
        else:
            break
    return zone


def get_zone_for_hr(hr: int, lthr: int, custom_pct: dict[str, Any] | None = None) -> int:
    """Return zone number (1-5) for a given heart rate value.
    
    Args:
        hr: Heart rate in bpm
        lthr: Lactate Threshold Heart Rate in bpm
        custom_pct: Optional custom zone percentages
        
    Returns:
        Zone number (1-5)
    """
    if hr <= 0 or lthr <= 0:
        return 1
    
    pct = _parse_custom_pct(custom_pct) or DEFAULT_HR_ZONES
    pct_of_lthr = (hr / lthr) * 100
    
    # Find the highest zone where HR >= min threshold
    zone = 1
    for zone_num in sorted(pct.keys()):
        min_pct, max_pct = pct[zone_num]
        if pct_of_lthr >= min_pct:
            zone = zone_num
        else:
            break
    return zone


def compute_zone_times(
    power_data: list[int | None],
    ftp: int | None,
    hr_data: list[int | None] | None = None,
    lthr: int | None = None,
    power_zone_pct: dict[str, Any] | None = None,
    hr_zone_pct: dict[str, Any] | None = None,
) -> tuple[dict[int, int] | None, dict[int, int] | None]:
    """Compute time spent in each zone from second-by-second data.
    
    Args:
        power_data: List of power values (1 per second), None for missing
        ftp: Functional Threshold Power (None = skip power zones)
        hr_data: Optional list of HR values (1 per second)
        lthr: Lactate Threshold HR (None = skip HR zones)
        power_zone_pct: Optional custom power zone percentages
        hr_zone_pct: Optional custom HR zone percentages
        
    Returns:
        Tuple of (power_zone_times, hr_zone_times) dicts mapping zone -> seconds
    """
    power_zone_times: dict[int, int] | None = None
    hr_zone_times: dict[int, int] | None = None
    
    if ftp and ftp > 0:
        power_zone_times = {z: 0 for z in range(1, 8)}
        for watts in power_data:
            if watts is not None and watts > 0:
                zone = get_zone_for_power(watts, ftp, power_zone_pct)
                power_zone_times[zone] += 1
    
    if hr_data and lthr and lthr > 0:
        hr_zone_times = {z: 0 for z in range(1, 6)}
        for hr in hr_data:
            if hr is not None and hr > 0:
                zone = get_zone_for_hr(hr, lthr, hr_zone_pct)
                hr_zone_times[zone] += 1
    
    return power_zone_times, hr_zone_times
