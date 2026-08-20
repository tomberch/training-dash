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
