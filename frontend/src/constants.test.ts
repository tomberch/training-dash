import { describe, it, expect } from "vitest";
import { TSB_ZONES, getTSBZone, POWER_ZONE_COLORS, HR_ZONE_COLORS } from "./constants";

describe("TSB_ZONES", () => {
  it("has 5 zones with correct names", () => {
    expect(TSB_ZONES).toHaveLength(5);
    expect(TSB_ZONES.map(z => z.name)).toEqual([
      "Fresh",
      "Optimal",
      "Neutral",
      "Fatigued",
      "Very Fatigued",
    ]);
  });

  it("zones have continuous coverage from -100 to 100", () => {
    const sortedByMin = [...TSB_ZONES].sort((a, b) => a.min - b.min);
    expect(sortedByMin[0].min).toBe(-100);
    expect(sortedByMin[sortedByMin.length - 1].max).toBe(100);
  });
});

describe("getTSBZone", () => {
  it("returns Fresh for TSB >= 25", () => {
    expect(getTSBZone(25).name).toBe("Fresh");
    expect(getTSBZone(50).name).toBe("Fresh");
    expect(getTSBZone(99).name).toBe("Fresh");
  });

  it("returns Optimal for TSB 5-24", () => {
    expect(getTSBZone(5).name).toBe("Optimal");
    expect(getTSBZone(15).name).toBe("Optimal");
    expect(getTSBZone(24).name).toBe("Optimal");
  });

  it("returns Neutral for TSB -10 to 4", () => {
    expect(getTSBZone(-10).name).toBe("Neutral");
    expect(getTSBZone(0).name).toBe("Neutral");
    expect(getTSBZone(4).name).toBe("Neutral");
  });

  it("returns Fatigued for TSB -25 to -11", () => {
    expect(getTSBZone(-25).name).toBe("Fatigued");
    expect(getTSBZone(-15).name).toBe("Fatigued");
    expect(getTSBZone(-11).name).toBe("Fatigued");
  });

  it("returns Very Fatigued for TSB < -25", () => {
    expect(getTSBZone(-26).name).toBe("Very Fatigued");
    expect(getTSBZone(-50).name).toBe("Very Fatigued");
    expect(getTSBZone(-100).name).toBe("Very Fatigued");
  });

  it("returns Very Fatigued for extreme negative values", () => {
    expect(getTSBZone(-150).name).toBe("Very Fatigued");
  });
});

describe("POWER_ZONE_COLORS", () => {
  it("has colors for zones 1-7", () => {
    expect(Object.keys(POWER_ZONE_COLORS)).toHaveLength(7);
    for (let i = 1; i <= 7; i++) {
      expect(POWER_ZONE_COLORS[String(i)]).toBeDefined();
      expect(POWER_ZONE_COLORS[String(i)]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});

describe("HR_ZONE_COLORS", () => {
  it("has colors for zones 1-5", () => {
    expect(Object.keys(HR_ZONE_COLORS)).toHaveLength(5);
    for (let i = 1; i <= 5; i++) {
      expect(HR_ZONE_COLORS[String(i)]).toBeDefined();
      expect(HR_ZONE_COLORS[String(i)]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
