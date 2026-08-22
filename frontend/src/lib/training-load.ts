/**
 * Training load calculations for Calc Lab.
 *
 * These formulas are ported from the backend to enable instant what-if
 * calculations in the browser without server round-trips.
 *
 * Formulas:
 * - IF (Intensity Factor) = NP / FTP
 * - TSS (Training Stress Score) = (duration_s × NP × IF) / (FTP × 3600) × 100
 */

// =============================================================================
// Types
// =============================================================================

export interface TrainingLoadResult {
  /** Intensity Factor (ratio of NP to FTP) */
  intensityFactor: number;
  /** Training Stress Score (0-∞, typically 0-300+) */
  tss: number;
}

export interface TrainingLoadInput {
  /** Normalized Power in watts */
  normalizedPower: number;
  /** Functional Threshold Power in watts */
  ftp: number;
  /** Duration in seconds */
  durationSeconds: number;
}

// =============================================================================
// Core Calculations
// =============================================================================

/**
 * Calculate Intensity Factor from Normalized Power and FTP.
 *
 * IF = NP / FTP
 *
 * Interpretation:
 * - IF < 0.75: Recovery/easy
 * - IF 0.75-0.85: Endurance
 * - IF 0.85-0.95: Tempo
 * - IF 0.95-1.05: Threshold
 * - IF > 1.05: VO2max/anaerobic
 *
 * @param normalizedPower - Normalized Power in watts
 * @param ftp - Functional Threshold Power in watts
 * @returns Intensity Factor (dimensionless ratio)
 */
export function calculateIntensityFactor(normalizedPower: number, ftp: number): number {
  if (ftp <= 0) return 0;
  if (normalizedPower <= 0) return 0;

  return normalizedPower / ftp;
}

/**
 * Calculate Training Stress Score from duration, NP, and FTP.
 *
 * TSS = (duration_s × NP × IF) / (FTP × 3600) × 100
 *
 * Simplified: TSS = (duration_s × NP²) / (FTP² × 36)
 *
 * Interpretation:
 * - TSS < 150: Low, easily recoverable
 * - TSS 150-300: Medium, some residual fatigue
 * - TSS 300-450: High, substantial fatigue
 * - TSS > 450: Very high, multiple days to recover
 *
 * Note: 100 TSS = 1 hour at FTP (IF = 1.0)
 *
 * @param input - Training load input parameters
 * @returns Training Stress Score (dimensionless)
 */
export function calculateTss(input: TrainingLoadInput): number {
  const { normalizedPower, ftp, durationSeconds } = input;

  if (ftp <= 0 || normalizedPower <= 0 || durationSeconds <= 0) {
    return 0;
  }

  const intensityFactor = normalizedPower / ftp;

  // TSS = (duration × NP × IF) / (FTP × 3600) × 100
  // Equivalent: (duration × NP × NP / FTP) / (FTP × 3600) × 100
  // Simplified: (duration × NP²) / (FTP² × 36)
  const tss = (durationSeconds * normalizedPower * intensityFactor) / (ftp * 3600) * 100;

  return tss;
}

/**
 * Calculate both IF and TSS in one call.
 *
 * @param input - Training load input parameters
 * @returns Object with intensityFactor and tss
 */
export function calculateTrainingLoad(input: TrainingLoadInput): TrainingLoadResult {
  const { normalizedPower, ftp, durationSeconds } = input;

  if (ftp <= 0 || normalizedPower <= 0 || durationSeconds <= 0) {
    return { intensityFactor: 0, tss: 0 };
  }

  const intensityFactor = calculateIntensityFactor(normalizedPower, ftp);
  const tss = calculateTss(input);

  return { intensityFactor, tss };
}

// =============================================================================
// What-If Calculations
// =============================================================================

/**
 * Recalculate IF and TSS with a new FTP value.
 *
 * Used in Calc Lab to show how training load changes with different FTP.
 * NP stays constant (it's derived from the actual power data), only the
 * interpretation changes.
 *
 * @param normalizedPower - Normalized Power in watts (unchanged)
 * @param newFtp - New FTP value for what-if calculation
 * @param durationSeconds - Duration in seconds (unchanged)
 * @returns New training load values
 */
export function recalculateWithNewFtp(
  normalizedPower: number,
  newFtp: number,
  durationSeconds: number
): TrainingLoadResult {
  return calculateTrainingLoad({
    normalizedPower,
    ftp: newFtp,
    durationSeconds,
  });
}

// =============================================================================
// Formatting Utilities
// =============================================================================

/**
 * Format Intensity Factor for display.
 *
 * @param intensityFactor - IF value (e.g., 0.875)
 * @param decimals - Number of decimal places (default 2)
 * @returns Formatted string (e.g., "0.88")
 */
export function formatIntensityFactor(intensityFactor: number, decimals = 2): string {
  return intensityFactor.toFixed(decimals);
}

/**
 * Format TSS for display.
 *
 * @param tss - TSS value (e.g., 114.8)
 * @param decimals - Number of decimal places (default 1)
 * @returns Formatted string (e.g., "114.8")
 */
export function formatTss(tss: number, decimals = 1): string {
  return tss.toFixed(decimals);
}

/**
 * Get a human-readable description of the training load level.
 *
 * @param tss - Training Stress Score
 * @returns Description string
 */
export function getTssDescription(tss: number): string {
  if (tss < 50) return "Very light - minimal fatigue";
  if (tss < 100) return "Light - easily recoverable";
  if (tss < 150) return "Moderate - normal training";
  if (tss < 250) return "Hard - noticeable fatigue";
  if (tss < 350) return "Very hard - significant fatigue";
  return "Extreme - multiple days recovery";
}

/**
 * Get a human-readable description of the intensity level.
 *
 * @param intensityFactor - Intensity Factor
 * @returns Description string
 */
export function getIntensityDescription(intensityFactor: number): string {
  if (intensityFactor < 0.55) return "Recovery";
  if (intensityFactor < 0.75) return "Endurance";
  if (intensityFactor < 0.90) return "Tempo";
  if (intensityFactor < 1.05) return "Threshold";
  if (intensityFactor < 1.20) return "VO2max";
  return "Anaerobic";
}
