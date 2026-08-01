import type { Records, RoutePR } from "./api";

export interface PR {
  label: string;
  value: string;
}

function formatDistance(m: number): string {
  return `${(m / 1000).toFixed(1)} km`;
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${sec}s`;
}

function formatSpeed(mps: number): string {
  return `${(mps * 3.6).toFixed(1)} km/h`;
}

interface PRDef {
  key: keyof Records;
  label: string;
  format: (value: number) => string;
}

const PR_DEFS: PRDef[] = [
  { key: "longest_distance_m", label: "Longest Ride", format: formatDistance },
  { key: "longest_moving_time_s", label: "Longest Ride (Time)", format: formatTime },
  { key: "fastest_5000_m", label: "Fastest 5km", format: formatTime },
  { key: "fastest_10000_m", label: "Fastest 10km", format: formatTime },
  { key: "fastest_40000_m", label: "Fastest 40km", format: formatTime },
  { key: "max_speed_mps", label: "Max Speed", format: formatSpeed },
  { key: "max_hr_bpm", label: "Max HR", format: (v) => `${v} bpm` },
  { key: "biggest_elevation_gain_m", label: "Biggest Climb", format: (v) => `${v.toFixed(0)} m` },
  { key: "highest_sustained_power_w", label: "Highest NP", format: (v) => `${v} W` },
];

export function prsFromRecords(records: Records): PR[] {
  const prs: PR[] = [];
  for (const def of PR_DEFS) {
    const pr = records[def.key];
    if (pr) {
      prs.push({ label: def.label, value: def.format(pr.value) });
    }
  }
  return prs;
}

export function routePRsFromRecords(routePrs: RoutePR[]): PR[] {
  return routePrs.map((rp) => ({
    label: `Route ${rp.route_id}`,
    value: formatTime(rp.fastest_time_s),
  }));
}