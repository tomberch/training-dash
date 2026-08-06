// ============================================================================
// Types
// ============================================================================

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
  // Training metrics
  np_power_w: number | null;
  intensity_factor: number | null;
  tss: number | null;
  training_load: number | null;
  power_zone_times: Record<string, number> | null;
  hr_zone_times: Record<string, number> | null;
  wbal_min_joules: number | null;
  wbal_min_pct: number | null;
  // Power source for HR-derived power
  power_source: "measured" | "hr_derived" | null;
  power_confidence: number | null;
  // Peaks and breakthrough
  peaks: PeakPower[];
  is_breakthrough: boolean;
  // Map polyline for list view thumbnails
  map_polyline: string | null;
  // UTC offset in minutes at time of activity (from FIT local_timestamp); null = unknown
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
}

export interface RecordsResponse {
  lifetime_prs: Records;
  route_prs: RoutePR[];
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

export interface User {
  id: number;
  email: string;
  display_name: string | null;
  avatar_path: string | null;
  is_admin: boolean;
  is_approved: boolean;
  unit_system: "metric" | "imperial";
  sync_hour: number;
}

export interface XertCredentialsStatus {
  configured: boolean;
  xert_email: string | null;
  sync_since: string | null;
}

export interface GarminCredentialsStatus {
  configured: boolean;
  garmin_email: string | null;
  sync_since: string | null;
}

export interface GarminSaveResponse {
  success?: boolean;
  garmin_email?: string;
  mfa_required?: boolean;
}

export interface PMCPoint {
  date: string;
  ctl: number;
  atl: number;
  tsb: number;
}

export interface ThresholdEntry {
  effective_date: string;
  ftp_watts: number | null;
  lthr_bpm: number | null;
  hrmax_bpm: number | null;
}

export interface PowerCurvePoint {
  duration_seconds: number;
  watts: number;
  achieved_date: string;
  days_ago: number;
}

export interface FitnessSnapshot {
  computed_at: string;
  pp_watts: number;
  w_prime_joules: number;
  cp_watts: number;
}

export interface FitnessResponse {
  current: FitnessSnapshot | null;
  history: FitnessSnapshot[];
}

export interface Notification {
  id: number;
  type: string;
  message: string;
  payload: { suggested_ftp?: number } | null;
  created_at: string;
}

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

export interface CreateThresholdRequest {
  effective_date?: string;
  ftp_watts?: number;
  lthr_bpm?: number;
  hrmax_bpm?: number;
}

// ============================================================================
// API Error and Base Helpers
// ============================================================================

/**
 * Structured API error with optional error_id for tracking.
 */
export class ApiError extends Error {
  status: number;
  errorId?: string;

  constructor(message: string, status: number, errorId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorId = errorId;
  }
}

const API_BASE = import.meta.env.VITE_API_URL || "/api";

/**
 * Extract error details from a failed response.
 */
async function extractError(
  res: Response,
  defaultMessage: string
): Promise<{ detail: string; errorId?: string }> {
  let detail = defaultMessage;
  let errorId: string | undefined;
  try {
    const body = await res.json();
    detail = body.detail || detail;
    errorId = body.error_id;
  } catch {
    // Response wasn't JSON, use status text
    detail = res.statusText || detail;
  }
  return { detail, errorId };
}

/**
 * GET request helper - fetches JSON from an API endpoint.
 */
async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, "Request failed");
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

/**
 * POST request helper - posts JSON to an API endpoint.
 */
async function apiPost<T>(
  path: string,
  body?: unknown,
  errorMessage = "Request failed"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
  // Handle void responses (204 No Content or empty body)
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

/**
 * PUT request helper - puts JSON to an API endpoint.
 */
async function apiPut<T>(
  path: string,
  body: unknown,
  errorMessage = "Request failed"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : ({} as T);
}

/**
 * PATCH request helper - patches JSON to an API endpoint.
 */
async function apiPatch<T>(
  path: string,
  body: unknown,
  errorMessage = "Request failed"
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

/**
 * DELETE request helper.
 */
async function apiDelete(path: string, errorMessage = "Request failed"): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, errorMessage);
    throw new ApiError(detail, res.status, errorId);
  }
}

// ============================================================================
// Activity API
// ============================================================================

export async function fetchActivities(page?: number, perPage?: number): Promise<PaginatedActivities> {
  const params = new URLSearchParams();
  if (page) params.set("page", page.toString());
  if (perPage) params.set("per_page", perPage.toString());
  const query = params.toString();
  return apiGet<PaginatedActivities>(`/activities${query ? `?${query}` : ""}`);
}

export async function fetchActivity(id: string): Promise<Activity> {
  return apiGet<Activity>(`/activities/${id}`);
}

export async function fetchActivityRecords(id: string): Promise<GeoJSONFeatureCollection> {
  return apiGet<GeoJSONFeatureCollection>(`/activities/${id}/records`);
}

export async function fetchActivityWbal(id: string): Promise<WbalResponse> {
  return apiGet<WbalResponse>(`/activities/${id}/wbal`);
}

export async function fetchSameRouteActivities(id: string): Promise<SameRouteResponse> {
  return apiGet<SameRouteResponse>(`/activities/${id}/same-route`);
}

export async function updateActivityTitle(id: string, title: string): Promise<Activity> {
  return apiPatch<Activity>(`/activities/${id}`, { title }, "Failed to update activity title");
}

export async function generateActivityTitle(id: string): Promise<Activity> {
  return apiPost<Activity>(`/activities/${id}/generate-title`, {}, "Failed to generate activity title");
}

export async function deleteActivity(id: string): Promise<void> {
  return apiDelete(`/activities/${id}`, "Failed to delete activity");
}

export async function fetchComparison(id: string, otherId: string): Promise<CompareResponse> {
  return apiGet<CompareResponse>(`/activities/${id}/compare?other=${otherId}`);
}

export async function uploadFit(
  file: File
): Promise<{ id?: string; job_id?: string; source_ref?: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) {
    const { detail, errorId } = await extractError(res, "Upload failed");
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  return apiGet<JobStatus>(`/jobs/${jobId}`);
}

// ============================================================================
// Auth API
// ============================================================================

export interface LoginResponse {
  user_id: number;
  email: string;
  is_admin: boolean;
  is_approved: boolean;
  display_name: string | null;
  avatar_path: string | null;
  unit_system: string;
  sync_hour: number;
}

export interface RegisterResponse {
  user_id: number;
  email: string;
  is_admin: boolean;
  is_approved: boolean;
}

export async function login(email: string, password: string): Promise<LoginResponse | null> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function register(email: string, password: string): Promise<RegisterResponse> {
  const res = await fetch(`${API_BASE}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const { detail } = await extractError(res, "Registration failed");
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function logout(): Promise<void> {
  return apiPost("/logout", undefined, "Logout failed");
}

// ============================================================================
// User API
// ============================================================================

export async function fetchMe(): Promise<User> {
  return apiGet<User>("/me");
}

export async function updatePreferences(prefs: { 
  unit_system?: string;
  display_name?: string | null;
  sync_hour?: number;
  date_of_birth?: string;
  weight_kg?: number;
  hr_derived_power_enabled?: boolean;
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

// ============================================================================
// Avatar API
// ============================================================================

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

// ============================================================================
// User Sync API
// ============================================================================

export async function triggerGarminSync(): Promise<{ success: boolean; job_id?: string }> {
  return apiPost("/me/sync/garmin", undefined, "Failed to trigger Garmin sync");
}

export async function triggerXertSync(): Promise<{ success: boolean; job_id?: string }> {
  return apiPost("/me/sync/xert", undefined, "Failed to trigger Xert sync");
}

// ============================================================================
// Thresholds and Zones API
// ============================================================================

export async function fetchThresholds(): Promise<ThresholdEntry[]> {
  return apiGet<ThresholdEntry[]>("/me/thresholds");
}

export async function createThreshold(request: CreateThresholdRequest): Promise<ThresholdEntry> {
  return apiPost<ThresholdEntry>("/me/thresholds", request, "Failed to create threshold");
}

export async function fetchZones(): Promise<ZonesResponse> {
  return apiGet<ZonesResponse>("/me/zones");
}

export async function updateZones(request: UpdateZonesRequest): Promise<ZonesResponse> {
  return apiPut<ZonesResponse>("/me/zones", request, "Failed to update zones");
}

// ============================================================================
// Integration Credentials API
// ============================================================================

// Xert
export async function fetchMyXertCredentials(): Promise<XertCredentialsStatus> {
  return apiGet<XertCredentialsStatus>("/me/xert-credentials");
}

export async function saveMyXertCredentials(
  xert_email: string,
  xert_password: string,
  sync_since?: string
): Promise<void> {
  const body: Record<string, string> = { xert_email, xert_password };
  if (sync_since) body.sync_since = sync_since;
  return apiPut("/me/xert-credentials", body, "Failed to save Xert credentials");
}

export async function deleteMyXertCredentials(): Promise<void> {
  return apiDelete("/me/xert-credentials", "Failed to disconnect Xert");
}

// Garmin
export async function fetchMyGarminCredentials(): Promise<GarminCredentialsStatus> {
  return apiGet<GarminCredentialsStatus>("/me/garmin-credentials");
}

export async function saveMyGarminCredentials(
  garmin_email: string,
  garmin_password: string,
  sync_since?: string
): Promise<GarminSaveResponse> {
  const body: Record<string, string> = { garmin_email, garmin_password };
  if (sync_since) body.sync_since = sync_since;
  return apiPut<GarminSaveResponse>("/me/garmin-credentials", body, "Failed to save Garmin credentials");
}

export async function completeGarminMfa(mfa_code: string): Promise<GarminSaveResponse> {
  return apiPost<GarminSaveResponse>(
    "/me/garmin-credentials/mfa",
    { mfa_code },
    "Failed to complete MFA"
  );
}

export async function deleteMyGarminCredentials(): Promise<void> {
  return apiDelete("/me/garmin-credentials", "Failed to disconnect Garmin");
}

// ============================================================================
// Admin API
// ============================================================================

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

export async function fetchAdminSettings(): Promise<AdminSettings> {
  return apiGet<AdminSettings>("/admin/settings");
}

export async function updateAdminSetting(key: string, value: boolean | string): Promise<void> {
  return apiPut(`/admin/settings/${key}`, { value }, "Failed to update setting");
}

// ============================================================================
// Nuke API
// ============================================================================

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

// ============================================================================
// Analytics API
// ============================================================================

export async function fetchRecords(): Promise<RecordsResponse> {
  return apiGet<RecordsResponse>("/records");
}

export async function fetchPMC(start?: string, end?: string): Promise<PMCPoint[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const query = params.toString();
  return apiGet<PMCPoint[]>(`/pmc${query ? `?${query}` : ""}`);
}

export async function fetchPowerCurve(start?: string, end?: string): Promise<PowerCurvePoint[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const query = params.toString();
  return apiGet<PowerCurvePoint[]>(`/power-curve${query ? `?${query}` : ""}`);
}

export async function fetchFitness(): Promise<FitnessResponse> {
  return apiGet<FitnessResponse>("/fitness");
}


// ============================================================================
// OAuth API
// ============================================================================

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
