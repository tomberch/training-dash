"""
The pacing power model: coefficients, grade-power formula, and Normalized Power.

This module is the single home of the pacing model's shared math (ADR 0004):
- PacingCoefficients: one dataclass, the only definition in the codebase
- Grade-power formula: power_mult = intercept + slope × grade% (clamped)
- Normalized Power: one core implementation (30s rolling, 4th-power mean)
- Ride-type resolution: presets mapping ride types to descent/stop parameters

Plan generators (pacing.py, fine_grained_pacing.py, pacing_optimizer.py)
consume this module; they own plan shapes and orchestration, not the formula.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import numpy as np

# =============================================================================
# Ride Type Configuration
# =============================================================================

RideTypePreset = Literal["race", "gran_fondo", "training", "touring", "custom"]


@dataclass
class RideTypeParams:
    """Parameters controlling ride time estimation.

    These affect how predicted times account for:
    1. Descent aggressiveness - how fast you take corners (affects curvature speed factor)
    2. Stop percentage - expected time spent stopped (traffic, feeds, breaks)

    Attributes:
        descent_aggressiveness: 0-100 scale. 0=very cautious (0.75x on hairpins),
                               100=race pace (0.95x on hairpins). Affects descent speeds.
        stop_pct: 0-50 range. Percentage of extra time for stops beyond physics prediction.
                  6% means a 1-hour physics time becomes 1h04m total.
    """

    descent_aggressiveness: int  # 0-100
    stop_pct: float  # 0-50

    def __post_init__(self):
        if not 0 <= self.descent_aggressiveness <= 100:
            raise ValueError(f"descent_aggressiveness must be 0-100, got {self.descent_aggressiveness}")
        if not 0 <= self.stop_pct <= 50:
            raise ValueError(f"stop_pct must be 0-50, got {self.stop_pct}")

    @property
    def ride_type_for_curvature(self) -> str:
        """Convert descent_aggressiveness to ride_type string for curvature factor."""
        # >=80 is aggressive (race-like), <80 is cautious (training-like)
        return "race" if self.descent_aggressiveness >= 80 else "training"

    @property
    def stop_factor(self) -> float:
        """Multiplier to apply to total time for stops.

        stop_pct=6 means 6% extra time, so factor = 1.06
        """
        return 1.0 + (self.stop_pct / 100.0)


# Preset configurations based on empirical data
RIDE_TYPE_PRESETS: dict[str, RideTypeParams] = {
    "race": RideTypeParams(
        descent_aggressiveness=90,
        stop_pct=0,
    ),
    "gran_fondo": RideTypeParams(
        descent_aggressiveness=85,
        stop_pct=3,
    ),
    "training": RideTypeParams(
        descent_aggressiveness=70,
        stop_pct=6,
    ),
    "touring": RideTypeParams(
        descent_aggressiveness=60,
        stop_pct=25,
    ),
}


def resolve_ride_type_params(
    ride_type: RideTypePreset,
    custom_params: RideTypeParams | None = None,
) -> RideTypeParams:
    """Resolve ride type preset to actual parameters.

    Args:
        ride_type: Preset name or "custom"
        custom_params: Required if ride_type is "custom"

    Returns:
        RideTypeParams with resolved values

    Raises:
        ValueError: If ride_type is "custom" but no custom_params provided,
                   or if ride_type is unknown
    """
    if ride_type == "custom":
        if custom_params is None:
            raise ValueError("custom_params required when ride_type is 'custom'")
        return custom_params

    if ride_type not in RIDE_TYPE_PRESETS:
        raise ValueError(
            f"Unknown ride_type: {ride_type}. Valid options: {list(RIDE_TYPE_PRESETS.keys()) + ['custom']}"
        )

    return RIDE_TYPE_PRESETS[ride_type]


# =============================================================================
# Coefficients
# =============================================================================


@dataclass
class PacingCoefficients:
    """Personalized pacing model coefficients.

    These parameters control how power targets are calculated based on terrain
    and how descent speeds are capped. They can be learned from actual ride
    data via the calibration pipeline.

    The five model coefficients drive the math. The remaining fields are
    provenance metadata populated by the repository when coefficients are
    loaded from the database.
    """

    # Climb coefficients (grade-power relationship)
    grade_power_intercept: float = 1.10  # Base multiplier at 0% grade
    grade_power_slope: float = 0.035  # Additional multiplier per 1% grade

    # Descent coefficients
    # curvature_speed_coefficient is a_lat — the rider's lateral acceleration
    # comfort limit in m/s² used by the cornering-speed limit
    # v = sqrt(a_lat / kappa) (ADR 0004 Phase B; formerly a dead slope value).
    max_descent_speed_mps: float = 18.0  # Absolute speed limit on descents
    descent_power_multiplier: float = 0.50  # Power on descents (grade < -3%)
    curvature_speed_coefficient: float = 4.8  # a_lat in m/s² (default = training, aggressiveness 70)

    # Provenance (populated by the repository; defaults describe "global default")
    user_id: int | None = None
    bike_id: int | None = None
    climb_sample_count: int = 0
    descent_sample_count: int = 0
    activity_count: int = 0
    last_calibrated_at: "datetime | None" = None

    # Learned stop/coast baseline per terrain type (ADR 0005 #635).
    # Shape: {terrain: {non_pedaling_pct, coasting_pct, stopped_pct,
    # activity_count}}. None = not learned (quality gate kept it unset);
    # missing terrain keys = too few rides in that bucket.
    terrain_behavior: "dict | None" = None

    @classmethod
    def defaults(cls) -> "PacingCoefficients":
        """Return global defaults."""
        return cls()


# Global defaults (single source; re-exported for backward compatibility)
DEFAULT_COEFFICIENTS = PacingCoefficients.defaults()

# Module-level defaults (backward compatibility for scripts importing constants)
GRADE_POWER_INTERCEPT = 1.10  # Base multiplier at 0% grade
GRADE_POWER_SLOPE = 0.035  # Additional multiplier per 1% grade (calibrated from data)

# Power multiplier bounds (prevent unrealistic values)
# Adjusted based on actual ride data:
# - Descents: Riders coast (actual ~0.1-0.3), but we set minimum 0.50 for modeling
# - Steep climbs: Power caps around 1.50× avg in practice
MIN_POWER_MULTIPLIER = 0.50  # Minimum for descents (coasting with some pedaling)

# Descent threshold (ADR 0005 #634): grades below this are "descents" for
# the Descent Multiplier — same threshold as the calibration extractor's
# descent sampling (pacing_calibration.extract_descent_samples).
DESCENT_GRADE_PCT = -3.0
MAX_POWER_MULTIPLIER = 1.50  # Maximum for very steep climbs (realistic ceiling)

# Default rider parameters used when none are provided
# (typical road cyclist: 83kg total mass, road CdA, asphalt Crr)
DEFAULT_RIDER_MASS_KG = 83.0
DEFAULT_RIDER_CDA = 0.32
DEFAULT_RIDER_CRR = 0.004


def get_grade_power_multiplier(
    grade_pct: float,
    coefficients: PacingCoefficients | None = None,
) -> float:
    """Calculate power multiplier based on grade using calibrated formula.

    Uses continuous formula derived from regression against real ride data:
        power_mult = intercept + slope × grade%

    This captures the natural power distribution pattern where riders push
    harder on climbs (where aero drag is low) and ease off on descents
    (where extra power yields diminishing returns due to v³ drag).

    Args:
        grade_pct: Road gradient as percentage (e.g., 5.0 for 5% grade).
        coefficients: Personalized coefficients. If None, uses global defaults.

    Returns:
        Power multiplier relative to base power (FTP × target_intensity).
        Clamped to [MIN_POWER_MULTIPLIER, MAX_POWER_MULTIPLIER] range.

    Examples:
        >>> get_grade_power_multiplier(0)   # Flat
        1.10
        >>> get_grade_power_multiplier(10)  # 10% climb
        1.45
        >>> get_grade_power_multiplier(-8)  # 8% descent
        0.50
    """
    if coefficients is None:
        coefficients = DEFAULT_COEFFICIENTS

    multiplier = coefficients.grade_power_intercept + coefficients.grade_power_slope * grade_pct
    return max(MIN_POWER_MULTIPLIER, min(MAX_POWER_MULTIPLIER, multiplier))


# =============================================================================
# Cornering physics (B1: one curvature definition, one cornering model)
# =============================================================================

# Lateral acceleration bounds for cornering speed (m/s²).
# Cautious riders corner at ~2 m/s²; confident racers reach ~6 m/s².
MIN_LAT_ACCEL = 2.0  # m/s² at descent_aggressiveness=0
MAX_LAT_ACCEL = 6.0  # m/s² at descent_aggressiveness=100


def a_lat_from_aggressiveness(descent_aggressiveness: int) -> float:
    """Map descent_aggressiveness (0-100) to lateral acceleration (m/s²).

    Linear mapping: 0 → MIN_LAT_ACCEL (very cautious), 100 → MAX_LAT_ACCEL
    (race pace). Calibration (B3) fits a personalized value from corner
    apex speeds; this mapping is the fallback for uncalibrated riders.
    """
    if not 0 <= descent_aggressiveness <= 100:
        raise ValueError(f"descent_aggressiveness must be 0-100, got {descent_aggressiveness}")
    span = MAX_LAT_ACCEL - MIN_LAT_ACCEL
    return MIN_LAT_ACCEL + (descent_aggressiveness / 100.0) * span


def cornering_speed_limit(curvature: float, a_lat: float) -> float:
    """Maximum speed through a corner: v = sqrt(a_lat / kappa).

    Args:
        curvature: Menger curvature in 1/m (0 = straight road). The same
            definition the calibration pipeline fits (single definition
            per ADR 0004 — runtime and calibration share it).
        a_lat: Lateral acceleration comfort limit in m/s².

    Returns:
        Cornering speed limit in m/s, or float("inf") on a straight road.
    """
    if curvature <= 0:
        return float("inf")
    if a_lat <= 0:
        raise ValueError(f"a_lat must be positive, got {a_lat}")
    return math.sqrt(a_lat / curvature)


def effective_a_lat(
    coefficients: "PacingCoefficients | None",
    descent_aggressiveness: int = 70,
) -> float:
    """Resolve the lateral acceleration for a plan.

    Calibrated coefficients (fitted from corner apex speeds by B3) win
    when present; the descent_aggressiveness mapping is the fallback for
    uncalibrated riders.
    """
    if coefficients is not None and coefficients.activity_count > 0:
        return coefficients.curvature_speed_coefficient
    return a_lat_from_aggressiveness(descent_aggressiveness)


def effective_descent_power_multiplier(coefficients: "PacingCoefficients | None") -> float:
    """Resolve the Descent Multiplier for a plan (ADR 0005 #634).

    The fitted value wins when the rider is calibrated (activity_count
    > 0; rows invalidated by migration 028 have activity_count = 0 and
    fall back cleanly). Uncalibrated riders get the documented default
    0.50 — half base power on descents, until calibration learns their
    real behavior (coasters ~0.0-0.3, descent-pedalers ~0.5-0.8).
    """
    if coefficients is not None and coefficients.activity_count > 0:
        return coefficients.descent_power_multiplier
    return DEFAULT_COEFFICIENTS.descent_power_multiplier


def calculate_curvature_menger(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    lat3: float,
    lon3: float,
) -> float:
    """Menger curvature through three GPS points, in 1/m.

    The single curvature definition (ADR 0004): used identically by the
    runtime physics loop and by calibration's descent sample extraction.

    0 = straight; higher = tighter. Clamped to [0, 0.05] (R >= 20m): the
    clamp bounds GPS-noise artifacts while keeping real hairpins
    measurable — at the runtime's 25m resampled baseline the noise floor
    is ~0.003, so R<100m corners (kappa > 0.01) survive the clamp intact
    (discovered during B3 recalibration: the old 0.01 clamp erased real
    hairpins, both in the fit and in the runtime cornering limit).

    Returns 0 when coordinates are degenerate (collinear or too close).
    """
    # Convert to approximate meters (rough for small areas)
    # 1 degree lat ≈ 111km, 1 degree lon ≈ 111km * cos(lat)
    lat_scale = 111000
    lon_scale = 111000 * math.cos(math.radians(lat2))

    x1, y1 = lon1 * lon_scale, lat1 * lat_scale
    x2, y2 = lon2 * lon_scale, lat2 * lat_scale
    x3, y3 = lon3 * lon_scale, lat3 * lat_scale

    # Triangle area (2x) using cross product
    area2 = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1))

    # Side lengths
    a = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    b = math.sqrt((x3 - x2) ** 2 + (y3 - y2) ** 2)
    c = math.sqrt((x3 - x1) ** 2 + (y3 - y1) ** 2)

    # Menger curvature = 4 * area / (a * b * c)
    if a * b * c < 0.001:  # Avoid division by very small numbers
        return 0.0

    curvature = (4 * area2) / (a * b * c)

    # Clamp to realistic values (0.05 = radius >= 20m)
    return min(0.05, curvature)


# =============================================================================
# Normalized Power (the one core implementation)
# =============================================================================


def calculate_normalized_power(powers: "np.ndarray", sample_rate_hz: float = 1.0) -> float:
    """
    Calculate Normalized Power using the standard algorithm.

    NP = (mean(rolling_30s_power^4))^0.25

    The 30-second rolling average smooths short spikes, then the 4th power
    weighting emphasizes intensity. This makes NP reflect the physiological
    cost better than simple average power.

    Args:
        powers: Array of power values in watts (one per sample).
        sample_rate_hz: Sample frequency in Hz. Default 1.0 (1 sample/sec).

    Returns:
        Normalized Power in watts. Returns 0 if insufficient data.
    """
    powers = np.asarray(powers, dtype=np.float64)

    if len(powers) < 30:
        # Not enough data for 30s average - return regular average
        return float(np.mean(powers)) if len(powers) > 0 else 0.0

    # Window size for 30-second rolling average
    window_size = int(30 * sample_rate_hz)
    window_size = max(1, min(window_size, len(powers)))

    # Calculate 30-second rolling average
    cumsum = np.cumsum(np.insert(powers, 0, 0))
    rolling_avg = (cumsum[window_size:] - cumsum[:-window_size]) / window_size

    if len(rolling_avg) == 0:
        return float(np.mean(powers))

    # 4th power mean, then 4th root
    np_power = (np.mean(rolling_avg**4)) ** 0.25

    return float(np_power)


def calculate_intensity_factor(np_watts: float, ftp: float) -> float:
    """
    Calculate Intensity Factor (IF).

    IF = NP / FTP

    IF provides a normalized measure of ride intensity:
    - < 0.75: Recovery/Endurance
    - 0.75-0.85: Tempo
    - 0.85-0.95: Threshold
    - 0.95-1.05: VO2max intervals
    - > 1.05: Anaerobic

    Args:
        np_watts: Normalized Power in watts.
        ftp: Functional Threshold Power in watts.

    Returns:
        Intensity Factor (dimensionless).
    """
    if ftp <= 0:
        return 0.0
    return np_watts / ftp


def estimate_tss(np_watts: float, ftp: float, duration_s: float) -> float:
    """
    Estimate Training Stress Score (TSS) for a planned effort.

    TSS = (duration_s × NP × IF) / (FTP × 3600) × 100

    TSS quantifies training load:
    - < 150: Low (easy recovery next day)
    - 150-300: Medium (some residual fatigue)
    - 300-450: High (2+ days recovery)
    - > 450: Very high (extended recovery needed)

    Args:
        np_watts: Normalized Power in watts.
        ftp: Functional Threshold Power in watts.
        duration_s: Duration in seconds.

    Returns:
        Training Stress Score.
    """
    if ftp <= 0 or duration_s <= 0:
        return 0.0

    intensity_factor = np_watts / ftp
    tss = (duration_s * np_watts * intensity_factor) / (ftp * 3600) * 100

    return tss
