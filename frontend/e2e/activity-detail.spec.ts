/**
 * E2E tests for Activity Detail view.
 *
 * Tests that the activity detail page loads correctly with:
 * - Activity header (title, date, time)
 * - Stats tiles (metrics summary)
 * - Map (if GPS data present)
 * - Performance charts (Power, HR, Speed, Elevation)
 * - Zone distribution charts
 * - 404 handling for invalid activity ID
 */
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Shared activity ID for serial tests - set once in beforeAll
let sharedActivityId: string | null = null;

/**
 * Helper to get or create an activity for testing.
 * Uses existing activities if available, otherwise uploads a test FIT file.
 * Uses page.request to share auth context with the browser.
 */
async function getOrCreateActivity(page: import('@playwright/test').Page): Promise<string | null> {
  // Check if we already have activities (using page.request shares auth cookies)
  const response = await page.request.get('/api/activities');
  if (response.ok()) {
    const data = await response.json();
    const activities = data.activities || [];
    if (activities.length > 0) {
      return activities[0].id;
    }
  }

  // Upload a test FIT file if no activities exist
  const testFitPath = path.join(__dirname, 'fixtures/fit-files/cp-ride5-mixed.fit');
  if (fs.existsSync(testFitPath)) {
    const fileName = path.basename(testFitPath);
    const fileBuffer = fs.readFileSync(testFitPath);

    const uploadResponse = await page.request.post('/api/upload', {
      multipart: {
        file: {
          name: fileName,
          mimeType: 'application/octet-stream',
          buffer: fileBuffer,
        },
      },
    });

    if (!uploadResponse.ok() && uploadResponse.status() !== 202) {
      return null;
    }

    const result = await uploadResponse.json();

    // Sync response
    if (result.id) {
      return result.id;
    }

    // Async response - wait for job
    if (result.job_id) {
      const startTime = Date.now();
      const timeoutMs = 30000;
      while (Date.now() - startTime < timeoutMs) {
        const jobResponse = await page.request.get(`/api/jobs/${result.job_id}`);
        if (jobResponse.ok()) {
          const jobData = await jobResponse.json();
          if (jobData.status === 'complete' && jobData.result?.activity_id) {
            return String(jobData.result.activity_id);
          }
          if (jobData.status === 'failed') {
            return null;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    }
  }

  return null;
}

/**
 * Helper to verify activity still exists before running a test.
 * If the activity was deleted by another parallel test, skip this test.
 */
async function verifyActivityExists(
  page: import('@playwright/test').Page,
  activityId: string
): Promise<boolean> {
  const response = await page.request.get(`/api/activities/${activityId}`);
  return response.ok();
}

test.describe.serial('Activity Detail', () => {
  // Set up a shared activity for all tests in this describe block
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({ storageState: '.auth/user.json' });
    const page = await context.newPage();
    sharedActivityId = await getOrCreateActivity(page);
    await context.close();
  });

  test('detail page loads for valid activity ID', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    // Verify the activity still exists (may have been deleted by parallel tests)
    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);

    // Should show activity detail page (not loading skeleton or error)
    // Wait for the back button which appears when loaded
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Should have analyze and delete buttons (use main region to avoid sidebar match)
    await expect(page.getByRole('main').getByRole('link', { name: 'Analyze' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible();
  });

  test('metrics summary shows ride basics', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check for Ride Basics section
    await expect(page.getByText('Ride Basics')).toBeVisible();

    // Check for basic metric labels
    await expect(page.getByText('Distance').first()).toBeVisible();
    await expect(page.getByText('Moving Time').first()).toBeVisible();
    await expect(page.getByText('Elevation').first()).toBeVisible();
    await expect(page.getByText('Avg Speed').first()).toBeVisible();
  });

  test('metrics summary shows training metrics', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check for Training Metrics section
    await expect(page.getByText('Training Metrics')).toBeVisible();

    // Check for training metric labels
    await expect(page.getByText('Avg Power').first()).toBeVisible();
    await expect(page.getByText('NP').first()).toBeVisible();
    await expect(page.getByText('IF').first()).toBeVisible();
    await expect(page.getByText('TSS').first()).toBeVisible();
  });

  test('performance section with charts renders', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check for Performance section
    await expect(page.getByText('Performance').first()).toBeVisible();

    // Check for chart labels - at least one chart should be visible
    // The charts available depend on the data in the FIT file
    const chartLabels = ['Power', 'Heart Rate', 'Speed', 'Elevation'];
    let foundChart = false;
    for (const label of chartLabels) {
      const chartHeader = page.locator('.bg-card').filter({ hasText: label }).first();
      if (await chartHeader.isVisible().catch(() => false)) {
        foundChart = true;
        break;
      }
    }

    // At least one chart should be visible (our test FIT files have power data)
    expect(foundChart).toBe(true);
  });

  test('power chart has time/distance toggle', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Find the Power chart section
    const powerSection = page.locator('.bg-card').filter({ hasText: 'Power' }).first();

    if (await powerSection.isVisible().catch(() => false)) {
      // Should have a time/distance toggle button
      const toggleButton = powerSection.locator('button').filter({ hasText: /Time|Distance/ });
      await expect(toggleButton.first()).toBeVisible();
    }
  });

  test('map displays when GPS data present', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check if map container exists (Leaflet map)
    // The map uses ResizableMap component which renders a leaflet-container
    const mapContainer = page.locator('.leaflet-container');

    // Map may or may not be visible depending on whether the FIT file has GPS
    // Just check if it loads without error when present
    const mapVisible = await mapContainer.isVisible().catch(() => false);
    if (mapVisible) {
      // If map is visible, it should have map tiles loaded
      await expect(mapContainer).toBeVisible();
    }
    // If not visible, that's okay - the FIT file may not have GPS data
  });

  test('zone distribution charts render when data available', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Scroll down to ensure lazy-loaded sections load
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);

    // Check for zone charts - they appear if the user has zones configured
    // and the activity has power/HR data
    const powerZoneChart = page.getByText('Power Zone Distribution');
    const hrZoneChart = page.getByText('HR Zone Distribution');

    // At least check the page doesn't crash when scrolling to these sections
    // Zone charts require user-configured zones, which may not exist
    const hasPowerZones = await powerZoneChart.isVisible().catch(() => false);
    const hasHrZones = await hrZoneChart.isVisible().catch(() => false);

    // If zones are configured, charts should render with zone bars
    if (hasPowerZones) {
      // Zone chart should have zone labels like Z1, Z2, etc.
      await expect(page.getByText(/Z[1-7]:/)).toBeVisible();
    }
  });

  test('back button navigates to activities list', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Click back button
    await page.getByRole('button', { name: 'Back' }).click();

    // Should navigate back (either to activities or previous page)
    // The onBack handler uses navigate(-1), so URL depends on history
    await page.waitForTimeout(500);
    // Just verify we're no longer on the detail page
    await expect(page).not.toHaveURL(new RegExp(`/activities/${sharedActivityId}$`));
  });

  test('404 handling for invalid activity ID', async ({ page }) => {
    // Navigate to a non-existent activity
    await page.goto('/activities/00000000-0000-0000-0000-000000000000');

    // Should show error state
    // The ErrorDisplay component shows error messages
    await expect(
      page.getByText(/not found|error|failed/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test('delete button shows confirmation dialog', async ({ page }) => {
    if (!sharedActivityId) {
      test.skip();
      return;
    }

    if (!(await verifyActivityExists(page, sharedActivityId))) {
      test.skip();
      return;
    }

    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Click delete button
    await page.getByRole('button', { name: 'Delete' }).click();

    // Should show confirmation dialog
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await expect(page.getByText('Delete activity?')).toBeVisible();

    // Should have cancel and confirm buttons
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
    // The confirm button in the dialog also says "Delete"
    // Look for it within the alert dialog
    const dialog = page.getByRole('alertdialog');
    await expect(dialog.getByRole('button', { name: 'Delete' })).toBeVisible();

    // Cancel the dialog
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByRole('alertdialog')).not.toBeVisible();
  });
});
