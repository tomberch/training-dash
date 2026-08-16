import { describe, it, expect } from "vitest";
import {
  formatEventDuration,
  isSingleDayEvent,
  formatEventDateRange,
  formatEventFullDate,
  formatEventHeaderDates,
} from "./event-utils";

describe("formatEventDuration", () => {
  it("formats minutes only for durations under an hour", () => {
    expect(formatEventDuration(0)).toBe("0m");
    expect(formatEventDuration(60)).toBe("1m");
    expect(formatEventDuration(300)).toBe("5m");
    expect(formatEventDuration(1800)).toBe("30m");
    expect(formatEventDuration(3540)).toBe("59m");
  });

  it("formats hours and minutes for durations of an hour or more", () => {
    expect(formatEventDuration(3600)).toBe("1h 0m");
    expect(formatEventDuration(3660)).toBe("1h 1m");
    expect(formatEventDuration(5400)).toBe("1h 30m");
    expect(formatEventDuration(7200)).toBe("2h 0m");
    expect(formatEventDuration(10800)).toBe("3h 0m");
  });

  it("handles large durations", () => {
    expect(formatEventDuration(36000)).toBe("10h 0m");
    expect(formatEventDuration(86400)).toBe("24h 0m"); // Full day
    expect(formatEventDuration(90061)).toBe("25h 1m");
  });
});

describe("isSingleDayEvent", () => {
  it("returns true when end date is null", () => {
    expect(isSingleDayEvent("2024-01-15", null)).toBe(true);
  });

  it("returns true when end date is undefined", () => {
    expect(isSingleDayEvent("2024-01-15", undefined)).toBe(true);
  });

  it("returns true when start and end dates are the same", () => {
    expect(isSingleDayEvent("2024-01-15", "2024-01-15")).toBe(true);
  });

  it("returns false when start and end dates differ", () => {
    expect(isSingleDayEvent("2024-01-15", "2024-01-16")).toBe(false);
    expect(isSingleDayEvent("2024-01-15", "2024-01-20")).toBe(false);
    expect(isSingleDayEvent("2024-01-15", "2024-02-15")).toBe(false);
    expect(isSingleDayEvent("2024-01-15", "2025-01-15")).toBe(false);
  });
});

describe("formatEventDateRange", () => {
  it("formats single day event (no end date)", () => {
    const result = formatEventDateRange("2024-01-15", null);
    // Locale-dependent, but should contain day and year
    expect(result).toContain("15");
    expect(result).toContain("2024");
  });

  it("formats single day event (same start/end)", () => {
    const result = formatEventDateRange("2024-01-15", "2024-01-15");
    expect(result).toContain("15");
    expect(result).toContain("2024");
  });

  it("formats same-month range", () => {
    const result = formatEventDateRange("2024-01-15", "2024-01-18");
    // Should contain both days and year once
    expect(result).toContain("15");
    expect(result).toContain("18");
    expect(result).toContain("2024");
    // Should contain en-dash separator
    expect(result).toContain("–");
  });

  it("formats same-year range", () => {
    const result = formatEventDateRange("2024-01-15", "2024-02-02");
    expect(result).toContain("15");
    expect(result).toContain("2");
    expect(result).toContain("2024");
  });

  it("formats cross-year range", () => {
    const result = formatEventDateRange("2023-12-28", "2024-01-05");
    expect(result).toContain("2023");
    expect(result).toContain("2024");
  });
});

describe("formatEventFullDate", () => {
  it("includes weekday, month, day, and year", () => {
    const result = formatEventFullDate("2024-01-15");
    // The specific format depends on locale, but should contain these elements
    expect(result).toContain("2024");
    expect(result).toContain("15");
    // Length check: full format should be longer than short format
    expect(result.length).toBeGreaterThan(10);
  });
});

describe("formatEventHeaderDates", () => {
  it("returns full date format for single-day events", () => {
    const result = formatEventHeaderDates("2024-01-15", "2024-01-15");
    // Should be in full format (long weekday, month, day, year)
    expect(result.length).toBeGreaterThan(15); // Full format is longer
    expect(result).toContain("2024");
  });

  it("returns range format for multi-day events", () => {
    const result = formatEventHeaderDates("2024-01-15", "2024-01-20");
    expect(result).toContain("–"); // Contains date range separator
  });

  it("handles null end date as single-day", () => {
    const result = formatEventHeaderDates("2024-01-15", null);
    // Should be full format
    expect(result.length).toBeGreaterThan(15);
  });
});
