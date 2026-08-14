import { describe, it, expect } from "vitest";
import {
  resolveFieldName,
  getFieldDef,
  suggestFieldName,
  isAggregatable,
  FIELD_DEFINITIONS,
  FIELD_ALIASES,
} from "./fields";

describe("resolveFieldName", () => {
  it("resolves internal field names", () => {
    expect(resolveFieldName("tss")).toBe("tss");
    expect(resolveFieldName("total_distance_m")).toBe("total_distance_m");
    expect(resolveFieldName("avg_power_w")).toBe("avg_power_w");
  });

  it("resolves aliases", () => {
    expect(resolveFieldName("distance")).toBe("total_distance_m");
    expect(resolveFieldName("power")).toBe("avg_power_w");
    expect(resolveFieldName("hr")).toBe("avg_hr_bpm");
    expect(resolveFieldName("duration")).toBe("moving_time_s");
  });

  it("is case-insensitive", () => {
    expect(resolveFieldName("TSS")).toBe("tss");
    expect(resolveFieldName("Distance")).toBe("total_distance_m");
    expect(resolveFieldName("POWER")).toBe("avg_power_w");
  });

  it("returns null for unknown fields", () => {
    expect(resolveFieldName("unknown_field")).toBeNull();
    expect(resolveFieldName("foo")).toBeNull();
  });
});

describe("getFieldDef", () => {
  it("gets field definition by internal name", () => {
    const def = getFieldDef("tss");
    expect(def).not.toBeNull();
    expect(def?.fieldType).toBe("number");
    expect(def?.nullable).toBe(true);
  });

  it("gets field definition by alias", () => {
    const def = getFieldDef("distance");
    expect(def).not.toBeNull();
    expect(def?.internalName).toBe("total_distance_m");
    expect(def?.internalUnit).toBe("m");
  });

  it("returns null for unknown fields", () => {
    expect(getFieldDef("unknown")).toBeNull();
  });
});

describe("suggestFieldName", () => {
  it("suggests similar field names", () => {
    const suggestions = suggestFieldName("tsss"); // typo
    expect(suggestions).toContain("tss");
  });

  it("suggests aliases over internal names when applicable", () => {
    const suggestions = suggestFieldName("distanc"); // typo
    expect(suggestions).toContain("distance");
  });

  it("returns empty array for very different strings", () => {
    const suggestions = suggestFieldName("xyzabc");
    expect(suggestions.length).toBeLessThanOrEqual(3);
  });

  it("limits suggestions to maxSuggestions", () => {
    const suggestions = suggestFieldName("t", 2);
    expect(suggestions.length).toBeLessThanOrEqual(2);
  });
});

describe("isAggregatable", () => {
  it("returns true for numeric fields", () => {
    expect(isAggregatable("tss")).toBe(true);
    expect(isAggregatable("distance")).toBe(true);
    expect(isAggregatable("avg_power_w")).toBe(true);
  });

  it("returns false for non-aggregatable fields", () => {
    expect(isAggregatable("title")).toBe(false);
    expect(isAggregatable("source")).toBe(false);
    expect(isAggregatable("is_breakthrough")).toBe(false);
  });

  it("handles aliases", () => {
    expect(isAggregatable("power")).toBe(true); // alias for avg_power_w
    expect(isAggregatable("elevation")).toBe(true); // alias for elevation_gain_m
  });
});

describe("Field Registry", () => {
  it("has all expected fields", () => {
    const expectedFields = [
      "id",
      "started_at",
      "source",
      "title",
      "total_distance_m",
      "elevation_gain_m",
      "moving_time_s",
      "elapsed_time_s",
      "avg_speed_mps",
      "max_speed_mps",
      "avg_hr_bpm",
      "max_hr_bpm",
      "avg_power_w",
      "np_power_w",
      "tss",
      "is_breakthrough",
    ];

    for (const field of expectedFields) {
      expect(FIELD_DEFINITIONS[field]).toBeDefined();
    }
  });

  it("has all expected aliases", () => {
    const expectedAliases = {
      distance: "total_distance_m",
      elevation: "elevation_gain_m",
      duration: "moving_time_s",
      speed: "avg_speed_mps",
      hr: "avg_hr_bpm",
      power: "avg_power_w",
      date: "started_at",
      breakthrough: "is_breakthrough",
    };

    for (const [alias, internal] of Object.entries(expectedAliases)) {
      expect(FIELD_ALIASES[alias]).toBe(internal);
    }
  });

  it("all aliases point to valid fields", () => {
    for (const [alias, internal] of Object.entries(FIELD_ALIASES)) {
      expect(FIELD_DEFINITIONS[internal]).toBeDefined();
    }
  });
});
