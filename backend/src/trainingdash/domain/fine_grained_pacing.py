"""
Fine-grained pacing for accurate speed and time predictions.

This module implements BestBikeSplit-style pacing with ~25m resolution,
running physics calculations at each point for accurate speed predictions.

Key insight: Coarse segments (500m+) average out terrain, leading to
inaccurate speed predictions because:
- Speed at 8% grade: ~12 km/h
- Speed at 2% grade: ~28 km/h
- Average of speeds ≠ Speed at average grade

Fine-grained resolution (25m) captures the actual terrain profile,
yielding much more accurate segment times and overall predictions.

Architecture:
1. Resample elevation profile to consistent ~25m intervals
2. Calculate grade at each point
3. Calculate curvature at each point (for descent speed reduction)
4. Apply terrain-adapted power targets (using personalized coefficients)
5. Run physics model to get speed at each point
6. Apply curvature factor to descent speeds
7. Integrate for segment times
8. Aggregate back to display segments (~50-100 for UI)
"""

import math
from dataclasses import dataclass

import numpy as np

from trainingdash.domain.pacing_model import (
    DEFAULT_RIDER_CDA,
    DEFAULT_RIDER_CRR,
    DEFAULT_RIDER_MASS_KG,
    PacingCoefficients,
    calculate_curvature_menger,
    calculate_normalized_power,
    cornering_speed_limit,
    effective_a_lat,
    get_grade_power_multiplier,
)
from trainingdash.domain.physics import (
    EnvironmentParams,
    RiderParams,
    air_density_from_altitude,
    calculate_bearing,
    calculate_headwind,
    speed_from_power,
)

# Braking deceleration used by the look-ahead envelope (B2).
# ~4 m/s² is a firm but realistic road-braking deceleration; riders brake
# harder in emergencies but this models sustainable braking into corners.
BRAKE_DECEL_MPS2 = 4.0

# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class FineGrainedPoint:
    """A single point in the fine-grained profile."""

    distance_m: float
    elevation_m: float
    grade_pct: float
    lat: float | None = None
    lon: float | None = None
    # Menger curvature in 1/m (0 = straight, None = no GPS data).
    # Same definition calibration fits — single definition per ADR 0004.
    curvature_1_m: float | None = None


@dataclass
class FineGrainedTarget:
    """Power and speed target at a fine-grained point."""

    distance_m: float
    grade_pct: float
    power_w: float
    speed_mps: float
    time_s: float  # Time to traverse from this point to next


@dataclass
class FineGrainedPlan:
    """Complete fine-grained pacing plan."""

    points: list[FineGrainedTarget]
    total_time_s: float
    total_distance_m: float
    avg_power_w: float
    normalized_power_w: float
    # Per-second power samples for detailed analysis
    power_samples: np.ndarray


# =============================================================================
# Curvature Calculation (shared Menger definition from pacing_model)
# =============================================================================


def calculate_curvature(
    points: list[FineGrainedPoint],
) -> list[float | None]:
    """
    Calculate Menger curvature (1/m) at each point from GPS coordinates.

    Uses the shared definition in pacing_model.calculate_curvature_menger —
    the same function calibration's descent extractor uses (ADR 0004).

    Args:
        points: Fine-grained points with lat/lon coordinates

    Returns:
        List of curvature values (1/m) for each point; None where GPS is
        missing (cornering limit then cannot apply — grade-only physics).
    """
    n = len(points)
    curvatures: list[float | None] = [0.0] * n

    if n < 3:
        return curvatures

    # Check if we have GPS data
    has_gps = all(p.lat is not None and p.lon is not None for p in points[:3])
    if not has_gps:
        return [None] * n

    for i in range(1, n - 1):
        prev_pt = points[i - 1]
        curr_pt = points[i]
        next_pt = points[i + 1]

        # Skip if any point missing GPS
        if any(p.lat is None or p.lon is None for p in [prev_pt, curr_pt, next_pt]):
            curvatures[i] = None
            continue

        curvatures[i] = calculate_curvature_menger(
            prev_pt.lat,
            prev_pt.lon,
            curr_pt.lat,
            curr_pt.lon,
            next_pt.lat,
            next_pt.lon,
        )

    # First and last points inherit from neighbors
    if n >= 2:
        curvatures[0] = curvatures[1]
        curvatures[-1] = curvatures[-2]

    return curvatures


# =============================================================================
# Elevation Profile Resampling
# =============================================================================


def resample_elevation_profile(
    elevation_profile: list[dict],
    target_spacing_m: float = 25.0,
) -> list[FineGrainedPoint]:
    """
    Resample elevation profile to consistent spacing.

    The input elevation_profile comes from RaceCourse.elevation_profile,
    which has variable spacing (typically 5-10m from GPS data). This
    function resamples to consistent intervals for predictable physics
    calculations.

    Args:
        elevation_profile: List of dicts with 'distance_m', 'elevation_m', 'grade_pct',
                          and optionally 'lat', 'lon' for curvature calculation
        target_spacing_m: Target spacing between points (default 25m)

    Returns:
        List of FineGrainedPoint at consistent intervals, with curvature calculated
    """
    if not elevation_profile:
        return []

    # Extract arrays from profile
    distances = np.array([p["distance_m"] for p in elevation_profile])
    elevations = np.array([p["elevation_m"] for p in elevation_profile])

    # Check for lat/lon data
    has_gps = "lat" in elevation_profile[0] and elevation_profile[0]["lat"] is not None
    if has_gps:
        lats = np.array([p.get("lat", 0) or 0 for p in elevation_profile])
        lons = np.array([p.get("lon", 0) or 0 for p in elevation_profile])
    else:
        lats = None
        lons = None

    if len(distances) < 2:
        return []

    # Create new distance array at target spacing
    total_distance = distances[-1]
    n_points = max(2, int(np.ceil(total_distance / target_spacing_m)) + 1)
    new_distances = np.linspace(0, total_distance, n_points)

    # Interpolate elevations at new distances
    new_elevations = np.interp(new_distances, distances, elevations)

    # Interpolate lat/lon if available
    if has_gps:
        new_lats = np.interp(new_distances, distances, lats)
        new_lons = np.interp(new_distances, distances, lons)
    else:
        new_lats = None
        new_lons = None

    # Smooth elevations slightly to reduce GPS noise
    # Use a small window (3 points = ~75m) to preserve real terrain features
    if len(new_elevations) >= 3:
        kernel = np.array([0.25, 0.5, 0.25])
        # Pad to handle edges
        padded = np.pad(new_elevations, (1, 1), mode="edge")
        smoothed = np.convolve(padded, kernel, mode="valid")
        new_elevations = smoothed

    # Calculate grades between points
    points: list[FineGrainedPoint] = []
    for i in range(len(new_distances)):
        if i < len(new_distances) - 1:
            delta_dist = new_distances[i + 1] - new_distances[i]
            delta_elev = new_elevations[i + 1] - new_elevations[i]
            grade_pct = (delta_elev / delta_dist) * 100 if delta_dist > 0 else 0.0
        else:
            # Last point: use previous grade
            grade_pct = points[-1].grade_pct if points else 0.0

        lat = float(new_lats[i]) if new_lats is not None else None
        lon = float(new_lons[i]) if new_lons is not None else None

        points.append(
            FineGrainedPoint(
                distance_m=new_distances[i],
                elevation_m=new_elevations[i],
                grade_pct=grade_pct,
                lat=lat,
                lon=lon,
            )
        )

    # Calculate curvature for each point
    curvatures = calculate_curvature(points)
    for i, curv in enumerate(curvatures):
        points[i].curvature_1_m = curv

    return points


# =============================================================================
# Power Target Calculation
# =============================================================================


def calculate_power_targets(
    points: list[FineGrainedPoint],
    base_power_w: float,
    grade_power_intercept: float = 1.10,
    grade_power_slope: float = 0.035,
    power_cap_w: float | None = None,
) -> list[float]:
    """
    Calculate terrain-adapted power targets at each point.

    Uses the continuous grade-power formula from pacing_model (single home
    of the formula per ADR 0004):
        power_mult = intercept + slope × grade%

    This captures natural riding behavior where riders push harder
    on climbs (low aero drag, efficient) and ease off on descents.

    Args:
        points: Fine-grained elevation points
        base_power_w: Base power (FTP × target_intensity)
        grade_power_intercept: Base multiplier at 0% grade (default 1.10)
        grade_power_slope: Additional multiplier per 1% grade (default 0.035)
        power_cap_w: Maximum power (e.g., FTP × 1.05). None = no cap.

    Returns:
        List of power targets in watts, one per point
    """
    # Shared coefficients object so the formula (including clamps) has one home
    coefficients = PacingCoefficients(
        grade_power_intercept=grade_power_intercept,
        grade_power_slope=grade_power_slope,
    )

    powers: list[float] = []

    for point in points:
        # Calculate power multiplier based on grade (shared formula)
        multiplier = get_grade_power_multiplier(point.grade_pct, coefficients)

        # Apply power cap if specified
        power = base_power_w * multiplier
        if power_cap_w is not None:
            power = min(power, power_cap_w)

        powers.append(max(0.0, power))

    return powers


# =============================================================================
# Speed and Time Calculation
# =============================================================================


# =============================================================================
# Per-point Environment (wind decomposition + altitude density)
# =============================================================================


def _point_bearings(points: list[FineGrainedPoint]) -> list[float | None]:
    """Travel bearing (degrees) at each point, from GPS track.

    Bearing at point i is the direction from point i-1 to point i (the
    direction of travel arriving there). None where GPS is missing.
    """
    bearings: list[float | None] = [None] * len(points)
    for i in range(1, len(points)):
        prev_pt, curr_pt = points[i - 1], points[i]
        if prev_pt.lat is None or prev_pt.lon is None or curr_pt.lat is None or curr_pt.lon is None:
            continue
        bearings[i] = calculate_bearing(prev_pt.lat, prev_pt.lon, curr_pt.lat, curr_pt.lon)
    # First point inherits the second's bearing (same direction of travel)
    if len(points) >= 2 and bearings[1] is not None:
        bearings[0] = bearings[1]
    return bearings


def _point_env(
    point: FineGrainedPoint,
    base_env: EnvironmentParams,
    wind_speed_mps: float | None,
    wind_direction_deg: float | None,
    rho_sea_level: float,
    bearing_deg: float | None,
) -> EnvironmentParams:
    """Environment for one fine-grained point: altitude density + headwind."""
    # Air density: scale the forecast/sea-level density by the ISA ratio at
    # this point's elevation (only when the point knows its elevation).
    air_density = base_env.air_density
    air_density = base_env.air_density * (air_density_from_altitude(point.elevation_m) / rho_sea_level)

    # Headwind: decompose meteorological wind onto the travel bearing
    headwind = base_env.wind_speed_mps
    if wind_speed_mps and bearing_deg is not None and wind_direction_deg is not None:
        headwind = calculate_headwind(wind_speed_mps, wind_direction_deg, bearing_deg)

    return EnvironmentParams(air_density=air_density, wind_speed_mps=headwind)


def calculate_speeds_and_times(
    points: list[FineGrainedPoint],
    powers: list[float],
    rider_params: RiderParams,
    env_params: EnvironmentParams | None = None,
    max_descent_speed_mps: float = 18.0,
    ride_type: str = "training",
    descent_aggressiveness: int = 70,
    wind_speed_mps: float | None = None,
    wind_direction_deg: float | None = None,
    coefficients: "PacingCoefficients | None" = None,
) -> tuple[list[float], list[float]]:
    """
    Calculate speed and segment time at each point using physics model.

    Runs the Newton-Raphson solver at each point to find the speed
    that corresponds to the given power output on the given grade.

    Applies the cornering-speed limit v = sqrt(a_lat / kappa) on descents
    (B1, ADR 0004): curvature is Menger 1/m, a_lat comes from
    descent_aggressiveness (or calibration, once B3 fits it). Points
    without curvature data (no GPS) get pure grade-based physics.

    Per-point conditions (B-wind/B-density, ADR 0004): air density follows
    the point's elevation (ISA ratio on the provided env density); wind
    decomposes per point from GPS bearings. Points without GPS use the
    uniform base env.

    Args:
        points: Fine-grained elevation points (with curvature)
        powers: Power target at each point (same length as points)
        rider_params: Rider and bike physical parameters
        env_params: Environmental conditions (air density, wind)
        max_descent_speed_mps: Cap descent speeds to this value
        ride_type: "training" or "race" (accepted for interface compat; the
            cornering limit is driven by descent_aggressiveness)
        descent_aggressiveness: 0-100; fallback for a_lat when uncalibrated
        wind_speed_mps: Meteorological wind speed (direction it comes FROM
            decomposed per point). None/0 = no wind.
        wind_direction_deg: Meteorological wind direction (FROM, degrees).
        coefficients: Personalized coefficients; a fitted a_lat
            (curvature_speed_coefficient with activity_count > 0) overrides
            the descent_aggressiveness mapping (B3).

    Returns:
        Tuple of (speeds, times) where:
        - speeds: Speed in m/s at each point
        - times: Time in seconds to traverse from each point to next
    """
    if env_params is None:
        env_params = EnvironmentParams()

    a_lat = effective_a_lat(coefficients, descent_aggressiveness)

    # Per-point environment: air density scales with point elevation (ISA
    # ratio against sea level); headwind decomposes from the point's travel
    # bearing. Points without GPS use the uniform env as-is.
    rho_sea_level = air_density_from_altitude(0.0)
    bearings = _point_bearings(points)

    # --- Forward pass: physics speed, capped by cornering limit (B1) --------
    speeds: list[float] = []
    for i, (point, power) in enumerate(zip(points, powers)):
        point_env = _point_env(
            point,
            base_env=env_params,
            wind_speed_mps=wind_speed_mps,
            wind_direction_deg=wind_direction_deg,
            rho_sea_level=rho_sea_level,
            bearing_deg=bearings[i],
        )

        speed = speed_from_power(
            power_w=power,
            grade_pct=point.grade_pct,
            rider=rider_params,
            env=point_env,
            max_descent_speed_mps=max_descent_speed_mps,
        )

        # Cornering-speed limit on curved points (any grade: corners bind
        # on flat approaches too, though they bind hardest on descents)
        if point.curvature_1_m:
            limit = cornering_speed_limit(point.curvature_1_m, a_lat)
            speed = min(speed, limit)

        speeds.append(max(0.5, speed))

    # --- Backward pass: braking envelope (B2, ADR 0004) --------------------
    # You cannot arrive at point i faster than the NEXT point's speed
    # permits given one spacing of braking: v[i]² ≤ v[i+1]² + 2·a_brake·d.
    # The loop is now stateful — speed depends on what lies ahead — so
    # braking starts *before* corners instead of at them.
    a_brake = BRAKE_DECEL_MPS2
    for i in range(len(points) - 2, -1, -1):
        spacing = points[i + 1].distance_m - points[i].distance_m
        if spacing <= 0:
            continue
        v_allowed = math.sqrt(speeds[i + 1] ** 2 + 2 * a_brake * spacing)
        if speeds[i] > v_allowed:
            speeds[i] = v_allowed

    # --- Times from final speeds -------------------------------------------
    times: list[float] = []
    for i in range(len(points)):
        if i < len(points) - 1:
            segment_distance = points[i + 1].distance_m - points[i].distance_m
            segment_time = segment_distance / speeds[i] if speeds[i] > 0 else 0
        else:
            segment_time = 0.0
        times.append(segment_time)

    return speeds, times


# =============================================================================
# Normalized Power Calculation
# =============================================================================


def calculate_np_from_fine_grained(
    powers: list[float],
    times: list[float],
) -> tuple[float, np.ndarray]:
    """
    Calculate Normalized Power from fine-grained power profile.

    Expands the variable power profile into per-second samples,
    then applies the standard NP algorithm:
        NP = (mean(rolling_30s_power^4))^0.25

    This gives accurate NP because the power actually varies across
    the fine-grained segments, unlike coarse segments where power
    is assumed constant within each segment.

    Args:
        powers: Power at each fine-grained point
        times: Time to traverse from each point to next

    Returns:
        Tuple of (normalized_power, power_samples) where:
        - normalized_power: NP in watts
        - power_samples: Per-second power array for detailed analysis
    """
    if not powers or not times:
        return 0.0, np.array([])

    # Expand to per-second samples
    power_samples: list[float] = []
    for power, time in zip(powers, times):
        n_seconds = max(1, int(round(time)))
        power_samples.extend([power] * n_seconds)

    if len(power_samples) < 30:
        # Too short for proper NP
        avg = sum(p * t for p, t in zip(powers, times)) / sum(times) if sum(times) > 0 else 0
        return avg, np.array(power_samples)

    samples = np.array(power_samples)

    # NP via the shared core (30s rolling, 4th-power mean)
    np_power = calculate_normalized_power(samples, sample_rate_hz=1.0)

    return np_power, samples


# =============================================================================
# Main Entry Point
# =============================================================================


def generate_fine_grained_plan(
    elevation_profile: list[dict],
    rider_ftp: float,
    target_intensity: float = 0.85,
    rider_params: RiderParams | None = None,
    env_params: EnvironmentParams | None = None,
    grade_power_intercept: float = 1.10,
    grade_power_slope: float = 0.035,
    max_descent_speed_mps: float = 18.0,
    power_cap_ftp_pct: float = 1.05,
    target_spacing_m: float = 25.0,
    ride_type: str = "training",
    descent_aggressiveness: int = 70,
    wind_speed_mps: float | None = None,
    wind_direction_deg: float | None = None,
    coefficients: "PacingCoefficients | None" = None,
) -> FineGrainedPlan:
    """
    Generate a fine-grained pacing plan with accurate speed predictions.

    This is the main entry point for fine-grained pacing. It:
    1. Resamples the elevation profile to consistent ~25m intervals
    2. Calculates Menger curvature (1/m) at each point from GPS coordinates
    3. Calculates terrain-adapted power targets at each point
    4. Runs the physics model to get speed at each point
    5. Applies the cornering-speed limit v = sqrt(a_lat / kappa) (B1)
    6. Calculates NP from the actual variable power profile

    Args:
        elevation_profile: Course elevation profile (from RaceCourse.elevation_profile)
                          Should include 'lat', 'lon' for curvature calculation
        rider_ftp: Rider's Functional Threshold Power in watts
        target_intensity: Target IF (0.85 = tempo, 0.95 = threshold)
        rider_params: Rider/bike physical parameters. If None, uses defaults.
        env_params: Environmental conditions. If None, uses sea level.
        grade_power_intercept: Base power multiplier at 0% grade
        grade_power_slope: Additional multiplier per 1% grade
        max_descent_speed_mps: Cap descent speeds
        power_cap_ftp_pct: Cap power at this fraction of FTP
        target_spacing_m: Spacing between fine-grained points
        ride_type: "training" or "race" (interface compat; cornering is driven
                   by descent_aggressiveness)
        descent_aggressiveness: 0-100; maps to lateral acceleration a_lat for
                   the cornering limit (B1). Higher = faster through corners.
        wind_speed_mps: Meteorological wind speed (m/s); decomposed per point
                   from GPS bearings. None/0 = no wind.
        wind_direction_deg: Meteorological wind direction (FROM, degrees).

    Returns:
        FineGrainedPlan with per-point targets and aggregated metrics
    """
    # Default parameters
    if rider_params is None:
        rider_params = RiderParams(mass_kg=DEFAULT_RIDER_MASS_KG, cda=DEFAULT_RIDER_CDA, crr=DEFAULT_RIDER_CRR)
    if env_params is None:
        env_params = EnvironmentParams()

    # Step 1: Resample elevation profile (includes curvature calculation)
    points = resample_elevation_profile(elevation_profile, target_spacing_m)

    if not points:
        return FineGrainedPlan(
            points=[],
            total_time_s=0,
            total_distance_m=0,
            avg_power_w=0,
            normalized_power_w=0,
            power_samples=np.array([]),
        )

    # Step 2: Calculate power targets
    base_power = rider_ftp * target_intensity
    power_cap = rider_ftp * power_cap_ftp_pct

    powers = calculate_power_targets(
        points=points,
        base_power_w=base_power,
        grade_power_intercept=grade_power_intercept,
        grade_power_slope=grade_power_slope,
        power_cap_w=power_cap,
    )

    # Step 3: Calculate speeds and times (with cornering-speed limit)
    speeds, times = calculate_speeds_and_times(
        points=points,
        powers=powers,
        rider_params=rider_params,
        env_params=env_params,
        max_descent_speed_mps=max_descent_speed_mps,
        ride_type=ride_type,
        descent_aggressiveness=descent_aggressiveness,
        wind_speed_mps=wind_speed_mps,
        wind_direction_deg=wind_direction_deg,
    )

    # Step 4: Build fine-grained targets
    targets: list[FineGrainedTarget] = []
    for i, point in enumerate(points):
        targets.append(
            FineGrainedTarget(
                distance_m=point.distance_m,
                grade_pct=point.grade_pct,
                power_w=powers[i],
                speed_mps=speeds[i],
                time_s=times[i],
            )
        )

    # Step 5: Calculate aggregated metrics
    total_time = sum(times)
    total_distance = points[-1].distance_m if points else 0

    # Time-weighted average power
    total_energy = sum(p * t for p, t in zip(powers, times))
    avg_power = total_energy / total_time if total_time > 0 else 0

    # Step 6: Calculate NP from variable power profile
    np_power, power_samples = calculate_np_from_fine_grained(powers, times)

    return FineGrainedPlan(
        points=targets,
        total_time_s=total_time,
        total_distance_m=total_distance,
        avg_power_w=avg_power,
        normalized_power_w=np_power,
        power_samples=power_samples,
    )
