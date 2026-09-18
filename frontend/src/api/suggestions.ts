/**
 * Segment Suggestions API - pending climb/sprint suggestions for the current user.
 */

import { apiGet, apiPost } from "./base";
import type { ClimbCategory, SegmentType } from "./segments";
import type { ElevationPoint } from "./types";

export interface SegmentSuggestion {
  id: string;
  segment_id: string;
  segment_type: SegmentType;
  climb_category: ClimbCategory | null;
  distance_m: number;
  elevation_gain_m: number;
  avg_grade_pct: number;
  max_grade_pct: number;
  repetition_count: number;
  first_ridden_at: string | null;
  last_ridden_at: string | null;
  expires_at: string | null;
  polyline: string;
  elevation_profile: ElevationPoint[];
  start_point: { lat: number; lng: number };
  end_point: { lat: number; lng: number };
}

export interface PaginatedSuggestions {
  items: SegmentSuggestion[];
  meta: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

export interface ApproveSuggestionResult {
  id: string;
  name: string;
}

export async function fetchSuggestions(
  page = 1,
  perPage = 20
): Promise<PaginatedSuggestions> {
  return apiGet<PaginatedSuggestions>(`/suggestions?page=${page}&per_page=${perPage}`);
}

/** Approve a suggestion with a name, creating the segment. Returns the approved segment. */
export async function approveSuggestion(
  id: string,
  name: string
): Promise<ApproveSuggestionResult> {
  return apiPost<ApproveSuggestionResult>(`/suggestions/${id}/approve`, { name }, "Failed to create segment");
}

/** Dismiss a single suggestion. */
export async function dismissSuggestion(id: string): Promise<void> {
  await apiPost<void>(`/suggestions/${id}/dismiss`, undefined, "Failed to dismiss suggestion");
}

/** Dismiss all pending suggestions for the current user. */
export async function dismissAllSuggestions(): Promise<void> {
  await apiPost<void>(`/suggestions/dismiss-all`, undefined, "Failed to dismiss suggestions");
}
