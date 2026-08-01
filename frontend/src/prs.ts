import type { Records } from "./api";

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

export function prsFromRecords(records: Records): PR[] {
  const prs: PR[] = [];

  if (records.longest_distance_m) {
    prs.push({ label: "Longest Ride", value: formatDistance(records.longest_distance_m.value) });
  }
  if (records.longest_moving_time_s) {
    prs.push({ label: "Longest Ride (Time)", value: formatTime(records.longest_moving_time_s.value) });
  }
  if (records.fastest_5000_m) {
    prs.push({ label: "Fastest 5km", value: formatTime(records.fastest_5000_m.value) });
  }
  if (records.fastest_10000_m) {
    prs.push({ label: "Fastest 10km", value: formatTime(records.fastest_10000_m.value) });
  }
  if (records.fastest_40000_m) {
    prs.push({ label: "Fastest 40km", value: formatTime(records.fastest_40000_m.value) });
  }
  if (records.max_speed_mps) {
    prs.push({ label: "Max Speed", value: formatSpeed(records.max_speed_mps.value) });
  }
  if (records.max_hr_bpm) {
    prs.push({ label: "Max HR", value: `${records.max_hr_bpm.value} bpm` });
  }
  if (records.biggest_elevation_gain_m) {
    prs.push({ label: "Biggest Climb", value: `${records.biggest_elevation_gain_m.value.toFixed(0)} m` });
  }
  if (records.highest_sustained_power_w) {
    prs.push({ label: "Highest NP", value: `${records.highest_sustained_power_w.value} W` });
  }

  return prs;
}