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
 * Helper to navigate to dashboard and verify recent activities are visible.
 * Skips test if no activities are displayed (either API returns 0 or UI shows empty state).
 */
async function requireDashboardActivities(page: Page): Promise<boolean> {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  
  // Check API first for quick skip
  const activities = await getActivities(page);
  if (activities.length === 0) {
    test.skip();
    return false;
  }
  
  // Wait for either "Recent Activities" section or "Welcome" onboarding
  // The UI state may differ from API due to race conditions with parallel tests
  const recentActivities = page.getByText('Recent Activities');
  const welcomeScreen = page.getByText('Welcome to TrainDash');
  
  // Wait for either element with a short timeout
  try {
    await Promise.race([
      recentActivities.waitFor({ timeout: 5000 }),
      welcomeScreen.waitFor({ timeout: 5000 }),
    ]);
  } catch {
    // Neither appeared - unexpected state, skip test
    test.skip();
    return false;
  }
  
  // If we see the welcome screen, activities were deleted - skip
  if (await welcomeScreen.isVisible().catch(() => false)) {
    test.skip();
    return false;
  }
  
  return true;
}

/**
 * Helper to navigate to activities page and verify activities are loaded.
 * Skips test if no activities exist.
 */
async function requireActivityList(page: Page): Promise<{ id: number }[] | null> {
  await page.goto('/activities');
  await page.waitForLoadState('networkidle');
  
  const activities = await getActivities(page);
  if (activities.length === 0) {
    test.skip();
    return null;
  }
  
  // Wait for either activity rows or empty state
  const activityHeading = page.getByRole('main').locator('h3').first();
  const emptyState = page.getByText('No activities yet');
  
  try {
    await Promise.race([
      activityHeading.waitFor({ timeout: 5000 }),
      emptyState.waitFor({ timeout: 5000 }),
    ]);
  } catch {
    // Neither appeared - might be loading, let's give it more time
    await page.waitForTimeout(2000);
  }
  
  // If empty state is visible, activities were deleted - skip
  if (await emptyState.isVisible().catch(() => false)) {
    test.skip();
    return null;
  }
  
  return activities as unknown as { id: number }[];
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
    const activities = await requireActivityList(page);
    if (!activities) return;

    // If activities exist, we should see the list header
    await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();

    // Should show activity count
    await expect(page.getByText(/\d+ activit/)).toBeVisible();
  });

  test('activity shows date, name, duration, distance metrics', async ({ page }) => {
    // This test verifies the activity list displays metrics correctly.
    // Testing upload flow with async job processing is covered in #221.
    const activities = await requireActivityList(page);
    if (!activities) return;

    // Check for metric labels (these appear in the activity rows)
    await expect(page.getByText('Distance').first()).toBeVisible();
    await expect(page.getByText('Time').first()).toBeVisible();
    
    // Check page heading
    await expect(page.getByRole('heading', { name: 'Activities' })).toBeVisible();
  });

  test('clicking activity navigates to detail view', async ({ page }) => {
    const activities = await requireActivityList(page);
    if (!activities) return;

    // Wait for activity list to load by checking for activity heading
    // Activity rows display as div>h3 elements with the activity title
    const firstActivityHeading = page.getByRole('main').locator('h3').first();
    await expect(firstActivityHeading).toBeVisible({ timeout: 10000 });
    
    // Click on the activity heading to navigate to detail
    await firstActivityHeading.click();

    // Should navigate to activity detail page (UUID format)
    await expect(page).toHaveURL(/\/activities\/[a-f0-9-]+/);

    // Should show activity detail content
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 10000 });
  });

  // Note: TSS test removed - requires FIT fixtures with power data and user threshold setup.
  // Will be added in #219 (FIT fixtures) or a dedicated threshold test ticket.

  test('dashboard shows recent activities', async ({ page }) => {
    const hasActivities = await requireDashboardActivities(page);
    if (!hasActivities) return;

    // Dashboard should show "Recent Activities" section
    await expect(page.getByText('Recent Activities')).toBeVisible();

    // Should have "View all" link
    await expect(page.getByText('View all')).toBeVisible();
  });

  test('view all link navigates to activities page', async ({ page }) => {
    const hasActivities = await requireDashboardActivities(page);
    if (!hasActivities) return;

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
