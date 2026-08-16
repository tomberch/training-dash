/**
 * Integration Credentials API - Xert and Garmin connections
 */
import { apiGet, apiPut, apiPatch, apiPost, apiDelete } from "./base";

// Xert types
export interface XertCredentialsStatus {
  configured: boolean;
  xert_email: string | null;
  sync_since: string | null;
  sync_enabled: boolean;
}

// Garmin types
export interface GarminCredentialsStatus {
  configured: boolean;
  garmin_email: string | null;
  sync_since: string | null;
  sync_enabled: boolean;
}

export interface GarminSaveResponse {
  success?: boolean;
  garmin_email?: string;
  mfa_required?: boolean;
}

// Xert API
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

export async function updateXertSyncEnabled(sync_enabled: boolean): Promise<{ success: boolean; sync_enabled: boolean }> {
  return apiPatch<{ success: boolean; sync_enabled: boolean }>("/me/xert-credentials", { sync_enabled }, "Failed to update sync setting");
}

// Garmin API
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

export async function updateGarminSyncEnabled(sync_enabled: boolean): Promise<{ success: boolean; sync_enabled: boolean }> {
  return apiPatch<{ success: boolean; sync_enabled: boolean }>("/me/garmin-credentials", { sync_enabled }, "Failed to update sync setting");
}
