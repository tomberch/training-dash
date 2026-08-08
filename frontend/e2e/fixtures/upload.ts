/**
 * Shared upload helpers for E2E tests.
 * 
 * These helpers handle FIT file uploads with proper waiting for async job completion.
 * The background worker processes jobs serially, so uploads during parallel test runs
 * may queue up. Timeouts are set to accommodate worst-case queue depth.
 */
import * as fs from 'fs';
import * as path from 'path';
import type { APIRequestContext } from '@playwright/test';

/**
 * Default timeout for upload + job completion.
 * 
 * With parallel tests uploading simultaneously:
 * - Worst case: ~20 jobs × 3s each = 60s queue time
 * - Buffer for variability: 120s total
 */
const DEFAULT_UPLOAD_TIMEOUT_MS = 120000;

/**
 * Polling interval for job status checks.
 */
const POLL_INTERVAL_MS = 500;

/**
 * Upload a FIT file and wait for async processing to complete.
 * 
 * Handles both sync responses (activity ID returned immediately) and async
 * responses (job_id returned, poll until complete).
 * 
 * Includes retry logic to handle transient worker failures under high load.
 * 
 * @param request - Playwright API request context (must be authenticated)
 * @param filePath - Absolute path to the FIT file
 * @param timeoutMs - Maximum time to wait for job completion
 * @param maxRetries - Maximum number of upload retries on failure
 * @returns Activity ID as string
 * @throws Error if upload fails, job fails, or timeout exceeded after all retries
 */
export async function uploadFitFileAndWait(
  request: APIRequestContext,
  filePath: string,
  timeoutMs = DEFAULT_UPLOAD_TIMEOUT_MS,
  maxRetries = 3
): Promise<string> {
  const fileName = path.basename(filePath);
  const fileBuffer = fs.readFileSync(filePath);

  let lastError: Error | null = null;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await request.post('/api/upload', {
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
        throw new Error(`Upload failed: ${response.status()} ${body}`);
      }

      const result = await response.json();

      // Sync response - activity created immediately (Redis unavailable)
      if (result.id) {
        return String(result.id);
      }

      // Async response - poll for job completion
      if (result.job_id) {
        return await waitForJob(request, result.job_id, timeoutMs);
      }

      throw new Error('Upload returned neither id nor job_id');
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // Don't retry on certain errors
      if (lastError.message.includes('Upload failed: 4')) {
        // 4xx errors are client errors, don't retry
        throw lastError;
      }
      
      if (attempt < maxRetries) {
        // Wait before retrying (exponential backoff)
        const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
        console.warn(`Upload attempt ${attempt} failed, retrying in ${delay}ms: ${lastError.message}`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }
  
  throw lastError || new Error('Upload failed after all retries');
}

/**
 * Poll for job completion.
 */
async function waitForJob(
  request: APIRequestContext,
  jobId: string,
  timeoutMs: number
): Promise<string> {
  const startTime = Date.now();
  let lastStatus = 'unknown';
  
  while (Date.now() - startTime < timeoutMs) {
    try {
      const jobResponse = await request.get(`/api/jobs/${jobId}`);
      
      if (jobResponse.ok()) {
        const jobData = await jobResponse.json();
        lastStatus = jobData.status;
        
        if (jobData.status === 'complete') {
          // Check if we got an activity_id - it might be a UUID object or string
          const activityId = jobData.result?.activity_id;
          if (activityId) {
            return String(activityId);
          }
          // Job completed but no activity_id - check for explicit failure
          if (jobData.result?.success === false) {
            throw new Error(`Job completed with failure: ${JSON.stringify(jobData.result)}`);
          }
          // If success is true but no activity_id, something unexpected happened
          if (jobData.result?.success === true) {
            throw new Error(`Job succeeded but no activity_id returned: ${JSON.stringify(jobData)}`);
          }
          // No success field and no activity_id - likely a different job type or error
          throw new Error(`Job completed but no activity_id in result: ${JSON.stringify(jobData)}`);
        }
        
        if (jobData.status === 'failed') {
          throw new Error(`Job failed: ${JSON.stringify(jobData.result || jobData)}`);
        }
        
        if (jobData.status === 'not_found') {
          // Job not in queue yet or expired - keep polling briefly
          // This can happen if we poll before the job is enqueued
        }
      }
    } catch (error) {
      // Network error during poll - continue polling
      if (error instanceof Error && !error.message.includes('Job')) {
        // Only ignore network-level errors, not our thrown errors
        console.warn(`Poll error for job ${jobId}: ${error.message}`);
      } else {
        throw error;
      }
    }
    
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  
  throw new Error(
    `Job ${jobId} did not complete after ${timeoutMs}ms. Last status: ${lastStatus}. ` +
    `This may indicate the background worker is overloaded or not running.`
  );
}

/**
 * Upload multiple FIT files sequentially.
 * 
 * @param request - Playwright API request context (must be authenticated)
 * @param filePaths - Array of absolute paths to FIT files
 * @param timeoutPerFile - Timeout for each individual upload
 * @returns Array of activity IDs
 */
export async function uploadMultipleFitFiles(
  request: APIRequestContext,
  filePaths: string[],
  timeoutPerFile = DEFAULT_UPLOAD_TIMEOUT_MS
): Promise<string[]> {
  const activityIds: string[] = [];
  
  for (const filePath of filePaths) {
    const activityId = await uploadFitFileAndWait(request, filePath, timeoutPerFile);
    activityIds.push(activityId);
  }
  
  return activityIds;
}

/**
 * Get the path to a fixture FIT file.
 * 
 * @param fileName - Name of the FIT file (e.g., 'cp-ride1-2min.fit')
 * @returns Absolute path to the fixture file
 */
export function getFixtureFitPath(fileName: string): string {
  // __dirname in ES modules context
  const currentDir = path.dirname(new URL(import.meta.url).pathname);
  return path.join(currentDir, 'fit-files', fileName);
}
