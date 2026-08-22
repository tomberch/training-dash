/**
 * Activity API - CRUD operations for activities
 */
import { apiGet, apiPost, apiPatch, apiDelete, API_BASE, ApiError, extractError } from "./base";
import type {
  Activity, PaginatedActivities, GeoJSONFeatureCollection,
  WbalResponse, SameRouteResponse, CompareResponse, JobStatus,
  ActivityType, WhatIfRequest, WhatIfResponse,
} from "./types";

export async function fetchActivities(
  page?: number,
  perPage?: number,
  activityType?: string | null
): Promise<PaginatedActivities> {
  const params = new URLSearchParams();
  if (page) params.set("page", page.toString());
  if (perPage) params.set("per_page", perPage.toString());
  // null = no filter (all), undefined = no filter, "" = unclassified, "road" etc = specific type
  if (activityType !== undefined && activityType !== null) {
    params.set("activity_type", activityType);
  }
  const query = params.toString();
  return apiGet<PaginatedActivities>(`/activities${query ? `?${query}` : ""}`);
}

export async function fetchActivity(id: string, include?: "calc_trace"): Promise<Activity> {
  const query = include ? `?include=${include}` : "";
  return apiGet<Activity>(`/activities/${id}${query}`);
}

export async function fetchWhatIf(id: string, params: WhatIfRequest): Promise<WhatIfResponse> {
  return apiPost<WhatIfResponse>(`/activities/${id}/what-if`, params, "Failed to calculate what-if");
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

export async function updateActivityType(id: string, activityType: ActivityType | null): Promise<Activity> {
  // Send empty string to clear (set to null), otherwise send the type
  return apiPatch<Activity>(
    `/activities/${id}`,
    { activity_type: activityType ?? "" },
    "Failed to update activity type"
  );
}

export async function updateActivityBike(id: string, bikeId: number | null): Promise<Activity> {
  return apiPatch<Activity>(
    `/activities/${id}`,
    { bike_id: bikeId },
    "Failed to update activity bike"
  );
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

// Upload to Provider
export interface FitDevice {
  id: number;
  name: string;
  display_name: string;
}

export interface FitDevicesResponse {
  devices: FitDevice[];
  total: number;
}

export interface UploadToProviderRequest {
  provider: "xert" | "garmin";
  device_product_id?: number | null;
}

export interface UploadToProviderResponse {
  provider: string;
  provider_activity_id: string;
}

export async function fetchFitDevices(): Promise<FitDevicesResponse> {
  return apiGet<FitDevicesResponse>(`/fit/devices`);
}

export async function uploadToProvider(
  activityId: string,
  request: UploadToProviderRequest
): Promise<UploadToProviderResponse> {
  return apiPost<UploadToProviderResponse>(
    `/activities/${activityId}/upload`,
    request,
    "Failed to upload to provider"
  );
}
