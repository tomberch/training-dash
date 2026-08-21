/**
 * Bikes API - CRUD operations for bikes/gear
 */
import { apiGet, apiPost, apiPatch } from "./base";
import type { Bike, BikeListResponse, BikeCreateRequest, BikeUpdateRequest } from "./types";

/**
 * Fetch all bikes for the current user.
 * @param includeRetired - If true, include retired bikes in the response.
 */
export async function fetchBikes(includeRetired = false): Promise<Bike[]> {
  const params = includeRetired ? "?include_retired=true" : "";
  const response = await apiGet<BikeListResponse>(`/bikes${params}`);
  return response.bikes;
}

/**
 * Fetch a single bike by ID.
 */
export async function fetchBike(id: number): Promise<Bike> {
  return apiGet<Bike>(`/bikes/${id}`);
}

/**
 * Create a new bike.
 */
export async function createBike(request: BikeCreateRequest): Promise<Bike> {
  return apiPost<Bike>("/bikes", request, "Failed to create bike");
}

/**
 * Update an existing bike.
 */
export async function updateBike(id: number, request: BikeUpdateRequest): Promise<Bike> {
  return apiPatch<Bike>(`/bikes/${id}`, request, "Failed to update bike");
}

/**
 * Set a bike as the default.
 */
export async function setDefaultBike(id: number): Promise<Bike> {
  return apiPost<Bike>(`/bikes/${id}/default`, {}, "Failed to set default bike");
}

/**
 * Retire a bike (soft delete).
 */
export async function retireBike(id: number): Promise<Bike> {
  return apiPost<Bike>(`/bikes/${id}/retire`, {}, "Failed to retire bike");
}


// =============================================================================
// Calibration Types
// =============================================================================

export interface CalibrationStatus {
  eligible: boolean;
  n_activities: number;
  estimated_confidence: "low" | "medium" | "high";
  last_calibrated: string | null;
  reason: string | null;
}

export interface CalibrationResult {
  bike_id: number;
  cda: number;
  confidence: "low" | "medium" | "high";
  n_activities_used: number;
  n_segments_used: number;
  total_duration_s: number;
  previous_cda: number | null;
  updated: boolean;
  warnings: string[];
  rejection_summary: Record<string, number>;
}

export interface CalibrateRequest {
  min_confidence?: "low" | "medium" | "high";
  rider_mass_kg?: number | null;
}

// =============================================================================
// Calibration API
// =============================================================================

/**
 * Get calibration status for a bike.
 * Returns whether the bike is eligible for calibration and estimated confidence.
 */
export async function getCalibrationStatus(bikeId: number): Promise<CalibrationStatus> {
  return apiGet<CalibrationStatus>(`/bikes/${bikeId}/calibration-status`);
}

/**
 * Trigger CdA calibration for a bike.
 * Analyzes recent activities tagged to this bike and estimates CdA.
 */
export async function calibrateBike(
  bikeId: number,
  request?: CalibrateRequest
): Promise<CalibrationResult> {
  return apiPost<CalibrationResult>(
    `/bikes/${bikeId}/calibrate`,
    request || {},
    "Failed to calibrate bike"
  );
}
