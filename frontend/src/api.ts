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
  activity_id: number | null;
  distance_m?: number;
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

const API_BASE = import.meta.env.VITE_API_URL || "";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
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

export async function fetchRecords(): Promise<Records> {
  return apiFetch<Records>("/records");
}

export async function login(
  username: string,
  password: string
): Promise<boolean> {
  const res = await fetch(`${API_BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  return res.ok;
}

export async function uploadFit(file: File): Promise<{ id: number }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}