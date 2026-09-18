import { describe, it, expect } from "vitest";
import { computeSegmentPreview, categorizeClimb, nearestFeatureIndex } from "./segmentPreview";
import type { GeoJSONFeatureCollection } from "@/api";

function feature(_index: number, lng: number, lat: number, altitude_m: number | null, distance_m: number) {
  return {
    type: "Feature" as const,
    geometry: altitude_m === null ? null : { type: "Point", coordinates: [lng, lat] },
    properties: {
      timestamp: "2024-01-01T00:00:00Z",
      distance_m,
      hr_bpm: null,
      power_w: null,
      speed_mps: null,
      altitude_m,
      cadence_rpm: null,
    },
  };
}

function collection(features: ReturnType<typeof feature>[]): GeoJSONFeatureCollection {
  return { type: "FeatureCollection", activity_id: "a1", features };
}

describe("categorizeClimb", () => {
  it("maps score to category", () => {
    expect(categorizeClimb(10000, 8)).toBe("hc");
    expect(categorizeClimb(8000, 8)).toBe("1");
    expect(categorizeClimb(4000, 8)).toBe("2");
    expect(categorizeClimb(2000, 8)).toBe("3");
    expect(categorizeClimb(1000, 8)).toBe("4");
    expect(categorizeClimb(500, 8)).toBe("nc");
  });
});

describe("computeSegmentPreview", () => {
  it("returns null when range has fewer than 2 valid points", () => {
    const c = collection([
      feature(0, 0, 0, null, 0),
      feature(1, 1, 1, null, 100),
    ]);
    expect(computeSegmentPreview(c.features, 0, 1)).toBeNull();
  });

  it("computes distance, elevation, grade, and classifies a climb", () => {
    // 300m climb at ~5% grade -> type climb
    const c = collection([
      feature(0, 0, 0, 0, 0),
      feature(1, 0.001, 0.001, 5, 100),
      feature(2, 0.002, 0.002, 10, 200),
      feature(3, 0.003, 0.003, 15, 300),
    ]);
    const p = computeSegmentPreview(c.features, 0, 3);
    expect(p).not.toBeNull();
    expect(p!.type).toBe("climb");
    expect(p!.distance_m).toBeGreaterThan(200);
    expect(p!.elevation_gain_m).toBeCloseTo(15, 0);
  });

  it("classifies a flat short section as sprint", () => {
    const c = collection([
      feature(0, 0, 0, 10, 0),
      feature(1, 0.002, 0, 10.5, 200),
      feature(2, 0.004, 0, 11, 400),
    ]);
    const p = computeSegmentPreview(c.features, 0, 2);
    expect(p).not.toBeNull();
    expect(p!.type).toBe("sprint");
    expect(p!.climb_category).toBeNull();
  });

  it("classifies other sections as custom", () => {
    const c = collection([
      feature(0, 0, 0, 10, 0),
      feature(1, 0.002, 0, 10.5, 200),
      feature(2, 0.004, 0, 11, 400),
      feature(3, 0.006, 0, 11.5, 600),
      feature(4, 0.008, 0, 12, 800),
    ]);
    const p = computeSegmentPreview(c.features, 0, 4);
    expect(p).not.toBeNull();
    expect(p!.type).toBe("custom");
  });
});

describe("nearestFeatureIndex", () => {
  it("returns nearest valid feature index", () => {
    const c = collection([
      feature(0, 0, 0, 0, 0),
      feature(1, 0.01, 0.01, 0, 100),
      feature(2, 0.02, 0.02, 0, 200),
    ]);
    expect(nearestFeatureIndex(c.features, 0.019, 0.019)).toBe(2);
  });

  it("returns null when no valid features", () => {
    const c = collection([feature(0, 0, 0, null, 0)]);
    expect(nearestFeatureIndex(c.features, 0, 0)).toBeNull();
  });
});
