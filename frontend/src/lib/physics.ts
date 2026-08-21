/**
 * Cycling physics model for power-speed calculations.
 *
 * Port of the Python physics module for client-side plan recalculation.
 * Implements the Martin et al. (1998) power equation:
 *
 *   P = v × (F_gravity + F_rolling + F_aero) / η
 *
 * Where:
 * - F_gravity = m·g·sin(θ)        (gravitational resistance on gradient)
 * - F_rolling = m·g·Crr·cos(θ)    (rolling resistance)
 * - F_aero = 0.5·ρ·CdA·v²         (aerodynamic drag)
 * - η = drivetrain efficiency
 */

// =============================================================================
// Constants
// =============================================================================

/** Standard gravity in m/s² */
export const GRAVITY = 9.80665;

/** Sea level air density in kg/m³ (ISA standard) */
export const SEA_LEVEL_AIR_DENSITY = 1.225;

/** Temperature decrease with altitude in K/m */
const ISA_TEMPERATURE_LAPSE_RATE = 0.0065;

/** Sea level temperature in K (15°C) */
const ISA_SEA_LEVEL_TEMPERATURE = 288.15;

/** Sea level pressure in Pa */
const ISA_SEA_LEVEL_PRESSURE = 101325.0;

/** Gas constant for dry air in J/(kg·K) */
const GAS_CONSTANT_DRY_AIR = 287.05;

// =============================================================================
// Types
// =============================================================================

export interface RiderParams {
  /** Total mass of rider + bike + gear in kg */
  massKg: number;
  /** Aerodynamic drag area (Cd × A) in m² */
  cda: number;
  /** Coefficient of rolling resistance (dimensionless) */
  crr: number;
  /** Drivetrain efficiency (0-1), typically 0.97-0.98 */
  efficiency?: number;
}

export interface EnvironmentParams {
  /** Air density in kg/m³ */
  airDensity?: number;
  /** Headwind speed in m/s. Positive = headwind, negative = tailwind */
  windSpeedMps?: number;
}

export interface Segment {
  /** Segment index */
  segmentIdx: number;
  /** Segment distance in meters */
  distanceM: number;
  /** Grade as percentage (e.g., 5.0 for 5%) */
  gradePct: number;
}

export interface SegmentResult {
  segmentIdx: number;
  distanceM: number;
  gradePct: number;
  powerW: number;
  speedMps: number;
  timeS: number;
}

export interface PlanResult {
  segments: SegmentResult[];
  totalTimeS: number;
  totalDistanceM: number;
  avgPowerW: number;
  avgSpeedMps: number;
}

// =============================================================================
// Air Density
// =============================================================================

/**
 * Calculate air density using ISA (International Standard Atmosphere).
 *
 * @param altitudeM - Altitude above sea level in meters
 * @returns Air density in kg/m³
 */
export function airDensityFromAltitude(altitudeM: number): number {
  // Clamp to valid ISA troposphere range
  const alt = Math.max(0, Math.min(11000, altitudeM));

  // Temperature at altitude
  const tempK = ISA_SEA_LEVEL_TEMPERATURE - ISA_TEMPERATURE_LAPSE_RATE * alt;

  // Pressure at altitude (barometric formula)
  const exponent = GRAVITY / (GAS_CONSTANT_DRY_AIR * ISA_TEMPERATURE_LAPSE_RATE);
  const pressurePa =
    ISA_SEA_LEVEL_PRESSURE * Math.pow(tempK / ISA_SEA_LEVEL_TEMPERATURE, exponent);

  // Density from ideal gas law
  return pressurePa / (GAS_CONSTANT_DRY_AIR * tempK);
}

// =============================================================================
// Power/Speed Calculations
// =============================================================================

/**
 * Calculate power required to maintain a given ground speed.
 *
 * @param speedMps - Ground speed in meters per second
 * @param gradePct - Road gradient as percentage
 * @param rider - Rider and bike parameters
 * @param env - Environmental conditions (optional)
 * @returns Power at the pedals in watts
 */
export function powerRequired(
  speedMps: number,
  gradePct: number,
  rider: RiderParams,
  env?: EnvironmentParams
): number {
  if (speedMps <= 0) return 0;

  const efficiency = rider.efficiency ?? 0.97;
  const airDensity = env?.airDensity ?? SEA_LEVEL_AIR_DENSITY;
  const windSpeed = env?.windSpeedMps ?? 0;

  // Convert grade percentage to angle
  const theta = Math.atan(gradePct / 100);

  // Airspeed (ground speed + headwind)
  const airspeed = speedMps + windSpeed;

  // Force components
  const fGravity = rider.massKg * GRAVITY * Math.sin(theta);
  const fRolling = rider.massKg * GRAVITY * rider.crr * Math.cos(theta);
  const fAero = Math.max(0, 0.5 * airDensity * rider.cda * airspeed * airspeed);

  // Total force and power
  const fTotal = fGravity + fRolling + fAero;
  const power = (fTotal * speedMps) / efficiency;

  return Math.max(0, power);
}

/**
 * Solve for ground speed given power output using Newton-Raphson iteration.
 *
 * @param powerW - Power at the pedals in watts
 * @param gradePct - Road gradient as percentage
 * @param rider - Rider and bike parameters
 * @param env - Environmental conditions (optional)
 * @returns Ground speed in meters per second
 */
export function speedFromPower(
  powerW: number,
  gradePct: number,
  rider: RiderParams,
  env?: EnvironmentParams
): number {
  if (powerW <= 0) return 0;

  const efficiency = rider.efficiency ?? 0.97;
  const airDensity = env?.airDensity ?? SEA_LEVEL_AIR_DENSITY;
  const windSpeed = env?.windSpeedMps ?? 0;

  const theta = Math.atan(gradePct / 100);
  const sinTheta = Math.sin(theta);
  const cosTheta = Math.cos(theta);

  // Compute residual and derivative for Newton-Raphson
  const fAndDf = (v: number): [number, number] => {
    const airspeed = v + windSpeed;

    // Force components
    const fGravity = rider.massKg * GRAVITY * sinTheta;
    const fRolling = rider.massKg * GRAVITY * rider.crr * cosTheta;
    const fAero = 0.5 * airDensity * rider.cda * airspeed * airspeed;

    // Total force and power required
    const fTotal = fGravity + fRolling + fAero;
    const pRequired = Math.max(0, (fTotal * v) / efficiency);

    // Residual
    const residual = pRequired - powerW;

    // Derivative dP/dv
    const dfAeroDv = airDensity * rider.cda * airspeed;
    let derivative: number;
    if (fTotal > 0) {
      derivative = (fTotal + v * dfAeroDv) / efficiency;
    } else {
      derivative = Math.max(0.1, (v * dfAeroDv) / efficiency);
    }

    return [residual, derivative];
  };

  // Initial guess depends on terrain
  let v: number;
  if (gradePct > 5) {
    // On climbs, gravity dominates
    if (sinTheta > 0.01) {
      v = (powerW * efficiency) / (rider.massKg * GRAVITY * sinTheta);
      v = Math.max(0.5, Math.min(15, v));
    } else {
      v = 5;
    }
  } else if (gradePct < -3) {
    // On descents, start with higher speed
    v = 15;
  } else {
    // Flat: aero-dominated (v ∝ P^(1/3))
    v = Math.pow((powerW * efficiency) / (0.5 * airDensity * rider.cda), 1 / 3);
    v = Math.max(0.5, Math.min(30, v));
  }

  // Newton-Raphson iteration
  const tol = 1e-6;
  const maxIter = 50;

  for (let i = 0; i < maxIter; i++) {
    const [residual, derivative] = fAndDf(v);

    if (Math.abs(residual) < tol) {
      return v;
    }

    // Avoid division by very small derivative
    const safeDeriv = Math.abs(derivative) < 1e-10 ? 0.1 : derivative;

    // Newton step with damping
    let delta = residual / safeDeriv;
    const maxStep = Math.max(1, v * 0.5);
    delta = Math.max(-maxStep, Math.min(maxStep, delta));

    const vNew = Math.max(0.1, Math.min(50, v - delta));

    // Check for convergence
    if (Math.abs(vNew - v) < tol * 0.01) {
      return vNew;
    }

    v = vNew;
  }

  return v;
}

/**
 * Calculate time to cover a segment at given power.
 *
 * @param distanceM - Segment length in meters
 * @param gradePct - Road gradient as percentage
 * @param powerW - Power at the pedals in watts
 * @param rider - Rider and bike parameters
 * @param env - Environmental conditions (optional)
 * @returns Time in seconds to cover the segment
 */
export function timeForSegment(
  distanceM: number,
  gradePct: number,
  powerW: number,
  rider: RiderParams,
  env?: EnvironmentParams
): number {
  if (distanceM <= 0) return 0;

  const speed = speedFromPower(powerW, gradePct, rider, env);
  if (speed <= 0) return Infinity;

  return distanceM / speed;
}

// =============================================================================
// Plan Recalculation
// =============================================================================

/**
 * Recalculate a race plan with updated rider parameters.
 *
 * Takes segment definitions and power targets, recalculates times using
 * the physics model with new rider/bike parameters.
 *
 * @param segments - Array of segment definitions with power targets
 * @param riderParams - Updated rider parameters (mass, CdA, Crr)
 * @param env - Environmental conditions (optional)
 * @returns Recalculated plan with new times
 */
export function recalculatePlan(
  segments: Array<Segment & { powerW: number }>,
  riderParams: RiderParams,
  env?: EnvironmentParams
): PlanResult {
  const results: SegmentResult[] = [];
  let totalTimeS = 0;
  let totalDistanceM = 0;
  let totalPowerDistance = 0; // For weighted average power

  for (const seg of segments) {
    const speed = speedFromPower(seg.powerW, seg.gradePct, riderParams, env);
    const time = seg.distanceM / speed;

    results.push({
      segmentIdx: seg.segmentIdx,
      distanceM: seg.distanceM,
      gradePct: seg.gradePct,
      powerW: seg.powerW,
      speedMps: speed,
      timeS: time,
    });

    totalTimeS += time;
    totalDistanceM += seg.distanceM;
    totalPowerDistance += seg.powerW * seg.distanceM;
  }

  const avgPowerW = totalDistanceM > 0 ? totalPowerDistance / totalDistanceM : 0;
  const avgSpeedMps = totalTimeS > 0 ? totalDistanceM / totalTimeS : 0;

  return {
    segments: results,
    totalTimeS,
    totalDistanceM,
    avgPowerW,
    avgSpeedMps,
  };
}

/**
 * Scale power targets by intensity factor and recalculate plan.
 *
 * @param segments - Original segment definitions with base power targets
 * @param intensityFactor - Multiplier for power (e.g., 0.85 for 85% of FTP)
 * @param baseFtp - Original FTP used to set power targets
 * @param newFtp - New FTP to use
 * @param riderParams - Rider parameters
 * @param env - Environmental conditions (optional)
 * @returns Recalculated plan with scaled power targets
 */
export function recalculatePlanWithIntensity(
  segments: Array<Segment & { powerW: number }>,
  intensityFactor: number,
  baseFtp: number,
  newFtp: number,
  riderParams: RiderParams,
  env?: EnvironmentParams
): PlanResult {
  // Scale each segment's power proportionally to FTP change
  const ftpRatio = newFtp / baseFtp;
  const scaledSegments = segments.map((seg) => ({
    ...seg,
    powerW: seg.powerW * ftpRatio * (intensityFactor / 0.85), // Adjust for intensity change from default 0.85
  }));

  return recalculatePlan(scaledSegments, riderParams, env);
}

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Format time in seconds as H:MM:SS or M:SS.
 */
export function formatTime(seconds: number): string {
  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Format time delta as +M:SS or -M:SS.
 */
export function formatTimeDelta(seconds: number): string {
  const sign = seconds >= 0 ? "+" : "-";
  const absSeconds = Math.abs(Math.round(seconds));
  const minutes = Math.floor(absSeconds / 60);
  const secs = absSeconds % 60;
  return `${sign}${minutes}:${secs.toString().padStart(2, "0")}`;
}
