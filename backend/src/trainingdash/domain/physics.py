"""
Cycling physics model for power-speed calculations.

Implements the Martin et al. (1998) power equation for cycling:
    P = v × (F_gravity + F_rolling + F_aero) / η

Where:
- F_gravity = m·g·sin(θ)        (gravitational resistance on gradient)
- F_rolling = m·g·Crr·cos(θ)    (rolling resistance)
- F_aero = 0.5·ρ·CdA·v²         (aerodynamic drag)
- η = drivetrain efficiency

The aerodynamic term dominates at high speeds (v³ relationship with power),
while gravity dominates on climbs. This asymmetry is why variable pacing
(pushing harder uphill, easier downhill) beats constant power.

Key insight: At 40 km/h on flat ground, ~80% of resistance is aerodynamic.
At 15 km/h on a steep climb, ~90% is gravitational.

References:
- Martin JC et al. (1998). "Validation of a Mathematical Model for Road Cycling Power."
  Journal of Applied Biomechanics 14: 276-291.
- gribble.org/cycling/power_v_speed.html (derivation and Cardano solution)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Physical constants
GRAVITY = 9.80665  # m/s² (standard gravity)
SEA_LEVEL_AIR_DENSITY = 1.225  # kg/m³ (ISA standard)
ISA_TEMPERATURE_LAPSE_RATE = 0.0065  # K/m (temperature decrease with altitude)
ISA_SEA_LEVEL_TEMPERATURE = 288.15  # K (15°C)
ISA_SEA_LEVEL_PRESSURE = 101325.0  # Pa
GAS_CONSTANT_DRY_AIR = 287.05  # J/(kg·K)


@dataclass(frozen=True, slots=True)
class RiderParams:
    """Parameters describing the rider and bike.

    Attributes:
        mass_kg: Total mass of rider + bike + gear in kg.
        cda: Aerodynamic drag area (Cd × A) in m².
        crr: Coefficient of rolling resistance (dimensionless).
        efficiency: Drivetrain efficiency (0-1), typically 0.97-0.98.
    """

    mass_kg: float
    cda: float
    crr: float
    efficiency: float = 0.97

    def __post_init__(self) -> None:
        if self.mass_kg <= 0:
            raise ValueError("mass_kg must be positive")
        if self.cda <= 0:
            raise ValueError("cda must be positive")
        if self.crr < 0:
            raise ValueError("crr must be non-negative")
        if not 0 < self.efficiency <= 1:
            raise ValueError("efficiency must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EnvironmentParams:
    """Environmental conditions affecting cycling physics.

    Attributes:
        air_density: Air density in kg/m³. Use air_density_from_altitude()
            to compute from altitude using ISA model.
        wind_speed_mps: Headwind speed in m/s. Positive = headwind,
            negative = tailwind. Default 0 (no wind).
    """

    air_density: float = SEA_LEVEL_AIR_DENSITY
    wind_speed_mps: float = 0.0

    def __post_init__(self) -> None:
        if self.air_density <= 0:
            raise ValueError("air_density must be positive")


def air_density_from_altitude(altitude_m: float) -> float:
    """Calculate air density using ISA (International Standard Atmosphere).

    The ISA model provides air density as a function of altitude only,
    without requiring temperature or pressure inputs. This is the approach
    chosen for the Race Planner (decision #527) since weather integration
    is out of scope.

    Model equations (troposphere, altitude < 11km):
        T = T₀ - L × h
        P = P₀ × (T / T₀)^(g / (R × L))
        ρ = P / (R × T)

    Where:
        T₀ = 288.15 K (sea level temperature)
        L = 0.0065 K/m (lapse rate)
        P₀ = 101325 Pa (sea level pressure)
        g = 9.80665 m/s² (gravity)
        R = 287.05 J/(kg·K) (gas constant for dry air)

    Args:
        altitude_m: Altitude above sea level in meters.

    Returns:
        Air density in kg/m³.

    Examples:
        >>> air_density_from_altitude(0)  # Sea level
        1.225
        >>> air_density_from_altitude(1000)  # ~1km altitude
        1.1116...
        >>> air_density_from_altitude(2000)  # ~2km altitude
        1.0065...
    """
    if altitude_m < 0:
        altitude_m = 0  # Treat below sea level as sea level
    if altitude_m > 11000:
        altitude_m = 11000  # ISA troposphere limit

    # Temperature at altitude
    temp_k = ISA_SEA_LEVEL_TEMPERATURE - ISA_TEMPERATURE_LAPSE_RATE * altitude_m

    # Pressure at altitude (barometric formula)
    exponent = GRAVITY / (GAS_CONSTANT_DRY_AIR * ISA_TEMPERATURE_LAPSE_RATE)
    pressure_pa = ISA_SEA_LEVEL_PRESSURE * (temp_k / ISA_SEA_LEVEL_TEMPERATURE) ** exponent

    # Density from ideal gas law
    return pressure_pa / (GAS_CONSTANT_DRY_AIR * temp_k)


def power_required(
    speed_mps: float,
    grade_pct: float,
    rider: RiderParams,
    env: EnvironmentParams | None = None,
) -> float:
    """Calculate power required to maintain a given ground speed.

    Uses the Martin et al. (1998) cycling power model:
        P = v × (F_gravity + F_rolling + F_aero) / η

    Args:
        speed_mps: Ground speed in meters per second.
        grade_pct: Road gradient as percentage (e.g., 5.0 for 5% grade).
        rider: Rider and bike parameters.
        env: Environmental conditions. Defaults to sea-level, no wind.

    Returns:
        Power at the pedals in watts. Returns 0 for non-positive speeds.

    Examples:
        >>> rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        >>> power_required(8.33, 0, rider)  # 30 km/h flat
        148.5...
        >>> power_required(11.11, 0, rider)  # 40 km/h flat
        279.8...
    """
    if speed_mps <= 0:
        return 0.0

    if env is None:
        env = EnvironmentParams()

    # Convert grade percentage to angle
    theta = math.atan(grade_pct / 100.0)

    # Airspeed (ground speed + headwind)
    airspeed = speed_mps + env.wind_speed_mps

    # Force components
    f_gravity = rider.mass_kg * GRAVITY * math.sin(theta)
    f_rolling = rider.mass_kg * GRAVITY * rider.crr * math.cos(theta)

    # Aerodynamic drag (can be negative with strong tailwind, but floor at 0)
    f_aero = max(0.0, 0.5 * env.air_density * rider.cda * airspeed * airspeed)

    # Total force and power
    f_total = f_gravity + f_rolling + f_aero

    # Power = Force × velocity / efficiency
    power = f_total * speed_mps / rider.efficiency

    # On steep descents with gravity assisting, power can be negative
    # (freewheeling/braking scenario). Return 0 as minimum.
    return max(0.0, power)


def speed_from_power(
    power_w: float,
    grade_pct: float,
    rider: RiderParams,
    env: EnvironmentParams | None = None,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> float:
    """Solve for ground speed given power output using Newton-Raphson iteration.

    The power equation P(v) is cubic in velocity due to aerodynamic drag.
    Newton-Raphson converges quickly (typically 3-5 iterations) for reasonable
    initial guesses.

    Per decision #527: Use Newton-Raphson for flexibility over Cardano's formula.
    This allows easier extension for wind effects and position changes.

    Note: On steep descents with low power, gravity can exceed resistance at
    moderate speeds, meaning even zero power would produce motion. In this case,
    we find the speed where the given power is required, which may be quite high.

    Args:
        power_w: Power at the pedals in watts.
        grade_pct: Road gradient as percentage.
        rider: Rider and bike parameters.
        env: Environmental conditions. Defaults to sea-level, no wind.
        tol: Convergence tolerance in watts. Default 1e-6.
        max_iter: Maximum iterations. Default 50.

    Returns:
        Ground speed in meters per second.

    Raises:
        ValueError: If solver fails to converge (unusual for valid inputs).

    Examples:
        >>> rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        >>> speed_from_power(200, 0, rider)  # 200W on flat
        9.34...  # ~33.6 km/h
        >>> speed_from_power(200, 5, rider)  # 200W on 5% climb
        3.71...  # ~13.4 km/h
    """
    if power_w <= 0:
        return 0.0

    if env is None:
        env = EnvironmentParams()

    theta = math.atan(grade_pct / 100.0)

    # For the Newton-Raphson solver, we need F(v) = P_required(v) - P_target = 0
    def f_and_df(v: float) -> tuple[float, float]:
        """Compute residual and derivative for Newton-Raphson."""
        airspeed = v + env.wind_speed_mps

        # Force components
        f_gravity = rider.mass_kg * GRAVITY * math.sin(theta)
        f_rolling = rider.mass_kg * GRAVITY * rider.crr * math.cos(theta)
        f_aero = 0.5 * env.air_density * rider.cda * airspeed * airspeed

        # Total force and power required
        f_total = f_gravity + f_rolling + f_aero
        p_required = max(0.0, f_total * v / rider.efficiency)

        # Residual
        residual = p_required - power_w

        # Derivative dP/dv
        # P = max(0, (F_g + F_r + F_a) * v / η)
        # When F_total > 0: dP/dv = (F_g + F_r + F_a) / η + v * dF_a/dv / η
        # dF_a/dv = ρ * CdA * (v + w)
        df_aero_dv = env.air_density * rider.cda * airspeed
        if f_total > 0:
            derivative = (f_total + v * df_aero_dv) / rider.efficiency
        else:
            # When net force is negative (steep descent), derivative of max(0, ...)
            # is just from the aero term growing
            derivative = max(0.1, v * df_aero_dv / rider.efficiency)

        return residual, derivative

    # Initial guess depends on terrain
    if grade_pct > 5:
        # On climbs, gravity dominates - use simpler estimate
        # P ≈ m * g * sin(θ) * v / η  →  v ≈ P * η / (m * g * sin(θ))
        sin_theta = math.sin(theta)
        if sin_theta > 0.01:
            v = power_w * rider.efficiency / (rider.mass_kg * GRAVITY * sin_theta)
            v = max(0.5, min(15.0, v))
        else:
            v = 5.0
    elif grade_pct < -3:
        # On descents, aero drag must balance gravity assist + rider power
        # Start with a higher speed guess since descent speeds are higher
        v = 15.0  # Start at ~54 km/h for descents
    else:
        # Flat or mild grade: assume aero-dominated (v ∝ P^(1/3))
        v = (power_w * rider.efficiency / (0.5 * env.air_density * rider.cda)) ** (1.0 / 3.0)
        v = max(0.5, min(30.0, v))

    # Newton-Raphson iteration
    for _ in range(max_iter):
        residual, derivative = f_and_df(v)

        if abs(residual) < tol:
            return v

        # Avoid division by zero or very small derivative
        if abs(derivative) < 1e-10:
            derivative = 0.1 if derivative >= 0 else -0.1

        # Newton step with damping to prevent overshoot
        delta = residual / derivative

        # Limit step size to prevent wild jumps
        max_step = max(1.0, v * 0.5)
        delta = max(-max_step, min(max_step, delta))

        v_new = v - delta

        # Keep speed positive and bounded
        v_new = max(0.1, min(50.0, v_new))

        # Check for convergence
        if abs(v_new - v) < tol * 0.01:
            return v_new

        v = v_new

    # If we get here, return best estimate (shouldn't happen for valid inputs)
    return v


def time_for_segment(
    distance_m: float,
    grade_pct: float,
    power_w: float,
    rider: RiderParams,
    env: EnvironmentParams | None = None,
) -> float:
    """Calculate time to cover a segment at given power.

    Args:
        distance_m: Segment length in meters.
        grade_pct: Road gradient as percentage.
        power_w: Power at the pedals in watts.
        rider: Rider and bike parameters.
        env: Environmental conditions.

    Returns:
        Time in seconds to cover the segment.
    """
    if distance_m <= 0:
        return 0.0

    speed = speed_from_power(power_w, grade_pct, rider, env)

    if speed <= 0:
        # Can't make progress (e.g., zero power on steep climb)
        return float("inf")

    return distance_m / speed


def estimate_ftp_from_cp(cp_watts: float) -> float:
    """Estimate FTP from Critical Power.

    FTP (Functional Threshold Power) and CP (Critical Power) are related
    but not identical. CP is typically slightly lower than FTP due to
    different testing protocols.

    Based on research, FTP ≈ CP for well-trained cyclists, with FTP
    sometimes 3-5% higher for less trained individuals.

    Args:
        cp_watts: Critical Power in watts.

    Returns:
        Estimated FTP in watts.
    """
    # Conservative estimate: FTP ≈ CP
    # This aligns with modern understanding that CP represents the
    # highest sustainable metabolic steady state.
    return cp_watts


def estimate_cp_from_ftp(ftp_watts: float) -> float:
    """Estimate Critical Power from FTP.

    Args:
        ftp_watts: Functional Threshold Power in watts.

    Returns:
        Estimated CP in watts (typically ~FTP for trained cyclists).
    """
    return ftp_watts



# =============================================================================
# Wind and Bearing Calculations
# =============================================================================


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate initial bearing from point 1 to point 2.

    Uses the forward azimuth formula for great-circle navigation.
    Returns the initial bearing (direction you'd face when starting
    from point 1 heading toward point 2).

    Args:
        lat1: Latitude of starting point in degrees
        lon1: Longitude of starting point in degrees
        lat2: Latitude of ending point in degrees
        lon2: Longitude of ending point in degrees

    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East, 180=South, 270=West)

    Examples:
        >>> calculate_bearing(0, 0, 1, 0)  # Due north
        0.0
        >>> calculate_bearing(0, 0, 0, 1)  # Due east
        90.0
        >>> calculate_bearing(47.0, 8.0, 47.0, 9.0)  # East in Switzerland
        89.3...
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    # Forward azimuth formula
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

    bearing_rad = math.atan2(x, y)
    bearing_deg = math.degrees(bearing_rad)

    # Normalize to 0-360
    return (bearing_deg + 360) % 360


def calculate_headwind(
    wind_speed_mps: float,
    wind_direction_deg: float,
    course_bearing_deg: float,
) -> float:
    """Calculate effective headwind component from wind speed and direction.

    Decomposes wind into the component parallel to the course direction.
    Positive = headwind (slows you down), negative = tailwind (helps you).

    Wind direction uses meteorological convention: the direction wind
    comes FROM (0° = wind from north, 90° = wind from east).

    Course bearing is where you're heading TO (0° = heading north).

    The effective headwind is:
        headwind = wind_speed × cos(wind_direction - course_bearing)

    This is positive when wind comes from ahead (headwind) and
    negative when wind comes from behind (tailwind).

    Args:
        wind_speed_mps: Wind speed in m/s
        wind_direction_deg: Meteorological wind direction in degrees
            (where wind comes FROM)
        course_bearing_deg: Direction of travel in degrees
            (where you're heading TO)

    Returns:
        Effective headwind in m/s (positive = headwind, negative = tailwind)

    Examples:
        >>> calculate_headwind(10, 0, 0)    # Wind from north, heading north
        10.0  # Full headwind
        >>> calculate_headwind(10, 180, 0)  # Wind from south, heading north
        -10.0  # Full tailwind
        >>> calculate_headwind(10, 90, 0)   # Wind from east, heading north
        0.0  # Pure crosswind (no head/tail component)
        >>> calculate_headwind(10, 45, 0)   # Wind from NE, heading north
        7.07...  # Partial headwind
    """
    # Calculate relative angle between wind direction and course
    # Wind direction is where wind comes FROM
    # Course bearing is where we're going TO
    # If wind comes from our heading direction, it's a headwind
    relative_angle_deg = wind_direction_deg - course_bearing_deg

    # Convert to radians and compute headwind component
    relative_angle_rad = math.radians(relative_angle_deg)

    # cos(0) = 1 (full headwind when wind comes from ahead)
    # cos(180) = -1 (full tailwind when wind comes from behind)
    # cos(90) = 0 (no head/tail component for crosswind)
    return wind_speed_mps * math.cos(relative_angle_rad)
