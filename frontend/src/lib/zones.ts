// Zone computation utilities
// Default percentages based on Coggan power zones and standard HR zones

export type ZonePercentages = Record<string, [number, number | null]>;

// Default 7-zone power model (Coggan)
export const DEFAULT_POWER_ZONES: ZonePercentages = {
  "1": [0, 55],
  "2": [56, 75],
  "3": [76, 90],
  "4": [91, 105],
  "5": [106, 120],
  "6": [121, 150],
  "7": [151, null], // null = no upper bound
};

// Default 5-zone HR model (LTHR-based)
export const DEFAULT_HR_ZONES: ZonePercentages = {
  "1": [0, 81],
  "2": [82, 89],
  "3": [90, 93],
  "4": [94, 99],
  "5": [100, null], // null = no upper bound
};

// Zone names
export const POWER_ZONE_NAMES: Record<string, string> = {
  "1": "Active Recovery",
  "2": "Endurance",
  "3": "Tempo",
  "4": "Threshold",
  "5": "VO2max",
  "6": "Anaerobic",
  "7": "Neuromuscular",
};

export const HR_ZONE_NAMES: Record<string, string> = {
  "1": "Recovery",
  "2": "Aerobic",
  "3": "Tempo",
  "4": "Threshold",
  "5": "Anaerobic",
};

// Computed zone result
export interface ComputedZone {
  zone: number;
  name: string;
  minPct: number;
  maxPct: number | null;
  minValue: number;
  maxValue: number | null;
}

// Compute power zones from FTP and percentages
export function computePowerZones(
  ftp: number,
  percentages: ZonePercentages = DEFAULT_POWER_ZONES
): ComputedZone[] {
  return Object.entries(percentages)
    .map(([zone, [minPct, maxPct]]) => ({
      zone: parseInt(zone),
      name: POWER_ZONE_NAMES[zone] || `Zone ${zone}`,
      minPct,
      maxPct,
      minValue: Math.round((ftp * minPct) / 100),
      maxValue: maxPct !== null ? Math.round((ftp * maxPct) / 100) : null,
    }))
    .sort((a, b) => a.zone - b.zone);
}

// Compute HR zones from LTHR and percentages
export function computeHrZones(
  lthr: number,
  percentages: ZonePercentages = DEFAULT_HR_ZONES
): ComputedZone[] {
  return Object.entries(percentages)
    .map(([zone, [minPct, maxPct]]) => ({
      zone: parseInt(zone),
      name: HR_ZONE_NAMES[zone] || `Zone ${zone}`,
      minPct,
      maxPct,
      minValue: Math.round((lthr * minPct) / 100),
      maxValue: maxPct !== null ? Math.round((lthr * maxPct) / 100) : null,
    }))
    .sort((a, b) => a.zone - b.zone);
}

// Validate zone percentages (must be contiguous, no gaps or overlaps)
export function validateZonePercentages(percentages: ZonePercentages): string | null {
  const zones = Object.entries(percentages)
    .map(([zone, [min, max]]) => ({ zone: parseInt(zone), min, max }))
    .sort((a, b) => a.zone - b.zone);

  for (let i = 0; i < zones.length; i++) {
    const current = zones[i];
    
    // Check min < max (for bounded zones)
    if (current.max !== null && current.min >= current.max) {
      return `Zone ${current.zone}: min must be less than max`;
    }

    // Check continuity with next zone
    if (i < zones.length - 1) {
      const next = zones[i + 1];
      if (current.max === null) {
        return `Zone ${current.zone}: only the last zone can be unbounded`;
      }
      if (next.min !== current.max + 1) {
        return `Gap or overlap between zones ${current.zone} and ${next.zone}`;
      }
    }
  }

  return null; // Valid
}
