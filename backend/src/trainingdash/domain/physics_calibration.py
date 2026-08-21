"""Physics-based CdA/Crr calibration from ride data.

This module provides a comprehensive approach to calibrating aerodynamic drag
(CdA) and rolling resistance (Crr) from actual ride data across all terrain
types, not just flat high-speed segments.

The key insight is that by using the full physics model and data from multiple
grades, we can solve for both CdA and Crr simultaneously:
- On climbs: gravity dominates, Crr has more influence than CdA
- On flats: aero dominates at higher speeds, CdA has more influence
- By fitting across all terrain, we get robust estimates for both

This approach is superior to the traditional "Chung method" which requires
30+ km/h flat segments that many riders don't have.

References:
- Martin JC et al. (1998) cycling power equation
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

# Physical constants
GRAVITY = 9.80665  # m/s²
SEA_LEVEL_AIR_DENSITY = 1.225  # kg/m³
DEFAULT_EFFICIENCY = 0.97


@dataclass(frozen=True, slots=True)
class CalibrationDataPoint:
    """A single data point for calibration.

    Represents averaged data over a segment of riding with consistent
    conditions (grade, power, speed).

    Attributes:
        grade_pct: Road gradient as percentage (positive = uphill).
        power_w: Average power in watts.
        speed_mps: Average speed in m/s.
        duration_s: Duration of segment in seconds (for weighting).
        air_density: Air density in kg/m³ (defaults to sea level).
    """

    grade_pct: float
    power_w: float
    speed_mps: float
    duration_s: float = 60.0
    air_density: float = SEA_LEVEL_AIR_DENSITY


@dataclass(frozen=True, slots=True)
class PhysicsCalibrationResult:
    """Result of physics-based CdA/Crr calibration.

    Attributes:
        cda: Estimated CdA in m².
        crr: Estimated rolling resistance coefficient.
        confidence: Confidence tier ('high', 'medium', 'low').
        rms_error_pct: Root mean square error as percentage.
        max_error_pct: Maximum absolute error as percentage.
        n_data_points: Number of data points used.
        grade_range: Tuple of (min_grade, max_grade) in the data.
        warnings: List of warning messages.
    """

    cda: float
    crr: float
    confidence: str
    rms_error_pct: float
    max_error_pct: float
    n_data_points: int
    grade_range: tuple[float, float]
    warnings: list[str]


def predict_speed_from_power(
    power_w: float,
    grade_pct: float,
    total_mass_kg: float,
    cda: float,
    crr: float,
    air_density: float = SEA_LEVEL_AIR_DENSITY,
    efficiency: float = DEFAULT_EFFICIENCY,
) -> float:
    """Predict speed given power using the cycling physics model.

    Uses Newton-Raphson iteration to solve the power equation for speed.

    Args:
        power_w: Power at the pedals in watts.
        grade_pct: Road gradient as percentage.
        total_mass_kg: Total mass (rider + bike) in kg.
        cda: Aerodynamic drag area in m².
        crr: Rolling resistance coefficient.
        air_density: Air density in kg/m³.
        efficiency: Drivetrain efficiency (0-1).

    Returns:
        Predicted ground speed in m/s.
    """
    if power_w <= 0:
        return 0.0

    theta = math.atan(grade_pct / 100.0)

    # Initial guess based on terrain
    if grade_pct > 5:
        v = 3.0  # ~10 km/h on steep climbs
    elif grade_pct < -3:
        v = 12.0  # ~43 km/h on descents
    else:
        v = 7.0  # ~25 km/h on flat/moderate

    # Newton-Raphson iteration
    for _ in range(50):
        # Force components
        f_gravity = total_mass_kg * GRAVITY * math.sin(theta)
        f_rolling = total_mass_kg * GRAVITY * crr * math.cos(theta)
        f_aero = 0.5 * air_density * cda * v * v

        f_total = f_gravity + f_rolling + f_aero
        p_required = max(0.0, f_total * v / efficiency)

        # Derivative dP/dv
        # P = (F_g + F_r + F_a) * v / η
        # dP/dv = (F_g + F_r + 3*F_a) / η  (since F_a ∝ v²)
        dp_dv = (f_gravity + f_rolling + 3 * f_aero) / efficiency

        if abs(dp_dv) < 1e-10:
            dp_dv = 0.1

        # Newton step
        delta = (p_required - power_w) / dp_dv
        v_new = v - delta
        v_new = max(0.5, min(50.0, v_new))

        if abs(v_new - v) < 1e-8:
            break
        v = v_new

    return v


def calibrate_from_data_points(
    data_points: list[CalibrationDataPoint],
    total_mass_kg: float,
    initial_cda: float = 0.35,
    initial_crr: float = 0.005,
    climb_weight: float = 2.0,
) -> PhysicsCalibrationResult:
    """Calibrate CdA and Crr from ride data points.

    Uses nonlinear least squares to fit the physics model to actual ride data,
    solving for both CdA and Crr simultaneously.

    Args:
        data_points: List of calibration data points.
        total_mass_kg: Total mass (rider + bike) in kg.
        initial_cda: Initial guess for CdA (default 0.35).
        initial_crr: Initial guess for Crr (default 0.005).
        climb_weight: Weight multiplier for climb data points (default 2.0).
            Climbs are weighted higher because they matter more for race pacing.

    Returns:
        PhysicsCalibrationResult with fitted parameters and diagnostics.

    Raises:
        ValueError: If insufficient data points provided.
    """
    warnings: list[str] = []

    if len(data_points) < 3:
        raise ValueError("At least 3 data points required for calibration")

    # Filter out steep descents where braking dominates physics
    # Keep grades from -4% to +15%
    filtered_points = [
        dp for dp in data_points if -4 <= dp.grade_pct <= 15 and dp.power_w > 30
    ]

    if len(filtered_points) < 3:
        raise ValueError(
            "Insufficient valid data points after filtering. "
            "Need data from grades between -4% and +15% with power > 30W."
        )

    # Check grade range
    grades = [dp.grade_pct for dp in filtered_points]
    min_grade, max_grade = min(grades), max(grades)

    if max_grade - min_grade < 3:
        warnings.append(
            f"Limited grade range ({min_grade:.0f}% to {max_grade:.0f}%). "
            "Results may be less accurate. Ride varied terrain for better calibration."
        )

    def residuals(params: np.ndarray) -> np.ndarray:
        """Calculate weighted residuals for optimization."""
        cda, crr = params
        errors = []

        for dp in filtered_points:
            predicted_speed = predict_speed_from_power(
                power_w=dp.power_w,
                grade_pct=dp.grade_pct,
                total_mass_kg=total_mass_kg,
                cda=cda,
                crr=crr,
                air_density=dp.air_density,
            )

            actual_speed = dp.speed_mps
            if actual_speed > 0:
                rel_error = (predicted_speed - actual_speed) / actual_speed

                # Weight by duration and terrain importance
                # Climbs matter more for race planning accuracy
                terrain_weight = climb_weight if dp.grade_pct >= 3 else 1.0
                duration_weight = math.sqrt(dp.duration_s / 60.0)  # Longer = more reliable

                errors.append(terrain_weight * duration_weight * rel_error)

        return np.array(errors)

    # Bounds for CdA and Crr
    # CdA: 0.20 (aero TT position) to 0.65 (very upright)
    # Crr: 0.002 (slick race tires) to 0.012 (rough surface/low pressure)
    bounds = ([0.20, 0.002], [0.65, 0.012])

    # Run optimization
    result = least_squares(
        residuals,
        x0=[initial_cda, initial_crr],
        bounds=bounds,
        method="trf",  # Trust Region Reflective - handles bounds well
    )

    fitted_cda, fitted_crr = result.x

    # Calculate error metrics
    errors_pct = []
    for dp in filtered_points:
        predicted = predict_speed_from_power(
            dp.power_w, dp.grade_pct, total_mass_kg, fitted_cda, fitted_crr, dp.air_density
        )
        if dp.speed_mps > 0:
            error = abs(predicted - dp.speed_mps) / dp.speed_mps * 100
            errors_pct.append(error)

    rms_error = float(np.sqrt(np.mean(np.array(errors_pct) ** 2)))
    max_error = float(max(errors_pct)) if errors_pct else 0.0

    # Determine confidence tier
    if len(filtered_points) >= 10 and max_grade >= 5 and min_grade <= 1 and rms_error < 5:
        confidence = "high"
    elif len(filtered_points) >= 5 and max_grade - min_grade >= 4 and rms_error < 10:
        confidence = "medium"
    else:
        confidence = "low"
        if rms_error > 15:
            warnings.append(f"High RMS error ({rms_error:.1f}%). Data may be inconsistent.")

    # Sanity check the results
    if fitted_cda < 0.25:
        warnings.append(
            f"Fitted CdA ({fitted_cda:.3f}) is very low - typically only achievable "
            "in aero TT position. Check data quality."
        )
    elif fitted_cda > 0.55:
        warnings.append(
            f"Fitted CdA ({fitted_cda:.3f}) is quite high - indicates very upright position "
            "or possible data issues."
        )

    if fitted_crr < 0.003:
        warnings.append(
            f"Fitted Crr ({fitted_crr:.4f}) is very low - only achievable with "
            "race tires on smooth roads. Check data quality."
        )
    elif fitted_crr > 0.008:
        warnings.append(
            f"Fitted Crr ({fitted_crr:.4f}) is high - indicates rough roads, "
            "low tire pressure, or wider tires."
        )

    return PhysicsCalibrationResult(
        cda=fitted_cda,
        crr=fitted_crr,
        confidence=confidence,
        rms_error_pct=rms_error,
        max_error_pct=max_error,
        n_data_points=len(filtered_points),
        grade_range=(min_grade, max_grade),
        warnings=warnings,
    )


def aggregate_records_to_data_points(
    power: np.ndarray,
    speed: np.ndarray,
    grade: np.ndarray,
    timestamps: np.ndarray,
    air_density: float = SEA_LEVEL_AIR_DENSITY,
    window_size: int = 60,
    min_power_w: float = 30.0,
    min_speed_mps: float = 1.5,
) -> list[CalibrationDataPoint]:
    """Aggregate time-series records into calibration data points.

    Groups records by grade bins and calculates weighted averages,
    producing one data point per grade level with sufficient data.

    Args:
        power: Power array in watts.
        speed: Speed array in m/s.
        grade: Grade array as percentage.
        timestamps: Timestamp array (for duration calculation).
        air_density: Air density in kg/m³.
        window_size: Window size for rolling averages.
        min_power_w: Minimum power to include (filters coasting).
        min_speed_mps: Minimum speed to include (filters stops).

    Returns:
        List of CalibrationDataPoint objects, one per grade bin.
    """
    if len(power) < window_size:
        return []

    # Filter valid samples
    valid_mask = (power >= min_power_w) & (speed >= min_speed_mps) & np.isfinite(grade)
    valid_indices = np.where(valid_mask)[0]

    if len(valid_indices) < window_size:
        return []

    # Group by grade bins (1% increments)
    grade_bins: dict[int, list[tuple[float, float, float]]] = {}

    for idx in valid_indices:
        grade_bin = int(round(grade[idx]))
        if grade_bin not in grade_bins:
            grade_bins[grade_bin] = []
        grade_bins[grade_bin].append((power[idx], speed[idx], 1.0))  # (power, speed, duration)

    # Create data points for bins with enough samples
    data_points = []
    for grade_bin, samples in grade_bins.items():
        if len(samples) < 30:  # Need at least 30 seconds of data
            continue

        powers, speeds, durations = zip(*samples)
        avg_power = float(np.mean(powers))
        avg_speed = float(np.mean(speeds))
        total_duration = float(len(samples))  # Assuming 1Hz

        data_points.append(
            CalibrationDataPoint(
                grade_pct=float(grade_bin),
                power_w=avg_power,
                speed_mps=avg_speed,
                duration_s=total_duration,
                air_density=air_density,
            )
        )

    return data_points
