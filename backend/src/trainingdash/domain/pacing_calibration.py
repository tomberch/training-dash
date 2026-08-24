"""
Pacing coefficient calibration from real ride data.

Extracts grade-power relationships from activities to personalize pacing models.
Uses weighted linear regression to fit climb coefficients and statistical analysis
for descent parameters.
"""

from dataclasses import dataclass

import numpy as np

# Global defaults (fallback when no personalized coefficients exist)
DEFAULT_GRADE_POWER_INTERCEPT = 1.10
DEFAULT_GRADE_POWER_SLOPE = 0.035
DEFAULT_MAX_DESCENT_SPEED_MPS = 18.0
DEFAULT_DESCENT_POWER_MULTIPLIER = 0.50
DEFAULT_CURVATURE_SPEED_COEFFICIENT = -68.0

# Minimum samples required for regression
MIN_CLIMB_SAMPLES = 500  # ~8 minutes of climb data
MIN_DESCENT_SAMPLES = 300  # ~5 minutes of descent data
MIN_ACTIVITIES = 3  # Minimum activities to calibrate


@dataclass
class GradePowerSample:
    """A single sample of grade and power multiplier."""

    grade_pct: float
    power_mult: float
    time_weight: float  # Seconds at this grade


@dataclass
class DescentSample:
    """A single sample of descent behavior."""

    grade_pct: float  # Negative for descents
    speed_mps: float
    power_mult: float
    curvature: float  # Curvature of the road (1/radius)
    time_weight: float


@dataclass
class CalibrationResult:
    """Result of pacing coefficient calibration."""

    # Climb coefficients
    grade_power_intercept: float
    grade_power_slope: float

    # Descent coefficients
    max_descent_speed_mps: float
    descent_power_multiplier: float
    curvature_speed_coefficient: float

    # Metadata
    climb_sample_count: int
    descent_sample_count: int
    activity_count: int

    # Quality metrics
    climb_r_squared: float
    descent_confidence: float


@dataclass
class PacingCoefficients:
    """Current pacing coefficients (from DB or defaults)."""

    grade_power_intercept: float
    grade_power_slope: float
    max_descent_speed_mps: float
    descent_power_multiplier: float
    curvature_speed_coefficient: float
    climb_sample_count: int
    descent_sample_count: int
    activity_count: int

    @classmethod
    def defaults(cls) -> "PacingCoefficients":
        """Return global defaults."""
        return cls(
            grade_power_intercept=DEFAULT_GRADE_POWER_INTERCEPT,
            grade_power_slope=DEFAULT_GRADE_POWER_SLOPE,
            max_descent_speed_mps=DEFAULT_MAX_DESCENT_SPEED_MPS,
            descent_power_multiplier=DEFAULT_DESCENT_POWER_MULTIPLIER,
            curvature_speed_coefficient=DEFAULT_CURVATURE_SPEED_COEFFICIENT,
            climb_sample_count=0,
            descent_sample_count=0,
            activity_count=0,
        )

    @classmethod
    def from_db_model(cls, model: "DBPacingCoefficients") -> "PacingCoefficients":
        """Convert from SQLAlchemy model."""
        return cls(
            grade_power_intercept=float(model.grade_power_intercept),
            grade_power_slope=float(model.grade_power_slope),
            max_descent_speed_mps=float(model.max_descent_speed_mps),
            descent_power_multiplier=float(model.descent_power_multiplier),
            curvature_speed_coefficient=float(model.curvature_speed_coefficient),
            climb_sample_count=model.climb_sample_count,
            descent_sample_count=model.descent_sample_count,
            activity_count=model.activity_count,
        )


# Type alias for DB model (avoid circular import)
DBPacingCoefficients = object


def extract_climb_samples(
    records: list,
    avg_power: float,
    min_grade: float = 1.0,
    max_grade: float = 20.0,
) -> list[GradePowerSample]:
    """
    Extract climb samples from activity records.

    Args:
        records: Activity records with power, altitude, distance, timestamp
        avg_power: Average power for the activity (for normalization)
        min_grade: Minimum grade to include (default 1%)
        max_grade: Maximum grade to include (default 20%, beyond is unrealistic)

    Returns:
        List of GradePowerSample objects for climb segments
    """
    samples = []

    # Filter valid records
    valid = [
        r
        for r in records
        if r.power_w is not None
        and r.power_w > 0
        and r.altitude_m is not None
        and r.distance_m is not None
        and r.timestamp is not None
    ]

    if len(valid) < 10:
        return samples

    # Sort by timestamp
    valid = sorted(valid, key=lambda r: r.timestamp)

    for i in range(1, len(valid)):
        prev = valid[i - 1]
        curr = valid[i]

        # Distance delta
        distance_delta = curr.distance_m - prev.distance_m
        if distance_delta < 1:
            continue

        # Elevation delta and grade
        elevation_delta = curr.altitude_m - prev.altitude_m
        grade_pct = (elevation_delta / distance_delta) * 100

        # Only include climbs in valid range
        if grade_pct < min_grade or grade_pct > max_grade:
            continue

        # Time delta
        time_delta = max(0.5, min(10, (curr.timestamp - prev.timestamp).total_seconds()))

        # Power for this segment
        power = (prev.power_w + curr.power_w) / 2
        power_mult = power / avg_power if avg_power > 0 else 1.0

        # Clamp unrealistic power multipliers
        if power_mult < 0.3 or power_mult > 3.0:
            continue

        samples.append(
            GradePowerSample(
                grade_pct=grade_pct,
                power_mult=power_mult,
                time_weight=time_delta,
            )
        )

    return samples


def extract_descent_samples(
    records: list,
    avg_power: float,
    min_grade: float = -3.0,  # Descents are negative
    max_grade: float = -20.0,
) -> list[DescentSample]:
    """
    Extract descent samples from activity records.

    Args:
        records: Activity records with power, speed, altitude, position
        avg_power: Average power for the activity
        min_grade: Minimum grade (most shallow descent, e.g., -3%)
        max_grade: Maximum grade (steepest descent, e.g., -20%)

    Returns:
        List of DescentSample objects
    """
    samples = []

    # Filter valid records
    valid = [
        r
        for r in records
        if r.power_w is not None
        and r.altitude_m is not None
        and r.distance_m is not None
        and r.timestamp is not None
        and r.lat is not None
        and r.lon is not None
    ]

    if len(valid) < 10:
        return samples

    # Sort by timestamp
    valid = sorted(valid, key=lambda r: r.timestamp)

    for i in range(2, len(valid)):  # Need 3 points for curvature
        prev2 = valid[i - 2]
        prev = valid[i - 1]
        curr = valid[i]

        # Distance and elevation deltas
        distance_delta = curr.distance_m - prev.distance_m
        if distance_delta < 1:
            continue

        elevation_delta = curr.altitude_m - prev.altitude_m
        grade_pct = (elevation_delta / distance_delta) * 100

        # Only include descents
        if grade_pct > min_grade or grade_pct < max_grade:
            continue

        # Time delta
        time_delta = max(0.5, min(10, (curr.timestamp - prev.timestamp).total_seconds()))

        # Speed
        speed_mps = distance_delta / time_delta if time_delta > 0 else 0
        if speed_mps < 1 or speed_mps > 30:  # Skip unrealistic speeds
            continue

        # Power multiplier
        power = (prev.power_w + curr.power_w) / 2 if curr.power_w and prev.power_w else 0
        power_mult = power / avg_power if avg_power > 0 and power > 0 else 0.5

        # Curvature (approximate from 3 points)
        curvature = _calculate_curvature(prev2.lat, prev2.lon, prev.lat, prev.lon, curr.lat, curr.lon)

        samples.append(
            DescentSample(
                grade_pct=grade_pct,
                speed_mps=speed_mps,
                power_mult=power_mult,
                curvature=curvature,
                time_weight=time_delta,
            )
        )

    return samples


def _calculate_curvature(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    lat3: float,
    lon3: float,
) -> float:
    """
    Calculate curvature from three GPS points using Menger curvature.

    Returns curvature in 1/meters (0 = straight line, higher = tighter curve).
    """
    import math

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
        return 0

    curvature = (4 * area2) / (a * b * c)

    # Clamp to realistic values (0 to 0.01 = radius > 100m)
    return min(0.01, curvature)


def fit_climb_coefficients(
    samples: list[GradePowerSample],
) -> tuple[float, float, float]:
    """
    Fit grade-power relationship using weighted linear regression.

    Returns:
        Tuple of (intercept, slope, r_squared)
    """
    if len(samples) < MIN_CLIMB_SAMPLES:
        return DEFAULT_GRADE_POWER_INTERCEPT, DEFAULT_GRADE_POWER_SLOPE, 0.0

    grades = np.array([s.grade_pct for s in samples])
    power_mults = np.array([s.power_mult for s in samples])
    weights = np.array([s.time_weight for s in samples])

    # Weighted least squares
    W = np.sum(weights)
    sum_wx = np.sum(weights * grades)
    sum_wy = np.sum(weights * power_mults)
    sum_wxx = np.sum(weights * grades * grades)
    sum_wxy = np.sum(weights * grades * power_mults)

    denom = W * sum_wxx - sum_wx * sum_wx
    if abs(denom) < 1e-10:
        return DEFAULT_GRADE_POWER_INTERCEPT, DEFAULT_GRADE_POWER_SLOPE, 0.0

    slope = (W * sum_wxy - sum_wx * sum_wy) / denom
    intercept = (sum_wy - slope * sum_wx) / W

    # R-squared (coefficient of determination)
    y_mean = sum_wy / W
    ss_tot = np.sum(weights * (power_mults - y_mean) ** 2)
    y_pred = intercept + slope * grades
    ss_res = np.sum(weights * (power_mults - y_pred) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Clamp to reasonable bounds
    intercept = max(0.8, min(1.3, intercept))
    slope = max(0.02, min(0.08, slope))

    return intercept, slope, r_squared


def fit_descent_coefficients(
    samples: list[DescentSample],
) -> tuple[float, float, float, float]:
    """
    Fit descent coefficients from samples.

    Returns:
        Tuple of (max_descent_speed, power_multiplier, curvature_coefficient, confidence)
    """
    if len(samples) < MIN_DESCENT_SAMPLES:
        return (
            DEFAULT_MAX_DESCENT_SPEED_MPS,
            DEFAULT_DESCENT_POWER_MULTIPLIER,
            DEFAULT_CURVATURE_SPEED_COEFFICIENT,
            0.0,
        )

    speeds = np.array([s.speed_mps for s in samples])
    power_mults = np.array([s.power_mult for s in samples])
    curvatures = np.array([s.curvature for s in samples])
    weights = np.array([s.time_weight for s in samples])

    # Max descent speed: 95th percentile of observed speeds
    # (accounts for real comfort/skill limits)
    max_descent_speed = np.percentile(speeds, 95)

    # Average power multiplier on descents (weighted)
    power_mult = np.sum(power_mults * weights) / np.sum(weights)

    # Curvature coefficient: how much speed decreases per unit curvature
    # Linear regression: speed = a - b * curvature
    # We're interested in the slope (b), which should be negative
    if np.std(curvatures) > 0.0001:  # Only if there's curvature variance
        W = np.sum(weights)
        sum_wc = np.sum(weights * curvatures)
        sum_ws = np.sum(weights * speeds)
        sum_wcc = np.sum(weights * curvatures * curvatures)
        sum_wcs = np.sum(weights * curvatures * speeds)

        denom = W * sum_wcc - sum_wc * sum_wc
        if abs(denom) > 1e-10:
            curv_coef = (W * sum_wcs - sum_wc * sum_ws) / denom
        else:
            curv_coef = DEFAULT_CURVATURE_SPEED_COEFFICIENT
    else:
        curv_coef = DEFAULT_CURVATURE_SPEED_COEFFICIENT

    # Confidence based on sample count
    confidence = min(1.0, len(samples) / 1000)

    # Clamp to reasonable bounds
    max_descent_speed = max(10.0, min(25.0, max_descent_speed))
    power_mult = max(0.2, min(0.8, power_mult))
    curv_coef = max(-150.0, min(-20.0, curv_coef))

    return max_descent_speed, power_mult, curv_coef, confidence


def calibrate_coefficients(
    climb_samples: list[GradePowerSample],
    descent_samples: list[DescentSample],
    activity_count: int,
) -> CalibrationResult | None:
    """
    Calibrate all pacing coefficients from accumulated samples.

    Returns:
        CalibrationResult if enough data, None if insufficient samples
    """
    if len(climb_samples) < MIN_CLIMB_SAMPLES and len(descent_samples) < MIN_DESCENT_SAMPLES:
        return None

    if activity_count < MIN_ACTIVITIES:
        return None

    # Fit climb coefficients
    intercept, slope, r_squared = fit_climb_coefficients(climb_samples)

    # Fit descent coefficients
    max_speed, power_mult, curv_coef, descent_conf = fit_descent_coefficients(descent_samples)

    return CalibrationResult(
        grade_power_intercept=intercept,
        grade_power_slope=slope,
        max_descent_speed_mps=max_speed,
        descent_power_multiplier=power_mult,
        curvature_speed_coefficient=curv_coef,
        climb_sample_count=len(climb_samples),
        descent_sample_count=len(descent_samples),
        activity_count=activity_count,
        climb_r_squared=r_squared,
        descent_confidence=descent_conf,
    )
