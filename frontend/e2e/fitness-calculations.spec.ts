/**
 * E2E tests for fitness calculations (CP, W', TSS).
 *
 * Uses pre-generated FIT files designed to produce known CP model values:
 * - CP = 220W
 * - W' = 15000J
 *
 * These files are in frontend/e2e/fixtures/fit-files/cp-ride*.fit
 * See the README.md in that directory for the formula and expected values.
 *
 * TSS calculation requires FTP threshold to be set first.
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Test user credentials (created by globalSetup)
const TEST_USER = {
  email: 'testuser@example.com',
  password: 'testpass',
};

// Expected values from cp-ride*.fit fixture files
const EXPECTED_CP_WATTS = 220;
const EXPECTED_W_PRIME_JOULES = 15000;
const EXPECTED_PP_WATTS = 345; // Peak power from 2-min file

// Expected peak powers at each duration (P = CP + W'/t)
const EXPECTED_PEAKS: Record<number, number> = {
  120: 345, // 2 min
  300: 270, // 5 min
  600: 245, // 10 min
  1200: 233, // 20 min (rounded from 232.5)
};

// Expected activity metrics (calculated from power profiles with FTP=220W)
// Each ride has warmup + effort + cooldown, so total duration > effort duration
// Keyed by started_at date (from generate_e2e_fit_fixtures.py)
const EXPECTED_ACTIVITY_METRICS: Record<string, { np: number; tss: number }> = {
  '2026-07-01': { np: 220, tss: 19.9 }, // cp-ride1-2min
  '2026-07-05': { np: 209, tss: 22.6 }, // cp-ride2-5min
  '2026-07-10': { np: 209, tss: 30.1 }, // cp-ride3-10min
  '2026-07-15': { np: 213, tss: 46.7 }, // cp-ride4-20min
  '2026-07-20': { np: 178, tss: 54.6 }, // cp-ride5-mixed
};

// Tolerance for floating point comparisons
const CP_TOLERANCE = 5; // watts
const W_PRIME_TOLERANCE = 500; // joules
const TSS_TOLERANCE = 0.5; // TSS points
const NP_TOLERANCE = 1; // watts (rounding differences)

/**
 * Helper to login via API.
 */
async function loginUser(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<{ id: number }> {
  const response = await request.post('/api/login', {
    data: { email, password },
  });
  if (!response.ok()) {
    throw new Error(`Login failed: ${response.status()}`);
  }
  return response.json();
}

/**
 * Helper to upload a FIT file and wait for processing.
 */
async function uploadFitFileAndWait(
  request: APIRequestContext,
  filePath: string,
  timeoutMs = 30000
): Promise<string> {
  const fileName = path.basename(filePath);
  const fileBuffer = fs.readFileSync(filePath);

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

  // Sync response - activity created immediately
  if (result.id) {
    return result.id;
  }

  // Async response - wait for job
  if (result.job_id) {
    const startTime = Date.now();
    while (Date.now() - startTime < timeoutMs) {
      const jobResponse = await request.get(`/api/jobs/${result.job_id}`);
      if (jobResponse.ok()) {
        const jobData = await jobResponse.json();
        if (jobData.status === 'complete') {
          if (jobData.result?.success && jobData.result?.activity_id) {
            return String(jobData.result.activity_id);
          }
          throw new Error(`Job completed but failed: ${JSON.stringify(jobData.result)}`);
        }
        if (jobData.status === 'failed' || jobData.status === 'not_found') {
          throw new Error(`Job failed: ${JSON.stringify(jobData)}`);
        }
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    throw new Error(`Job ${result.job_id} did not complete after ${timeoutMs}ms`);
  }

  throw new Error('Upload returned neither id nor job_id');
}

/**
 * Helper to get list of FIT fixture files.
 */
function getCpRideFitFiles(): string[] {
  const fixturesDir = path.join(__dirname, 'fixtures/fit-files');
  const files = fs.readdirSync(fixturesDir);
  return files
    .filter((f) => f.startsWith('cp-ride') && f.endsWith('.fit'))
    .map((f) => path.join(fixturesDir, f))
    .sort();
}

/**
 * Helper to delete all activities for the current user.
 */
async function deleteAllActivities(request: APIRequestContext): Promise<void> {
  const response = await request.get('/api/activities');
  if (!response.ok()) return;

  const data = await response.json();
  const activities = data.activities || [];

  for (const activity of activities) {
    await request.delete(`/api/activities/${activity.id}`);
  }

  // Wait for recalculation jobs to complete
  await new Promise((resolve) => setTimeout(resolve, 2000));
}

test.describe.serial('Fitness Calculations', () => {
  const uploadedActivityIds: string[] = [];

  test.beforeAll(async ({ request }) => {
    // Login as test user
    await loginUser(request, TEST_USER.email, TEST_USER.password);

    // Clean up any existing activities to get a fresh start
    await deleteAllActivities(request);

    // Set FTP threshold (needed for TSS calculation)
    await request.post('/api/me/thresholds', {
      data: { ftp_watts: EXPECTED_CP_WATTS, lthr_bpm: 165 },
    });
  });

  test('upload all CP test FIT files', async ({ request }) => {
    const fitFiles = getCpRideFitFiles();
    expect(fitFiles.length).toBeGreaterThanOrEqual(4);

    for (const filePath of fitFiles) {
      const activityId = await uploadFitFileAndWait(request, filePath);
      uploadedActivityIds.push(activityId);
    }

    expect(uploadedActivityIds.length).toBe(fitFiles.length);
  });

  test('CP model produces expected values', async ({ request }) => {
    // Wait a moment for fitness model to be updated
    await new Promise((resolve) => setTimeout(resolve, 1000));

    const response = await request.get('/api/fitness');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.current).not.toBeNull();

    const { cp_watts, w_prime_joules, pp_watts } = data.current;

    // CP should be within tolerance of expected
    expect(cp_watts).toBeGreaterThanOrEqual(EXPECTED_CP_WATTS - CP_TOLERANCE);
    expect(cp_watts).toBeLessThanOrEqual(EXPECTED_CP_WATTS + CP_TOLERANCE);

    // W' should be within tolerance of expected
    expect(w_prime_joules).toBeGreaterThanOrEqual(EXPECTED_W_PRIME_JOULES - W_PRIME_TOLERANCE);
    expect(w_prime_joules).toBeLessThanOrEqual(EXPECTED_W_PRIME_JOULES + W_PRIME_TOLERANCE);

    // Peak power should match the 2-min file (highest sustained power)
    expect(pp_watts).toBe(EXPECTED_PP_WATTS);
  });

  test('power curve shows correct peak powers at each duration', async ({ request }) => {
    const response = await request.get('/api/power-curve');
    expect(response.ok()).toBeTruthy();

    const curve = await response.json();
    expect(Array.isArray(curve)).toBeTruthy();
    expect(curve.length).toBeGreaterThan(0);

    // Build a map of duration -> watts from the response
    const powerByDuration: Record<number, number> = {};
    for (const point of curve) {
      powerByDuration[point.duration_seconds] = point.watts;
    }

    // Verify expected peaks
    for (const [duration, expectedWatts] of Object.entries(EXPECTED_PEAKS)) {
      const durationSecs = parseInt(duration);
      const actualWatts = powerByDuration[durationSecs];

      expect(actualWatts).toBeDefined();
      // Allow small tolerance due to rounding
      expect(actualWatts).toBeGreaterThanOrEqual(expectedWatts - 2);
      expect(actualWatts).toBeLessThanOrEqual(expectedWatts + 2);
    }
  });

  test('activities have correct NP and TSS values', async ({ request }) => {
    const response = await request.get('/api/activities');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    const activities = data.activities || [];

    expect(activities.length).toBeGreaterThanOrEqual(5);

    // For each activity, fetch details and verify NP/TSS
    for (const activitySummary of activities) {
      // Get activity detail (which includes np_power_w)
      const detailResponse = await request.get(`/api/activities/${activitySummary.id}`);
      expect(detailResponse.ok()).toBeTruthy();
      const activity = await detailResponse.json();

      // Extract date from started_at (format: "2026-07-01T09:00:00+00:00")
      const activityDate = activity.started_at.split('T')[0];
      const expected = EXPECTED_ACTIVITY_METRICS[activityDate];

      if (expected) {
        // NP should match expected value within tolerance (rounding differences)
        expect(activity.np_power_w).toBeGreaterThanOrEqual(expected.np - NP_TOLERANCE);
        expect(activity.np_power_w).toBeLessThanOrEqual(expected.np + NP_TOLERANCE);

        // TSS should be within tolerance (floating point)
        expect(activity.tss).not.toBeNull();
        expect(activity.tss).toBeGreaterThanOrEqual(expected.tss - TSS_TOLERANCE);
        expect(activity.tss).toBeLessThanOrEqual(expected.tss + TSS_TOLERANCE);
      }
    }
  });

  test('TSS follows correct formula: (duration × NP × IF) / (FTP × 3600) × 100', async ({ request }) => {
    // Get a specific activity to verify the formula
    const response = await request.get('/api/activities');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    const activities = data.activities || [];

    // Get detail for an activity that has all metrics
    for (const activitySummary of activities) {
      const detailResponse = await request.get(`/api/activities/${activitySummary.id}`);
      expect(detailResponse.ok()).toBeTruthy();
      const activity = await detailResponse.json();

      if (
        activity.np_power_w !== null &&
        activity.intensity_factor !== null &&
        activity.tss !== null &&
        (activity.moving_time_s || activity.elapsed_time_s)
      ) {
        // Verify TSS matches the formula
        // TSS = (duration_s × NP × IF) / (FTP × 3600) × 100
        const FTP = 220; // Set in beforeAll
        const duration_s = activity.moving_time_s || activity.elapsed_time_s;
        const np = activity.np_power_w;
        const if_value = activity.intensity_factor;
        const expectedTss = (duration_s * np * if_value) / (FTP * 3600) * 100;

        // Allow small tolerance for rounding
        expect(activity.tss).toBeGreaterThanOrEqual(expectedTss - 0.5);
        expect(activity.tss).toBeLessThanOrEqual(expectedTss + 0.5);

        // Only need to verify one activity
        return;
      }
    }

    // Should have found at least one activity with all metrics
    throw new Error('No activity found with all metrics (NP, IF, TSS)');
  });

  test('fitness history tracks model updates', async ({ request }) => {
    const response = await request.get('/api/fitness');
    expect(response.ok()).toBeTruthy();

    const data = await response.json();

    // Should have history entries
    expect(data.history).toBeDefined();
    expect(data.history.length).toBeGreaterThan(0);

    // Each history entry should have the required fields
    for (const entry of data.history) {
      expect(entry.computed_at).toBeDefined();
      expect(entry.cp_watts).toBeDefined();
      expect(entry.w_prime_joules).toBeDefined();
      expect(entry.pp_watts).toBeDefined();
    }

    // Most recent entry should match current
    expect(data.history[0].cp_watts).toBe(data.current.cp_watts);
    expect(data.history[0].w_prime_joules).toBe(data.current.w_prime_joules);
  });

  test.afterAll(async ({ request }) => {
    // Clean up: delete uploaded activities
    for (const activityId of uploadedActivityIds) {
      try {
        await request.delete(`/api/activities/${activityId}`);
      } catch {
        // Ignore errors during cleanup
      }
    }
  });
});
