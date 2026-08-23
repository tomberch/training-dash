/**
 * E2E tests for the Import button in the header.
 *
 * Tests that the import button:
 * 1. Is NOT visible when no integrations are configured
 * 2. IS visible when at least one integration (Xert) is configured
 * 3. Becomes NOT visible again when the integration is removed
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';

const testUser = generateTestUser('import-button');

test.describe('Import Button Visibility', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('import button visibility changes based on integration status', async ({ page }) => {
    // Login as test user
    await loginViaApi(page, testUser);

    // Go to dashboard
    await page.goto('/');

    // Wait for page to be loaded (header should be visible)
    await expect(page.getByRole('button', { name: /Upload FIT/i })).toBeVisible();

    // Step 1: Import button should NOT be visible (no integrations configured)
    const importButton = page.getByTestId('import-button');
    await expect(importButton).not.toBeVisible();

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

    // Import button should now be visible
    await expect(importButton).toBeVisible();

    // Verify the button shows "Import" text
    await expect(importButton).toHaveText(/Import/);

    // Step 3: Remove Xert integration via API
    const deleteResponse = await page.request.delete('/api/me/xert-credentials');
    expect(deleteResponse.ok()).toBeTruthy();

    // Reload the page
    await page.reload();

    // Wait for header to load
    await expect(page.getByRole('button', { name: /Upload FIT/i })).toBeVisible();

    // Import button should NOT be visible again
    await expect(importButton).not.toBeVisible();
  });

  test('import button triggers import when clicked', async ({ page }) => {
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

    // Wait for import button to be visible
    const importButton = page.getByTestId('import-button');
    await expect(importButton).toBeVisible();

    // Click import button
    await importButton.click();

    // Should show importing state (button text changes to "Importing...")
    await expect(importButton).toHaveText(/Importing/);

    // Wait for success toast
    await expect(page.getByText('Import started')).toBeVisible();

    // Button should return to normal state
    await expect(importButton).toHaveText(/Import/);

    // Cleanup: remove integration
    await page.request.delete('/api/me/xert-credentials');
  });
});
