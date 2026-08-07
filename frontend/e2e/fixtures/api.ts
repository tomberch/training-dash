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
 * Returns immediately with job_id (202) or activity id (200).
 */
export async function uploadFitFile(
  page: Page,
  fileBuffer: Buffer,
  fileName: string
): Promise<{ job_id?: string; id?: string }> {
  const response = await page.request.post('/api/upload', {
    multipart: {
      file: {
        name: fileName,
        mimeType: 'application/octet-stream',
        buffer: fileBuffer,
      },
    },
  });
  
  if (!response.ok() && response.status() !== 202) {
    const body = await response.text();
    throw new Error(`Failed to upload FIT file: ${response.status()} ${body}`);
  }
  
  return response.json();
}

/**
 * Wait for an ingest job to complete.
 * Returns the activity ID when done.
 */
export async function waitForJob(
  page: Page,
  jobId: string,
  timeoutMs = 30000
): Promise<string> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < timeoutMs) {
    const response = await page.request.get(`/api/jobs/${jobId}`);
    if (response.ok()) {
      const data = await response.json();
      // Job complete - check result
      if (data.status === 'complete') {
        const result = data.result;
        if (result?.success && result?.activity_id) {
          return String(result.activity_id);
        }
        if (result?.success === false) {
          throw new Error('Job completed but activity ingest failed');
        }
        // Job complete but result is an error object (e.g. DB error)
        if (result && !result.success && !result.activity_id) {
          throw new Error(`Job failed: ${JSON.stringify(result)}`);
        }
      }
      if (data.status === 'not_found') {
        throw new Error(`Job ${jobId} not found`);
      }
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  
  throw new Error(`Job ${jobId} did not complete after ${timeoutMs}ms`);
}

/**
 * Upload a FIT file and wait for processing to complete.
 * Handles both sync (200) and async (202) responses.
 */
export async function uploadFitFileAndWait(
  page: Page,
  fileBuffer: Buffer,
  fileName: string,
  timeoutMs = 30000
): Promise<string> {
  const result = await uploadFitFile(page, fileBuffer, fileName);
  
  // Sync response - activity created immediately
  if (result.id) {
    return result.id;
  }
  
  // Async response - wait for job
  if (result.job_id) {
    return await waitForJob(page, result.job_id, timeoutMs);
  }
  
  throw new Error('Upload returned neither id nor job_id');
}
