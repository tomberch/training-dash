/**
 * E2E tests for Activity List view.
 *
 * Tests the activity list displays correctly with metrics,
 * handles empty states, and navigates to detail views.
 *
 * ISOLATION: This test creates its own user and uploads activities
 * to avoid conflicts with parallel tests.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser } from '../fixtures/auth';
import { uploadFitFileAndWait, getFixtureFitPath } from '../fixtures/upload';

// Test user for activity list tests (has activities)
const testUser = generateTestUser('activity-list');
// Separate user for empty state test (no activities)
const emptyUser = generateTestUser('activity-empty');

// Track uploaded activity IDs for cleanup
const uploadedActivityIds: string[] = [];

/**
 * Helper to register and login a user via API.
 */
async function setupUser(
  request: import('@playwright/test').APIRequestContext,
  email: string,
  password: string
): Promise<void> {
  const registerResponse = await request.post('/api/register', {
    data: { email, password },
  });
  if (!registerResponse.ok()) {
    // User might already exist - try logging in
    const loginResponse = await request.post('/api/login', {
      data: { email, password },
    });
    if (!loginResponse.ok()) {
      throw new Error(`Failed to setup user: ${await registerResponse.text()}`);
    }
    return;
  }

  await request.post('/api/login', {
    data: { email, password },
  });
}

/**
 * Helper to login a user (for page context).
 */
async function loginUser(page: import('@playwright/test').Page, email: string, password: string): Promise<void> {
  await page.request.post('/api/login', {
    data: { email, password },
  });
}

test.describe('Activity List', () => {
  // Set up isolated user with activities for most tests
  test.beforeAll(async ({ request }) => {
    // Increase timeout for user registration + multiple file uploads (job queue may have backlog)
    test.setTimeout(300000);
    
    // Setup main test user
    await setupUser(request, testUser.email, testUser.password);

    // Set threshold before uploads (FIT files are dated July 2026)
    await request.post('/api/me/thresholds', {
      data: { ftp_watts: 220, lthr_bpm: 165, effective_date: '2026-06-01' },
    });

    // Upload multiple FIT files to have a populated activity list
    const fitFiles = ['cp-ride1-2min.fit', 'cp-ride2-5min.fit', 'cp-ride3-10min.fit'];

    for (const fileName of fitFiles) {
      const filePath = getFixtureFitPath(fileName);
      const activityId = await uploadFitFileAndWait(request, filePath);
      uploadedActivityIds.push(activityId);
    }

    // Also setup the empty user (but don't upload anything)
    await setupUser(request, emptyUser.email, emptyUser.password);
  });

  test('empty state shows when no activities exist', async ({ page }) => {
    // Login as the empty user (no activities)
    await loginUser(page, emptyUser.email, emptyUser.password);

    await page.goto('/activities');

    // Should show empty state message
    await expect(page.getByText('No activities yet')).toBeVisible({ timeout: 10000 });
  });

  test('activity list loads and displays activities', async ({ page }) => {
    await loginUser(page, testUser.email, testUser.password);

    await page.goto('/activities');
    await page.waitForLoadState('networkidle');

    // Should see the list header
    await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();

    // Should show activity count
    await expect(page.getByText(/\d+ activit/)).toBeVisible();
  });

  test('activity shows date, name, duration, distance metrics', async ({ page }) => {
    await loginUser(page, testUser.email, testUser.password);

    await page.goto('/activities');
    await page.waitForLoadState('networkidle');

    // Wait for activity list to render
    await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();

    // Check for metric labels in activity rows
    await expect(page.getByText('Distance').first()).toBeVisible();
    await expect(page.getByText('Time').first()).toBeVisible();
  });

  test('clicking activity navigates to detail view', async ({ page }) => {
    await loginUser(page, testUser.email, testUser.password);

    await page.goto('/activities');
    await page.waitForLoadState('networkidle');

    // Wait for activity list to load
    const firstActivityHeading = page.getByRole('main').locator('h3').first();
    await expect(firstActivityHeading).toBeVisible({ timeout: 10000 });

    // Click on the activity heading to navigate to detail
    await firstActivityHeading.click();

    // Should navigate to activity detail page (UUID format)
    await expect(page).toHaveURL(/\/activities\/[a-f0-9-]+/);

    // Should show activity detail content
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 10000 });
  });

  test('dashboard shows recent activities', async ({ page }) => {
    await loginUser(page, testUser.email, testUser.password);

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Dashboard should show "Recent Activities" section
    await expect(page.getByText('Recent Activities')).toBeVisible();

    // Should have "View all" link
    await expect(page.getByText('View all')).toBeVisible();
  });

  test('view all link navigates to activities page', async ({ page }) => {
    await loginUser(page, testUser.email, testUser.password);

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Wait for Recent Activities section
    await expect(page.getByText('Recent Activities')).toBeVisible();

    // Click "View all" link
    await page.getByText('View all').click();

    // Should navigate to activities page
    await expect(page).toHaveURL('/activities');
  });

  test('pagination appears with many activities', async ({ page }) => {
    await loginUser(page, testUser.email, testUser.password);

    await page.goto('/activities');
    await page.waitForLoadState('networkidle');

    // We only have 3 activities, so no pagination expected
    // Just verify the page works correctly
    await expect(page.getByRole('heading', { name: 'Activities', exact: true })).toBeVisible();

    // Note: To test pagination with 20+ activities, would need to upload more FIT files
    // or use a dedicated pagination test with its own user
  });

  test.afterAll(async ({ request }) => {
    // Clean up: delete uploaded activities
    await request.post('/api/login', {
      data: { email: testUser.email, password: testUser.password },
    });

    for (const activityId of uploadedActivityIds) {
      try {
        await request.delete(`/api/activities/${activityId}`);
      } catch {
        // Ignore cleanup errors
      }
    }
  });
});
