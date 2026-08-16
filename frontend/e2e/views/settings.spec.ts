/**
 * E2E tests for Settings page.
 *
 * Tests preferences, unit system toggle, theme selection, and Xert credentials.
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * Uses admin API to approve user in case require_approval is enabled.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';

const testUser = generateTestUser('settings');

test.describe('Settings', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('settings page loads with all tabs', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Should show Settings heading
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Should show all tabs
    await expect(page.getByRole('tab', { name: 'Profile' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Preferences' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Training' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Connections' })).toBeVisible();

    // Profile tab should be active by default and show Profile card
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Profile' })).toBeVisible();
  });

  test('unit system toggle switches between metric and imperial', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Click Preferences tab to see unit system
    await page.getByRole('tab', { name: 'Preferences' }).click();

    // Wait for preferences section to load
    await expect(page.getByText('Unit System')).toBeVisible();

    // Find the Imperial button (clicking it will switch from default metric to imperial)
    const imperialButton = page.getByRole('button', { name: 'Imperial' });
    await expect(imperialButton).toBeVisible();

    // Click to switch to Imperial
    await imperialButton.click();

    // Should show success feedback (indicates API call completed)
    await expect(page.getByText('Preferences saved')).toBeVisible();
  });

  test('theme selector allows choosing light, dark, or system', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Click Preferences tab to see theme selector
    await page.getByRole('tab', { name: 'Preferences' }).click();

    // Wait for preferences section
    await expect(page.getByText('Theme')).toBeVisible();

    // Find theme buttons (exact: true to avoid matching map style buttons like "Dark Matter")
    const lightButton = page.getByRole('button', { name: 'Light', exact: true });
    const darkButton = page.getByRole('button', { name: 'Dark', exact: true });
    const systemButton = page.getByRole('button', { name: 'System', exact: true });

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

    // Generate unique display name to ensure change triggers auto-save
    const uniqueName = `Test User ${Date.now()}`;
    
    // Enter a display name
    await displayNameInput.fill(uniqueName);
    
    // Verify the value was entered
    await expect(displayNameInput).toHaveValue(uniqueName);
  });

  test('settings page is navigable from dashboard', async ({ page }) => {
    await loginViaApi(page, testUser);

    // Start from dashboard
    await page.goto('/');
    
    // Navigate to settings via menu or direct link
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Can navigate back to dashboard
    await page.goto('/');
    await expect(page).not.toHaveURL('/settings');
  });
});
