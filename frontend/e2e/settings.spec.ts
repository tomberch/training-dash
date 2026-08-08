/**
 * E2E tests for Settings page.
 *
 * Tests preferences, unit system toggle, theme selection, and Xert credentials.
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * Uses admin API to approve user in case require_approval is enabled.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from './fixtures/auth';

const testUser = generateTestUser('settings');

test.describe('Settings', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('settings page loads with all sections', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Should show Settings heading
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Should show main sections (CardTitle uses data-slot="card-title")
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Profile' })).toBeVisible();
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Preferences' })).toBeVisible();
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Thresholds' })).toBeVisible();
  });

  test('unit system toggle switches between metric and imperial', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for preferences section to load
    await expect(page.getByText('Unit System')).toBeVisible();

    // Find the unit toggle button
    const unitToggle = page.getByTestId('unit-toggle');
    await expect(unitToggle).toBeVisible();

    // Get current state and toggle
    const initialText = await unitToggle.textContent();
    const isMetric = initialText?.includes('Metric');

    // Click to toggle
    await unitToggle.click();

    // Should show success feedback (indicates API call completed)
    await expect(page.getByText('Preferences saved')).toBeVisible();

    // Verify the toggle changed
    if (isMetric) {
      // Should now highlight Imperial
      await expect(page.getByText('miles and feet')).toBeVisible();
    } else {
      // Should now highlight Metric
      await expect(page.getByText('kilometers and meters')).toBeVisible();
    }
  });

  test('theme selector allows choosing light, dark, or system', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for preferences section
    await expect(page.getByText('Theme')).toBeVisible();

    // Find theme buttons
    const lightButton = page.getByRole('button', { name: 'Light' });
    const darkButton = page.getByRole('button', { name: 'Dark' });
    const systemButton = page.getByRole('button', { name: 'System' });

    await expect(lightButton).toBeVisible();
    await expect(darkButton).toBeVisible();
    await expect(systemButton).toBeVisible();

    // Click dark theme
    await darkButton.click();

    // The button should become active (has different styling)
    // Theme is applied via data-theme attribute on html
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'mocha');

    // Click light theme
    await lightButton.click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'latte');
  });

  test('profile section shows email and allows display name edit', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Should show Profile section (CardTitle uses data-slot="card-title")
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Profile' })).toBeVisible();

    // Email should be visible (read-only)
    const emailInput = page.locator('input[type="email"][disabled]');
    await expect(emailInput).toBeVisible();
    await expect(emailInput).toHaveValue(testUser.email);

    // Display name field should be editable
    const displayNameInput = page.getByPlaceholder('How you want to be called');
    await expect(displayNameInput).toBeVisible();

    // Enter a display name
    await displayNameInput.fill('Test User');

    // Save
    await page.getByRole('button', { name: 'Save Profile' }).click();

    // Should show success
    await expect(page.getByText('Profile saved')).toBeVisible();
  });

  test('thresholds section allows adding FTP', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for thresholds section (CardTitle uses data-slot="card-title")
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Thresholds' })).toBeVisible();

    // Click Add/Update button to show form
    const addButton = page.getByRole('button', { name: /Add|Update/ });
    await addButton.click();

    // Form should appear
    const ftpInput = page.getByPlaceholder(/e\.g\. 250|Current:/);
    await expect(ftpInput).toBeVisible();

    // Enter FTP value
    await ftpInput.fill('220');

    // Save
    await page.getByRole('button', { name: 'Save Threshold' }).click();

    // Should show success
    await expect(page.getByText('Threshold saved')).toBeVisible();

    // Threshold should be displayed (shown in the current threshold box and in the table)
    await expect(page.locator('.text-xl', { hasText: '220W' })).toBeVisible();
  });

  test('back button navigates away from settings', async ({ page }) => {
    await loginViaApi(page, testUser);

    // Start from dashboard
    await page.goto('/');
    await expect(page.getByText('Recent Activities')).toBeVisible({ timeout: 10000 }).catch(() => {
      // New user might see welcome screen
    });

    // Navigate to settings
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Click back button
    await page.getByRole('button', { name: /Back/ }).click();

    // Should navigate away from settings
    await expect(page).not.toHaveURL('/settings');
  });
});
