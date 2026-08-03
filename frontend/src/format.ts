export type UnitSystem = "metric" | "imperial";

const KM_TO_MILES = 0.621371;
const M_TO_FEET = 3.28084;
const MPS_TO_KMH = 3.6;
const MPS_TO_MPH = 2.23694;

export function formatDistance(m: number, unitSystem: UnitSystem = "metric"): string {
  if (unitSystem === "imperial") {
    const miles = (m / 1000) * KM_TO_MILES;
    return `${miles.toFixed(1)} mi`;
  }
  return `${(m / 1000).toFixed(1)} km`;
}

export function formatElevation(m: number, unitSystem: UnitSystem = "metric"): string {
  if (unitSystem === "imperial") {
    const feet = m * M_TO_FEET;
    return `${Math.round(feet)} ft`;
  }
  return `${Math.round(m)} m`;
}

export function formatSpeed(mps: number, unitSystem: UnitSystem = "metric"): string {
  if (unitSystem === "imperial") {
    const mph = mps * MPS_TO_MPH;
    return `${mph.toFixed(1)} mph`;
  }
  const kmh = mps * MPS_TO_KMH;
  return `${kmh.toFixed(1)} km/h`;
}

export function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${sec}s`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CH", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 14) return "1 week ago";
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 60) return "1 month ago";
  return `${Math.floor(diffDays / 30)} months ago`;
}