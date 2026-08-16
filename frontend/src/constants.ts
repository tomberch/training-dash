// TSB (Training Stress Balance) zone definitions
export interface TSBZone {
  name: string;
  min: number;
  max: number;
  color: string;
}

export const TSB_ZONES: TSBZone[] = [
  { name: "Fresh", min: 25, max: 100, color: "#bbf7d0" },      // Green
  { name: "Optimal", min: 5, max: 25, color: "#fef08a" },      // Yellow
  { name: "Neutral", min: -10, max: 5, color: "#e5e7eb" },     // Gray
  { name: "Fatigued", min: -25, max: -10, color: "#fed7aa" },  // Orange
  { name: "Very Fatigued", min: -100, max: -25, color: "#fecaca" }, // Red
];

export function getTSBZone(tsb: number): TSBZone {
  return TSB_ZONES.find(z => tsb >= z.min && tsb < z.max) || TSB_ZONES[4];
}

// Zone colors (matching typical training zone colors)
export const POWER_ZONE_COLORS: Record<string, string> = {
  "1": "#9ca3af", // Recovery - gray
  "2": "#3b82f6", // Endurance - blue
  "3": "#22c55e", // Tempo - green
  "4": "#eab308", // Threshold - yellow
  "5": "#f97316", // VO2max - orange
  "6": "#ef4444", // Anaerobic - red
  "7": "#7c3aed", // Neuromuscular - purple
};

export const HR_ZONE_COLORS: Record<string, string> = {
  "1": "#9ca3af", // Recovery - gray
  "2": "#3b82f6", // Aerobic - blue
  "3": "#22c55e", // Tempo - green
  "4": "#eab308", // Threshold - yellow
  "5": "#ef4444", // VO2max - red
};

// Day colors for multi-day event maps (cycling through distinguishable colors)
export const DAY_COLORS: string[] = [
  "#6366f1", // indigo
  "#f97316", // orange
  "#22c55e", // green
  "#ec4899", // pink
  "#3b82f6", // blue
  "#eab308", // yellow
  "#8b5cf6", // violet
  "#14b8a6", // teal
  "#ef4444", // red
  "#84cc16", // lime
  "#06b6d4", // cyan
  "#f43f5e", // rose
];
