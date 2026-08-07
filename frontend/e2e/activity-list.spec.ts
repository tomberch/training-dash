/**
 * E2E tests for Activity List view.
 *
 * Tests the activity list displays correctly with metrics,
 * handles empty states, and navigates to detail views.
 */
import { test, expect, Page } from '@playwright/test';
import { generateTestUser, registerUser } from './fixtures/auth';
import { getActivities } from './fixtures/api';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Helper to navigate to a page and skip the test if no activities exist.
 * Returns the activities array if activities exist, or calls test.skip() and returns null.
 */
async function requireActivities(page: Page, url: string): Promise<{ id: number }[] | null> {
  await page.goto(url);
  await page.waitForLoadState('networkidle');
  const activities = await getActivities(page);
  if (activities.length === 0) {
    test.skip();
    return null;
  }
  return activities;
}

test.describe('Activity List', () => {
  test('empty state shows when no activities exist', async ({ page }) => {
    // Create a fresh user with no activities
    const user = generateTestUser('activity-empty');
    await registerUser(page, user);

    // Navigate to activities page
    await page.goto('/activities');

    // Should show empty state message
    await expect(page.getByText('No activities yet')).toBeVisible({ timeout: 10000 });
  });

  test('activity list loads and displays activities', async ({ page }) => {
    // Use the authenticated state from setup (baseline user)
    const activities = await requireActivities(page, '/activities');
    if (!activities) return;

    // If activities exist, we should see the list header
    await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();

    // Should show activity count
    await expect(page.getByText(/\d+ activit/)).toBeVisible();
  });

  test('activity shows date, name, duration, distance metrics', async ({ page }) => {
    // Upload a test FIT file to ensure we have at least one activity
    const fitFilePath = path.join(__dirname, 'fixtures/fit-files/test-ride.fit');

    // Check if test FIT file exists, skip if not (created in #219)
    if (!fs.existsSync(fitFilePath)) {
      test.skip();
      return;
    }

    // Create a fresh user
    const user = generateTestUser('activity-metrics');
    await registerUser(page, user);

    // Upload the FIT file
    const fileBuffer = fs.readFileSync(fitFilePath);
    const response = await page.request.post('/api/activities/upload', {
      multipart: {
        file: {
          name: 'test-ride.fit',
          mimeType: 'application/octet-stream',
          buffer: fileBuffer,
        },
      },
    });
    expect(response.ok()).toBeTruthy();

    // Navigate to activities page
    await page.goto('/activities');

    // Wait for activity to appear
    await expect(page.getByText(/\d+ activit/)).toBeVisible({ timeout: 10000 });

    // Check for date (format varies but should have month/day pattern or relative date)
    const activityRow = page.locator('.bg-card').first();
    // Date appears as relative time (e.g., "2 hours ago") or formatted date
    await expect(activityRow.getByText(/ago|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec/)).toBeVisible();

    // Check for activity name/title (ride type or custom name)
    await expect(activityRow.getByText(/Ride|Run|Swim|Workout/i)).toBeVisible();

    // Check for metric labels
    await expect(page.getByText('Distance').first()).toBeVisible();
    await expect(page.getByText('Time').first()).toBeVisible();
  });

  test('clicking activity navigates to detail view', async ({ page }) => {
    const activities = await requireActivities(page, '/activities');
    if (!activities) return;

    // Click on the first activity row (the clickable area is the whole row)
    const firstActivityRow = page.locator('.bg-card').first();
    await firstActivityRow.click();

    // Should navigate to activity detail page
    await expect(page).toHaveURL(/\/activities\/\d+/);

    // Should show activity detail content
    await expect(page.getByRole('heading').first()).toBeVisible({ timeout: 10000 });
  });

  // Note: TSS test removed - requires FIT fixtures with power data and user threshold setup.
  // Will be added in #219 (FIT fixtures) or a dedicated threshold test ticket.

  test('dashboard shows recent activities', async ({ page }) => {
    const activities = await requireActivities(page, '/');
    if (!activities) return;

    // Dashboard should show "Recent Activities" section
    await expect(page.getByText('Recent Activities')).toBeVisible();

    // Should have "View all" link
    await expect(page.getByText('View all')).toBeVisible();
  });

  test('view all link navigates to activities page', async ({ page }) => {
    const activities = await requireActivities(page, '/');
    if (!activities) return;

    // Click "View all" link
    await page.getByText('View all').click();

    // Should navigate to activities page
    await expect(page).toHaveURL('/activities');
  });

  test('pagination appears with many activities', async ({ page }) => {
    // This test verifies pagination UI appears when there are many activities
    // Note: We may not have enough activities to trigger pagination in test env

    await page.goto('/activities');
    await page.waitForLoadState('networkidle');

    const activities = await getActivities(page);

    if (activities.length <= 20) {
      // Not enough activities for pagination - just verify page works
      await expect(page.getByRole('heading', { name: 'Activities', exact: true })).toBeVisible();
      return;
    }

    // If we have more than 20 activities, pagination should appear
    await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
  });
});
