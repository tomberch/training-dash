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
