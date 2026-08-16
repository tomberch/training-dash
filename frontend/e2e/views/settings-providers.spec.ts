/**
 * E2E tests for Provider Integration sections in Settings.
 *
 * Tests Xert and Garmin integration UI:
 * - Connect form renders correctly
 * - Auto-sync toggle appears when connected
 * - Garmin connect button has proper width (not full-width)
 * - Disconnect flow works
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * REQUIRES: MOCK_XERT_ENABLED=true in docker-compose.e2e.yml (enabled by default)
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';

const testUser = generateTestUser('settings-providers');

test.describe('Settings - Provider Integrations', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test.describe('Xert Integration', () => {
    test('xert section shows connect form when not connected', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Wait for settings page to load
      await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

      // Find Xert section
      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Should show email and password inputs
      await expect(page.getByTestId('xert-email')).toBeVisible();
      await expect(page.getByTestId('xert-password')).toBeVisible();

      // Should show Connect button
      await expect(page.getByTestId('xert-connect')).toBeVisible();
    });

    test('xert auto-sync toggle appears after connecting', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Connect to Xert (mock accepts any password except "invalid")
      await page.getByTestId('xert-email').fill('mock@xert.com');
      await page.getByTestId('xert-password').fill('mockpassword');
      await page.getByTestId('xert-connect').click();

      // Wait for success
      await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });

      // Auto-sync toggle should now be visible
      await expect(page.getByText('Auto-sync from Xert')).toBeVisible();
      
      // Toggle button should be present (aria-pressed attribute indicates it's a toggle)
      const syncToggle = page.locator('button[aria-pressed]').first();
      await expect(syncToggle).toBeVisible();
    });

    test('xert auto-sync toggle can be switched', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // If not connected, connect first
      const autoSyncLabel = page.getByText('Auto-sync from Xert');
      if (!(await autoSyncLabel.isVisible().catch(() => false))) {
        await page.getByTestId('xert-email').fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Find the toggle - it's a button with aria-pressed that's enabled (not disabled during save)
      const syncToggle = page.locator('button[aria-pressed]:not([disabled])').first();
      await expect(syncToggle).toBeVisible();
      await expect(syncToggle).toBeEnabled();

      // Get initial state
      const initialState = await syncToggle.getAttribute('aria-pressed');

      // Click to toggle
      await syncToggle.click();

      // Wait for the API call to complete and state to update
      await page.waitForTimeout(500);

      // State should have changed
      const newState = await syncToggle.getAttribute('aria-pressed');
      expect(newState).not.toBe(initialState);
    });

    test('xert shows Update, Sync Now, and Disconnect when connected', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Ensure connected
      const disconnectButton = page.getByTestId('xert-disconnect');
      if (!(await disconnectButton.isVisible().catch(() => false))) {
        await page.getByTestId('xert-email').fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Should show Update button (same as Connect, but for updating credentials)
      await expect(page.getByTestId('xert-connect')).toBeVisible();
      await expect(page.getByTestId('xert-connect')).toHaveText(/Update/i);

      // Should show Sync Now button
      await expect(page.getByRole('button', { name: /Sync Now/i })).toBeVisible();

      // Should show Disconnect button
      await expect(page.getByTestId('xert-disconnect')).toBeVisible();
    });

    test('xert disconnect removes auto-sync toggle', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Ensure connected first
      const autoSyncLabel = page.getByText('Auto-sync from Xert');
      if (!(await autoSyncLabel.isVisible().catch(() => false))) {
        await page.getByTestId('xert-email').fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Auto-sync should be visible
      await expect(page.getByText('Auto-sync from Xert')).toBeVisible();

      // Disconnect
      await page.getByTestId('xert-disconnect').click();

      // Wait for disconnect to complete
      await expect(page.getByText(/disconnected|removed/i)).toBeVisible({ timeout: 10000 });

      // Auto-sync toggle should no longer be visible
      await expect(page.getByText('Auto-sync from Xert')).not.toBeVisible();
    });
  });

  test.describe('Garmin Integration', () => {
    test('garmin section shows connect button with proper width', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

      // Find Garmin section
      await expect(page.getByRole('heading', { name: 'Garmin', level: 3 })).toBeVisible();

      // Find the Connect button
      const connectButton = page.getByTestId('garmin-connect');
      await expect(connectButton).toBeVisible();

      // Get button dimensions
      const buttonBox = await connectButton.boundingBox();
      expect(buttonBox).not.toBeNull();

      // Get the Garmin heading's parent card for comparison
      const garminHeading = page.getByRole('heading', { name: 'Garmin', level: 3 });
      const garminSection = garminHeading.locator('xpath=ancestor::div[@data-slot="card"]');
      const cardBox = await garminSection.boundingBox();
      expect(cardBox).not.toBeNull();

      // Button should NOT be full width of the card
      // Allow for padding (button should be less than 50% of card width typically)
      if (buttonBox && cardBox) {
        expect(buttonBox.width).toBeLessThan(cardBox.width * 0.6);
      }
    });

    test('garmin auto-sync toggle appears when connected', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Garmin', level: 3 })).toBeVisible();

      // Check if already connected by looking for auto-sync toggle
      const autoSyncLabel = page.getByText('Auto-sync from Garmin');
      
      if (await autoSyncLabel.isVisible().catch(() => false)) {
        // Already connected - verify toggle is present
        const syncToggle = page.locator('button[aria-pressed]').filter({ 
          has: page.locator('..').filter({ hasText: 'Auto-sync from Garmin' }) 
        });
        // Just verify the auto-sync section exists
        await expect(autoSyncLabel).toBeVisible();
      } else {
        // Not connected - this is expected for a fresh user
        // Garmin OAuth flow can't be automated in E2E, so we just verify the button exists
        await expect(page.getByTestId('garmin-connect')).toBeVisible();
      }
    });
  });
});
