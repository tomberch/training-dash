import type { Records, RoutePR } from "./api";
import { formatDistance, formatSpeed, formatElevation, formatTime } from "./format";
import type { UnitSystem } from "./format";

export interface PR {
  label: string;
  value: string;
}

interface PRDef {
  key: keyof Records;
  label: string;
  format: (value: number, unitSystem: UnitSystem) => string;
}

const PR_DEFS: PRDef[] = [
  { key: "longest_distance_m", label: "Longest Ride", format: formatDistance },
  { key: "longest_moving_time_s", label: "Longest Ride (Time)", format: formatTime },
  { key: "fastest_5000_m", label: "Fastest 5km", format: formatTime },
  { key: "fastest_10000_m", label: "Fastest 10km", format: formatTime },
  { key: "fastest_40000_m", label: "Fastest 40km", format: formatTime },
  { key: "max_speed_mps", label: "Max Speed", format: formatSpeed },
  { key: "max_hr_bpm", label: "Max HR", format: (v) => `${v} bpm` },
  { key: "biggest_elevation_gain_m", label: "Biggest Climb", format: formatElevation },
  { key: "highest_sustained_power_w", label: "Highest NP", format: (v) => `${v} W` },
];

export function prsFromRecords(records: Records, unitSystem: UnitSystem = "metric"): PR[] {
  const prs: PR[] = [];
  for (const def of PR_DEFS) {
    const pr = records[def.key];
    if (pr) {
      prs.push({ label: def.label, value: def.format(pr.value, unitSystem) });
    }
  }
  return prs;
}

export function routePRsFromRecords(routePrs: RoutePR[]): PR[] {
  return routePrs.map((rp) => ({
    label: `Route ${rp.route_label}`,
    value: formatTime(rp.fastest_time_s),
  }));
}