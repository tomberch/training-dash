/**
 * Event-related utility functions
 * Shared helpers for event date formatting, duration display, and single-day detection
 */

/**
 * Format a duration in seconds to a human-readable string
 * Examples: 300 → "5m", 3660 → "1h 1m", 7200 → "2h 0m"
 */
export function formatEventDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Check if an event is a single-day event
 * Single-day events have the same start and end date (or no end date)
 */
export function isSingleDayEvent(startDate: string, endDate: string | null | undefined): boolean {
  if (!endDate) return true;
  return startDate === endDate;
}

/**
 * Format a date range for display in event lists/cards
 * Handles single day, same month, same year, and different year cases
 * 
 * Examples:
 * - Single day: "Jan 15, 2024"
 * - Same month: "Jan 15 – 18, 2024"
 * - Same year: "Jan 15 – Feb 2, 2024"
 * - Different year: "Dec 2023 – Jan 2024"
 */
export function formatEventDateRange(start: string, end: string | null | undefined): string {
  const s = new Date(start);
  const e = end ? new Date(end) : s;
  
  // Single day event
  if (!end || start === end) {
    return s.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
  
  // Same year
  if (s.getFullYear() === e.getFullYear()) {
    // Same month
    if (s.getMonth() === e.getMonth()) {
      return `${s.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${e.getDate()}, ${e.getFullYear()}`;
    }
    // Different months
    return `${s.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${e.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
  }
  
  // Different years
  return `${s.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })} – ${e.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}`;
}

/**
 * Format a single date for full display (event detail header)
 * Example: "Saturday, January 15, 2024"
 */
export function formatEventFullDate(date: string): string {
  return new Date(date).toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
}

/**
 * Format dates for event detail header
 * Returns full format for single day, range format for multi-day
 */
export function formatEventHeaderDates(start: string, end: string | null | undefined): string {
  if (isSingleDayEvent(start, end)) {
    return formatEventFullDate(start);
  }
  return `${new Date(start).toLocaleDateString()} – ${new Date(end!).toLocaleDateString()}`;
}
