export interface PeakPower {
  duration_seconds: number;
  watts: number;
  all_time_pr: number | null;
  pct_of_pr: number | null;
  is_pr: boolean;
}

export interface Activity {
  id: number;
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

// Structured API error with optional error_id for tracking
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

const API_BASE = import.meta.env.VITE_API_URL || "";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) {
    // Try to parse structured error response
    let detail = `Request failed`;
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // Response wasn't JSON, use status text
      detail = res.statusText || detail;
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function fetchActivities(): Promise<Activity[]> {
  return apiFetch<Activity[]>("/activities");
}

export async function fetchActivity(id: number): Promise<Activity> {
  return apiFetch<Activity>(`/activities/${id}`);
}

export async function fetchActivityRecords(
  id: number
): Promise<GeoJSONFeatureCollection> {
  return apiFetch<GeoJSONFeatureCollection>(`/activities/${id}/records`);
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

export async function fetchActivityWbal(id: number): Promise<WbalResponse> {
  return apiFetch<WbalResponse>(`/activities/${id}/wbal`);
}

export async function fetchRecords(): Promise<RecordsResponse> {
  return apiFetch<RecordsResponse>("/records");
}

export async function fetchSameRouteActivities(id: number): Promise<SameRouteResponse> {
  return apiFetch<SameRouteResponse>(`/activities/${id}/same-route`);
}

export async function fetchComparison(id: number, otherId: number): Promise<CompareResponse> {
  return apiFetch<CompareResponse>(`/activities/${id}/compare?other=${otherId}`);
}

export async function login(
  username: string,
  password: string
): Promise<LoginResponse | null> {
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
  const res = await fetch(`${API_BASE}/logout`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiError("Logout failed", res.status);
  }
}

export async function uploadFit(file: File): Promise<{ id?: number; job_id?: string; source_ref?: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) {
    let detail = "Upload failed";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export interface JobStatus {
  status: "pending" | "processing" | "complete" | "not_found" | "unknown";
  result: { success: boolean; activity_id: number | null } | null;
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  return apiFetch<JobStatus>(`/jobs/${jobId}`);
}

// Admin API

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

export async function fetchMe(): Promise<User> {
  return apiFetch<User>("/me");
}

export async function updatePreferences(prefs: { unit_system?: string }): Promise<User> {
  const res = await fetch(`${API_BASE}/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(prefs),
  });
  if (!res.ok) {
    let detail = "Failed to update preferences";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/admin/users");
}

export async function createUser(username: string, password: string): Promise<AdminUser> {
  const res = await fetch(`${API_BASE}/admin/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    let detail = "Failed to create user";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function resetUserPassword(userId: number, password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/admin/users/${userId}/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    let detail = "Failed to reset password";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
}

export async function triggerUserSync(userId: number): Promise<{ job_id: string | null }> {
  const res = await fetch(`${API_BASE}/admin/users/${userId}/sync`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) {
    let detail = "Failed to trigger sync";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

// User Xert credentials API

export interface XertCredentialsStatus {
  configured: boolean;
  xert_email: string | null;
  sync_since: string | null;
}

export async function fetchMyXertCredentials(): Promise<XertCredentialsStatus> {
  return apiFetch<XertCredentialsStatus>("/me/xert-credentials");
}

export async function saveMyXertCredentials(
  xert_email: string,
  xert_password: string,
  sync_since?: string
): Promise<void> {
  const body: Record<string, string> = { xert_email, xert_password };
  if (sync_since) body.sync_since = sync_since;
  
  const res = await fetch(`${API_BASE}/me/xert-credentials`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "Failed to save Xert credentials";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
}

export async function deleteMyXertCredentials(): Promise<void> {
  const res = await fetch(`${API_BASE}/me/xert-credentials`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    let detail = "Failed to disconnect Xert";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
}

// User Garmin credentials API

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

export async function fetchMyGarminCredentials(): Promise<GarminCredentialsStatus> {
  return apiFetch<GarminCredentialsStatus>("/me/garmin-credentials");
}

export async function saveMyGarminCredentials(
  garmin_email: string,
  garmin_password: string,
  sync_since?: string
): Promise<GarminSaveResponse> {
  const body: Record<string, string> = { garmin_email, garmin_password };
  if (sync_since) body.sync_since = sync_since;
  
  const res = await fetch(`${API_BASE}/me/garmin-credentials`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = "Failed to save Garmin credentials";
    let errorId: string | undefined;
    try {
      const respBody = await res.json();
      detail = respBody.detail || detail;
      errorId = respBody.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function completeGarminMfa(mfa_code: string): Promise<GarminSaveResponse> {
  const res = await fetch(`${API_BASE}/me/garmin-credentials/mfa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ mfa_code }),
  });
  if (!res.ok) {
    let detail = "Failed to complete MFA";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
  return res.json();
}

export async function deleteMyGarminCredentials(): Promise<void> {
  const res = await fetch(`${API_BASE}/me/garmin-credentials`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) {
    let detail = "Failed to disconnect Garmin";
    let errorId: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      errorId = body.error_id;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status, errorId);
  }
}




// PMC (Performance Management Chart) types
export interface PMCPoint {
  date: string;
  ctl: number;
  atl: number;
  tsb: number;
}

export async function fetchPMC(start?: string, end?: string): Promise<PMCPoint[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const query = params.toString();
  return apiFetch<PMCPoint[]>(`/pmc${query ? `?${query}` : ""}`);
}

// Threshold history for FTP markers
export interface ThresholdEntry {
  effective_date: string;
  ftp_watts: number | null;
  lthr_bpm: number | null;
  max_hr_bpm: number | null;
}

export async function fetchThresholds(): Promise<ThresholdEntry[]> {
  return apiFetch<ThresholdEntry[]>("/me/thresholds");
}


// Power curve types
export interface PowerCurvePoint {
  duration_seconds: number;
  watts: number;
  achieved_date: string;
  days_ago: number;
}

export async function fetchPowerCurve(start?: string, end?: string): Promise<PowerCurvePoint[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const query = params.toString();
  return apiFetch<PowerCurvePoint[]>(`/power-curve${query ? `?${query}` : ""}`);
}

// Fitness model types
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

export async function fetchFitness(): Promise<FitnessResponse> {
  return apiFetch<FitnessResponse>("/fitness");
}


// Notifications types
export interface Notification {
  id: number;
  type: string;
  message: string;
  payload: { suggested_ftp?: number } | null;
  created_at: string;
}

export async function fetchNotifications(): Promise<Notification[]> {
  return apiFetch<Notification[]>("/me/notifications");
}

export async function acceptNotification(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/me/notifications/${id}/accept`, { 
    method: "POST", 
    credentials: "include" 
  });
  if (!res.ok) {
    throw new ApiError("Failed to accept notification", res.status);
  }
}

export async function dismissNotification(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/me/notifications/${id}/dismiss`, { 
    method: "POST", 
    credentials: "include" 
  });
  if (!res.ok) {
    throw new ApiError("Failed to dismiss notification", res.status);
  }
}


// Zones types
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

export async function fetchZones(): Promise<ZonesResponse> {
  return apiFetch<ZonesResponse>("/me/zones");
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

export async function updateZones(request: UpdateZonesRequest): Promise<ZonesResponse> {
  const res = await fetch(`${API_BASE}/me/zones`, {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    let detail = "Failed to update zones";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

// Create threshold
export interface CreateThresholdRequest {
  effective_date?: string;
  ftp_watts: number;
  lthr_bpm: number;
  hrmax_bpm: number;
}

export async function createThreshold(request: CreateThresholdRequest): Promise<ThresholdEntry> {
  const res = await fetch(`${API_BASE}/me/thresholds`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    let detail = "Failed to create threshold";
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {}
    throw new ApiError(detail, res.status);
  }
  return res.json();
}
