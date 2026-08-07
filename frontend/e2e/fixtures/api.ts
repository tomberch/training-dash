import { Page, APIRequestContext } from '@playwright/test';

/**
 * API helper functions for E2E tests.
 * These allow tests to set up state quickly without UI interactions.
 */

/**
 * Wait for the app to be healthy.
 */
export async function waitForHealthy(request: APIRequestContext, timeoutMs = 30000): Promise<void> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeoutMs) {
    try {
      const response = await request.get('/api/health');
      if (response.ok()) {
        return;
      }
    } catch {
      // Server not ready yet
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  
  throw new Error(`App not healthy after ${timeoutMs}ms`);
}

/**
 * Get the current user info.
 */
export async function getCurrentUser(page: Page): Promise<{ id: number; email: string; is_admin: boolean } | null> {
  const response = await page.request.get('/api/me');
  if (!response.ok()) {
    return null;
  }
  return response.json();
}

/**
 * Wait for activities to appear in the list.
 * Used after Xert sync to verify activities were imported.
 */
export async function waitForActivities(
  page: Page,
  expectedCount: number,
  timeoutMs = 30000
): Promise<void> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeoutMs) {
    const response = await page.request.get('/api/activities');
    if (response.ok()) {
      const data = await response.json();
      if (data.activities && data.activities.length >= expectedCount) {
        return;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  throw new Error(`Expected ${expectedCount} activities but timed out after ${timeoutMs}ms`);
}

/**
 * Get all activities for the current user.
 */
export async function getActivities(page: Page): Promise<unknown[]> {
  const response = await page.request.get('/api/activities');
  if (!response.ok()) {
    throw new Error(`Failed to get activities: ${response.status()}`);
  }
  const data = await response.json();
  return data.activities || [];
}

/**
 * Upload a FIT file directly via API.
 */
export async function uploadFitFile(
  page: Page,
  filePath: string,
  fileName: string
): Promise<{ activity_id: number }> {
  const fs = await import('fs');
  const fileBuffer = fs.readFileSync(filePath);
  
  const response = await page.request.post('/api/activities/upload', {
    multipart: {
      file: {
        name: fileName,
        mimeType: 'application/octet-stream',
        buffer: fileBuffer,
      },
    },
  });
  
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to upload FIT file: ${response.status()} ${body}`);
  }
  
  return response.json();
}
