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
  id: number;
  title: string | null;
  title_source: "auto" | "manual";
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
  activity_id: number;
  features: GeoJSONFeature[];
}

export interface PRValue {
  value: number;
  activity_id?: number;
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
  activity_id: number | null;
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
  result: { success: boolean; activity_id: number | null } | null;
}

export interface AdminUser {
  id: number;
  username: string;
  is_admin: boolean;
  created_at: string;
}

export interface LoginResponse {
  user_id: number;
  username: string;
  is_admin?: boolean;
}

export interface User {
  id: number;
  username: string;
  is_admin: boolean;
  unit_system: "metric" | "imperial";
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
  max_hr_bpm: number | null;
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
  ftp_watts: number;
  lthr_bpm: number;
  hrmax_bpm: number;
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

export async function fetchActivities(): Promise<Activity[]> {
  return apiGet<Activity[]>("/activities");
}

export async function fetchActivity(id: number): Promise<Activity> {
  return apiGet<Activity>(`/activities/${id}`);
}

export async function fetchActivityRecords(id: number): Promise<GeoJSONFeatureCollection> {
  return apiGet<GeoJSONFeatureCollection>(`/activities/${id}/records`);
}

export async function fetchActivityWbal(id: number): Promise<WbalResponse> {
  return apiGet<WbalResponse>(`/activities/${id}/wbal`);
}

export async function fetchSameRouteActivities(id: number): Promise<SameRouteResponse> {
  return apiGet<SameRouteResponse>(`/activities/${id}/same-route`);
}

export async function updateActivityTitle(id: number, title: string): Promise<Activity> {
  return apiPatch<Activity>(`/activities/${id}`, { title }, "Failed to update activity title");
}

export async function fetchComparison(id: number, otherId: number): Promise<CompareResponse> {
  return apiGet<CompareResponse>(`/activities/${id}/compare?other=${otherId}`);
}

export async function uploadFit(
  file: File
): Promise<{ id?: number; job_id?: string; source_ref?: string }> {
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

export async function login(username: string, password: string): Promise<LoginResponse | null> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) return null;
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

export async function updatePreferences(prefs: { unit_system?: string }): Promise<User> {
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

export async function createUser(username: string, password: string): Promise<AdminUser> {
  return apiPost<AdminUser>("/admin/users", { username, password }, "Failed to create user");
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
