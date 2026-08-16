/**
 * Admin API - user management, settings, system dashboard
 */
import { apiGet, apiPost, apiPut } from "./base";

// Admin user types
export interface AdminUser {
  id: number;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  is_approved: boolean;
  created_at: string;
}

export interface AdminSettings {
  require_approval: boolean;
}

// User management
export async function fetchAdminUsers(): Promise<AdminUser[]> {
  return apiGet<AdminUser[]>("/admin/users");
}

export async function fetchPendingUsers(): Promise<AdminUser[]> {
  return apiGet<AdminUser[]>("/admin/users/pending");
}

export async function createUser(email: string, password: string): Promise<AdminUser> {
  return apiPost<AdminUser>("/admin/users", { email, password }, "Failed to create user");
}

export async function approveUser(userId: number): Promise<void> {
  return apiPost(`/admin/users/${userId}/approve`, undefined, "Failed to approve user");
}

export async function rejectUser(userId: number): Promise<void> {
  return apiPost(`/admin/users/${userId}/reject`, undefined, "Failed to reject user");
}

export async function resetUserPassword(userId: number, password: string): Promise<void> {
  return apiPost(`/admin/users/${userId}/reset-password`, { password }, "Failed to reset password");
}

export async function triggerUserSync(userId: number): Promise<{ job_id: string | null }> {
  return apiPost<{ job_id: string | null }>(
    `/admin/users/${userId}/sync`,
    undefined,
    "Failed to trigger sync"
  );
}

// Admin settings
export async function fetchAdminSettings(): Promise<AdminSettings> {
  return apiGet<AdminSettings>("/admin/settings");
}

export async function updateAdminSetting(key: string, value: boolean | string): Promise<void> {
  return apiPut(`/admin/settings/${key}`, { value }, "Failed to update setting");
}

// Nuke API
export interface NukePreview {
  user: AdminUser;
  is_self: boolean;
  activities: {
    activities: number;
    records: number;
    laps: number;
    peaks: number;
    routes: number;
    fitness_history: number;
    notifications: number;
  };
  integrations: {
    garmin: number;
    xert: number;
  };
  account: {
    thresholds: number;
    power_zones: number;
    hr_zones: number;
    ef_model: number;
  };
}

export async function fetchNukePreview(userId: number): Promise<NukePreview> {
  return apiGet<NukePreview>(`/admin/users/${userId}/nuke-preview`);
}

export async function nukeActivities(userId: number, confirmEmail: string): Promise<{ success: boolean; deleted: string }> {
  return apiPost(`/admin/users/${userId}/nuke/activities`, { confirm_email: confirmEmail }, "Failed to nuke activities");
}

export async function nukeIntegrations(userId: number, confirmEmail: string): Promise<{ success: boolean; deleted: string }> {
  return apiPost(`/admin/users/${userId}/nuke/integrations`, { confirm_email: confirmEmail }, "Failed to nuke integrations");
}

export async function nukeAccount(userId: number, confirmEmail: string): Promise<{ success: boolean; deleted: string }> {
  return apiPost(`/admin/users/${userId}/nuke/account`, { confirm_email: confirmEmail }, "Failed to nuke account");
}

// System Dashboard API
export interface SystemEvent {
  id: number;
  created_at: string;
  event_type: string;
  outcome: "success" | "failure" | "info";
  user_id: number | null;
  user_email: string | null;
  payload: Record<string, unknown>;
}

export interface SystemEventsResponse {
  events: SystemEvent[];
  total: number;
}

export interface SystemEventsFilters {
  event_type?: string;
  outcome?: string;
  user_id?: number;
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export interface ActiveJob {
  key: string;
  function: string;
  status: string;
  scheduled: string | null;
  started: string | null;
  kwargs: Record<string, unknown> | null;
}

export interface ActiveJobsResponse {
  jobs: ActiveJob[];
}

export interface CacheTypeStats {
  hits: number;
  misses: number;
}

export interface CacheHistoryEntry {
  bucket_start: string;
  cache_type: string;
  hits: number;
  misses: number;
}

export interface CacheSizes {
  tiles_mb: number;
  geocoding_count: number;
}

export interface CacheStatsResponse {
  current: Record<string, CacheTypeStats>;
  history: CacheHistoryEntry[];
  sizes: CacheSizes;
}

export async function fetchSystemEvents(filters?: SystemEventsFilters): Promise<SystemEventsResponse> {
  const params = new URLSearchParams();
  if (filters?.event_type) params.set("event_type", filters.event_type);
  if (filters?.outcome) params.set("outcome", filters.outcome);
  if (filters?.user_id) params.set("user_id", filters.user_id.toString());
  if (filters?.since) params.set("since", filters.since);
  if (filters?.until) params.set("until", filters.until);
  if (filters?.limit) params.set("limit", filters.limit.toString());
  if (filters?.offset) params.set("offset", filters.offset.toString());
  const query = params.toString();
  return apiGet<SystemEventsResponse>(`/admin/system/events${query ? `?${query}` : ""}`);
}

export async function fetchActiveJobs(): Promise<ActiveJobsResponse> {
  return apiGet<ActiveJobsResponse>("/admin/system/jobs");
}

export async function fetchCacheStats(days?: number): Promise<CacheStatsResponse> {
  const params = new URLSearchParams();
  if (days) params.set("days", days.toString());
  const query = params.toString();
  return apiGet<CacheStatsResponse>(`/admin/system/cache-stats${query ? `?${query}` : ""}`);
}
