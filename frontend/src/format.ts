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
  const pad = (n: number) => n.toString().padStart(2, "0");
  if (h > 0) {
    if (sec > 0) return `${h}h ${pad(m)}m ${pad(sec)}s`;
    return `${h}h ${pad(m)}m`;
  }
  if (sec > 0) return `${m}m ${pad(sec)}s`;
  return `${m}m`;
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
    return new Date(localMs).toLocaleDateString(undefined, { ...options, timeZone: "UTC" });
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
    return new Date(localMs).toLocaleTimeString(undefined, { ...options, timeZone: "UTC" });
  }
  return new Date(iso).toLocaleTimeString(undefined, options);
}

/**
 * Format elapsed seconds as H:MM:SS (or M:SS when under one hour).
 * Used for chart axis tick labels and activity time ranges.
 */
export function formatElapsedTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * Format a distance in metres for chart axis labels.
 * Values ≥ 1 km are shown as km (with one decimal place unless whole number).
 */
export function formatDistanceAxis(meters: number): string {
  if (meters >= 1000) {
    const km = meters / 1000;
    return km % 1 === 0 ? `${km.toFixed(0)} km` : `${km.toFixed(1)} km`;
  }
  return `${meters.toFixed(0)} m`;
}

/**
 * Return the ISO string for the end time of an activity.
 * Keeps the arithmetic out of JSX and centralises the "start + elapsed" concept.
 */
export function activityEndTimeIso(startedAt: string, elapsedTimeS: number): string {
  return new Date(new Date(startedAt).getTime() + elapsedTimeS * 1000).toISOString();
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m.toString().padStart(2, "0")}m`;
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