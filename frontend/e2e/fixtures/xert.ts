/**
 * Xert mock fixtures for E2E testing.
 *
 * The actual Xert API mocking happens in the backend via MockXertClient
 * (activated by MOCK_XERT_ENABLED=true in docker-compose.e2e.yml).
 *
 * This module provides helper functions for E2E tests that exercise
 * Xert import functionality.
 *
 * Mock behavior:
 * - login() always succeeds unless password is "invalid"
 * - list_activities() returns activities based on FIT files in fixtures/fit-files/
 * - download_fit() returns the corresponding FIT file bytes
 * - get_xss() returns predefined XSS values for known activity IDs
 *
 * Available mock activities (from fixtures/fit-files/):
 * - cp-ride1-2min: 2-minute CP test ride (XSS: 45)
 * - cp-ride2-5min: 5-minute CP test ride (XSS: 65)
 * - cp-ride3-10min: 10-minute CP test ride (XSS: 85)
 * - cp-ride4-20min: 20-minute CP test ride (XSS: 95)
 * - cp-ride5-mixed: Mixed duration ride (XSS: 120)
 * - test-ride: Basic test ride (XSS: 50)
 */

import { APIRequestContext } from '@playwright/test';

/**
 * Set up Xert credentials for a user via the settings API.
 *
 * This configures the user to import from Xert. When MOCK_XERT_ENABLED=true,
 * the backend will use MockXertClient instead of the real Xert API.
 *
 * @param request - Playwright API request context (must be authenticated)
 * @param xertEmail - Email to store (used for display, not actual auth in mock)
 * @param xertPassword - Password to store (use "invalid" to test login failure)
 */
export async function setXertCredentials(
  request: APIRequestContext,
  xertEmail: string = 'mock@xert.com',
  xertPassword: string = 'mockpassword'
): Promise<void> {
  const response = await request.put('/api/me/xert-credentials', {
    data: {
      xert_email: xertEmail,
      xert_password: xertPassword,
    },
  });

  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to set Xert credentials: ${response.status()} ${body}`);
  }
}

/**
 * Trigger a Xert import for the current user.
 *
 * This enqueues an import job that will use MockXertClient when
 * MOCK_XERT_ENABLED=true.
 *
 * @param request - Playwright API request context (must be authenticated)
 * @returns The job result from the import endpoint
 */
export async function triggerXertImport(
  request: APIRequestContext
): Promise<{ success: boolean; job_id?: string; error?: string }> {
  const response = await request.post('/api/me/import/xert');

  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to trigger Xert import: ${response.status()} ${body}`);
  }

  return response.json();
}

/**
 * Clear Xert credentials for the current user.
 *
 * @param request - Playwright API request context (must be authenticated)
 */
export async function clearXertCredentials(
  request: APIRequestContext
): Promise<void> {
  const response = await request.delete('/api/me/xert-credentials');

  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to clear Xert credentials: ${response.status()} ${body}`);
  }
}

/**
 * Get Xert credentials status for the current user.
 *
 * @param request - Playwright API request context (must be authenticated)
 * @returns Credential status with configured flag and email if set
 */
export async function getXertCredentialsStatus(
  request: APIRequestContext
): Promise<{ configured: boolean; xert_email: string | null; last_synced_at: string | null }> {
  const response = await request.get('/api/me/xert-credentials');

  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to get Xert credentials: ${response.status()} ${body}`);
  }

  return response.json();
}

/**
 * Expected mock activity IDs that will be returned by MockXertClient.
 *
 * These correspond to the FIT files in frontend/e2e/fixtures/fit-files/.
 */
export const MOCK_ACTIVITY_IDS = [
  'cp-ride1-2min',
  'cp-ride2-5min',
  'cp-ride3-10min',
  'cp-ride4-20min',
  'cp-ride5-mixed',
  'test-ride',
] as const;

/**
 * Expected XSS (Xert Strain Score) values for mock activities.
 */
export const MOCK_XSS_VALUES: Record<string, number> = {
  'cp-ride1-2min': 45.0,
  'cp-ride2-5min': 65.0,
  'cp-ride3-10min': 85.0,
  'cp-ride4-20min': 95.0,
  'cp-ride5-mixed': 120.0,
  'test-ride': 50.0,
  'breakthrough-5min': 75.0,
};
