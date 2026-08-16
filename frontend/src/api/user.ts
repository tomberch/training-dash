/**
 * User API - current user profile, preferences, avatar, notifications
 */
import { apiGet, apiPost, apiPatch, apiDelete, API_BASE, ApiError, extractError } from "./base";

export interface HrPowerModelStatus {
  enabled: boolean;
  model_exists: boolean;
  ef_value: number | null;
  confidence: number | null;
  ride_count: number;
  computed_at: string | null;
  is_stale: boolean | null;
}

export interface User {
  id: number;
  email: string;
  display_name: string | null;
  avatar_path: string | null;
  is_admin: boolean;
  is_approved: boolean;
  unit_system: "metric" | "imperial";
  sync_hour: number;
  date_of_birth: string | null;
  weight_kg: number | null;
  height_cm: number | null;
  gender: "male" | "female" | null;
  power_zone_percentages: Record<string, [number, number | null]> | null;
  hr_zone_percentages: Record<string, [number, number | null]> | null;
  hr_derived_power_enabled: boolean;
  map_tile_style: "osm" | "positron" | "dark_matter" | "voyager";
  hr_power_model: HrPowerModelStatus | null;
}

export interface Notification {
  id: number;
  type: string;
  message: string;
  payload: { suggested_ftp?: number; suggested_hrmax?: number } | null;
  created_at: string;
}

export async function fetchMe(): Promise<User> {
  return apiGet<User>("/me");
}

export async function updatePreferences(prefs: { 
  unit_system?: string;
  display_name?: string | null;
  sync_hour?: number;
  date_of_birth?: string;
  weight_kg?: number;
  height_cm?: number;
  gender?: "male" | "female" | null;
  power_zone_percentages?: Record<string, [number, number | null]> | null;
  hr_zone_percentages?: Record<string, [number, number | null]> | null;
  hr_derived_power_enabled?: boolean;
  map_tile_style?: "osm" | "positron" | "dark_matter" | "voyager";
}): Promise<User> {
  return apiPatch<User>("/me", prefs, "Failed to update preferences");
}

export async function fetchNotifications(): Promise<Notification[]> {
  return apiGet<Notification[]>("/me/notifications");
}

export async function acceptNotification(id: number): Promise<void> {
  return apiPost(`/me/notifications/${id}/accept`, undefined, "Failed to accept notification");
}

export async function dismissNotification(id: number): Promise<void> {
  return apiPost(`/me/notifications/${id}/dismiss`, undefined, "Failed to dismiss notification");
}

// Avatar
export async function uploadAvatar(file: File): Promise<{ avatar_path: string }> {
  const res = await fetch(`${API_BASE}/me/avatar`, {
    method: "POST",
    headers: { "Content-Type": file.type },
    credentials: "include",
    body: file,
  });
  if (!res.ok) {
    const { detail } = await extractError(res, "Failed to upload avatar");
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function deleteAvatar(): Promise<void> {
  return apiDelete("/me/avatar", "Failed to delete avatar");
}

// Sync triggers
export async function triggerGarminSync(): Promise<{ success: boolean; job_id?: string }> {
  return apiPost("/me/sync/garmin", undefined, "Failed to trigger Garmin sync");
}

export async function triggerXertSync(): Promise<{ success: boolean; job_id?: string }> {
  return apiPost("/me/sync/xert", undefined, "Failed to trigger Xert sync");
}

// Metric Recalculation
export interface RecalculationJob {
  id: number;
  user_id: number;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
  activities_updated: number | null;
  error_message: string | null;
}

export async function triggerRecalculation(): Promise<RecalculationJob> {
  return apiPost("/me/recalculate-metrics", undefined, "Failed to trigger metric recalculation");
}

export async function fetchRecalculationStatus(): Promise<RecalculationJob | null> {
  return apiGet("/me/recalculate-metrics");
}

// OAuth Links
export interface OAuthLink {
  provider: string;
  provider_email: string | null;
  display_name: string | null;
  avatar_url: string | null;
  created_at: string | null;
}

export async function fetchOAuthLinks(): Promise<OAuthLink[]> {
  return apiGet<OAuthLink[]>("/me/oauth-links");
}

export async function disconnectOAuthProvider(provider: string): Promise<void> {
  return apiDelete(`/me/oauth-links/${provider}`, "Failed to disconnect provider");
}

export async function setPassword(password: string): Promise<{ success: boolean }> {
  return apiPost("/me/set-password", { password }, "Failed to set password");
}

export async function hasPassword(): Promise<{ has_password: boolean }> {
  return apiGet<{ has_password: boolean }>("/me/has-password");
}
