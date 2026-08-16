/**
 * Chart axis utility functions based on Heckbert's "nice numbers" algorithm
 * from Graphics Gems. Used for generating clean axis ticks.
 */

/**
 * Returns a "nice" number approximately equal to range.
 * If round is true, round to nearest nice number, otherwise ceiling.
 */
export function niceNum(range: number, round: boolean): number {
  const exponent = Math.floor(Math.log10(range));
  const fraction = range / Math.pow(10, exponent);
  let niceFraction: number;

  if (round) {
    if (fraction < 1.5) niceFraction = 1;
    else if (fraction < 3) niceFraction = 2;
    else if (fraction < 7) niceFraction = 5;
    else niceFraction = 10;
  } else {
    if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;
  }

  return niceFraction * Math.pow(10, exponent);
}

/**
 * Generate nice tick values using Heckbert's algorithm.
 */
export function getNiceTicks(min: number, max: number, maxTicks: number = 8): number[] {
  if (max === min) return [min];
  
  const range = niceNum(max - min, false);
  const tickSpacing = niceNum(range / (maxTicks - 1), true);
  const niceLowerBound = Math.floor(min / tickSpacing) * tickSpacing;
  const niceUpperBound = Math.ceil(max / tickSpacing) * tickSpacing;
  
  const ticks: number[] = [];
  for (let tick = niceLowerBound; tick <= niceUpperBound + tickSpacing * 0.5; tick += tickSpacing) {
    // Round to avoid floating point issues
    const roundedTick = Math.round(tick * 1e10) / 1e10;
    if (roundedTick >= min - tickSpacing * 0.1 && roundedTick <= max + tickSpacing * 0.1) {
      ticks.push(roundedTick);
    }
  }
  return ticks;
}

/**
 * Generate nice time ticks using human-friendly intervals (30s, 1m, 2m, 5m, etc.).
 */
export function getNiceTimeTicks(maxSeconds: number, maxTicks: number = 10): number[] {
  // Nice time intervals in seconds - more granular options
  const niceIntervals = [10, 15, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600];
  const idealInterval = maxSeconds / maxTicks;
  const interval = niceIntervals.find(i => i >= idealInterval) || niceIntervals[niceIntervals.length - 1];
  
  const ticks: number[] = [];
  for (let t = 0; t <= maxSeconds; t += interval) {
    ticks.push(t);
  }
  return ticks;
}

// ============================================================================
// Chart-specific formatting utilities
// ============================================================================

/**
 * Format duration for chart axis ticks (compact form: "5s", "1m", "1h").
 * Different from format.ts formatDuration which uses verbose form like "1h 05m".
 */
export function formatAxisDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h`;
}

/**
 * Key durations commonly used in power curve charts.
 * These are the tick points on a log scale from 1s to 2h.
 */
export const POWER_CURVE_DURATIONS = [1, 5, 10, 30, 60, 120, 300, 600, 1200, 3600, 7200];

/**
 * PMC chart colors (CTL, ATL, TSB).
 */
export const PMC_COLORS = {
  ctl: "#3b82f6", // blue
  atl: "#ec4899", // pink  
  tsb: "#f59e0b", // amber
} as const;

/**
 * Common chart series colors for consistency.
 */
export const CHART_COLORS = {
  power: "#f59e0b",    // amber
  hr: "#ef4444",       // red
  speed: "#3b82f6",    // blue
  cadence: "#7c3aed",  // violet
  elevation: "#10b981", // emerald
  primary: "#6366f1",  // indigo
  secondary: "#f59e0b", // amber
} as const;

