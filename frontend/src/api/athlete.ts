/**
 * Athlete Metrics API - thresholds, zones, metrics history
 */
import { apiGet, apiPost, apiPatch, apiPut, apiDelete } from "./base";

// Threshold types
export interface ThresholdEntry {
  effective_date: string;
  ftp_watts: number | null;
  lthr_bpm: number | null;
  hrmax_bpm: number | null;
}

export interface CreateThresholdRequest {
  effective_date?: string;
  ftp_watts?: number;
  lthr_bpm?: number;
  hrmax_bpm?: number;
}

// Zone types
export interface PowerZone {
  zone_number: number;
  name: string;
  min_watts: number;
  max_watts: number | null;
  is_custom: boolean;
}

export interface HrZone {
  zone_number: number;
  name: string;
  min_bpm: number;
  max_bpm: number | null;
  is_custom: boolean;
}

export interface ZonesResponse {
  power_zones: PowerZone[];
  hr_zones: HrZone[];
}

export interface ZoneUpdate {
  zone_number: number;
  name?: string;
  min_value?: number;
  max_value?: number;
}

export interface UpdateZonesRequest {
  power_zones?: ZoneUpdate[];
  hr_zones?: ZoneUpdate[];
  reset_to_defaults?: boolean;
}

// Metric entry types
export interface MetricEntryResponse {
  id: number;
  metric_type: string;
  metric_type_display: string;
  unit: string;
  category: "threshold" | "body" | "fitness" | "recovery";
  effective_date: string;
  value: number;
  source: "manual" | "calculated" | "device";
  source_detail: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MetricEntryCreate {
  metric_type: string;
  effective_date: string;
  value: number;
  source?: "manual" | "calculated" | "device";
  source_detail?: string;
  notes?: string;
}

export interface MetricEntryUpdate {
  value?: number;
  effective_date?: string;
  notes?: string;
}

export type CurrentMetricsResponse = Record<string, MetricEntryResponse | null>;

// Thresholds API
export async function fetchThresholds(): Promise<ThresholdEntry[]> {
  return apiGet<ThresholdEntry[]>("/me/thresholds");
}

export async function createThreshold(request: CreateThresholdRequest): Promise<ThresholdEntry> {
  return apiPost<ThresholdEntry>("/me/thresholds", request, "Failed to create threshold");
}

// Zones API
export async function fetchZones(): Promise<ZonesResponse> {
  return apiGet<ZonesResponse>("/me/zones");
}

export async function updateZones(request: UpdateZonesRequest): Promise<ZonesResponse> {
  return apiPut<ZonesResponse>("/me/zones", request, "Failed to update zones");
}

// Metrics API
export async function fetchMetrics(params?: {
  metric_type?: string;
  category?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}): Promise<MetricEntryResponse[]> {
  const searchParams = new URLSearchParams();
  if (params?.metric_type) searchParams.set("metric_type", params.metric_type);
  if (params?.category) searchParams.set("category", params.category);
  if (params?.from_date) searchParams.set("from_date", params.from_date);
  if (params?.to_date) searchParams.set("to_date", params.to_date);
  if (params?.limit) searchParams.set("limit", params.limit.toString());
  if (params?.offset) searchParams.set("offset", params.offset.toString());
  const query = searchParams.toString();
  return apiGet<MetricEntryResponse[]>(`/me/metrics${query ? `?${query}` : ""}`);
}

export async function createMetric(entry: MetricEntryCreate): Promise<MetricEntryResponse> {
  return apiPost<MetricEntryResponse>("/me/metrics", entry, "Failed to create metric entry");
}

export async function updateMetric(entryId: number, update: MetricEntryUpdate): Promise<MetricEntryResponse> {
  return apiPatch<MetricEntryResponse>(`/me/metrics/${entryId}`, update, "Failed to update metric entry");
}

export async function deleteMetric(entryId: number): Promise<void> {
  return apiDelete(`/me/metrics/${entryId}`, "Failed to delete metric entry");
}

export async function fetchCurrentMetrics(): Promise<CurrentMetricsResponse> {
  return apiGet<CurrentMetricsResponse>("/me/metrics/current");
}

export async function fetchEffectiveMetrics(date: string, metricTypes?: string[]): Promise<CurrentMetricsResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("date", date);
  if (metricTypes?.length) searchParams.set("metric_types", metricTypes.join(","));
  return apiGet<CurrentMetricsResponse>(`/me/metrics/effective?${searchParams.toString()}`);
}
