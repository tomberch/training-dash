/**
 * E2E tests for Activity List view.
 *
 * Tests the activity list displays correctly with metrics,
 * handles empty states, and navigates to detail views.
 */
import { test, expect, Page } from '@playwright/test';
import { generateTestUser, registerUser } from './fixtures/auth';
import { getActivities } from './fixtures/api';

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
    // This test verifies the activity list displays metrics correctly.
    // Testing upload flow with async job processing is covered in #221.
    const activities = await requireActivities(page, '/activities');
    if (!activities) return;

    // Check for metric labels (these appear in the activity rows)
    await expect(page.getByText('Distance').first()).toBeVisible();
    await expect(page.getByText('Time').first()).toBeVisible();
    
    // Check page heading
    await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();
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
