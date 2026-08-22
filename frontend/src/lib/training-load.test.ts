import { describe, it, expect } from "vitest";
import {
  calculateIntensityFactor,
  calculateTss,
  calculateTrainingLoad,
  recalculateWithNewFtp,
  formatIntensityFactor,
  formatTss,
  getTssDescription,
  getIntensityDescription,
} from "./training-load";

describe("calculateIntensityFactor", () => {
  it("returns correct IF for threshold effort", () => {
    // NP equals FTP -> IF = 1.0
    const if1 = calculateIntensityFactor(280, 280);
    expect(if1).toBe(1.0);
  });

  it("returns IF < 1 for sub-threshold effort", () => {
    // NP = 245, FTP = 280 -> IF ≈ 0.875
    const if1 = calculateIntensityFactor(245, 280);
    expect(if1).toBeCloseTo(0.875, 3);
  });

  it("returns IF > 1 for supra-threshold effort", () => {
    // NP = 300, FTP = 280 -> IF ≈ 1.071
    const if1 = calculateIntensityFactor(300, 280);
    expect(if1).toBeCloseTo(1.071, 3);
  });

  it("returns 0 for zero FTP", () => {
    expect(calculateIntensityFactor(200, 0)).toBe(0);
  });

  it("returns 0 for zero NP", () => {
    expect(calculateIntensityFactor(0, 280)).toBe(0);
  });

  it("returns 0 for negative values", () => {
    expect(calculateIntensityFactor(-100, 280)).toBe(0);
    expect(calculateIntensityFactor(100, -280)).toBe(0);
  });
});

describe("calculateTss", () => {
  it("returns ~100 TSS for 1 hour at FTP", () => {
    // 1 hour at FTP should give TSS = 100
    const tss = calculateTss({
      normalizedPower: 280,
      ftp: 280,
      durationSeconds: 3600,
    });
    expect(tss).toBeCloseTo(100, 1);
  });

  it("returns ~50 TSS for 1 hour at 70% FTP", () => {
    // IF = 0.707, TSS = (3600 × 198 × 0.707) / (280 × 3600) × 100 ≈ 50
    const tss = calculateTss({
      normalizedPower: 198, // ~70.7% of 280
      ftp: 280,
      durationSeconds: 3600,
    });
    expect(tss).toBeCloseTo(50, 1);
  });

  it("scales linearly with duration", () => {
    const tss1h = calculateTss({
      normalizedPower: 245,
      ftp: 280,
      durationSeconds: 3600,
    });
    const tss2h = calculateTss({
      normalizedPower: 245,
      ftp: 280,
      durationSeconds: 7200,
    });
    expect(tss2h).toBeCloseTo(tss1h * 2, 1);
  });

  it("scales with IF squared", () => {
    // TSS ∝ IF² (since TSS = duration × NP × IF / (FTP × 3600) × 100)
    // If we double IF (by doubling NP), TSS quadruples
    const tss1 = calculateTss({
      normalizedPower: 140,
      ftp: 280,
      durationSeconds: 3600,
    }); // IF = 0.5
    const tss2 = calculateTss({
      normalizedPower: 280,
      ftp: 280,
      durationSeconds: 3600,
    }); // IF = 1.0

    // TSS2 / TSS1 should be ~4 (1²/0.5² = 4)
    expect(tss2 / tss1).toBeCloseTo(4, 1);
  });

  it("returns 0 for invalid inputs", () => {
    expect(calculateTss({ normalizedPower: 0, ftp: 280, durationSeconds: 3600 })).toBe(0);
    expect(calculateTss({ normalizedPower: 245, ftp: 0, durationSeconds: 3600 })).toBe(0);
    expect(calculateTss({ normalizedPower: 245, ftp: 280, durationSeconds: 0 })).toBe(0);
  });

  it("matches backend calculation for typical activity", () => {
    // Test case: 90 min ride, NP=245W, FTP=280W
    // TSS = (5400 × 245 × 0.875) / (280 × 3600) × 100 = 114.84
    const tss = calculateTss({
      normalizedPower: 245,
      ftp: 280,
      durationSeconds: 5400,
    });
    expect(tss).toBeCloseTo(114.8, 1);
  });
});

describe("calculateTrainingLoad", () => {
  it("returns both IF and TSS", () => {
    const result = calculateTrainingLoad({
      normalizedPower: 245,
      ftp: 280,
      durationSeconds: 3600,
    });

    expect(result.intensityFactor).toBeCloseTo(0.875, 3);
    expect(result.tss).toBeGreaterThan(0);
  });

  it("returns zeros for invalid inputs", () => {
    const result = calculateTrainingLoad({
      normalizedPower: 0,
      ftp: 280,
      durationSeconds: 3600,
    });

    expect(result.intensityFactor).toBe(0);
    expect(result.tss).toBe(0);
  });
});

describe("recalculateWithNewFtp", () => {
  it("increases TSS when FTP decreases", () => {
    const original = calculateTrainingLoad({
      normalizedPower: 245,
      ftp: 280,
      durationSeconds: 3600,
    });

    const withLowerFtp = recalculateWithNewFtp(245, 260, 3600);

    expect(withLowerFtp.intensityFactor).toBeGreaterThan(original.intensityFactor);
    expect(withLowerFtp.tss).toBeGreaterThan(original.tss);
  });

  it("decreases TSS when FTP increases", () => {
    const original = calculateTrainingLoad({
      normalizedPower: 245,
      ftp: 280,
      durationSeconds: 3600,
    });

    const withHigherFtp = recalculateWithNewFtp(245, 300, 3600);

    expect(withHigherFtp.intensityFactor).toBeLessThan(original.intensityFactor);
    expect(withHigherFtp.tss).toBeLessThan(original.tss);
  });

  it("keeps NP constant (only interpretation changes)", () => {
    // When FTP changes, NP stays the same (it's from the data)
    // Only IF and TSS change
    const result1 = recalculateWithNewFtp(245, 280, 3600);
    const result2 = recalculateWithNewFtp(245, 260, 3600);

    // Both used NP=245, but different FTP
    expect(result1.intensityFactor).toBeCloseTo(245 / 280, 3);
    expect(result2.intensityFactor).toBeCloseTo(245 / 260, 3);
  });
});

describe("formatIntensityFactor", () => {
  it("formats to 2 decimal places by default", () => {
    expect(formatIntensityFactor(0.875)).toBe("0.88");
    expect(formatIntensityFactor(1.0)).toBe("1.00");
    expect(formatIntensityFactor(1.123456)).toBe("1.12");
  });

  it("respects custom decimal places", () => {
    expect(formatIntensityFactor(0.875, 3)).toBe("0.875");
    expect(formatIntensityFactor(0.875, 1)).toBe("0.9");
  });
});

describe("formatTss", () => {
  it("formats to 1 decimal place by default", () => {
    expect(formatTss(114.84)).toBe("114.8");
    expect(formatTss(100)).toBe("100.0");
  });

  it("respects custom decimal places", () => {
    expect(formatTss(114.84, 0)).toBe("115");
    expect(formatTss(114.84, 2)).toBe("114.84");
  });
});

describe("getTssDescription", () => {
  it("returns appropriate descriptions for TSS ranges", () => {
    expect(getTssDescription(30)).toContain("Very light");
    expect(getTssDescription(75)).toContain("Light");
    expect(getTssDescription(125)).toContain("Moderate");
    expect(getTssDescription(200)).toContain("Hard");
    expect(getTssDescription(300)).toContain("Very hard");
    expect(getTssDescription(400)).toContain("Extreme");
  });
});

describe("getIntensityDescription", () => {
  it("returns appropriate descriptions for IF ranges", () => {
    expect(getIntensityDescription(0.5)).toBe("Recovery");
    expect(getIntensityDescription(0.65)).toBe("Endurance");
    expect(getIntensityDescription(0.82)).toBe("Tempo");
    expect(getIntensityDescription(0.98)).toBe("Threshold");
    expect(getIntensityDescription(1.1)).toBe("VO2max");
    expect(getIntensityDescription(1.25)).toBe("Anaerobic");
  });
});
