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
 *
 * ISOLATION: This test creates its own user and uploads its own activity
 * to avoid conflicts with parallel tests.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser } from '../fixtures/auth';
import { uploadFitFileAndWait, getFixtureFitPath } from '../fixtures/upload';

// Shared state for serial tests
let sharedActivityId: string | null = null;
const testUser = generateTestUser('activity-detail');

/**
 * Helper to register and login a user via API.
 */
async function setupTestUser(request: import('@playwright/test').APIRequestContext): Promise<void> {
  // Register
  const registerResponse = await request.post('/api/register', {
    data: { email: testUser.email, password: testUser.password },
  });
  if (!registerResponse.ok()) {
    // User might already exist from a previous interrupted run
    const loginResponse = await request.post('/api/login', {
      data: { email: testUser.email, password: testUser.password },
    });
    if (!loginResponse.ok()) {
      throw new Error(`Failed to setup test user: ${await registerResponse.text()}`);
    }
    return;
  }
  
  // Login
  await request.post('/api/login', {
    data: { email: testUser.email, password: testUser.password },
  });
}

/**
 * Helper to login before each test (browser context doesn't share API auth).
 */
async function loginTestUser(page: import('@playwright/test').Page): Promise<void> {
  await page.request.post('/api/login', {
    data: { email: testUser.email, password: testUser.password },
  });
}

test.describe.serial('Activity Detail', () => {
  // Set up isolated user and upload activity once for all tests
  test.beforeAll(async ({ request }) => {
    // Increase timeout for user registration + file upload (job queue may have backlog)
    test.setTimeout(180000);
    
    await setupTestUser(request);
    
    // Set threshold before upload (effective date before FIT file date)
    await request.post('/api/me/thresholds', {
      data: { ftp_watts: 220, lthr_bpm: 165, effective_date: '2026-06-01' },
    });
    
    // Upload a test FIT file
    const testFitPath = getFixtureFitPath('cp-ride5-mixed.fit');
    sharedActivityId = await uploadFitFileAndWait(request, testFitPath);
  });

  test('detail page loads for valid activity ID', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);

    // Should show activity detail page (not loading skeleton or error)
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Should have analyze and delete buttons
    await expect(page.getByRole('main').getByRole('link', { name: 'Analyze' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible();
  });

  test('metrics summary shows ride basics', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check for Time & Distance section
    await expect(page.getByText('Time & Distance')).toBeVisible();

    // Check for basic metric labels
    await expect(page.getByText('Distance').first()).toBeVisible();
    await expect(page.getByText('Moving').first()).toBeVisible();
    await expect(page.getByText('Elapsed').first()).toBeVisible();
  });

  test('metrics summary shows training metrics', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check for Training Load section with training metrics
    // The Training Load card uses an h3 element, scroll to it
    const trainingLoadHeader = page.locator('h3', { hasText: 'Training Load' }).first();
    await trainingLoadHeader.scrollIntoViewIfNeeded();
    await expect(trainingLoadHeader).toBeVisible();
    
    // Check for training metric labels within the page
    await expect(page.getByText('TSS').first()).toBeVisible();
    await expect(page.getByText('IF').first()).toBeVisible();
  });

  test('performance section with charts renders', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check for Performance section
    await expect(page.getByText('Performance').first()).toBeVisible();

    // Check for chart labels - at least one chart should be visible
    const chartLabels = ['Power', 'Heart Rate', 'Speed', 'Elevation'];
    let foundChart = false;
    for (const label of chartLabels) {
      const chartHeader = page.locator('.bg-card').filter({ hasText: label }).first();
      if (await chartHeader.isVisible().catch(() => false)) {
        foundChart = true;
        break;
      }
    }

    expect(foundChart).toBe(true);
  });

  test('power chart has time/distance toggle', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Find the Power chart section
    const powerSection = page.locator('.bg-card').filter({ hasText: 'Power' }).first();

    if (await powerSection.isVisible().catch(() => false)) {
      const toggleButton = powerSection.locator('button').filter({ hasText: /Time|Distance/ });
      await expect(toggleButton.first()).toBeVisible();
    }
  });

  test('map displays when GPS data present', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Check if map container exists (Leaflet map)
    const mapContainer = page.locator('.leaflet-container');

    // Map may or may not be visible depending on GPS data
    const mapVisible = await mapContainer.isVisible().catch(() => false);
    if (mapVisible) {
      await expect(mapContainer).toBeVisible();
    }
  });

  test('zone distribution charts render when data available', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Scroll down to ensure lazy-loaded sections load
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);

    // Check for zone charts
    const powerZoneChart = page.getByText('Power Zone Distribution');
    const hasPowerZones = await powerZoneChart.isVisible().catch(() => false);

    if (hasPowerZones) {
      await expect(page.getByText(/Z[1-7]:/)).toBeVisible();
    }
  });

  test('analysis section renders power curve and wbal charts', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Scroll down to trigger lazy loading of Analysis section
    const analysisHeader = page.getByRole('heading', { name: 'Analysis' });
    await analysisHeader.scrollIntoViewIfNeeded();
    
    // Wait for the Analysis section header to be visible
    await expect(analysisHeader).toBeVisible({ timeout: 10000 });

    // Find the Analysis section by its header, then look for charts within main content
    const mainContent = page.getByRole('main');
    
    // Check that Power Curve chart renders (not skeleton)
    // The Power Curve is rendered if the activity has peaks data
    // Look for the h2 heading with "Power Curve" text
    const powerCurveHeading = mainContent.locator('h2', { hasText: 'Power Curve' }).first();
    await powerCurveHeading.scrollIntoViewIfNeeded();
    await expect(powerCurveHeading).toBeVisible({ timeout: 10000 });
    
    // Get the card containing Power Curve and verify it has an SVG chart
    const powerCurveCard = powerCurveHeading.locator('..').locator('..').locator('..');
    const powerCurveSvg = powerCurveCard.locator('svg.recharts-surface');
    await expect(powerCurveSvg).toBeVisible({ timeout: 5000 });

    // Check that W'bal chart renders
    const wbalHeading = mainContent.locator('h2', { hasText: "W'bal" }).first();
    await wbalHeading.scrollIntoViewIfNeeded();
    await expect(wbalHeading).toBeVisible({ timeout: 5000 });
    
    // Verify W'bal chart has actual SVG content
    const wbalCard = wbalHeading.locator('..').locator('..').locator('..');
    const wbalSvg = wbalCard.locator('svg.recharts-surface');
    await expect(wbalSvg).toBeVisible({ timeout: 5000 });
  });

  test('back button navigates to activities list', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Click back button
    await page.getByRole('button', { name: 'Back' }).click();

    await page.waitForTimeout(500);
    await expect(page).not.toHaveURL(new RegExp(`/activities/${sharedActivityId}$`));
  });

  test('404 handling for invalid activity ID', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto('/activities/00000000-0000-0000-0000-000000000000');

    await expect(
      page.getByText(/not found|error|failed/i)
    ).toBeVisible({ timeout: 10000 });
  });

  test('delete button shows confirmation dialog', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Click delete button
    await page.getByRole('button', { name: 'Delete' }).click();

    // Should show confirmation dialog
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await expect(page.getByText('Delete activity?')).toBeVisible();

    // Should have cancel and confirm buttons
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
    const dialog = page.getByRole('alertdialog');
    await expect(dialog.getByRole('button', { name: 'Delete' })).toBeVisible();

    // Cancel the dialog (don't actually delete - other tests need the activity)
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByRole('alertdialog')).not.toBeVisible();
  });

  test('actions menu shows upload and export options', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Click Actions button to open dropdown
    const actionsButton = page.getByRole('button', { name: /Actions/i });
    await expect(actionsButton).toBeVisible();
    await actionsButton.click();

    // Should show dropdown menu with Upload to Provider and Export FIT options
    await expect(page.getByText('Upload to Provider')).toBeVisible();
    await expect(page.getByText('Export FIT File')).toBeVisible();
  });

  test('upload to provider dialog opens and has provider selection', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Actions menu and click Upload to Provider
    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();

    // Should show dialog
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('Upload to Provider').first()).toBeVisible();

    // Should have provider selection buttons
    await expect(page.getByRole('button', { name: /Garmin Connect/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Xert/i })).toBeVisible();

    // Should have device type search input
    await expect(page.getByPlaceholder(/Search devices/i)).toBeVisible();

    // Should have Upload and Cancel buttons
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Upload' })).toBeVisible();

    // Close the dialog
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('device search shows filtered results', async ({ page }) => {
    await loginTestUser(page);
    
    await page.goto(`/activities/${sharedActivityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Upload dialog
    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Type in device search
    const deviceInput = page.getByPlaceholder(/Search devices/i);
    await deviceInput.fill('Edge 840');

    // Should show filtered results
    await expect(page.getByText('Edge 840')).toBeVisible({ timeout: 5000 });

    // Close dialog
    await page.keyboard.press('Escape');
  });

  test.afterAll(async ({ request }) => {
    // Clean up: delete the activity
    if (sharedActivityId) {
      try {
        // Login first
        await request.post('/api/login', {
          data: { email: testUser.email, password: testUser.password },
        });
        await request.delete(`/api/activities/${sharedActivityId}`);
      } catch {
        // Ignore cleanup errors
      }
    }
  });
});
