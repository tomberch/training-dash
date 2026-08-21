import { describe, it, expect } from "vitest";
import {
  airDensityFromAltitude,
  powerRequired,
  speedFromPower,
  timeForSegment,
  recalculatePlan,
  formatTime,
  formatTimeDelta,
  SEA_LEVEL_AIR_DENSITY,
  type RiderParams,
} from "./physics";

const defaultRider: RiderParams = {
  massKg: 83, // 75kg rider + 8kg bike
  cda: 0.32,
  crr: 0.004,
  efficiency: 0.97,
};

describe("airDensityFromAltitude", () => {
  it("returns sea level density at altitude 0", () => {
    const density = airDensityFromAltitude(0);
    expect(density).toBeCloseTo(SEA_LEVEL_AIR_DENSITY, 3);
  });

  it("returns lower density at higher altitude", () => {
    const seaLevel = airDensityFromAltitude(0);
    const at1000m = airDensityFromAltitude(1000);
    const at2000m = airDensityFromAltitude(2000);

    expect(at1000m).toBeLessThan(seaLevel);
    expect(at2000m).toBeLessThan(at1000m);
  });

  it("returns ~1.11 kg/m³ at 1000m", () => {
    const density = airDensityFromAltitude(1000);
    expect(density).toBeCloseTo(1.112, 2);
  });

  it("clamps negative altitude to sea level", () => {
    const density = airDensityFromAltitude(-100);
    expect(density).toBeCloseTo(SEA_LEVEL_AIR_DENSITY, 3);
  });
});

describe("powerRequired", () => {
  it("returns 0 for zero speed", () => {
    expect(powerRequired(0, 0, defaultRider)).toBe(0);
  });

  it("increases cubically with speed on flat ground", () => {
    const p1 = powerRequired(8, 0, defaultRider); // ~29 km/h
    const p2 = powerRequired(12, 0, defaultRider); // ~43 km/h

    // Power should scale roughly with v³ (aero-dominated)
    // 12/8 = 1.5, so power ratio should be ~1.5³ = 3.375
    const ratio = p2 / p1;
    expect(ratio).toBeGreaterThan(2.5);
    expect(ratio).toBeLessThan(4);
  });

  it("requires much more power on climbs", () => {
    const flat = powerRequired(5, 0, defaultRider);
    const climb5pct = powerRequired(5, 5, defaultRider);

    expect(climb5pct).toBeGreaterThan(flat * 3);
  });

  it("requires less power on descents", () => {
    const flat = powerRequired(10, 0, defaultRider);
    const descent = powerRequired(10, -3, defaultRider);

    expect(descent).toBeLessThan(flat);
  });
});

describe("speedFromPower", () => {
  it("returns 0 for zero power", () => {
    expect(speedFromPower(0, 0, defaultRider)).toBe(0);
  });

  it("returns ~9.4 m/s (34 km/h) for 200W on flat", () => {
    const speed = speedFromPower(200, 0, defaultRider);
    expect(speed).toBeCloseTo(9.4, 1);
  });

  it("returns slower speed on climbs", () => {
    const flat = speedFromPower(200, 0, defaultRider);
    const climb = speedFromPower(200, 5, defaultRider);

    expect(climb).toBeLessThan(flat);
    expect(climb).toBeGreaterThan(2); // Should still be moving
    expect(climb).toBeLessThan(6); // But much slower
  });

  it("returns faster speed on descents", () => {
    const flat = speedFromPower(200, 0, defaultRider);
    const descent = speedFromPower(200, -3, defaultRider);

    expect(descent).toBeGreaterThan(flat);
  });

  it("is inverse of powerRequired (round-trip)", () => {
    const originalPower = 250;
    const speed = speedFromPower(originalPower, 2, defaultRider);
    const recoveredPower = powerRequired(speed, 2, defaultRider);

    expect(recoveredPower).toBeCloseTo(originalPower, 1);
  });

  it("handles steep climbs", () => {
    const speed = speedFromPower(300, 10, defaultRider);
    expect(speed).toBeGreaterThan(1);
    expect(speed).toBeLessThan(5);
  });

  it("handles steep descents", () => {
    const speed = speedFromPower(100, -8, defaultRider);
    expect(speed).toBeGreaterThan(10);
  });
});

describe("timeForSegment", () => {
  it("returns 0 for zero distance", () => {
    expect(timeForSegment(0, 0, 200, defaultRider)).toBe(0);
  });

  it("calculates time correctly for flat segment", () => {
    const speed = speedFromPower(200, 0, defaultRider);
    const expectedTime = 1000 / speed;
    const time = timeForSegment(1000, 0, 200, defaultRider);

    expect(time).toBeCloseTo(expectedTime, 1);
  });

  it("takes longer on climbs", () => {
    const flatTime = timeForSegment(1000, 0, 200, defaultRider);
    const climbTime = timeForSegment(1000, 5, 200, defaultRider);

    expect(climbTime).toBeGreaterThan(flatTime);
  });
});

describe("recalculatePlan", () => {
  const segments = [
    { segmentIdx: 0, distanceM: 2000, gradePct: 0, powerW: 200 },
    { segmentIdx: 1, distanceM: 2000, gradePct: 5, powerW: 250 },
    { segmentIdx: 2, distanceM: 2000, gradePct: -3, powerW: 150 },
  ];

  it("calculates total distance correctly", () => {
    const result = recalculatePlan(segments, defaultRider);
    expect(result.totalDistanceM).toBe(6000);
  });

  it("calculates total time as sum of segment times", () => {
    const result = recalculatePlan(segments, defaultRider);

    let expectedTime = 0;
    for (const seg of segments) {
      expectedTime += timeForSegment(seg.distanceM, seg.gradePct, seg.powerW, defaultRider);
    }

    expect(result.totalTimeS).toBeCloseTo(expectedTime, 1);
  });

  it("calculates weighted average power", () => {
    const result = recalculatePlan(segments, defaultRider);

    // Weighted average: (200*2000 + 250*2000 + 150*2000) / 6000 = 200
    expect(result.avgPowerW).toBeCloseTo(200, 1);
  });

  it("returns segment results with calculated speeds", () => {
    const result = recalculatePlan(segments, defaultRider);

    expect(result.segments).toHaveLength(3);
    expect(result.segments[0].speedMps).toBeGreaterThan(0);
    expect(result.segments[1].speedMps).toBeLessThan(result.segments[0].speedMps); // Climb is slower
    expect(result.segments[2].speedMps).toBeGreaterThan(result.segments[0].speedMps); // Descent is faster
  });

  it("changes total time when rider mass changes", () => {
    const lightRider = { ...defaultRider, massKg: 70 };
    const heavyRider = { ...defaultRider, massKg: 95 };

    const lightResult = recalculatePlan(segments, lightRider);
    const heavyResult = recalculatePlan(segments, heavyRider);

    // Lighter rider should be faster
    expect(lightResult.totalTimeS).toBeLessThan(heavyResult.totalTimeS);
  });

  it("changes total time when CdA changes", () => {
    const aerodynamicRider = { ...defaultRider, cda: 0.25 };
    const unaerodynamicRider = { ...defaultRider, cda: 0.40 };

    const aeroResult = recalculatePlan(segments, aerodynamicRider);
    const unaeroResult = recalculatePlan(segments, unaerodynamicRider);

    // More aero rider should be faster
    expect(aeroResult.totalTimeS).toBeLessThan(unaeroResult.totalTimeS);
  });
});

describe("formatTime", () => {
  it("formats seconds as M:SS", () => {
    expect(formatTime(65)).toBe("1:05");
    expect(formatTime(125)).toBe("2:05");
    expect(formatTime(0)).toBe("0:00");
  });

  it("formats hours as H:MM:SS", () => {
    expect(formatTime(3665)).toBe("1:01:05");
    expect(formatTime(7325)).toBe("2:02:05");
  });

  it("pads minutes and seconds", () => {
    expect(formatTime(3601)).toBe("1:00:01");
    expect(formatTime(3660)).toBe("1:01:00");
  });
});

describe("formatTimeDelta", () => {
  it("formats positive delta with + sign", () => {
    expect(formatTimeDelta(65)).toBe("+1:05");
    expect(formatTimeDelta(125)).toBe("+2:05");
  });

  it("formats negative delta with - sign", () => {
    expect(formatTimeDelta(-65)).toBe("-1:05");
    expect(formatTimeDelta(-125)).toBe("-2:05");
  });

  it("formats zero as +0:00", () => {
    expect(formatTimeDelta(0)).toBe("+0:00");
  });
});
