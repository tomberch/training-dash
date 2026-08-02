import { describe, it, expect } from "vitest";
import { formatDistance, formatElevation, formatSpeed } from "./format";

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
