import { describe, it, expect } from "vitest";
import {
  computePowerZones,
  computeHrZones,
  validateZonePercentages,
  DEFAULT_POWER_ZONES,
  DEFAULT_HR_ZONES,
  POWER_ZONE_NAMES,
  HR_ZONE_NAMES,
} from "./zones";

describe("computePowerZones", () => {
  it("computes 7 zones with correct names", () => {
    const zones = computePowerZones(280);

    expect(zones).toHaveLength(7);
    expect(zones[0].name).toBe("Active Recovery");
    expect(zones[1].name).toBe("Endurance");
    expect(zones[2].name).toBe("Tempo");
    expect(zones[3].name).toBe("Threshold");
    expect(zones[4].name).toBe("VO2max");
    expect(zones[5].name).toBe("Anaerobic");
    expect(zones[6].name).toBe("Neuromuscular");
  });

  it("computes correct zone boundaries for FTP=280", () => {
    const zones = computePowerZones(280);

    // Zone 1: 0-55% -> 0-154W
    expect(zones[0].zone).toBe(1);
    expect(zones[0].minValue).toBe(0);
    expect(zones[0].maxValue).toBe(Math.round(280 * 0.55)); // 154

    // Zone 4: 91-105% -> 255-294W
    expect(zones[3].zone).toBe(4);
    expect(zones[3].minValue).toBe(Math.round(280 * 0.91)); // 255
    expect(zones[3].maxValue).toBe(Math.round(280 * 1.05)); // 294

    // Zone 7: 151%+ -> 423+
    expect(zones[6].zone).toBe(7);
    expect(zones[6].minValue).toBe(Math.round(280 * 1.51)); // 423
    expect(zones[6].maxValue).toBeNull();
  });

  it("matches backend calculation for FTP=280", () => {
    // Verify parity with backend domain/zones.py
    const zones = computePowerZones(280);

    // Zone boundaries from backend test
    expect(zones[0].minValue).toBe(0);
    expect(zones[0].maxValue).toBe(154); // 55% of 280 = 154
    expect(zones[1].minValue).toBe(157); // 56% of 280 = 156.8 -> 157
    expect(zones[1].maxValue).toBe(210); // 75% of 280 = 210
    expect(zones[2].minValue).toBe(213); // 76% of 280 = 212.8 -> 213
    expect(zones[2].maxValue).toBe(252); // 90% of 280 = 252
    expect(zones[3].minValue).toBe(255); // 91% of 280 = 254.8 -> 255
    expect(zones[3].maxValue).toBe(294); // 105% of 280 = 294
  });

  it("handles custom percentages", () => {
    const customPct = {
      "1": [0, 50] as [number, number | null],
      "2": [51, 100] as [number, number | null],
      "3": [101, null] as [number, number | null],
    };
    const zones = computePowerZones(200, customPct);

    expect(zones).toHaveLength(3);
    expect(zones[0].maxValue).toBe(100); // 50% of 200
    expect(zones[1].minValue).toBe(102); // 51% of 200
    expect(zones[2].maxValue).toBeNull();
  });

  it("returns sorted zones", () => {
    const zones = computePowerZones(280);
    for (let i = 1; i < zones.length; i++) {
      expect(zones[i].zone).toBeGreaterThan(zones[i - 1].zone);
    }
  });
});

describe("computeHrZones", () => {
  it("computes 5 zones with correct names", () => {
    const zones = computeHrZones(165);

    expect(zones).toHaveLength(5);
    expect(zones[0].name).toBe("Recovery");
    expect(zones[1].name).toBe("Aerobic");
    expect(zones[2].name).toBe("Tempo");
    expect(zones[3].name).toBe("Threshold");
    expect(zones[4].name).toBe("Anaerobic");
  });

  it("computes correct zone boundaries for LTHR=165", () => {
    const zones = computeHrZones(165);

    // Zone 1: 0-81% -> 0-134 bpm
    expect(zones[0].zone).toBe(1);
    expect(zones[0].minValue).toBe(0);
    expect(zones[0].maxValue).toBe(Math.round(165 * 0.81)); // 134

    // Zone 4: 94-99% -> 155-163 bpm
    expect(zones[3].zone).toBe(4);
    expect(zones[3].minValue).toBe(Math.round(165 * 0.94)); // 155
    expect(zones[3].maxValue).toBe(Math.round(165 * 0.99)); // 163

    // Zone 5: 100%+ -> 165+
    expect(zones[4].zone).toBe(5);
    expect(zones[4].minValue).toBe(Math.round(165 * 1.0)); // 165
    expect(zones[4].maxValue).toBeNull();
  });

  it("returns sorted zones", () => {
    const zones = computeHrZones(165);
    for (let i = 1; i < zones.length; i++) {
      expect(zones[i].zone).toBeGreaterThan(zones[i - 1].zone);
    }
  });
});

describe("validateZonePercentages", () => {
  it("returns null for valid default power zones", () => {
    expect(validateZonePercentages(DEFAULT_POWER_ZONES)).toBeNull();
  });

  it("returns null for valid default HR zones", () => {
    expect(validateZonePercentages(DEFAULT_HR_ZONES)).toBeNull();
  });

  it("returns error for min >= max", () => {
    const invalid = {
      "1": [50, 40] as [number, number | null],
      "2": [60, null] as [number, number | null],
    };
    const error = validateZonePercentages(invalid);
    expect(error).toContain("min must be less than max");
  });

  it("returns error for unbounded zone that is not last", () => {
    const invalid = {
      "1": [0, null] as [number, number | null],
      "2": [50, 100] as [number, number | null],
    };
    const error = validateZonePercentages(invalid);
    expect(error).toContain("only the last zone can be unbounded");
  });

  it("returns error for gaps between zones", () => {
    const invalid = {
      "1": [0, 50] as [number, number | null],
      "2": [60, null] as [number, number | null], // Gap: 51-59 missing
    };
    const error = validateZonePercentages(invalid);
    expect(error).toContain("Gap or overlap");
  });
});

describe("zone constants", () => {
  it("has 7 power zone names", () => {
    expect(Object.keys(POWER_ZONE_NAMES)).toHaveLength(7);
  });

  it("has 5 HR zone names", () => {
    expect(Object.keys(HR_ZONE_NAMES)).toHaveLength(5);
  });

  it("has 7 default power zones", () => {
    expect(Object.keys(DEFAULT_POWER_ZONES)).toHaveLength(7);
  });

  it("has 5 default HR zones", () => {
    expect(Object.keys(DEFAULT_HR_ZONES)).toHaveLength(5);
  });
});
