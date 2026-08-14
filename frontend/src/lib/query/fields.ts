/**
 * Field registry for the query DSL.
 * Mirrors the backend Python fields.py for consistency.
 */

export type FieldType = "number" | "string" | "date" | "boolean" | "duration";

export interface FieldDef {
  internalName: string;
  fieldType: FieldType;
  nullable: boolean;
  internalUnit: string | null;
  description: string;
}

// Field definitions
export const FIELD_DEFINITIONS: Record<string, FieldDef> = {
  id: {
    internalName: "id",
    fieldType: "string",
    nullable: false,
    internalUnit: null,
    description: "Activity UUID",
  },
  started_at: {
    internalName: "started_at",
    fieldType: "date",
    nullable: false,
    internalUnit: null,
    description: "Activity start time",
  },
  source: {
    internalName: "source",
    fieldType: "string",
    nullable: false,
    internalUnit: null,
    description: "Data source (xert, garmin, upload)",
  },
  title: {
    internalName: "title",
    fieldType: "string",
    nullable: true,
    internalUnit: null,
    description: "Activity title",
  },
  total_distance_m: {
    internalName: "total_distance_m",
    fieldType: "number",
    nullable: false,
    internalUnit: "m",
    description: "Total distance in meters",
  },
  elevation_gain_m: {
    internalName: "elevation_gain_m",
    fieldType: "number",
    nullable: false,
    internalUnit: "m",
    description: "Elevation gain in meters",
  },
  moving_time_s: {
    internalName: "moving_time_s",
    fieldType: "duration",
    nullable: false,
    internalUnit: "s",
    description: "Moving time in seconds",
  },
  elapsed_time_s: {
    internalName: "elapsed_time_s",
    fieldType: "duration",
    nullable: false,
    internalUnit: "s",
    description: "Elapsed time in seconds",
  },
  avg_speed_mps: {
    internalName: "avg_speed_mps",
    fieldType: "number",
    nullable: false,
    internalUnit: "mps",
    description: "Average speed in m/s",
  },
  max_speed_mps: {
    internalName: "max_speed_mps",
    fieldType: "number",
    nullable: false,
    internalUnit: "mps",
    description: "Max speed in m/s",
  },
  avg_hr_bpm: {
    internalName: "avg_hr_bpm",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Average heart rate in bpm",
  },
  max_hr_bpm: {
    internalName: "max_hr_bpm",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Max heart rate in bpm",
  },
  avg_power_w: {
    internalName: "avg_power_w",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Average power in watts",
  },
  np_power_w: {
    internalName: "np_power_w",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Normalized power in watts",
  },
  power_source: {
    internalName: "power_source",
    fieldType: "string",
    nullable: true,
    internalUnit: null,
    description: "Power source (measured, hr_derived)",
  },
  power_confidence: {
    internalName: "power_confidence",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Power confidence for hr_derived (0-1)",
  },
  tss: {
    internalName: "tss",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Training Stress Score",
  },
  intensity_factor: {
    internalName: "intensity_factor",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Intensity Factor (IF)",
  },
  training_load: {
    internalName: "training_load",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Training load",
  },
  wbal_min_joules: {
    internalName: "wbal_min_joules",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Minimum W' balance in joules",
  },
  wbal_min_pct: {
    internalName: "wbal_min_pct",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Minimum W' balance as percentage",
  },
  is_breakthrough: {
    internalName: "is_breakthrough",
    fieldType: "boolean",
    nullable: false,
    internalUnit: null,
    description: "Breakthrough activity flag",
  },
  route_id: {
    internalName: "route_id",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Associated route",
  },
  direction_bearing: {
    internalName: "direction_bearing",
    fieldType: "number",
    nullable: true,
    internalUnit: null,
    description: "Direction bearing (0-359 degrees)",
  },
};

// User-friendly aliases
export const FIELD_ALIASES: Record<string, string> = {
  distance: "total_distance_m",
  dist: "total_distance_m",
  elevation: "elevation_gain_m",
  elev: "elevation_gain_m",
  gain: "elevation_gain_m",
  climbing: "elevation_gain_m",
  duration: "moving_time_s",
  time: "moving_time_s",
  moving_time: "moving_time_s",
  elapsed: "elapsed_time_s",
  elapsed_time: "elapsed_time_s",
  speed: "avg_speed_mps",
  avg_speed: "avg_speed_mps",
  max_speed: "max_speed_mps",
  hr: "avg_hr_bpm",
  avg_hr: "avg_hr_bpm",
  heart_rate: "avg_hr_bpm",
  max_hr: "max_hr_bpm",
  power: "avg_power_w",
  avg_power: "avg_power_w",
  watts: "avg_power_w",
  np: "np_power_w",
  normalized_power: "np_power_w",
  date: "started_at",
  start: "started_at",
  started: "started_at",
  if: "intensity_factor",
  load: "training_load",
  breakthrough: "is_breakthrough",
  name: "title",
  route: "route_id",
};

// All valid field names
export const ALL_FIELD_NAMES: Set<string> = new Set([
  ...Object.keys(FIELD_DEFINITIONS),
  ...Object.keys(FIELD_ALIASES),
]);

/**
 * Resolve a field name or alias to the internal field name.
 */
export function resolveFieldName(name: string): string | null {
  const nameLower = name.toLowerCase();

  // Check internal names
  for (const internal of Object.keys(FIELD_DEFINITIONS)) {
    if (internal.toLowerCase() === nameLower) {
      return internal;
    }
  }

  // Check aliases
  for (const [alias, internal] of Object.entries(FIELD_ALIASES)) {
    if (alias.toLowerCase() === nameLower) {
      return internal;
    }
  }

  return null;
}

/**
 * Get the field definition for a field name or alias.
 */
export function getFieldDef(name: string): FieldDef | null {
  const internal = resolveFieldName(name);
  return internal ? FIELD_DEFINITIONS[internal] ?? null : null;
}

/**
 * Suggest similar field names for a typo.
 */
export function suggestFieldName(name: string, maxSuggestions = 3): string[] {
  const nameLower = name.toLowerCase();
  const candidates: Array<[number, string]> = [];

  for (const field of ALL_FIELD_NAMES) {
    const dist = editDistance(nameLower, field.toLowerCase());
    if (dist <= 3) {
      candidates.push([dist, field]);
    }
  }

  candidates.sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]));

  const suggestions: string[] = [];
  const seenInternal = new Set<string>();

  for (const [, field] of candidates) {
    const internal = resolveFieldName(field);
    if (internal && !seenInternal.has(internal)) {
      suggestions.push(field in FIELD_ALIASES ? field : internal);
      seenInternal.add(internal);
    }
    if (suggestions.length >= maxSuggestions) break;
  }

  return suggestions;
}

function editDistance(s1: string, s2: string): number {
  if (s1.length < s2.length) return editDistance(s2, s1);
  if (s2.length === 0) return s1.length;

  let previousRow = Array.from({ length: s2.length + 1 }, (_, i) => i);

  for (let i = 0; i < s1.length; i++) {
    const currentRow = [i + 1];
    for (let j = 0; j < s2.length; j++) {
      const insertions = previousRow[j + 1] + 1;
      const deletions = currentRow[j] + 1;
      const substitutions = previousRow[j] + (s1[i] !== s2[j] ? 1 : 0);
      currentRow.push(Math.min(insertions, deletions, substitutions));
    }
    previousRow = currentRow;
  }

  return previousRow[s2.length];
}

// Fields valid for aggregation
export const AGGREGATABLE_FIELDS = new Set([
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
  "intensity_factor",
  "training_load",
  "wbal_min_joules",
  "wbal_min_pct",
]);

export function isAggregatable(fieldName: string): boolean {
  const internal = resolveFieldName(fieldName);
  return internal ? AGGREGATABLE_FIELDS.has(internal) : false;
}

// Valid operators by field type
export const VALID_OPERATORS: Record<FieldType, Set<string>> = {
  number: new Set(["=", "!=", ">", ">=", "<", "<="]),
  string: new Set(["=", "!="]),
  date: new Set(["=", "!=", ">", ">=", "<", "<="]),
  boolean: new Set(["=", "!="]),
  duration: new Set(["=", "!=", ">", ">=", "<", "<="]),
};
