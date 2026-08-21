"""CdA estimation from calibration segments using linear regression.

Estimates the aerodynamic drag area (CdA) from steady-state ride segments.
The method is based on the cycling power equation rearranged into linear form.

Method:
1. For each segment, use the simplified power equation (flat ground):
   P = v × (m·g·Crr + 0.5·ρ·CdA·v²) / η

2. Rearrange to isolate the velocity-squared term:
   P·η/v = m·g·Crr + 0.5·ρ·CdA·v²

   Let y = P·η/v - m·g·Crr  (adjusted power per velocity)
   Let x = 0.5·ρ·v²         (dynamic pressure × reference area)

   Then: y = CdA × x (linear through origin)

3. Use least-squares regression to find CdA

4. Weight segments by duration for more robust estimation

References:
- Chung's method for CdA estimation
- Martin JC et al. (1998) power equation
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .bike import BIKE_TYPE_DEFAULTS
from .calibration_segments import CalibrationSegment

# Physical constants
GRAVITY = 9.80665  # m/s²


@dataclass(frozen=True, slots=True)
class CdAEstimate:
    """Result of CdA estimation.

    Attributes:
        cda: Estimated CdA in m².
        confidence: Confidence tier ('high', 'medium', 'low').
        std_error: Standard error of the CdA estimate.
        r_squared: R² goodness of fit (0-1).
        n_segments: Number of segments used in estimation.
        total_duration_s: Total duration of all segments.
        estimates_by_segment: CdA estimate from each individual segment.
    """

    cda: float
    confidence: str
    std_error: float
    r_squared: float
    n_segments: int
    total_duration_s: float
    estimates_by_segment: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CalibrationInput:
    """Input data for a single calibration segment.

    Attributes:
        power: Power readings in watts (array).
        speed: Speed readings in m/s (array).
        grade: Grade readings as percentage (array).
        air_density: Air density in kg/m³.
        rider_mass: Total mass (rider + bike) in kg.
        crr: Rolling resistance coefficient.
    """

    power: tuple[float, ...]
    speed: tuple[float, ...]
    grade: tuple[float, ...]
    air_density: float
    rider_mass: float
    crr: float

    @property
    def duration_s(self) -> float:
        """Duration of segment in seconds (assumes 1Hz sampling)."""
        return float(len(self.power))

    @property
    def mean_power(self) -> float:
        """Mean power in watts."""
        return float(np.mean(self.power)) if self.power else 0.0

    @property
    def mean_speed(self) -> float:
        """Mean speed in m/s."""
        return float(np.mean(self.speed)) if self.speed else 0.0

    @property
    def mean_grade(self) -> float:
        """Mean grade as percentage."""
        return float(np.mean(self.grade)) if self.grade else 0.0


def _estimate_cda_single_segment(inp: CalibrationInput, efficiency: float = 0.97) -> float:
    """Estimate CdA from a single calibration segment using its mean values.

    Rearranges the power equation to solve for CdA:
    P·η/v = m·g·Crr·cos(θ) + m·g·sin(θ) + 0.5·ρ·CdA·v²
    CdA = (P·η/v - m·g·Crr·cos(θ) - m·g·sin(θ)) / (0.5·ρ·v²)

    Args:
        inp: Calibration input with power, speed, etc.
        efficiency: Drivetrain efficiency (default 0.97).

    Returns:
        Estimated CdA in m². May be negative if data is bad.
    """
    mean_speed = inp.mean_speed
    mean_power = inp.mean_power
    mean_grade = inp.mean_grade

    if mean_speed <= 0:
        return 0.0

    import math

    theta = math.atan(mean_grade / 100.0)

    # Force at wheel = P × η / v
    wheel_force = mean_power * efficiency / mean_speed

    # Subtract gravity and rolling resistance forces
    gravity_force = inp.rider_mass * GRAVITY * math.sin(theta)
    rolling_force = inp.rider_mass * GRAVITY * inp.crr * math.cos(theta)
    aero_force = wheel_force - gravity_force - rolling_force

    # Aero force = 0.5 × ρ × CdA × v²
    # CdA = aero_force / (0.5 × ρ × v²)
    dynamic_pressure = 0.5 * inp.air_density * mean_speed * mean_speed

    if dynamic_pressure <= 0:
        return 0.0

    return aero_force / dynamic_pressure


def estimate_cda(
    segments: list[CalibrationInput],
    crr_fixed: float | None = None,
) -> CdAEstimate:
    """Estimate CdA using linear regression across segments.

    Uses the cycling power equation rearranged into linear form:
    P·η/v - m·g·Crr = 0.5·ρ·CdA·v²

    Let y = P·η/v - m·g·Crr  (adjusted power per velocity)
    Let x = 0.5·ρ·v²         (dynamic pressure)

    Then: y = CdA × x (linear through origin)

    Args:
        segments: List of calibration inputs (one per segment).
        crr_fixed: Fixed rolling resistance coefficient. If None, uses
            the crr from each segment's input.

    Returns:
        CdAEstimate with the estimated value and confidence metrics.

    Raises:
        ValueError: If no valid inputs provided.
    """
    import math

    if not segments:
        raise ValueError("No calibration inputs provided")

    efficiency = 0.97  # Drivetrain efficiency

    # Build arrays for linear regression
    # y = adjusted_force (what's left after subtracting rolling/gravity)
    # x = dynamic_pressure (0.5 * rho * v^2)
    # Regression: y = CdA * x (through origin)

    x_values: list[float] = []
    y_values: list[float] = []
    weights: list[float] = []
    segment_estimates: list[float] = []

    for inp in segments:
        mean_speed = inp.mean_speed
        mean_power = inp.mean_power
        mean_grade = inp.mean_grade
        crr = crr_fixed if crr_fixed is not None else inp.crr

        if mean_speed <= 0:
            continue

        theta = math.atan(mean_grade / 100.0)

        # Force at wheel = P × η / v
        wheel_force = mean_power * efficiency / mean_speed

        # Subtract gravity and rolling resistance forces
        gravity_force = inp.rider_mass * GRAVITY * math.sin(theta)
        rolling_force = inp.rider_mass * GRAVITY * crr * math.cos(theta)
        adjusted_force = wheel_force - gravity_force - rolling_force  # y

        # Dynamic pressure term
        dynamic_pressure = 0.5 * inp.air_density * mean_speed * mean_speed  # x

        if dynamic_pressure <= 0:
            continue

        # Per-segment CdA estimate
        cda_estimate = adjusted_force / dynamic_pressure
        if 0.1 < cda_estimate < 0.8:  # Reasonable CdA range
            x_values.append(dynamic_pressure)
            y_values.append(adjusted_force)
            weights.append(inp.duration_s)
            segment_estimates.append(cda_estimate)

    if not x_values:
        # All estimates were invalid - return a default with low confidence
        return CdAEstimate(
            cda=0.32,  # Default road bike CdA
            confidence="low",
            std_error=0.1,
            r_squared=0.0,
            n_segments=0,
            total_duration_s=0.0,
            estimates_by_segment=(),
        )

    x_arr = np.array(x_values)
    y_arr = np.array(y_values)
    weights_arr = np.array(weights)

    # Weighted linear regression through origin: y = CdA * x
    # CdA = sum(w * x * y) / sum(w * x^2)
    numerator = np.sum(weights_arr * x_arr * y_arr)
    denominator = np.sum(weights_arr * x_arr * x_arr)

    if denominator <= 0:
        cda = 0.32
    else:
        cda = float(numerator / denominator)

    # Calculate R² for regression through origin
    # R² = 1 - SS_res / SS_tot
    # where SS_tot = sum(w * y^2) for regression through origin
    y_pred = cda * x_arr
    ss_res = float(np.sum(weights_arr * (y_arr - y_pred) ** 2))
    ss_tot = float(np.sum(weights_arr * y_arr**2))

    if ss_tot > 0:
        r_squared = max(0.0, 1.0 - ss_res / ss_tot)
    else:
        r_squared = 1.0

    # Calculate standard error of CdA estimate
    n = len(x_values)
    if n > 1:
        # Residual standard error
        residual_var = ss_res / (n - 1)  # -1 for one parameter (CdA)
        # Standard error of slope in weighted regression through origin
        std_error = float(np.sqrt(residual_var / denominator)) if denominator > 0 else 0.1
    else:
        std_error = 0.1

    total_duration = float(np.sum(weights_arr))

    # Calculate CV for confidence tier
    estimates_arr = np.array(segment_estimates)
    weighted_mean = float(np.average(estimates_arr, weights=weights_arr))
    variance = float(np.average((estimates_arr - weighted_mean) ** 2, weights=weights_arr))
    std_dev = np.sqrt(variance)
    coefficient_of_variation = std_dev / weighted_mean if weighted_mean > 0 else 1.0

    # Determine confidence tier
    confidence = confidence_tier(n, total_duration, coefficient_of_variation)

    return CdAEstimate(
        cda=cda,
        confidence=confidence,
        std_error=std_error,
        r_squared=r_squared,
        n_segments=n,
        total_duration_s=total_duration,
        estimates_by_segment=tuple(segment_estimates),
    )


def confidence_tier(
    n_segments: int,
    total_duration_s: float,
    cv: float,
) -> str:
    """Determine confidence tier for CdA estimate.

    Per design #529:
    - High: >= 5 segments, >= 300s total, CV < 3%
    - Medium: >= 3 segments, >= 120s total, CV < 5%
    - Low: anything else

    Args:
        n_segments: Number of valid segments.
        total_duration_s: Total duration of all segments.
        cv: Coefficient of variation of estimates.

    Returns:
        Confidence tier string.
    """
    if n_segments >= 5 and total_duration_s >= 300 and cv < 0.03:
        return "high"
    if n_segments >= 3 and total_duration_s >= 120 and cv < 0.05:
        return "medium"
    return "low"


def get_default_crr(bike_type: str) -> float:
    """Return default Crr for a bike type.

    Args:
        bike_type: The bike type (road, tt, gravel, mtb, ebike).

    Returns:
        Default rolling resistance coefficient.

    Raises:
        KeyError: If bike_type is not recognized.
    """
    return BIKE_TYPE_DEFAULTS[bike_type]["crr"]


def get_default_cda(bike_type: str) -> float:
    """Return default CdA for a bike type.

    Args:
        bike_type: The bike type (road, tt, gravel, mtb, ebike).

    Returns:
        Default aerodynamic drag area in m².

    Raises:
        KeyError: If bike_type is not recognized.
    """
    return BIKE_TYPE_DEFAULTS[bike_type]["cda"]


def inputs_from_segments(
    segments: list[CalibrationSegment],
    power: NDArray[np.floating],
    speed: NDArray[np.floating],
    grade: NDArray[np.floating],
    air_density: float,
    rider_mass: float,
    crr: float,
) -> list[CalibrationInput]:
    """Create CalibrationInputs from segments and raw data.

    Extracts the array slices for each segment and creates CalibrationInput
    objects with the raw data arrays for the estimation function.

    Args:
        segments: List of calibration segments.
        power: Full power array.
        speed: Full speed array.
        grade: Full grade array.
        air_density: Air density in kg/m³.
        rider_mass: Total mass (rider + bike) in kg.
        crr: Rolling resistance coefficient.

    Returns:
        List of CalibrationInput objects with array data.
    """
    inputs: list[CalibrationInput] = []

    for seg in segments:
        # Extract array slices for this segment
        seg_power = power[seg.start_idx : seg.end_idx]
        seg_speed = speed[seg.start_idx : seg.end_idx]
        seg_grade = grade[seg.start_idx : seg.end_idx]

        inputs.append(
            CalibrationInput(
                power=tuple(float(p) for p in seg_power),
                speed=tuple(float(s) for s in seg_speed),
                grade=tuple(float(g) for g in seg_grade),
                air_density=air_density,
                rider_mass=rider_mass,
                crr=crr,
            )
        )

    return inputs
