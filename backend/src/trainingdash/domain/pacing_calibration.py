"""
Pacing coefficient calibration from real ride data.

Extracts grade-power relationships from activities to personalize pacing models.
Uses weighted linear regression to fit climb coefficients and statistical analysis
for descent parameters.

The fitted coefficients flow into the shared PacingCoefficients
(pacing_model.py) via the calibration use case; this module owns only
the fitting math over primitive samples.
"""

from dataclasses import dataclass

import numpy as np

from trainingdash.domain.pacing_model import (
    GRADE_POWER_INTERCEPT as DEFAULT_GRADE_POWER_INTERCEPT,
)
from trainingdash.domain.pacing_model import (
    GRADE_POWER_SLOPE as DEFAULT_GRADE_POWER_SLOPE,
)
from trainingdash.domain.pacing_model import (
    PacingCoefficients as ModelCoefficients,
)
from trainingdash.domain.pacing_model import (
    calculate_curvature_menger as _calculate_curvature,
)

# Fallback defaults for descent parameters (single source: pacing_model defaults)
_DEFAULT_COEFFS = ModelCoefficients()
DEFAULT_MAX_DESCENT_SPEED_MPS = _DEFAULT_COEFFS.max_descent_speed_mps
DEFAULT_DESCENT_POWER_MULTIPLIER = _DEFAULT_COEFFS.descent_power_multiplier
DEFAULT_CURVATURE_SPEED_COEFFICIENT = _DEFAULT_COEFFS.curvature_speed_coefficient

# Minimum samples required for regression
MIN_CLIMB_SAMPLES = 500  # ~8 minutes of climb data
MIN_DESCENT_SAMPLES = 300  # ~5 minutes of descent data
MIN_ACTIVITIES = 3  # Minimum activities to calibrate

# Fit quality gate (ADR 0005): a grade-power regression this weak describes
# noise, not riding behavior. Storing it poisons every subsequent plan
# (the reference data produced R²=0.009 → "pedal hard downhill" plans).
MIN_CLIMB_R_SQUARED = 0.25

# Descent multiplier bounds (ADR 0005 #634): riders coast descents (~0.0-0.3)
# or pedal them (~0.5-0.8); a fitted value outside this band means bad data.
MAX_DESCENT_POWER_MULT = 0.8


@dataclass
class GradePowerSample:
    """A single sample of grade and power multiplier."""

    grade_pct: float
    power_mult: float
    time_weight: float  # Seconds at this grade


def pedaling_average_power(records: list) -> float | None:
    """Average power over samples where the rider is pedaling (power > 0).

    The whole-ride average includes 0W coasting time, which dilutes the
    normalizer and poisons the grade-power fit (ADR 0005): a rider pushing
    260W on climbs of an 82%-pedaling ride would show power_mult 1.4+ when
    normalized by the whole-ride average. Normalizing by pedaling-time
    average lets the coefficients describe *pedaling shape*; coasting is
    the descent multiplier's business.

    Returns None when the rider never pedals (no usable normalizer).
    """
    pedaling = [r.power_w for r in records if r.power_w is not None and r.power_w > 0]
    if not pedaling:
        return None
    return sum(pedaling) / len(pedaling)


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

    Curvature uses distance-anchored triples (~25m spacing, the same
    baseline as the runtime resampler). Consecutive records (~5m apart)
    are too close: ±3m GPS jitter turns straight roads into apparent
    R<100m corners, saturating kappa and poisoning the a_lat fit
    (discovered during B3 recalibration, ADR 0004).

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

    # Distance-anchored curvature triple: keep TWO walking indices so the
    # three curvature points are evenly spaced (~50m / ~25m / 0m behind the
    # current record). Menger curvature divides by the shortest triangle
    # side, so a degenerate triple (50m, 5m, 43m) lets GPS noise on the
    # middle point saturate kappa; evenly spaced triples condition the
    # noise floor to kappa ~0.003 at ±3m jitter while real corners
    # (R <= 200m) read at kappa >= 0.005.
    CURVATURE_ANCHOR_M = 50.0
    anchor_a = 0  # ~50m behind
    anchor_b = 0  # ~25m behind

    for i in range(2, len(valid)):
        curr = valid[i]

        # Advance curvature anchors (evenly spaced triples)
        while anchor_a < i - 2 and curr.distance_m - valid[anchor_a].distance_m > 2 * CURVATURE_ANCHOR_M:
            anchor_a += 1
        while anchor_b < i - 2 and curr.distance_m - valid[anchor_b].distance_m > CURVATURE_ANCHOR_M:
            anchor_b += 1
        if anchor_b <= anchor_a:
            anchor_b = min(anchor_a + 1, i - 1)

        prev2 = valid[anchor_a]
        prev = valid[i - 1]
        curv_mid = valid[anchor_b]

        # Skip samples whose curvature baseline is too short (start of ride)
        if curr.distance_m - prev2.distance_m < CURVATURE_ANCHOR_M:
            continue

        # Distance and elevation deltas (record resolution for speed/grade)
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
        power_mult = power / avg_power if avg_power > 0 and power > 0 else 0.0

        # Curvature from the evenly spaced triple
        curvature = _calculate_curvature(prev2.lat, prev2.lon, curv_mid.lat, curv_mid.lon, curr.lat, curr.lon)

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

    The curvature coefficient is a_lat (m/s²): the lateral acceleration the
    rider held through corners, computed per sample as v²·κ (the cornering
    limit v = sqrt(a_lat/kappa) rearranged). The weighted mean across
    corner samples estimates the rider's comfort limit (ADR 0004 Phase B3).

    Returns:
        Tuple of (max_descent_speed, power_multiplier, a_lat, confidence)
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

    # a_lat: lateral acceleration the rider demonstrates holding through
    # corners, v²·kappa per sample. Along a corner, v²·k varies (braking in,
    # accelerating out), so the weighted MEAN measures average cornering
    # intensity — which underestimates the limit the cornering model needs.
    # The time-weighted p90 captures the demonstrated maximum while staying
    # robust to noise (calibration found the mean sat at only the ~67th
    # percentile, predicting 19 km/h hairpins for a rider who rides them at
    # 30+). Only corner samples (curvature above the noise floor) inform it.
    corner_mask = curvatures > 1e-4  # tighter than a 10km-radius "corner"
    if np.any(corner_mask):
        corner_speeds = speeds[corner_mask]
        corner_kappas = curvatures[corner_mask]
        corner_weights = weights[corner_mask]
        a_lat_samples = corner_speeds**2 * corner_kappas
        order = np.argsort(a_lat_samples)
        cum_weights = np.cumsum(corner_weights[order]) / np.sum(corner_weights)
        p90_idx = int(np.searchsorted(cum_weights, 0.90))
        p90_idx = min(p90_idx, len(order) - 1)
        curv_coef = float(a_lat_samples[order][p90_idx])
    else:
        curv_coef = DEFAULT_CURVATURE_SPEED_COEFFICIENT

    # Confidence based on sample count
    confidence = min(1.0, len(samples) / 1000)

    # Clamp to reasonable bounds. The descent power multiplier floor is 0.0:
    # coasting riders hold ~0.0-0.1 of base power on descents (ADR 0005
    # #634), and clamping them to 0.2 would plan soft-pedaling they don't do.
    max_descent_speed = max(10.0, min(25.0, max_descent_speed))
    power_mult = max(0.0, min(MAX_DESCENT_POWER_MULT, power_mult))
    curv_coef = max(1.0, min(8.0, curv_coef))

    return max_descent_speed, power_mult, curv_coef, confidence


def fit_descent_coefficients_or_none(
    samples: list[DescentSample],
) -> tuple[float, float, float, float] | None:
    """
    Fit descent coefficients, returning None when the data can't support a fit.

    The descent-side quality gate (ADR 0005 #634): fewer than
    MIN_DESCENT_SAMPLES samples → None (uncalibrated). Unlike the climb
    gate, no R² exists here — a time-weighted mean of held power needs
    volume, not correlation. The caller decides what "None" means for the
    stored row (use case keeps prior values / falls back to defaults).

    Returns:
        Tuple of (max_descent_speed, power_multiplier, a_lat, confidence)
        or None when the sample volume is below the floor.
    """
    if len(samples) < MIN_DESCENT_SAMPLES:
        return None
    return fit_descent_coefficients(samples)


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

    # Quality gate (ADR 0005): a weak grade-power fit describes noise.
    # Keep the previously stored coefficients rather than poisoning plans.
    if r_squared < MIN_CLIMB_R_SQUARED:
        return None

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
