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
        power: Mean power in watts.
        speed: Mean speed in m/s.
        grade: Mean grade as percentage.
        air_density: Air density in kg/m³.
        rider_mass: Total mass (rider + bike) in kg.
        crr: Rolling resistance coefficient.
        duration_s: Segment duration in seconds (for weighting).
    """

    power: float
    speed: float
    grade: float
    air_density: float
    rider_mass: float
    crr: float
    duration_s: float = 1.0


def _estimate_cda_single_segment(inp: CalibrationInput, efficiency: float = 0.97) -> float:
    """Estimate CdA from a single calibration segment.

    Rearranges the power equation to solve for CdA:
    P·η/v = m·g·Crr·cos(θ) + m·g·sin(θ) + 0.5·ρ·CdA·v²
    CdA = (P·η/v - m·g·Crr·cos(θ) - m·g·sin(θ)) / (0.5·ρ·v²)

    Args:
        inp: Calibration input with power, speed, etc.
        efficiency: Drivetrain efficiency (default 0.97).

    Returns:
        Estimated CdA in m². May be negative if data is bad.
    """
    if inp.speed <= 0:
        return 0.0

    import math

    theta = math.atan(inp.grade / 100.0)

    # Force at wheel = P × η / v
    wheel_force = inp.power * efficiency / inp.speed

    # Subtract gravity and rolling resistance forces
    gravity_force = inp.rider_mass * GRAVITY * math.sin(theta)
    rolling_force = inp.rider_mass * GRAVITY * inp.crr * math.cos(theta)
    aero_force = wheel_force - gravity_force - rolling_force

    # Aero force = 0.5 × ρ × CdA × v²
    # CdA = aero_force / (0.5 × ρ × v²)
    dynamic_pressure = 0.5 * inp.air_density * inp.speed * inp.speed

    if dynamic_pressure <= 0:
        return 0.0

    return aero_force / dynamic_pressure


def estimate_cda(
    inputs: list[CalibrationInput],
    efficiency: float = 0.97,
) -> CdAEstimate:
    """Estimate CdA using weighted linear regression across segments.

    Uses duration-weighted averaging of per-segment estimates, with
    outlier filtering.

    Args:
        inputs: List of calibration inputs (one per segment).
        efficiency: Drivetrain efficiency (default 0.97).

    Returns:
        CdAEstimate with the estimated value and confidence metrics.

    Raises:
        ValueError: If no valid inputs provided.
    """
    if not inputs:
        raise ValueError("No calibration inputs provided")

    # Calculate per-segment estimates
    segment_estimates: list[float] = []
    segment_weights: list[float] = []

    for inp in inputs:
        cda = _estimate_cda_single_segment(inp, efficiency)
        # Filter out clearly invalid estimates
        if 0.1 < cda < 0.8:  # Reasonable CdA range
            segment_estimates.append(cda)
            segment_weights.append(inp.duration_s)

    if not segment_estimates:
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

    estimates_arr = np.array(segment_estimates)
    weights_arr = np.array(segment_weights)

    # Duration-weighted mean
    weighted_mean = float(np.average(estimates_arr, weights=weights_arr))

    # Calculate weighted standard deviation
    variance = float(
        np.average((estimates_arr - weighted_mean) ** 2, weights=weights_arr)
    )
    std_dev = np.sqrt(variance)

    # Standard error of the weighted mean
    n = len(estimates_arr)
    std_error = std_dev / np.sqrt(n) if n > 1 else std_dev

    # Calculate R² as a measure of consistency
    # R² = 1 - SS_res / SS_tot where SS_tot is variance from the weighted mean
    # Since we're measuring consistency of individual estimates, not fitting a model,
    # we use the weighted variance relative to the overall weighted mean
    ss_tot = float(np.sum(weights_arr * (estimates_arr - weighted_mean) ** 2))

    # For estimation from repeated measurements, R² reflects how much variance
    # is explained by the weighted mean. With perfect consistency, all estimates
    # equal the mean and R² = 1.
    if ss_tot > 0:
        # Residuals are the deviations from weighted mean
        # In this context, lower variance = higher R²
        # We normalize by the variance of estimates around a naive mean (unweighted)
        naive_mean = float(np.mean(estimates_arr))
        ss_naive = float(np.sum((estimates_arr - naive_mean) ** 2))
        if ss_naive > 0:
            # Weighted mean should explain more variance than naive mean
            ss_res_weighted = float(np.sum(weights_arr * (estimates_arr - weighted_mean) ** 2))
            # Normalize both by number of segments for fair comparison
            r_squared = max(0.0, 1.0 - (ss_res_weighted / np.sum(weights_arr)) / (ss_naive / n))
        else:
            r_squared = 1.0  # All estimates identical
    else:
        r_squared = 1.0  # All estimates identical

    # Also calculate CV for confidence tier determination
    cv = std_dev / weighted_mean if weighted_mean > 0 else 1.0

    total_duration = float(np.sum(weights_arr))

    # Determine confidence tier
    confidence = confidence_tier(n, total_duration, cv)

    return CdAEstimate(
        cda=weighted_mean,
        confidence=confidence,
        std_error=float(std_error),
        r_squared=float(r_squared),
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

    Convenience function to extract segment data and create CalibrationInput
    objects for the estimation function.

    Args:
        segments: List of calibration segments.
        power: Full power array.
        speed: Full speed array.
        grade: Full grade array.
        air_density: Air density in kg/m³.
        rider_mass: Total mass (rider + bike) in kg.
        crr: Rolling resistance coefficient.

    Returns:
        List of CalibrationInput objects.
    """
    inputs: list[CalibrationInput] = []

    for seg in segments:
        # Use segment means directly if available, or recalculate from arrays
        inputs.append(
            CalibrationInput(
                power=seg.mean_power_w,
                speed=seg.mean_speed_mps,
                grade=seg.mean_grade_pct,
                air_density=air_density,
                rider_mass=rider_mass,
                crr=crr,
                duration_s=seg.duration_s,
            )
        )

    return inputs
