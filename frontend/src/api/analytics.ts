/**
 * Analytics API - records, PMC, power curve, fitness
 */
import { apiGet } from "./base";
import type { RecordsResponse } from "./types";

export interface PMCPoint {
  date: string;
  ctl: number;
  atl: number;
  tsb: number;
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

export async function fetchRecords(
  routeLimit: number = 20,
  routeOffset: number = 0
): Promise<RecordsResponse> {
  const params = new URLSearchParams({
    route_limit: routeLimit.toString(),
    route_offset: routeOffset.toString(),
  });
  return apiGet<RecordsResponse>(`/records?${params}`);
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
