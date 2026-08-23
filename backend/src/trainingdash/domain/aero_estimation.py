"""Wind-corrected CdA/Crr estimation from activity data.

This module extends the physics-based calibration approach with wind correction
using weather data. The key improvements over basic regression:

1. Uses apparent wind speed (ground speed + headwind component) for aero term
2. Uses hybrid air density: FIT temperature + weather API pressure
3. Calculates rider heading from GPS track for wind angle computation

The wind-corrected power equation:
    P = P_gravity + P_rolling + P_aero

Where:
    P_gravity = m × g × v × sin(θ)
    P_rolling = Crr × m × g × v × cos(θ)
    P_aero = 0.5 × ρ × CdA × v_apparent³

    v_apparent = v_ground + v_headwind
    v_headwind = wind_speed × cos(wind_direction - rider_heading)

References:
- Martin JC et al. (1998) cycling power equation
- Chung method for virtual elevation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import least_squares

if TYPE_CHECKING:
    from collections.abc import Sequence


class WeatherStatus(StrEnum):
    """Status of weather data fetch for an activity."""

    PENDING = "pending"  # Eligible for weather fetch, awaiting processing
    FETCHED = "fetched"  # Weather data successfully retrieved
    FAILED = "failed"  # Weather fetch attempted but failed
    NOT_APPLICABLE = "not_applicable"  # Activity not eligible (indoor, no GPS, etc.)


# Physical constants
GRAVITY = 9.80665  # m/s²
SEA_LEVEL_PRESSURE = 1013.25  # hPa
DEFAULT_EFFICIENCY = 0.97

# Minimum requirements for estimation
MIN_DURATION_MINUTES = 20
MIN_GPS_COVERAGE_PCT = 50
MIN_POWER_COVERAGE_PCT = 50
MIN_GRADE_RANGE_PCT = 2


@dataclass(frozen=True, slots=True)
class WindCorrectedDataPoint:
    """A single data point for wind-corrected calibration.

    Attributes:
        grade_pct: Road gradient as percentage (positive = uphill).
        power_w: Power in watts.
        ground_speed_mps: Ground speed in m/s.
        apparent_speed_mps: Apparent wind speed (ground + headwind) in m/s.
        air_density: Air density in kg/m³.
        duration_s: Duration of segment in seconds (for weighting).
    """

    grade_pct: float
    power_w: float
    ground_speed_mps: float
    apparent_speed_mps: float
    air_density: float
    duration_s: float = 1.0


@dataclass(frozen=True, slots=True)
class DataQuality:
    """Quality metrics from data preparation.

    Attributes:
        weather_coverage_pct: Percentage of data points with weather data (0-100).
        gps_coverage_pct: Percentage of records with valid GPS (0-100).
        power_coverage_pct: Percentage of records with valid power (0-100).
    """

    weather_coverage_pct: float
    gps_coverage_pct: float
    power_coverage_pct: float


@dataclass(frozen=True, slots=True)
class AeroEstimationResult:
    """Result of wind-corrected CdA/Crr estimation.

    Attributes:
        cda: Estimated CdA in m².
        crr: Estimated rolling resistance coefficient.
        confidence: Confidence score 0.0-1.0.
        rms_error_pct: Root mean square error as percentage.
        n_data_points: Number of data points used.
        grade_range: Tuple of (min_grade, max_grade) in the data.
        avg_wind_speed_mps: Average wind speed during activity.
        warnings: List of warning messages.
    """

    cda: float
    crr: float
    confidence: float
    rms_error_pct: float
    n_data_points: int
    grade_range: tuple[float, float]
    avg_wind_speed_mps: float
    warnings: list[str]


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    """Minimal record data needed for aero estimation."""

    timestamp_s: float  # Seconds from activity start
    lat: float | None
    lon: float | None
    power_w: int | None
    speed_mps: float | None
    altitude_m: float | None
    temperature_c: int | None
    grade_pct: float | None  # Pre-computed or from FIT


@dataclass(frozen=True, slots=True)
class WeatherSnapshot:
    """Weather data for a point in time during the activity."""

    hour_offset: int  # Hours from activity start
    wind_speed_mps: float
    wind_direction_deg: float  # Meteorological: direction wind comes FROM
    pressure_hpa: float
    humidity_pct: float
    temperature_c: float


def calculate_air_density(
    temp_c: float,
    pressure_hpa: float,
    humidity_pct: float = 50.0,
) -> float:
    """Calculate air density from temperature, pressure, and humidity.

    Uses the formula for moist air density accounting for water vapor.

    Args:
        temp_c: Temperature in Celsius.
        pressure_hpa: Barometric pressure in hPa (mbar).
        humidity_pct: Relative humidity as percentage (0-100).

    Returns:
        Air density in kg/m³.
    """
    temp_k = temp_c + 273.15
    pressure_pa = pressure_hpa * 100

    # Saturation vapor pressure (Tetens formula)
    e_sat = 6.1078 * (10 ** (7.5 * temp_c / (237.3 + temp_c))) * 100  # Pa

    # Actual vapor pressure
    e_vapor = (humidity_pct / 100.0) * e_sat

    # Dry air partial pressure
    p_dry = pressure_pa - e_vapor

    # Gas constants
    R_dry = 287.05  # J/(kg·K) for dry air
    R_vapor = 461.495  # J/(kg·K) for water vapor

    # Density of moist air
    rho = (p_dry / (R_dry * temp_k)) + (e_vapor / (R_vapor * temp_k))

    return rho


def calculate_rider_heading(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate heading (bearing) between two GPS points.

    Args:
        lat1, lon1: Start point coordinates in degrees.
        lat2, lon2: End point coordinates in degrees.

    Returns:
        Heading in degrees (0-360, 0=North, 90=East).
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlon_rad = math.radians(lon2 - lon1)

    x = math.sin(dlon_rad) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)

    heading_rad = math.atan2(x, y)
    heading_deg = math.degrees(heading_rad)

    # Normalize to 0-360
    return (heading_deg + 360) % 360


def calculate_headwind_component(
    rider_heading_deg: float,
    wind_direction_deg: float,
    wind_speed_mps: float,
) -> float:
    """Calculate the headwind component experienced by the rider.

    Meteorological wind direction is where wind comes FROM.
    Headwind is positive (slows rider), tailwind is negative (helps rider).

    Args:
        rider_heading_deg: Direction rider is traveling (0=N, 90=E).
        wind_direction_deg: Direction wind is coming FROM (meteorological).
        wind_speed_mps: Wind speed in m/s.

    Returns:
        Headwind component in m/s (positive = headwind, negative = tailwind).
    """
    # Convert wind FROM direction to wind TO direction
    wind_to_deg = (wind_direction_deg + 180) % 360

    # Angle between rider direction and wind direction
    angle_diff = math.radians(rider_heading_deg - wind_to_deg)

    # Headwind component: positive when wind opposes rider
    # cos(0) = 1 means pure headwind, cos(180) = -1 means pure tailwind
    headwind = -wind_speed_mps * math.cos(angle_diff)

    return headwind


def calculate_grade_from_altitude(
    altitude: Sequence[float | None],
    distance: Sequence[float],
    smoothing_window: int = 5,
) -> list[float | None]:
    """Calculate grade from altitude and distance arrays.

    Args:
        altitude: Altitude array in meters (may contain None).
        distance: Cumulative distance array in meters.
        smoothing_window: Window size for smoothing (reduces GPS noise).

    Returns:
        Grade array as percentage (positive = uphill).
    """
    n = len(altitude)
    if n < 2:
        return [None] * n

    grades: list[float | None] = [None] * n

    for i in range(1, n):
        if altitude[i] is None or altitude[i - 1] is None:
            continue

        d_dist = distance[i] - distance[i - 1]
        if d_dist < 0.1:  # Less than 10cm, skip
            continue

        d_alt = altitude[i] - altitude[i - 1]
        grade = (d_alt / d_dist) * 100  # As percentage

        # Clamp to reasonable range
        grade = max(-30, min(30, grade))
        grades[i] = grade

    # Apply simple moving average smoothing if requested
    if smoothing_window > 1:
        smoothed: list[float | None] = [None] * n
        half_window = smoothing_window // 2

        for i in range(n):
            window_grades = []
            for j in range(max(0, i - half_window), min(n, i + half_window + 1)):
                if grades[j] is not None:
                    window_grades.append(grades[j])
            if window_grades:
                smoothed[i] = sum(window_grades) / len(window_grades)

        return smoothed

    return grades


def interpolate_weather(
    record_timestamp_s: float,
    weather_snapshots: list[WeatherSnapshot],
) -> WeatherSnapshot | None:
    """Interpolate weather data to a specific timestamp.

    Args:
        record_timestamp_s: Seconds from activity start.
        weather_snapshots: Hourly weather snapshots.

    Returns:
        Interpolated weather snapshot, or None if no data.
    """
    if not weather_snapshots:
        return None

    hour = record_timestamp_s / 3600.0

    # Find surrounding snapshots
    before = None
    after = None

    for snap in sorted(weather_snapshots, key=lambda s: s.hour_offset):
        if snap.hour_offset <= hour:
            before = snap
        elif after is None:
            after = snap
            break

    if before is None and after is None:
        return None

    if before is None:
        return after
    if after is None:
        return before

    # Linear interpolation
    t = (hour - before.hour_offset) / max(1, after.hour_offset - before.hour_offset)

    # Interpolate wind direction carefully (handle 360/0 wraparound)
    dir1 = before.wind_direction_deg
    dir2 = after.wind_direction_deg
    diff = dir2 - dir1
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    interp_dir = (dir1 + t * diff) % 360

    return WeatherSnapshot(
        hour_offset=int(hour),
        wind_speed_mps=before.wind_speed_mps + t * (after.wind_speed_mps - before.wind_speed_mps),
        wind_direction_deg=interp_dir,
        pressure_hpa=before.pressure_hpa + t * (after.pressure_hpa - before.pressure_hpa),
        humidity_pct=before.humidity_pct + t * (after.humidity_pct - before.humidity_pct),
        temperature_c=before.temperature_c + t * (after.temperature_c - before.temperature_c),
    )


def prepare_data_points(
    records: list[ActivityRecord],
    weather_snapshots: list[WeatherSnapshot],
    default_pressure_hpa: float = SEA_LEVEL_PRESSURE,
    default_humidity_pct: float = 50.0,
    min_speed_mps: float = 3.0,
    max_speed_mps: float = 20.0,
    min_power_w: float = 50.0,
    max_power_w: float = 600.0,
) -> tuple[list[WindCorrectedDataPoint], DataQuality, list[str]]:
    """Convert activity records and weather to calibration data points.

    Args:
        records: Activity records with GPS, power, speed, temperature.
        weather_snapshots: Hourly weather data for the activity.
        default_pressure_hpa: Default pressure if no weather data.
        default_humidity_pct: Default humidity if no weather data.

    Returns:
        Tuple of (data_points, data_quality, warnings).
    """
    warnings: list[str] = []
    data_points: list[WindCorrectedDataPoint] = []

    if len(records) < 2:
        warnings.append("Insufficient records for estimation")
        return [], DataQuality(0.0, 0.0, 0.0), warnings

    # Pre-compute grades if not provided
    altitudes = [r.altitude_m for r in records]
    distances = [r.timestamp_s * (r.speed_mps or 0) for r in records]  # Rough distance estimate

    # Better distance calculation using actual distance if available
    cumulative_dist = [0.0]
    for i in range(1, len(records)):
        speed = records[i].speed_mps or 0
        dt = records[i].timestamp_s - records[i - 1].timestamp_s
        cumulative_dist.append(cumulative_dist[-1] + speed * dt)

    grades = calculate_grade_from_altitude(altitudes, cumulative_dist)

    # Track statistics for warnings
    wind_speeds: list[float] = []
    missing_gps = 0
    missing_power = 0
    points_with_weather = 0
    points_without_weather = 0

    for i in range(1, len(records)):
        r = records[i]
        r_prev = records[i - 1]

        # Skip if missing essential data
        if r.power_w is None or r.power_w < min_power_w:
            missing_power += 1
            continue
        if r.power_w > max_power_w:
            continue  # Likely sprint or data error
        if r.speed_mps is None or r.speed_mps < min_speed_mps:
            continue  # Too slow, likely stopped or technical
        if r.speed_mps > max_speed_mps:
            continue  # Descending or data error
        if r.lat is None or r.lon is None or r_prev.lat is None or r_prev.lon is None:
            missing_gps += 1
            continue

        # Get grade (from FIT or computed)
        grade = r.grade_pct if r.grade_pct is not None else grades[i]
        if grade is None:
            continue

        # Filter out extreme grades (likely GPS errors or braking on descents)
        if grade < -8 or grade > 18:
            continue

        # Calculate rider heading
        heading = calculate_rider_heading(r_prev.lat, r_prev.lon, r.lat, r.lon)

        # Get weather for this timestamp
        weather = interpolate_weather(r.timestamp_s, weather_snapshots)

        if weather:
            points_with_weather += 1
            wind_speeds.append(weather.wind_speed_mps)

            # Calculate headwind component
            headwind = calculate_headwind_component(heading, weather.wind_direction_deg, weather.wind_speed_mps)

            # Apparent speed for aero calculation
            apparent_speed = r.speed_mps + headwind

            # Air density: prefer FIT temperature, use weather pressure
            temp_c = float(r.temperature_c) if r.temperature_c is not None else weather.temperature_c
            air_density = calculate_air_density(temp_c, weather.pressure_hpa, weather.humidity_pct)
        else:
            # No weather data - use defaults
            points_without_weather += 1
            apparent_speed = r.speed_mps
            temp_c = float(r.temperature_c) if r.temperature_c is not None else 20.0
            air_density = calculate_air_density(temp_c, default_pressure_hpa, default_humidity_pct)

        # Skip if apparent speed is too low or negative (strong tailwind)
        if apparent_speed < 1.0:
            continue

        data_points.append(
            WindCorrectedDataPoint(
                grade_pct=grade,
                power_w=float(r.power_w),
                ground_speed_mps=r.speed_mps,
                apparent_speed_mps=apparent_speed,
                air_density=air_density,
                duration_s=r.timestamp_s - r_prev.timestamp_s,
            )
        )

    # Add warnings based on data quality
    total = len(records)
    if missing_gps > total * 0.3:
        warnings.append(f"High GPS data loss ({missing_gps}/{total} records)")
    if missing_power > total * 0.3:
        warnings.append(f"High power data loss ({missing_power}/{total} records)")
    if not weather_snapshots:
        warnings.append("No weather data - using default air density, no wind correction")

    # Calculate quality metrics
    total_points = points_with_weather + points_without_weather
    weather_coverage = (points_with_weather / total_points * 100) if total_points > 0 else 0.0
    gps_coverage = ((total - missing_gps) / total * 100) if total > 0 else 0.0
    power_coverage = ((total - missing_power) / total * 100) if total > 0 else 0.0

    data_quality = DataQuality(
        weather_coverage_pct=weather_coverage,
        gps_coverage_pct=gps_coverage,
        power_coverage_pct=power_coverage,
    )

    return data_points, data_quality, warnings


def estimate_cda_crr(
    data_points: list[WindCorrectedDataPoint],
    total_mass_kg: float,
    initial_cda: float = 0.32,
    initial_crr: float = 0.005,
    weather_coverage_pct: float = 100.0,
) -> AeroEstimationResult:
    """Estimate CdA and Crr from wind-corrected data points.

    Uses nonlinear least squares to fit the physics model, accounting for
    wind via the apparent speed term.

    Args:
        data_points: Wind-corrected calibration data points.
        total_mass_kg: Total mass (rider + bike) in kg.
        initial_cda: Initial guess for CdA.
        initial_crr: Initial guess for Crr.
        weather_coverage_pct: Percentage of data points with weather data (0-100).

    Returns:
        AeroEstimationResult with fitted parameters and diagnostics.
    """
    warnings: list[str] = []

    if len(data_points) < 10:
        return AeroEstimationResult(
            cda=initial_cda,
            crr=initial_crr,
            confidence=0.0,
            rms_error_pct=100.0,
            n_data_points=len(data_points),
            grade_range=(0.0, 0.0),
            avg_wind_speed_mps=0.0,
            warnings=["Insufficient data points for estimation (need at least 10)"],
        )

    # Analyze grade range
    grades = [dp.grade_pct for dp in data_points]
    min_grade, max_grade = min(grades), max(grades)
    grade_range = max_grade - min_grade

    if grade_range < MIN_GRADE_RANGE_PCT:
        warnings.append(f"Limited grade range ({min_grade:.1f}% to {max_grade:.1f}%). CdA/Crr separation may be poor.")

    # Calculate average wind for confidence scoring
    # Estimate from apparent vs ground speed difference
    speed_diffs = [dp.apparent_speed_mps - dp.ground_speed_mps for dp in data_points]
    avg_wind = sum(abs(d) for d in speed_diffs) / len(speed_diffs) if speed_diffs else 0.0

    def residuals(params: np.ndarray) -> np.ndarray:
        """Calculate residuals for optimization."""
        cda, crr = params
        errors = []

        for dp in data_points:
            theta = math.atan(dp.grade_pct / 100.0)

            # Force components
            f_gravity = total_mass_kg * GRAVITY * math.sin(theta)
            f_rolling = total_mass_kg * GRAVITY * crr * math.cos(theta)
            # Aero uses apparent speed (ground + headwind)
            f_aero = 0.5 * dp.air_density * cda * dp.apparent_speed_mps**2

            # Power required to maintain ground speed
            f_total = f_gravity + f_rolling + f_aero
            p_required = f_total * dp.ground_speed_mps / DEFAULT_EFFICIENCY

            if dp.power_w > 0:
                rel_error = (p_required - dp.power_w) / dp.power_w

                # Weight by terrain importance (climbs matter more for race pacing)
                terrain_weight = 1.5 if dp.grade_pct >= 3 else 1.0
                errors.append(terrain_weight * rel_error)

        return np.array(errors)

    # Bounds for CdA and Crr
    bounds = ([0.20, 0.002], [0.60, 0.012])

    try:
        result = least_squares(
            residuals,
            x0=[initial_cda, initial_crr],
            bounds=bounds,
            method="trf",
        )
        fitted_cda, fitted_crr = result.x
    except Exception as e:
        warnings.append(f"Optimization failed: {e}")
        return AeroEstimationResult(
            cda=initial_cda,
            crr=initial_crr,
            confidence=0.0,
            rms_error_pct=100.0,
            n_data_points=len(data_points),
            grade_range=(min_grade, max_grade),
            avg_wind_speed_mps=avg_wind,
            warnings=warnings,
        )

    # Calculate RMS error
    final_residuals = residuals(np.array([fitted_cda, fitted_crr]))
    rms_error = float(np.sqrt(np.mean(final_residuals**2)) * 100)

    # Sanity check results
    if fitted_cda < 0.22:
        warnings.append(f"CdA ({fitted_cda:.3f}) is very low - typical only in full aero TT position")
    elif fitted_cda > 0.50:
        warnings.append(f"CdA ({fitted_cda:.3f}) is high - indicates upright position or data issues")

    if fitted_crr < 0.003:
        warnings.append(f"Crr ({fitted_crr:.4f}) is very low - only achievable with race tires on smooth roads")
    elif fitted_crr > 0.008:
        warnings.append(f"Crr ({fitted_crr:.4f}) is high - indicates rough roads or wide tires")

    # Calculate confidence score
    confidence = _calculate_confidence(
        n_points=len(data_points),
        grade_range=grade_range,
        avg_wind_mps=avg_wind,
        rms_error_pct=rms_error,
        weather_coverage_pct=weather_coverage_pct,
    )

    return AeroEstimationResult(
        cda=fitted_cda,
        crr=fitted_crr,
        confidence=confidence,
        rms_error_pct=rms_error,
        n_data_points=len(data_points),
        grade_range=(min_grade, max_grade),
        avg_wind_speed_mps=avg_wind,
        warnings=warnings,
    )


def _calculate_confidence(
    n_points: int,
    grade_range: float,
    avg_wind_mps: float,
    rms_error_pct: float,
    weather_coverage_pct: float = 100.0,
) -> float:
    """Calculate confidence score (0.0-1.0) for the estimation.

    Higher confidence when:
    - More data points
    - Wider grade range (better CdA/Crr separation)
    - Lower wind speed
    - Lower fitting error
    - Higher weather data coverage

    Args:
        n_points: Number of data points used.
        grade_range: Difference between max and min grade.
        avg_wind_mps: Average wind speed.
        rms_error_pct: RMS fitting error as percentage.
        weather_coverage_pct: Percentage of points with weather data (0-100).

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    score = 1.0

    # Data quantity factor
    if n_points < 100:
        score *= n_points / 100
    elif n_points < 500:
        score *= 0.9 + 0.1 * (n_points - 100) / 400

    # Grade range factor (need variety for separation)
    if grade_range < 2:
        score *= 0.5
    elif grade_range < 4:
        score *= 0.7
    elif grade_range < 6:
        score *= 0.85

    # Wind factor (high wind = less reliable)
    if avg_wind_mps > 8:
        score *= 0.4
    elif avg_wind_mps > 5:
        score *= 0.6
    elif avg_wind_mps > 3:
        score *= 0.8

    # Fit quality factor
    if rms_error_pct > 20:
        score *= 0.3
    elif rms_error_pct > 15:
        score *= 0.5
    elif rms_error_pct > 10:
        score *= 0.7
    elif rms_error_pct > 5:
        score *= 0.9

    # Weather coverage factor - incomplete weather data reduces confidence
    # Without weather, wind correction is missing, so estimate is less reliable
    if weather_coverage_pct < 50:
        score *= 0.5  # Significant penalty for <50% coverage
    elif weather_coverage_pct < 80:
        score *= 0.7  # Moderate penalty for 50-80% coverage
    elif weather_coverage_pct < 95:
        score *= 0.9  # Small penalty for 80-95% coverage

    return round(max(0.0, min(1.0, score)), 2)


def check_estimation_requirements(
    records: list[ActivityRecord],
    power_source: str | None,
) -> tuple[bool, list[str]]:
    """Check if activity meets minimum requirements for CdA/Crr estimation.

    Args:
        records: Activity records.
        power_source: Source of power data ('measured', 'estimated', etc).

    Returns:
        Tuple of (can_estimate, reasons_if_not).
    """
    reasons: list[str] = []

    # Must have measured power
    if power_source != "measured":
        reasons.append(f"Power source is '{power_source}', need 'measured'")

    if not records:
        reasons.append("No records")
        return False, reasons

    # Check duration
    duration_s = records[-1].timestamp_s - records[0].timestamp_s if len(records) > 1 else 0
    duration_min = duration_s / 60
    if duration_min < MIN_DURATION_MINUTES:
        reasons.append(f"Duration {duration_min:.0f}min < {MIN_DURATION_MINUTES}min required")

    # Check GPS coverage
    gps_count = sum(1 for r in records if r.lat is not None and r.lon is not None)
    gps_pct = (gps_count / len(records)) * 100 if records else 0
    if gps_pct < MIN_GPS_COVERAGE_PCT:
        reasons.append(f"GPS coverage {gps_pct:.0f}% < {MIN_GPS_COVERAGE_PCT}% required")

    # Check power coverage
    power_count = sum(1 for r in records if r.power_w is not None and r.power_w > 0)
    power_pct = (power_count / len(records)) * 100 if records else 0
    if power_pct < MIN_POWER_COVERAGE_PCT:
        reasons.append(f"Power coverage {power_pct:.0f}% < {MIN_POWER_COVERAGE_PCT}% required")

    return len(reasons) == 0, reasons
