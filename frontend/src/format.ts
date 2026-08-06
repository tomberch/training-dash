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
  const sec = Math.round(s % 60);
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

/**
 * Format an activity's start date in the athlete's local time.
 *
 * When utcOffsetMinutes is provided (from the FIT file's local_timestamp), the
 * date is shown in the timezone where the ride was recorded, regardless of the
 * viewer's browser timezone.
 *
 * When utcOffsetMinutes is null (historical activities or devices that don't
 * write local_timestamp), falls back to the browser's local timezone — correct
 * for the common case where users ride at home.
 */
export function formatActivityDate(
  iso: string,
  utcOffsetMinutes: number | null,
  options: Intl.DateTimeFormatOptions = { year: "numeric", month: "short", day: "numeric" },
): string {
  if (utcOffsetMinutes !== null) {
    // Shift the UTC timestamp by the stored offset, then render as UTC so the
    // browser does not apply its own timezone conversion on top.
    const utcMs = new Date(iso).getTime();
    const localMs = utcMs + utcOffsetMinutes * 60_000;
    return new Date(localMs).toLocaleDateString("en-CH", { ...options, timeZone: "UTC" });
  }
  return new Date(iso).toLocaleDateString(undefined, options);
}

/**
 * Format an activity's start time in the athlete's local time.
 *
 * Same offset logic as formatActivityDate. When offset is null, falls back to
 * browser local timezone.
 */
export function formatActivityTime(
  iso: string,
  utcOffsetMinutes: number | null,
  options: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hour12: false },
): string {
  if (utcOffsetMinutes !== null) {
    const utcMs = new Date(iso).getTime();
    const localMs = utcMs + utcOffsetMinutes * 60_000;
    return new Date(localMs).toLocaleTimeString("en-CH", { ...options, timeZone: "UTC" });
  }
  return new Date(iso).toLocaleTimeString(undefined, options);
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