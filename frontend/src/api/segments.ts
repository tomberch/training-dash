/**
 * Segments API - listing, detail, efforts, and ownership management.
 */

import { apiGet, apiPatch, apiDelete, ApiError, API_BASE } from "./base";
import type { SegmentSuggestion } from "./suggestions";
import type { ElevationPoint } from "./types";

// --- Types ---

export type SegmentType = "climb" | "sprint" | "custom";
export type ClimbCategory = "hc" | "1" | "2" | "3" | "4" | "nc";

export interface SegmentSummary {
  id: string;
  name: string;
  type: SegmentType;
  climb_category: ClimbCategory | null;
  distance_m: number;
  elevation_gain_m: number;
  avg_grade_pct: number;
  effort_count: number;
  athlete_count: number;
  /** Present only when requested via with_polyline */
  polyline?: string;
}

export interface PaginationMeta {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface PaginatedSegments {
  segments: SegmentSummary[];
  pagination: PaginationMeta;
}

export interface LatLng {
  lat: number;
  lng: number;
}

export interface SegmentMyStats {
  effort_count: number;
  pr_time_seconds: number | null;
  pr_date: string | null;
}

export interface SegmentEffort {
  id: string;
  segment_id: string;
  activity_id: string;
  started_at: string;
  elapsed_time_seconds: number;
  moving_time_seconds: number | null;
  avg_power_watts: number | null;
  avg_hr_bpm: number | null;
  is_pr: boolean;
}

export interface SegmentDetailData {
  id: string;
  name: string;
  type: SegmentType;
  status: "suggested" | "approved";
  climb_category: ClimbCategory | null;
  polyline: string;
  start_point: LatLng;
  end_point: LatLng;
  distance_m: number;
  elevation_gain_m: number;
  avg_grade_pct: number;
  max_grade_pct: number;
  elevation_profile: ElevationPoint[];
  effort_count: number;
  athlete_count: number;
  created_by: number | null;
  created_at: string;
  my_stats: SegmentMyStats | null;
}

export interface PaginatedEfforts {
  efforts: SegmentEffort[];
  pagination: PaginationMeta;
}

export interface ActivitySegmentEffort {
  id: string;
  segment_id: string;
  segment_name: string;
  segment_type: SegmentType;
  climb_category: ClimbCategory | null;
  distance_m: number;
  elapsed_time_seconds: number;
  moving_time_seconds: number | null;
  avg_power_watts: number | null;
  avg_hr_bpm: number | null;
  is_pr: boolean;
  delta_to_pr_seconds: number | null;
  start_index: number;
  end_index: number;
}

export interface ActivitySegments {
  efforts: ActivitySegmentEffort[];
  suggestion: SegmentSuggestion | null;
}

export interface ListSegmentsParams {
  type?: SegmentType;
  category?: ClimbCategory[];
  bounds?: [number, number, number, number];
  q?: string;
  with_polyline?: boolean;
  sort?: "popularity" | "name" | "distance" | "elevation";
  order?: "asc" | "desc";
  page?: number;
  per_page?: number;
}

// --- API functions ---

function encodeParams(params: ListSegmentsParams): string {
  const search = new URLSearchParams();
  if (params.type) search.set("type", params.type);
  if (params.category?.length) search.set("category", params.category.join(","));
  if (params.bounds) search.set("bounds", params.bounds.join(","));
  if (params.q) search.set("q", params.q);
  if (params.with_polyline) search.set("with_polyline", "true");
  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);
  if (params.page) search.set("page", String(params.page));
  if (params.per_page) search.set("per_page", String(params.per_page));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchSegments(
  params: ListSegmentsParams = {}
): Promise<PaginatedSegments> {
  return apiGet<PaginatedSegments>(`/segments${encodeParams(params)}`);
}

export async function fetchSegment(id: string): Promise<SegmentDetailData> {
  return apiGet<SegmentDetailData>(`/segments/${id}`);
}

export async function fetchActivitySegments(activityId: string): Promise<ActivitySegments> {
  return apiGet<ActivitySegments>(`/activities/${activityId}/segments`);
}

export interface ListEffortsParams {
  sort?: "time" | "date" | "power";
  order?: "asc" | "desc";
  page?: number;
  per_page?: number;
}

export async function fetchSegmentEfforts(
  id: string,
  params: ListEffortsParams = {}
): Promise<PaginatedEfforts> {
  const search = new URLSearchParams();
  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);
  if (params.page) search.set("page", String(params.page));
  if (params.per_page) search.set("per_page", String(params.per_page));
  const qs = search.toString();
  return apiGet<PaginatedEfforts>(`/segments/${id}/efforts${qs ? `?${qs}` : ""}`);
}

/** Rename a segment. Only the owner may update (backend enforces 403). */
export async function updateSegmentName(id: string, name: string): Promise<SegmentDetailData> {
  return apiPatch<SegmentDetailData>(`/segments/${id}`, { name }, "Failed to rename segment");
}

/** Soft-delete a segment. Only the owner may delete (backend enforces 403). */
export async function deleteSegment(id: string): Promise<void> {
  return apiDelete(`/segments/${id}`, "Failed to delete segment");
}

export interface CreateSegmentRequest {
  name: string;
  activity_id: string;
  start_index: number;
  end_index: number;
}

/** Error thrown when the segment duplicates an existing one (409). */
export class SegmentDuplicateError extends ApiError {
  duplicateSegmentId: string;

  constructor(message: string, duplicateSegmentId: string) {
    super(message, 409);
    this.duplicateSegmentId = duplicateSegmentId;
  }
}

/** Create a segment from an activity's record index range. */
export async function createSegment(request: CreateSegmentRequest): Promise<SegmentDetailData> {
  const res = await fetch(`${API_BASE}/segments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (res.status === 409 && typeof body.detail === "object" && body.detail?.duplicate_segment_id) {
      throw new SegmentDuplicateError(
        body.detail.message || "A similar segment already exists",
        body.detail.duplicate_segment_id
      );
    }
    const detail = typeof body.detail === "object" ? body.detail?.message : body.detail;
    throw new ApiError(detail || res.statusText || "Failed to create segment", res.status);
  }
  return res.json();
}
