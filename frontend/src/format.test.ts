import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatDistance,
  formatElevation,
  formatSpeed,
  formatDuration,
  formatRelativeTime,
  formatActivityDate,
  formatActivityTime,
} from "./format";

describe("formatDistance", () => {
  it("returns km for metric", () => {
    expect(formatDistance(5000, "metric")).toBe("5.0 km");
    expect(formatDistance(12345, "metric")).toBe("12.3 km");
  });

  it("returns miles for imperial", () => {
    // 5000m = 5km = 3.10686 miles
    expect(formatDistance(5000, "imperial")).toBe("3.1 mi");
    // 16093m ≈ 10 miles
    expect(formatDistance(16093, "imperial")).toBe("10.0 mi");
  });

  it("defaults to metric when no unit system provided", () => {
    expect(formatDistance(5000)).toBe("5.0 km");
  });
});

describe("formatElevation", () => {
  it("returns meters for metric", () => {
    expect(formatElevation(500, "metric")).toBe("500 m");
    expect(formatElevation(1234, "metric")).toBe("1234 m");
  });

  it("returns feet for imperial", () => {
    // 500m = 1640.42 feet
    expect(formatElevation(500, "imperial")).toBe("1640 ft");
    // 100m = 328.084 feet
    expect(formatElevation(100, "imperial")).toBe("328 ft");
  });

  it("defaults to metric when no unit system provided", () => {
    expect(formatElevation(500)).toBe("500 m");
  });
});

describe("formatSpeed", () => {
  it("returns km/h for metric", () => {
    // 10 m/s = 36 km/h
    expect(formatSpeed(10, "metric")).toBe("36.0 km/h");
    // 5 m/s = 18 km/h
    expect(formatSpeed(5, "metric")).toBe("18.0 km/h");
  });

  it("returns mph for imperial", () => {
    // 10 m/s = 22.3694 mph
    expect(formatSpeed(10, "imperial")).toBe("22.4 mph");
    // 5 m/s = 11.1847 mph
    expect(formatSpeed(5, "imperial")).toBe("11.2 mph");
  });

  it("defaults to metric when no unit system provided", () => {
    expect(formatSpeed(10)).toBe("36.0 km/h");
  });
});

describe("formatDuration", () => {
  it("formats minutes only for durations under an hour", () => {
    expect(formatDuration(300)).toBe("5m");
    expect(formatDuration(1800)).toBe("30m");
    expect(formatDuration(60)).toBe("1m");
  });

  it("formats hours and minutes with leading zeros for longer durations", () => {
    expect(formatDuration(3600)).toBe("1h 00m");
    expect(formatDuration(3660)).toBe("1h 01m");
    expect(formatDuration(7200)).toBe("2h 00m");
    expect(formatDuration(5400)).toBe("1h 30m");
  });

  it("handles zero", () => {
    expect(formatDuration(0)).toBe("0m");
  });
});

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-06-15T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns Today for same day", () => {
    expect(formatRelativeTime("2024-06-15T08:00:00Z")).toBe("Today");
  });

  it("returns Yesterday for previous day", () => {
    expect(formatRelativeTime("2024-06-14T12:00:00Z")).toBe("Yesterday");
  });

  it("returns days ago for 2-6 days", () => {
    expect(formatRelativeTime("2024-06-13T12:00:00Z")).toBe("2 days ago");
    expect(formatRelativeTime("2024-06-10T12:00:00Z")).toBe("5 days ago");
  });

  it("returns 1 week ago for 7-13 days", () => {
    expect(formatRelativeTime("2024-06-08T12:00:00Z")).toBe("1 week ago");
    expect(formatRelativeTime("2024-06-03T12:00:00Z")).toBe("1 week ago");
  });

  it("returns weeks ago for 14-29 days", () => {
    expect(formatRelativeTime("2024-06-01T12:00:00Z")).toBe("2 weeks ago");
    expect(formatRelativeTime("2024-05-20T12:00:00Z")).toBe("3 weeks ago");
  });

  it("returns 1 month ago for 30-59 days", () => {
    expect(formatRelativeTime("2024-05-16T12:00:00Z")).toBe("1 month ago");
    expect(formatRelativeTime("2024-04-20T12:00:00Z")).toBe("1 month ago");
  });

  it("returns months ago for 60+ days", () => {
    expect(formatRelativeTime("2024-04-15T12:00:00Z")).toBe("2 months ago");
    expect(formatRelativeTime("2024-01-15T12:00:00Z")).toBe("5 months ago");
  });
});


describe("formatActivityDate", () => {
  it("uses browser locale when utcOffsetMinutes is null", () => {
    // When offset is null the result is locale-dependent; just verify it's a non-empty string
    const result = formatActivityDate("2024-06-15T07:30:00+00:00", null);
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("shows date in ride-local time when offset is positive (UTC+2)", () => {
    // 2024-06-15T22:30:00Z + 120min → 2024-06-16T00:30 local
    // With timeZone:'UTC' and undefined locale the date portion should be June 16
    const result = formatActivityDate("2024-06-15T22:30:00+00:00", 120);
    expect(result).toContain("16");   // day 16 in local time
    expect(result).not.toContain("15"); // not day 15 (UTC day)
  });

  it("shows date in ride-local time when offset is negative (UTC-5)", () => {
    // 2024-06-15T02:00:00Z - 300min → 2024-06-14T21:00 local
    const result = formatActivityDate("2024-06-15T02:00:00+00:00", -300);
    expect(result).toContain("14");   // day 14 in local time
    expect(result).not.toContain("15");
  });

  it("accepts custom DateTimeFormatOptions", () => {
    const result = formatActivityDate(
      "2024-06-15T07:30:00+00:00",
      120,
      { month: "long", day: "numeric" },
    );
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });
});

describe("formatActivityTime", () => {
  it("uses browser locale when utcOffsetMinutes is null", () => {
    const result = formatActivityTime("2024-06-15T07:30:00+00:00", null);
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("shows time in ride-local time when offset is positive (UTC+2)", () => {
    // 07:30 UTC + 120min → 09:30 local
    const result = formatActivityTime("2024-06-15T07:30:00+00:00", 120);
    expect(result).toBe("09:30");
  });

  it("shows time in ride-local time when offset is negative (UTC-5)", () => {
    // 14:00 UTC - 300min → 09:00 local
    const result = formatActivityTime("2024-06-15T14:00:00+00:00", -300);
    expect(result).toBe("09:00");
  });

  it("handles midnight rollover correctly", () => {
    // 23:00 UTC + 120min → 01:00 next day
    const result = formatActivityTime("2024-06-15T23:00:00+00:00", 120);
    expect(result).toBe("01:00");
  });
});
