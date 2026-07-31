import { describe, it, expect } from "vitest";
import { resampleByDistance, BUCKET_SIZE_M } from "./resampler";
import type { ResampleInput } from "./resampler";

function makeRecords(num: number, step: number = 10): ResampleInput[] {
  const records: ResampleInput[] = [];
  for (let i = 0; i < num; i++) {
    records.push({
      distance_m: i * step,
      hr_bpm: 120 + i,
      power_w: 200 + i,
      speed_mps: 8.0 + i * 0.1,
      altitude_m: 500.0 + i,
    });
  }
  return records;
}

describe("resampleByDistance", () => {
  it("produces uniform 50m buckets", () => {
    const records = makeRecords(20, 10); // 0 to 190m
    const result = resampleByDistance(records);
    expect(result.length).toBeGreaterThan(0);
    for (let i = 0; i < result.length; i++) {
      expect(result[i].distance_m).toBeCloseTo(i * BUCKET_SIZE_M, 5);
    }
  });

  it("handles zero-distance activity", () => {
    const records: ResampleInput[] = [
      { distance_m: 0, hr_bpm: 120, power_w: 200, speed_mps: 8.0, altitude_m: 500 },
    ];
    const result = resampleByDistance(records);
    expect(result.length).toBe(1);
    expect(result[0].distance_m).toBe(0);
    expect(result[0].hr_bpm).toBe(120);
  });

  it("handles empty input", () => {
    const result = resampleByDistance([]);
    expect(result).toEqual([]);
  });

  it("preserves hr/power/alt at each bucket via interpolation", () => {
    const records = makeRecords(10, 10); // 0 to 90m
    const result = resampleByDistance(records);
    // At 0m, should match first record
    expect(result[0].hr_bpm).toBe(120);
    expect(result[0].power_w).toBe(200);
    // At 50m, should interpolate between record at 50m (index 5)
    const b50 = result[1];
    expect(b50.distance_m).toBeCloseTo(50, 5);
    expect(b50.hr_bpm).toBe(125);
    expect(b50.power_w).toBe(205);
  });

  it("truncates to the shorter ride when comparing (max distance)", () => {
    const short = makeRecords(5, 10); // 0 to 40m
    const long = makeRecords(20, 10); // 0 to 190m
    const shortRes = resampleByDistance(short);
    const longRes = resampleByDistance(long);
    // Short ride has fewer buckets
    expect(shortRes.length).toBeLessThan(longRes.length);
    // Both start at 0
    expect(shortRes[0].distance_m).toBe(0);
    expect(longRes[0].distance_m).toBe(0);
  });

  it("handles null fields in records", () => {
    const records: ResampleInput[] = [
      { distance_m: 0, hr_bpm: null, power_w: null, speed_mps: null, altitude_m: null },
      { distance_m: 100, hr_bpm: 140, power_w: 250, speed_mps: 9.0, altitude_m: 520 },
    ];
    const result = resampleByDistance(records);
    expect(result[0].hr_bpm).toBeNull();
    // At 50m, interpolate between null and 140 → 140 (lerp handles null)
    expect(result[1].hr_bpm).toBe(140);
  });
});