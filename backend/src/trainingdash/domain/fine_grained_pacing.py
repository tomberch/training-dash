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
from typing import Sequence

import numpy as np

from trainingdash.domain.physics import (
    EnvironmentParams,
    RiderParams,
    speed_from_power,
)


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
    curvature_deg_per_100m: float = 0.0  # Turn angle per 100m (0 = straight)


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
# Curvature Calculation
# =============================================================================


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing between two points in radians."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.atan2(x, y)


def _angle_diff(a1: float, a2: float) -> float:
    """Smallest angle difference in radians (unsigned)."""
    diff = a2 - a1
    while diff > math.pi:
        diff -= 2 * math.pi
    while diff < -math.pi:
        diff += 2 * math.pi
    return abs(diff)


def calculate_curvature(
    points: list[FineGrainedPoint],
) -> list[float]:
    """
    Calculate curvature at each point from GPS coordinates.
    
    Curvature is measured as degrees of turn per 100m of distance.
    Higher values indicate sharper turns (hairpins, switchbacks).
    
    Args:
        points: Fine-grained points with lat/lon coordinates
        
    Returns:
        List of curvature values (degrees per 100m) for each point
    """
    n = len(points)
    curvatures = [0.0] * n
    
    if n < 3:
        return curvatures
    
    # Check if we have GPS data
    has_gps = all(p.lat is not None and p.lon is not None for p in points[:3])
    if not has_gps:
        return curvatures
    
    for i in range(1, n - 1):
        prev_pt = points[i - 1]
        curr_pt = points[i]
        next_pt = points[i + 1]
        
        # Skip if any point missing GPS
        if any(p.lat is None or p.lon is None for p in [prev_pt, curr_pt, next_pt]):
            continue
        
        # Calculate bearings
        bearing_in = _bearing(prev_pt.lat, prev_pt.lon, curr_pt.lat, curr_pt.lon)
        bearing_out = _bearing(curr_pt.lat, curr_pt.lon, next_pt.lat, next_pt.lon)
        
        # Calculate turn angle
        turn_angle_rad = _angle_diff(bearing_in, bearing_out)
        turn_angle_deg = math.degrees(turn_angle_rad)
        
        # Calculate distance for this segment
        segment_dist = next_pt.distance_m - prev_pt.distance_m
        
        # Curvature = degrees per 100m
        if segment_dist > 1:  # Avoid division by zero
            curvature = turn_angle_deg * 100 / segment_dist
        else:
            curvature = 0.0
        
        curvatures[i] = curvature
    
    # First and last points inherit from neighbors
    if n >= 2:
        curvatures[0] = curvatures[1]
        curvatures[-1] = curvatures[-2]
    
    return curvatures


def get_curvature_speed_factor(
    curvature_deg_per_100m: float,
    grade_pct: float,
    ride_type: str = "training",
) -> float:
    """
    Get speed reduction factor based on curvature.
    
    Only applies to descents (grade < 0) where braking for curves matters.
    On climbs, curvature has negligible effect on speed.
    
    Based on empirical data:
    - Straight (<5°/100m): 1.0 (no reduction)
    - Gentle (5-15°/100m): 0.95
    - Curvy (15-30°/100m): 0.90
    - Hairpin (>30°/100m): 0.80
    
    For races, factors are less aggressive (assume faster descending).
    
    Args:
        curvature_deg_per_100m: Turn angle in degrees per 100m
        grade_pct: Gradient percentage (negative = descent)
        ride_type: "training" or "race"
        
    Returns:
        Speed multiplier (0.0 to 1.0)
    """
    # Curvature only affects descents
    if grade_pct >= 0:
        return 1.0
    
    # Curvature thresholds and factors
    if ride_type == "race":
        # More aggressive descending in races
        if curvature_deg_per_100m < 5:
            return 1.0
        elif curvature_deg_per_100m < 15:
            return 0.98
        elif curvature_deg_per_100m < 30:
            return 0.95
        else:
            return 0.90
    else:
        # Training ride - more cautious
        if curvature_deg_per_100m < 5:
            return 1.0
        elif curvature_deg_per_100m < 15:
            return 0.95
        elif curvature_deg_per_100m < 30:
            return 0.90
        else:
            return 0.80


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
        points[i].curvature_deg_per_100m = curv

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
    min_power_mult: float = 0.50,
    max_power_mult: float = 1.50,
) -> list[float]:
    """
    Calculate terrain-adapted power targets at each point.

    Uses the continuous grade-power formula:
        power_mult = intercept + slope × grade%

    This captures natural riding behavior where riders push harder
    on climbs (low aero drag, efficient) and ease off on descents.

    Args:
        points: Fine-grained elevation points
        base_power_w: Base power (FTP × target_intensity)
        grade_power_intercept: Base multiplier at 0% grade (default 1.10)
        grade_power_slope: Additional multiplier per 1% grade (default 0.035)
        power_cap_w: Maximum power (e.g., FTP × 1.05). None = no cap.
        min_power_mult: Minimum multiplier for descents (default 0.50)
        max_power_mult: Maximum multiplier for steep climbs (default 1.50)

    Returns:
        List of power targets in watts, one per point
    """
    powers: list[float] = []

    for point in points:
        # Calculate power multiplier based on grade
        multiplier = grade_power_intercept + grade_power_slope * point.grade_pct

        # Clamp to reasonable range
        multiplier = max(min_power_mult, min(max_power_mult, multiplier))

        # Calculate target power
        power = base_power_w * multiplier

        # Apply power cap if specified
        if power_cap_w is not None:
            power = min(power, power_cap_w)

        powers.append(max(0.0, power))

    return powers


# =============================================================================
# Speed and Time Calculation
# =============================================================================


def calculate_speeds_and_times(
    points: list[FineGrainedPoint],
    powers: list[float],
    rider_params: RiderParams,
    env_params: EnvironmentParams | None = None,
    max_descent_speed_mps: float = 18.0,
    ride_type: str = "training",
) -> tuple[list[float], list[float]]:
    """
    Calculate speed and segment time at each point using physics model.

    Runs the Newton-Raphson solver at each point to find the speed
    that corresponds to the given power output on the given grade.
    
    Applies curvature-based speed reduction on descents to account
    for braking through corners.

    Args:
        points: Fine-grained elevation points (with curvature)
        powers: Power target at each point (same length as points)
        rider_params: Rider and bike physical parameters
        env_params: Environmental conditions (air density, wind)
        max_descent_speed_mps: Cap descent speeds to this value
        ride_type: "training" or "race" - affects curvature speed factors

    Returns:
        Tuple of (speeds, times) where:
        - speeds: Speed in m/s at each point
        - times: Time in seconds to traverse from each point to next
    """
    if env_params is None:
        env_params = EnvironmentParams()

    speeds: list[float] = []
    times: list[float] = []

    for i, (point, power) in enumerate(zip(points, powers)):
        # Calculate speed from power using physics model
        speed = speed_from_power(
            power_w=power,
            grade_pct=point.grade_pct,
            rider=rider_params,
            env=env_params,
            max_descent_speed_mps=max_descent_speed_mps,
        )

        # Apply curvature-based speed reduction on descents
        curvature_factor = get_curvature_speed_factor(
            point.curvature_deg_per_100m,
            point.grade_pct,
            ride_type,
        )
        speed = speed * curvature_factor

        # Ensure minimum speed (don't get stuck)
        speed = max(0.5, speed)
        speeds.append(speed)

        # Calculate time to next point
        if i < len(points) - 1:
            segment_distance = points[i + 1].distance_m - point.distance_m
            segment_time = segment_distance / speed if speed > 0 else 0
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

    # 30-second rolling average
    window = 30
    cumsum = np.cumsum(np.insert(samples, 0, 0))
    rolling_avg = (cumsum[window:] - cumsum[:-window]) / window

    # 4th power mean, then 4th root
    np_power = float((np.mean(rolling_avg**4)) ** 0.25)

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
) -> FineGrainedPlan:
    """
    Generate a fine-grained pacing plan with accurate speed predictions.

    This is the main entry point for fine-grained pacing. It:
    1. Resamples the elevation profile to consistent ~25m intervals
    2. Calculates curvature at each point from GPS coordinates
    3. Calculates terrain-adapted power targets at each point
    4. Runs the physics model to get speed at each point
    5. Applies curvature-based speed reduction on descents
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
        ride_type: "training" or "race" - affects curvature speed factors
                   Training = more cautious descending (learned from your data)
                   Race = more aggressive descending

    Returns:
        FineGrainedPlan with per-point targets and aggregated metrics
    """
    # Default parameters
    if rider_params is None:
        rider_params = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
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

    # Step 3: Calculate speeds and times (with curvature factor)
    speeds, times = calculate_speeds_and_times(
        points=points,
        powers=powers,
        rider_params=rider_params,
        env_params=env_params,
        max_descent_speed_mps=max_descent_speed_mps,
        ride_type=ride_type,
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


# =============================================================================
# Aggregation to Display Segments
# =============================================================================


def aggregate_to_display_segments(
    fine_plan: FineGrainedPlan,
    target_segment_count: int = 50,
    min_segment_length_m: float = 200.0,
) -> list[dict]:
    """
    Aggregate fine-grained points into display segments for UI.

    The fine-grained plan may have 1000+ points, which is too many
    for a race plan display. This function combines them into
    ~50-100 display segments with weighted-average metrics.

    Args:
        fine_plan: The fine-grained pacing plan
        target_segment_count: Target number of display segments
        min_segment_length_m: Minimum segment length in meters

    Returns:
        List of display segment dicts with:
        - start_distance_m, end_distance_m, distance_m
        - avg_grade_pct, avg_power_w, avg_speed_mps
        - time_s, terrain_type
    """
    if not fine_plan.points:
        return []

    total_distance = fine_plan.total_distance_m
    target_length = max(min_segment_length_m, total_distance / target_segment_count)

    segments: list[dict] = []
    current_start_idx = 0
    current_start_dist = 0.0

    for i, point in enumerate(fine_plan.points):
        segment_length = point.distance_m - current_start_dist

        # Check if we should close this segment
        is_last = i == len(fine_plan.points) - 1
        should_close = segment_length >= target_length or is_last

        if should_close and i > current_start_idx:
            # Aggregate points in this segment
            segment_points = fine_plan.points[current_start_idx : i + 1]

            # Time-weighted averages
            total_time = sum(p.time_s for p in segment_points)
            if total_time > 0:
                avg_power = sum(p.power_w * p.time_s for p in segment_points) / total_time
                avg_speed = sum(p.speed_mps * p.time_s for p in segment_points) / total_time
            else:
                avg_power = sum(p.power_w for p in segment_points) / len(segment_points)
                avg_speed = sum(p.speed_mps for p in segment_points) / len(segment_points)

            # Distance-weighted grade
            distances = [
                segment_points[j + 1].distance_m - segment_points[j].distance_m
                for j in range(len(segment_points) - 1)
            ]
            if distances:
                total_dist = sum(distances)
                avg_grade = (
                    sum(segment_points[j].grade_pct * distances[j] for j in range(len(distances))) / total_dist
                    if total_dist > 0
                    else 0
                )
            else:
                avg_grade = segment_points[0].grade_pct

            # Classify terrain
            terrain_type = _classify_terrain_from_grade(avg_grade)

            segments.append(
                {
                    "segment_idx": len(segments),
                    "start_distance_m": current_start_dist,
                    "end_distance_m": point.distance_m,
                    "distance_m": point.distance_m - current_start_dist,
                    "avg_grade_pct": round(avg_grade, 2),
                    "avg_power_w": round(avg_power, 0),
                    "avg_speed_mps": round(avg_speed, 2),
                    "avg_speed_kmh": round(avg_speed * 3.6, 1),
                    "time_s": round(total_time, 1),
                    "terrain_type": terrain_type,
                }
            )

            # Start new segment
            current_start_idx = i
            current_start_dist = point.distance_m

    return segments


def _classify_terrain_from_grade(grade_pct: float) -> str:
    """Classify terrain type based on average grade."""
    if grade_pct < -6:
        return "steep_descent"
    elif grade_pct < -2:
        return "descent"
    elif grade_pct < 2:
        return "flat"
    elif grade_pct < 4:
        return "false_flat"
    elif grade_pct < 8:
        return "climb"
    else:
        return "steep_climb"
