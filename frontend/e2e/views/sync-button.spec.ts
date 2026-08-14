/**
 * E2E tests for the Sync button in the header.
 *
 * Tests that the sync button:
 * 1. Is NOT visible when no integrations are configured
 * 2. IS visible when at least one integration (Xert) is configured
 * 3. Becomes NOT visible again when the integration is removed
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';

const testUser = generateTestUser('sync-button');

test.describe('Sync Button Visibility', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('sync button visibility changes based on integration status', async ({ page }) => {
    // Login as test user
    await loginViaApi(page, testUser);

    // Go to dashboard
    await page.goto('/');

    // Wait for page to be loaded (header should be visible)
    await expect(page.getByRole('button', { name: /Upload FIT/i })).toBeVisible();

    // Step 1: Sync button should NOT be visible (no integrations configured)
    const syncButton = page.getByTestId('sync-button');
    await expect(syncButton).not.toBeVisible();

    // Step 2: Add Xert integration via API (use page.request to share session cookies)
    const setResponse = await page.request.put('/api/me/xert-credentials', {
      data: {
        xert_email: 'mock@xert.com',
        xert_password: 'mockpassword',
      },
    });
    expect(setResponse.ok()).toBeTruthy();

    // Reload the page to pick up the new integration status
    await page.reload();

    // Wait for header to load
    await expect(page.getByRole('button', { name: /Upload FIT/i })).toBeVisible();

    // Sync button should now be visible
    await expect(syncButton).toBeVisible();

    // Verify the button shows "Sync" text
    await expect(syncButton).toHaveText(/Sync/);

    // Step 3: Remove Xert integration via API
    const deleteResponse = await page.request.delete('/api/me/xert-credentials');
    expect(deleteResponse.ok()).toBeTruthy();

    // Reload the page
    await page.reload();

    // Wait for header to load
    await expect(page.getByRole('button', { name: /Upload FIT/i })).toBeVisible();

    // Sync button should NOT be visible again
    await expect(syncButton).not.toBeVisible();
  });

  test('sync button triggers sync when clicked', async ({ page }) => {
    // Login and set up integration
    await loginViaApi(page, testUser);

    // Set Xert credentials via API (use page.request to share session cookies)
    const setResponse = await page.request.put('/api/me/xert-credentials', {
      data: {
        xert_email: 'mock@xert.com',
        xert_password: 'mockpassword',
      },
    });
    expect(setResponse.ok()).toBeTruthy();

    // Go to dashboard
    await page.goto('/');

    // Wait for sync button to be visible
    const syncButton = page.getByTestId('sync-button');
    await expect(syncButton).toBeVisible();

    // Click sync button
    await syncButton.click();

    // Should show syncing state (button text changes to "Syncing...")
    await expect(syncButton).toHaveText(/Syncing/);

    // Wait for success toast
    await expect(page.getByText('Sync started')).toBeVisible();

    // Button should return to normal state
    await expect(syncButton).toHaveText(/Sync/);

    // Cleanup: remove integration
    await page.request.delete('/api/me/xert-credentials');
  });
});
