/**
 * Shared API type definitions
 */

export interface PeakPower {
  duration_seconds: number;
  watts: number;
  all_time_pr: number | null;
  pct_of_pr: number | null;
  is_pr: boolean;
}

export type ActivityType = "road" | "gravel" | "mtb" | "virtual" | "indoor" | "commute" | "other";

/** All valid activity types as an array for iteration */
export const ACTIVITY_TYPES: readonly ActivityType[] = ["road", "gravel", "mtb", "virtual", "indoor", "commute", "other"] as const;

/** Activity type display labels */
export const ACTIVITY_TYPE_LABELS: Record<ActivityType, string> = {
  road: "Road",
  gravel: "Gravel",
  mtb: "MTB",
  virtual: "Virtual",
  indoor: "Indoor",
  commute: "Commute",
  other: "Other",
};

// ============================================================================
// Bike/Gear Types (defined before Activity for type reference)
// ============================================================================

export type BikeType = "road" | "gravel" | "mtb" | "tt" | "track" | "cx" | "commuter" | "ebike" | "other";

/** All valid bike types as an array for iteration */
export const BIKE_TYPES: readonly BikeType[] = [
  "road",
  "gravel",
  "mtb",
  "tt",
  "track",
  "cx",
  "commuter",
  "ebike",
  "other",
] as const;

/** Bike type display labels */
export const BIKE_TYPE_LABELS: Record<BikeType, string> = {
  road: "Road",
  gravel: "Gravel",
  mtb: "MTB",
  tt: "TT/Tri",
  track: "Track",
  cx: "Cyclocross",
  commuter: "Commuter",
  ebike: "E-bike",
  other: "Other",
};

/** Minimal bike summary embedded in activity responses */
export interface BikeSummary {
  id: number;
  name: string;
  bike_type: BikeType;
}

export interface Bike {
  id: number;
  name: string;
  bike_type: BikeType;
  model_year: number | null;
  weight_kg: number | null;
  photo_path: string | null;
  total_distance_m: number;
  cda: number | null;
  crr: number | null;
  cda_source: "manual" | "calibrated" | null;
  crr_source: "manual" | "calibrated" | null;
  calibrated_at: string | null;
  is_default: boolean;
  retired_at: string | null;
  created_at: string;
  updated_at: string;
  // Estimated aero aggregates from activities
  estimated_cda_avg: number | null;
  estimated_crr_avg: number | null;
  estimated_cda_stddev: number | null;
  estimated_crr_stddev: number | null;
  aero_sample_count: number | null;
}

export interface BikeListResponse {
  bikes: Bike[];
}

export interface BikeCreateRequest {
  name: string;
  bike_type: BikeType;
  model_year?: number | null;
  weight_kg?: number | null;
  cda?: number | null;
  crr?: number | null;
  cda_source?: "manual" | "calibrated" | null;
  crr_source?: "manual" | "calibrated" | null;
  is_default?: boolean;
}

export interface BikeUpdateRequest {
  name?: string;
  bike_type?: BikeType;
  model_year?: number | null;
  weight_kg?: number | null;
  cda?: number | null;
  crr?: number | null;
  cda_source?: "manual" | "calibrated" | null;
  crr_source?: "manual" | "calibrated" | null;
}

// ============================================================================
// Activity Types
// ============================================================================

export interface Activity {
  id: string;
  title: string | null;
  title_source: "auto" | "manual" | "pending";
  started_at: string;
  total_distance_m: number;
  moving_time_s: number;
  elapsed_time_s: number;
  elevation_gain_m: number;
  avg_speed_mps: number;
  avg_hr_bpm: number | null;
  avg_power_w: number | null;
  max_speed_mps: number;
  max_hr_bpm: number | null;
  np_power_w: number | null;
  intensity_factor: number | null;
  tss: number | null;
  training_load: number | null;
  power_zone_times: Record<string, number> | null;
  hr_zone_times: Record<string, number> | null;
  wbal_min_joules: number | null;
  wbal_min_pct: number | null;
  power_source: "measured" | "hr_derived" | null;
  power_confidence: number | null;
  peaks: PeakPower[];
  is_breakthrough: boolean;
  map_polyline: string | null;
  utc_offset_minutes: number | null;
  activity_type: ActivityType | null;
  bike_id: number | null;
  bike: BikeSummary | null;
  // Aero estimation
  estimated_cda: number | null;
  estimated_crr: number | null;
  aero_confidence: number | null;
  weather_status: "pending" | "fetched" | "failed" | "not_applicable" | null;
  // Effective thresholds at activity time
  effective_ftp: number | null;
  effective_lthr: number | null;
  // Calc trace (only present when ?include=calc_trace)
  calc_trace?: CalcTrace;
}

export interface CalcTrace {
  power_zones: CalcTracePowerZone[] | null;
  hr_zones: CalcTraceHrZone[] | null;
  power_zone_times: Record<number, number> | null;
  hr_zone_times: Record<number, number> | null;
  wbal_curve: CalcTraceWbalPoint[] | null;
  w_prime_joules: number | null;
  cp_watts: number | null;
  peak_windows: PeakWindow[];
}

export interface CalcTracePowerZone {
  zone: number;
  name: string;
  min_watts: number;
  max_watts: number | null;
}

export interface CalcTraceHrZone {
  zone: number;
  name: string;
  min_bpm: number;
  max_bpm: number | null;
}

export interface CalcTraceWbalPoint {
  elapsed_s: number;
  wbal_joules: number;
  wbal_pct: number;
}

export interface PeakWindow {
  duration_seconds: number;
  watts: number;
  start_index: number;
  end_index: number;
}

export interface WhatIfRequest {
  ftp?: number | null;
  lthr?: number | null;
  cp?: number | null;
  w_prime?: number | null;
}

export interface WhatIfResponse {
  activity_id: string;
  what_if_params: WhatIfRequest;
  calc_trace: CalcTrace;
}

export interface PaginationMeta {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface PaginatedActivities {
  activities: Activity[];
  pagination: PaginationMeta;
}

export interface GeoJSONFeature {
  type: "Feature";
  geometry: { type: string; coordinates: number[] } | null;
  properties: {
    timestamp: string;
    distance_m: number;
    hr_bpm: number | null;
    power_w: number | null;
    speed_mps: number | null;
    altitude_m: number | null;
    cadence_rpm: number | null;
  };
}

export interface GeoJSONFeatureCollection {
  type: "FeatureCollection";
  activity_id: string;
  features: GeoJSONFeature[];
}

export interface PRValue {
  value: number;
  activity_id?: string;
}

export interface Records {
  longest_distance_m: PRValue | null;
  longest_moving_time_s: PRValue | null;
  fastest_5000_m: PRValue | null;
  fastest_10000_m: PRValue | null;
  fastest_40000_m: PRValue | null;
  max_speed_mps: PRValue | null;
  max_hr_bpm: PRValue | null;
  biggest_elevation_gain_m: PRValue | null;
  highest_sustained_power_w: PRValue | null;
}

export interface RoutePR {
  route_id: number;
  route_label: string;
  fastest_time_s: number;
  activity_id: string | null;
  activity_title: string | null;
  polyline: string | null;
  started_at: string | null;
  distance_m: number | null;
}

export interface RoutePRsPage {
  items: RoutePR[];
  total: number;
}

export interface RecordsResponse {
  lifetime_prs: Records;
  route_prs: RoutePRsPage;
}

export interface GapPoint {
  distance_m: number;
  gap_s: number;
}

export interface CompareResponse {
  comparable: boolean;
  gap_series: GapPoint[];
  other_geojson: GeoJSONFeatureCollection | null;
  reason?: "different_routes" | "opposite_direction" | "insufficient_gps" | "no_gps_match" | "missing_gps";
  message?: string;
}

export interface SameRouteResponse {
  route_id: number | null;
  activities: Activity[];
}

export interface WbalPoint {
  elapsed_s: number;
  distance_m: number;
  wbal_joules: number;
  wbal_pct: number;
}

export interface WbalResponse {
  wbal_series: WbalPoint[];
  w_prime_joules: number | null;
  ftp_watts: number | null;
  wbal_min_joules: number | null;
  wbal_min_pct: number | null;
}

export interface JobStatus {
  status: "pending" | "processing" | "complete" | "not_found" | "unknown";
  result: { success: boolean; activity_id: string | null } | null;
}



// ============================================================================
// Race Plan Types
// ============================================================================

export interface SegmentTarget {
  segment_idx: number;
  power_w: number;
  time_s: number;
  speed_mps: number;
}

export interface RiderParams {
  weight_kg: number;
  ftp_watts: number;
  cp_watts: number | null;
  w_prime_joules: number | null;
}

export interface BikeParams {
  weight_kg: number | null;
  cda: number;
  crr: number;
}

export interface WbalPrediction {
  min_wbal: number | null;
  min_wbal_distance_m: number | null;
}

export interface PlanComparison {
  constant_time_s?: number | null;
  heuristic_time_s?: number | null;
  optimized_time_s?: number | null;
  improvement_vs_constant_pct?: number | null;
  improvement_vs_heuristic_pct?: number | null;
}

export interface RacePlanListItem {
  id: number;
  course_id: number;
  name: string | null;
  total_time_s: number;
  total_time_formatted: string;
  avg_power_w: number;
  optimization_method: string | null;
  created_at: string;
}

export interface RacePlanDetail {
  id: number;
  course_id: number;
  name: string | null;
  total_time_s: number;
  total_time_formatted: string;
  avg_power_w: number;
  normalized_power_w: number | null;
  intensity_factor: number | null;
  comparison: PlanComparison;
  warnings: string[];
  segment_targets: SegmentTarget[];
  wbal_prediction: WbalPrediction | null;
  rider_params: RiderParams;
  bike_params: BikeParams;
  optimization_method: string | null;
  created_at: string;
}

export interface GeneratePlanRequest {
  course_id: number;
  bike_id?: number | null;
  rider_weight_kg?: number | null;
  ftp_watts: number;
  cp_watts?: number | null;
  w_prime_joules?: number | null;
  target_intensity?: number;
  target_time_s?: number | null; // Target finish time in seconds (overrides intensity)
  use_optimizer?: boolean;
  name?: string | null;
}

export interface RacePlanResponse {
  id: number;
  course_id: number;
  name: string | null;
  total_time_s: number;
  total_time_formatted: string;
  avg_power_w: number;
  normalized_power_w: number | null;
  intensity_factor: number | null;
  comparison: PlanComparison;
  warnings: string[];
}

// Course types for race planner
export interface CourseSegment {
  start_m: number;
  end_m: number;
  distance_m: number;
  avg_grade_pct: number;
  elevation_gain_m: number;
  elevation_loss_m: number;
  terrain_type: string;
}

export interface CourseClimb {
  name: string | null;
  start_m: number;
  end_m: number;
  distance_m: number;
  avg_grade_pct: number;
  elevation_gain_m: number;
  max_grade_pct: number;
  category: string | null;
}

export interface ElevationPoint {
  distance_m: number;
  elevation_m: number;
  grade_pct: number;
}

export interface CourseListItem {
  id: number;
  name: string;
  source_type: string;
  distance_m: number;
  elevation_gain_m: number;
  created_at: string;
}

export interface CourseDetail {
  id: number;
  name: string;
  description: string | null;
  source_type: string;
  source_filename: string | null;
  distance_m: number;
  elevation_gain_m: number;
  elevation_loss_m: number;
  min_elevation_m: number | null;
  max_elevation_m: number | null;
  created_at: string;
  updated_at: string;
  segments: CourseSegment[];
  climbs: CourseClimb[];
  elevation_profile: ElevationPoint[];
}

export interface CourseUploadResponse {
  id: number;
  name: string;
  source_type: string;
  source_filename: string | null;
  distance_m: number;
  elevation_gain_m: number;
  elevation_loss_m: number;
  min_elevation_m: number | null;
  max_elevation_m: number | null;
  created_at: string;
  warnings: string[];
}



// ============================================================================
// Execution Comparison Types
// ============================================================================

export interface SegmentComparison {
  segment_idx: number;
  distance_m: number;
  grade_pct: number;
  planned_power_w: number;
  actual_power_w: number | null;
  power_delta_pct: number | null;
  planned_time_s: number;
  actual_time_s: number | null;
  time_delta_s: number | null;
}

export interface ExecutionComparison {
  plan_id: number;
  activity_id: string;
  total_planned_time_s: number;
  total_planned_time_formatted: string;
  total_actual_time_s: number;
  total_actual_time_formatted: string;
  time_delta_s: number;
  time_delta_formatted: string;
  time_delta_pct: number;
  pacing_consistency: number;
  segments_over_target: number;
  segments_under_target: number;
  segment_comparisons: SegmentComparison[];
  insights: string[];
}

export interface MatchingActivity {
  id: string;
  name: string | null;
  started_at: string;
  total_distance_m: number;
  moving_time_s: number;
  avg_power_w: number | null;
}
